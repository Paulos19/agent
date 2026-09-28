import re
import time
import httpx
from typing import Optional, Tuple, Dict, Any, Set
from config import settings

# Armazena mensagens recentemente enviadas pela API para não processar eco do próprio bot
_recently_sent_messages: Dict[str, float] = {}

def _clean_expired_cache():
    """Remove mensagens do cache com mais de 3 minutos."""
    now = time.time()
    expired = [k for k, t in _recently_sent_messages.items() if now - t > 180]
    for k in expired:
        _recently_sent_messages.pop(k, None)

def extract_evolution_message(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extrai informações cruciais do webhook da Evolution API:
    Retorna: (sender_id, clean_number, message_text) ou (None, None, None)
    """
    _clean_expired_cache()

    event = payload.get("event", "").lower()
    
    # Eventos aceitos de mensagem recebida
    if event not in ["messages.upsert", "messages_upsert"]:
        return None, None, None

    data = payload.get("data", {})
    key = data.get("key", {})
    is_from_me = key.get("fromMe", False)

    # Identifica o melhor candidato a remoteJid (WhatsApp JID)
    remote_jid = key.get("remoteJid", "")
    remote_jid_alt = key.get("remoteJidAlt", "")
    participant = key.get("participant", "") or data.get("participant", "")
    sender = data.get("sender", "")

    # Se remoteJid for @lid (Linked Identity), usa o remoteJidAlt ou participant que contém o número real
    target_jid = remote_jid
    if "@lid" in target_jid:
        if remote_jid_alt and "@s.whatsapp.net" in remote_jid_alt:
            target_jid = remote_jid_alt
        elif sender and "@s.whatsapp.net" in sender:
            target_jid = sender
        elif participant and "@s.whatsapp.net" in participant:
            target_jid = participant

    if not target_jid:
        return None, None, None

    # Extrai o texto da mensagem
    message_content = data.get("message", {})
    text = ""
    if "conversation" in message_content and message_content["conversation"]:
        text = message_content["conversation"]
    elif "extendedTextMessage" in message_content:
        text = message_content["extendedTextMessage"].get("text", "")
    elif "imageMessage" in message_content:
        text = message_content["imageMessage"].get("caption", "")

    text = text.strip()
    if not text:
        return None, None, None

    # Se for mensagem enviada por mim (fromMe == True):
    # Pode ser o próprio usuário conversando consigo mesmo ou enviando comandos na própria instância!
    if is_from_me:
        # Verifica se o texto é um eco exato de algo que o bot acabou de enviar via API
        if text in _recently_sent_messages:
            # É eco da resposta do bot, ignora
            return None, None, None

    # Extrai apenas os dígitos do número
    clean_number = re.sub(r"\D", "", target_jid.split("@")[0])

    return target_jid, clean_number, text

async def send_evolution_message(recipient: str, text: str) -> bool:
    """
    Envia uma mensagem de texto pelo WhatsApp através da Evolution API.
    """
    if not settings.EVOLUTION_API_URL or not settings.EVOLUTION_INSTANCE_NAME:
        print("[Evolution API] Erro: URL da Evolution ou Nome da Instância não configurados.")
        return False

    # Registra no cache de mensagens enviadas para evitar loop de eco
    _recently_sent_messages[text.strip()] = time.time()

    url = f"{settings.EVOLUTION_API_URL.rstrip('/')}/message/sendText/{settings.EVOLUTION_INSTANCE_NAME}"
    headers = {
        "Content-Type": "application/json",
        "apikey": settings.EVOLUTION_API_KEY
    }
    
    # Se o recipient não tiver @s.whatsapp.net, formata apenas com número
    number_target = recipient.split("@")[0] if "@" in recipient else recipient

    payload = {
        "number": number_target,
        "text": text,
        "delay": 500,
        "linkPreview": True
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in [200, 201]:
                return True
            else:
                print(f"[Evolution API] Falha no envio ({resp.status_code}): {resp.text}")
                return False
    except Exception as e:
        print(f"[Evolution API] Exceção ao enviar mensagem: {str(e)}")
        return False
