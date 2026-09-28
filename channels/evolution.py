import re
import httpx
from typing import Optional, Tuple, Dict, Any
from config import settings

def extract_evolution_message(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extrai informações cruciais do webhook da Evolution API:
    Retorna: (sender_id, clean_number, message_text) ou (None, None, None)
    """
    event = payload.get("event", "").lower()
    
    # Eventos aceitos de mensagem recebida
    if event not in ["messages.upsert", "messages_upsert"]:
        return None, None, None

    data = payload.get("data", {})
    key = data.get("key", {})
    
    # Ignora mensagens enviadas pelo próprio bot para evitar loops infinitos
    if key.get("fromMe", False):
        return None, None, None

    remote_jid = key.get("remoteJid", "")
    if not remote_jid:
        return None, None, None

    # Extrai o número limpo (apenas dígitos)
    clean_number = re.sub(r"\D", "", remote_jid.split("@")[0])

    # Extrai o texto da mensagem (pode vir em conversation ou extendedTextMessage)
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

    return remote_jid, clean_number, text

async def send_evolution_message(recipient: str, text: str) -> bool:
    """
    Envia uma mensagem de texto pelo WhatsApp através da Evolution API.
    
    Args:
        recipient: O remoteJid (ex: 551199999999@s.whatsapp.net) ou o número de telefone limpo.
        text: O texto da mensagem a ser enviada.
    """
    if not settings.EVOLUTION_API_URL or not settings.EVOLUTION_INSTANCE_NAME:
        print("[Evolution API] Erro: URL da Evolution ou Nome da Instância não configurados.")
        return False

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
