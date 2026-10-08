import mimetypes
from pathlib import Path
import httpx
from typing import Optional, Tuple, Dict, Any
from config import settings

async def extract_telegram_message(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    """
    Extrai informações cruciais do webhook do Telegram:
    Retorna: (chat_id_str, message_text, media_info) ou (None, None, None)
    """
    message = payload.get("message") or payload.get("edited_message")
    if not message:
        return None, None, None

    chat = message.get("chat", {})
    chat_id = str(chat.get("id", ""))
    text = (message.get("text") or "").strip()
    media_info: Optional[Dict[str, Any]] = None
    token = settings.TELEGRAM_BOT_TOKEN

    # 1. Foto enviada no Telegram
    if "photo" in message and message["photo"] and token:
        photos = message["photo"]
        best_photo = photos[-1]
        file_id = best_photo.get("file_id")
        caption = (message.get("caption") or "").strip()
        text = caption or "Analise esta imagem em detalhes e me diga o que há nela ou resolva o que for necessário."
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}")
                if res.status_code == 200:
                    file_path = res.json().get("result", {}).get("file_path")
                    if file_path:
                        img_res = await client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")
                        if img_res.status_code == 200:
                            import base64
                            b64_data = base64.b64encode(img_res.content).decode("utf-8")
                            media_info = {
                                "type": "image",
                                "mimetype": "image/jpeg",
                                "base64": b64_data,
                                "caption": caption
                            }
        except Exception:
            pass

    # 2. Áudio / Mensagem de voz enviada no Telegram
    elif ("voice" in message or "audio" in message) and token:
        audio_obj = message.get("voice") or message.get("audio")
        file_id = audio_obj.get("file_id")
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}")
                if res.status_code == 200:
                    file_path = res.json().get("result", {}).get("file_path")
                    if file_path:
                        audio_res = await client.get(f"https://api.telegram.org/file/bot{token}/{file_path}")
                        if audio_res.status_code == 200:
                            import base64
                            from tools.voice import transcribe_audio_bytes
                            raw_bytes = audio_res.content
                            b64_data = base64.b64encode(raw_bytes).decode("utf-8")
                            transcription = await transcribe_audio_bytes(raw_bytes, "audio/ogg")
                            text = transcription.strip() or "[Áudio enviado pelo usuário]"
                            media_info = {
                                "type": "audio",
                                "mimetype": "audio/ogg",
                                "base64": b64_data,
                                "transcription": text,
                                "input_is_audio": True
                            }
        except Exception:
            pass

    if not chat_id or not text:
        return None, None, None

    return chat_id, text, media_info

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

