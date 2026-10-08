import re
import time
import base64
import mimetypes
from pathlib import Path
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

async def get_evolution_media_base64(data_payload: Dict[str, Any], message_id: str) -> Optional[Tuple[str, str]]:
    """
    Obtém o conteúdo em Base64 e o mimetype de uma mídia recebida via Evolution API.
    Verifica primeiro no payload do webhook; caso não esteja, consulta o endpoint getBase64FromMediaMessage.
    """
    if not settings.EVOLUTION_API_URL or not settings.EVOLUTION_INSTANCE_NAME:
        return None

    msg_obj = data_payload.get("message", {})
    img_obj = msg_obj.get("imageMessage", {})
    audio_obj = msg_obj.get("audioMessage", {})
    doc_obj = msg_obj.get("documentMessage", {})

    # 1. Verifica se já veio em base64 direto no payload do webhook
    for obj in [img_obj, audio_obj, doc_obj, data_payload]:
        if isinstance(obj, dict):
            b64 = obj.get("base64")
            mimetype = obj.get("mimetype") or ("image/jpeg" if img_obj else "audio/ogg")
            if b64:
                return b64, mimetype

    # 2. Chama a API da Evolution para obter a mídia descriptografada em Base64
    url = f"{settings.EVOLUTION_API_URL.rstrip('/')}/chat/getBase64FromMediaMessage/{settings.EVOLUTION_INSTANCE_NAME}"
    headers = {
        "Content-Type": "application/json",
        "apikey": settings.EVOLUTION_API_KEY
    }

    payloads_to_try = [
        {"message": {"key": {"id": message_id}}, "convertToMp4": False},
        {"message": data_payload, "convertToMp4": False}
    ]

    for p in payloads_to_try:
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.post(url, json=p, headers=headers)
                if resp.status_code in [200, 201]:
                    res_json = resp.json()
                    b64 = res_json.get("base64")
                    mimetype = res_json.get("mimetype") or ("image/jpeg" if img_obj else "audio/ogg")
                    if b64:
                        return b64, mimetype
        except Exception:
            pass

    return None

