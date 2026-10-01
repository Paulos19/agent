import mimetypes
from pathlib import Path
import httpx
from typing import Optional, Tuple, Dict, Any
from config import settings

def extract_telegram_message(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrai informações cruciais do webhook do Telegram:
    Retorna: (chat_id_str, message_text) ou (None, None)
    """
    message = payload.get("message") or payload.get("edited_message")
    if not message:
        return None, None

    chat = message.get("chat", {})
    chat_id = str(chat.get("id", ""))
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return None, None

    return chat_id, text

async def send_telegram_message(chat_id: str, text: str) -> bool:
    """
    Envia uma mensagem para o Telegram usando o Bot Token configurado.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        print("[Telegram] Erro: TELEGRAM_BOT_TOKEN não configurado.")
        return False

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Primeira tentativa com formatação Markdown
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                return True
            
            # Se falhou por erro de parse do Markdown (muito comum quando há caracteres especiais do terminal),
            # reenvia sem parse_mode para garantir a entrega da mensagem
            payload.pop("parse_mode", None)
            retry_resp = await client.post(url, json=payload)
            return retry_resp.status_code == 200
    except Exception as e:
        print(f"[Telegram] Exceção ao enviar mensagem: {str(e)}")
        return False

async def send_telegram_media(
    chat_id: str,
    file_path: str,
    caption: str = "",
    media_type: str = "document",
    file_name: Optional[str] = None
) -> bool:
    """
    Envia arquivo de áudio, vídeo ou documento via bot do Telegram.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        print("[Telegram] Erro: TELEGRAM_BOT_TOKEN não configurado.")
        return False

    p = Path(file_path)
    if not p.exists():
        print(f"[Telegram] Arquivo não encontrado: {file_path}")
        return False

    actual_filename = file_name or p.name
    endpoint_method = "sendAudio" if media_type == "audio" else ("sendVideo" if media_type == "video" else "sendDocument")
    field_name = "audio" if media_type == "audio" else ("video" if media_type == "video" else "document")

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{endpoint_method}"

    try:
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption

        ext = p.suffix.lower()
        if ext == ".mp3":
            mime = "audio/mpeg"
        elif ext == ".mp4":
            mime = "video/mp4"
        else:
            mime = mimetypes.guess_type(str(p))[0] or "application/octet-stream"

        file_bytes = p.read_bytes()
        files = {field_name: (actual_filename, file_bytes, mime)}

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, data=data, files=files)
            if resp.status_code == 200:
                return True
            else:
                print(f"[Telegram] Falha no envio de mídia ({resp.status_code}): {resp.text}")
                return False
    except Exception as e:
        print(f"[Telegram] Exceção ao enviar mídia: {str(e)}")
        return False