async def extract_evolution_message(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    """
    Extrai informações cruciais do webhook da Evolution API:
    Retorna: (target_jid, clean_number, message_text, media_info) ou (None, None, None, None)
    media_info pode conter detalhes de imagem ou áudio transcrito.
    """
    _clean_expired_cache()

    event = payload.get("event", "").lower()
    
    # Eventos aceitos de mensagem recebida
    if event not in ["messages.upsert", "messages_upsert"]:
        return None, None, None, None

    data = payload.get("data", {})
    key = data.get("key", {})
    is_from_me = key.get("fromMe", False)

    # Identifica o melhor candidato a remoteJid (WhatsApp JID)
    remote_jid = key.get("remoteJid", "")
    
    # 1. Ignora sumariamente mensagens de grupos, canais, newsletters e broadcasts de status
    if not remote_jid or any(s in remote_jid for s in ["@g.us", "@broadcast", "@newsletter"]):
        return None, None, None, None

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
        return None, None, None, None

    message_content = data.get("message", {})
    message_id = key.get("id", "")
    media_info: Optional[Dict[str, Any]] = None
    text = ""

    # Extração de texto e mídias multimodais (Imagens e Áudios)
    if "conversation" in message_content and message_content["conversation"]:
        text = message_content["conversation"]
    elif "extendedTextMessage" in message_content:
        text = message_content["extendedTextMessage"].get("text", "")
    elif "imageMessage" in message_content:
        caption = message_content["imageMessage"].get("caption", "").strip()
        text = caption or "Analise esta imagem em detalhes e me diga o que há nela ou resolva o que for necessário."
        b64_res = await get_evolution_media_base64(data, message_id)
        if b64_res:
            b64_data, mime = b64_res
            media_info = {
                "type": "image",
                "mimetype": mime or "image/jpeg",
                "base64": b64_data,
                "caption": caption
            }
    elif "audioMessage" in message_content:
        # Áudio recebido do usuário (nota de voz ou áudio encaminhado)
        b64_res = await get_evolution_media_base64(data, message_id)
        if b64_res:
            b64_data, mime = b64_res
            try:
                from tools.voice import transcribe_audio_bytes
                raw_bytes = base64.b64decode(b64_data.split(",")[-1])
                transcription = await transcribe_audio_bytes(raw_bytes, mime or "audio/ogg")
                text = transcription.strip()
            except Exception as e:
                text = ""

            if not text:
                text = "[Áudio enviado pelo usuário]"
                
            media_info = {
                "type": "audio",
                "mimetype": mime or "audio/ogg",
                "base64": b64_data,
                "transcription": text,
                "input_is_audio": True
            }

    text = text.strip()
    if not text:
        return None, None, None, None

    # Verifica se o texto é um eco exato de algo que o bot acabou de enviar via API
    if text in _recently_sent_messages:
        return None, None, None, None

    # Extrai apenas os dígitos do número do destinatário/remetente
    clean_number = re.sub(r"\D", "", target_jid.split("@")[0])
    allowed = settings.allowed_users_set
    guests = settings.guest_users_set

    # Regras de privacidade
    is_owner = (clean_number in allowed) if allowed else True
    is_guest = (clean_number in guests)

    if not is_owner and not is_guest:
        return None, None, None, None

    if is_from_me:
        if not is_owner:
            return None, None, None, None
    else:
        if is_guest and not is_owner:
            from tools.youtube_downloader import extract_media_url
            media_url = extract_media_url(text)
            if not media_url:
                return None, None, None, None

    return target_jid, clean_number, text, media_info

def format_whatsapp_message(text: str) -> str:
    """
    Converte marcações Markdown genéricas para o padrão nativo do WhatsApp:
    - Links [Label](URL) ou [URL](URL) -> URL pura ou Label: URL (clicável no WhatsApp)
    - **negrito** -> *negrito*
    - Headers # Título -> *Título*
    - Listas com asterisco (* item) -> • item (evita conflito com negrito do WhatsApp)
    """
    if not text:
        return ""
    # Converte links markdown
    def _link_repl(match):
        label, url = match.group(1).strip(), match.group(2).strip()
        if label == url or "http" in label:
            return url
        return f"{label}: {url}"
    formatted = re.sub(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)', _link_repl, text)
    # Converte **negrito** (Markdown padrão) para *negrito* (WhatsApp)
    formatted = re.sub(r'\*\*(.*?)\*\*', r'*\1*', formatted)
    # Converte headers #, ##, ### para *Header*
    formatted = re.sub(r'^#{1,6}\s*(.+)$', r'*\1*', formatted, flags=re.MULTILINE)
    # Substitui asteriscos soltos no início de linhas de lista por marcadores para evitar quebrar o negrito nativo
    formatted = re.sub(r'^\*\s+', r'• ', formatted, flags=re.MULTILINE)
    return formatted

async def send_evolution_message(recipient: str, text: str) -> bool:
    """
    Envia uma mensagem de texto pelo WhatsApp através da Evolution API.
    """
    if not settings.EVOLUTION_API_URL or not settings.EVOLUTION_INSTANCE_NAME:
        print("[Evolution API] Erro: URL da Evolution ou Nome da Instância não configurados.")
        return False

    formatted_text = format_whatsapp_message(text)

    # Registra no cache de mensagens enviadas para evitar loop de eco
    _recently_sent_messages[text.strip()] = time.time()
    _recently_sent_messages[formatted_text.strip()] = time.time()

    url = f"{settings.EVOLUTION_API_URL.rstrip('/')}/message/sendText/{settings.EVOLUTION_INSTANCE_NAME}"
    headers = {
        "Content-Type": "application/json",
        "apikey": settings.EVOLUTION_API_KEY
    }
    
    # Se o recipient não tiver @s.whatsapp.net, formata apenas com número
    number_target = recipient.split("@")[0] if "@" in recipient else recipient

    payload = {
        "number": number_target,
        "text": formatted_text,
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

async def send_evolution_media(
    recipient: str,
    file_path: str,
    caption: str = "",
    media_type: str = "document",
    file_name: Optional[str] = None
) -> bool:
    """
    Envia um arquivo de mídia (áudio MP3, vídeo MP4 ou documento) pelo WhatsApp via Evolution API.
    """
    if not settings.EVOLUTION_API_URL or not settings.EVOLUTION_INSTANCE_NAME:
        print("[Evolution API] Erro: URL da Evolution ou Nome da Instância não configurados.")
        return False

    p = Path(file_path)
    if not p.exists():
        print(f"[Evolution API] Arquivo não encontrado: {file_path}")
        return False

    file_size_mb = p.stat().st_size / (1024 * 1024)
    if file_size_mb > 35.0:
        print(f"[Evolution API] Arquivo muito grande para envio direto no WhatsApp ({file_size_mb:.1f}MB).")
        return False

    raw_data = p.read_bytes()
    b64_data = base64.b64encode(raw_data).decode("utf-8")
    actual_filename = file_name or p.name

    # Determina mimetype apropriado
    ext = p.suffix.lower()
    if ext == ".mp3":
        mime = "audio/mpeg"
        if media_type not in ["audio", "document"]:
            media_type = "audio"
    elif ext == ".m4a":
        mime = "audio/mp4"
    elif ext == ".mp4":
        mime = "video/mp4"
        if media_type not in ["video", "document"]:
            media_type = "video"
    else:
        mime = mimetypes.guess_type(str(p))[0] or "application/octet-stream"

    url = f"{settings.EVOLUTION_API_URL.rstrip('/')}/message/sendMedia/{settings.EVOLUTION_INSTANCE_NAME}"
    headers = {
        "Content-Type": "application/json",
        "apikey": settings.EVOLUTION_API_KEY
    }

    number_target = recipient.split("@")[0] if "@" in recipient else recipient

    payload = {
        "number": number_target,
        "mediatype": media_type,
        "mimetype": mime,
        "caption": format_whatsapp_message(caption) if caption else "",
        "media": b64_data,
        "fileName": actual_filename
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in [200, 201]:
                return True
            else:
                print(f"[Evolution API] Falha no envio de mídia ({resp.status_code}): {resp.text}")
                return False
    except Exception as e:
        print(f"[Evolution API] Exceção ao enviar mídia: {str(e)}")
        return False

async def send_evolution_audio_ptt(recipient: str, audio_file_path: str) -> bool:
    """
    Envia áudio como nota de voz gravada no WhatsApp (PTT / Voice Note) via Evolution API.
    Aparece no celular do usuário como gravação de microfone com as ondas sonoras verdes.
    """
    if not settings.EVOLUTION_API_URL or not settings.EVOLUTION_INSTANCE_NAME:
        print("[Evolution API] Erro: URL da Evolution ou Nome da Instância não configurados.")
        return False

    p = Path(audio_file_path)
    if not p.exists():
        print(f"[Evolution API] Arquivo de áudio não encontrado: {audio_file_path}")
        return False

    raw_bytes = p.read_bytes()
    b64_data = base64.b64encode(raw_bytes).decode("utf-8")
    number_target = recipient.split("@")[0] if "@" in recipient else recipient

    # 1. Tenta endpoint nativo sendWhatsAppAudio (simula gravação de voz PTT)
    url_ptt = f"{settings.EVOLUTION_API_URL.rstrip('/')}/message/sendWhatsAppAudio/{settings.EVOLUTION_INSTANCE_NAME}"
    headers = {
        "Content-Type": "application/json",
        "apikey": settings.EVOLUTION_API_KEY
    }
    payload_ptt = {
        "number": number_target,
        "audio": b64_data,
        "delay": 1200,
        "encoding": True
    }
    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            resp = await client.post(url_ptt, json=payload_ptt, headers=headers)
            if resp.status_code in [200, 201]:
                return True
    except Exception as e:
        print(f"[Evolution API] Falha no endpoint sendWhatsAppAudio: {e}. Tentando fallback sendMedia...")

    # 2. Fallback: sendMedia com mediatype audio
    return await send_evolution_media(recipient, str(p), media_type="audio", file_name="audio.mp3")

