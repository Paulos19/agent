import logging
from typing import Optional
from .evolution import (
    extract_evolution_message,
    send_evolution_message,
    send_evolution_media,
    send_evolution_audio_ptt
)
from .telegram import extract_telegram_message, send_telegram_message, send_telegram_media

logger = logging.getLogger("assistente-channels")

async def send_channel_media(
    recipient: str,
    channel: str,
    file_path: str,
    caption: str = "",
    media_type: str = "document",
    file_name: Optional[str] = None
) -> bool:
    """
    Despacha arquivo de mídia/áudio/vídeo/documento para o canal do usuário (WhatsApp ou Telegram).
    """
    try:
        if channel == "whatsapp":
            return await send_evolution_media(recipient, file_path, caption=caption, media_type=media_type, file_name=file_name)
        elif channel == "telegram":
            return await send_telegram_media(recipient, file_path, caption=caption, media_type=media_type, file_name=file_name)
        return False
    except Exception as e:
        logger.error(f"[Canal {channel}] Erro ao enviar mídia para {recipient}: {e}")
        return False

async def send_channel_audio(
    recipient: str,
    channel: str,
    audio_file_path: str
) -> bool:
    """
    Despacha resposta em áudio (nota de voz no WhatsApp ou áudio no Telegram).
    No WhatsApp, simula gravação de voz PTT direta (com as ondas de áudio).
    """
    try:
        if channel == "whatsapp":
            return await send_evolution_audio_ptt(recipient, audio_file_path)
        elif channel == "telegram":
            return await send_telegram_media(recipient, audio_file_path, media_type="audio", file_name="resposta.mp3")
        return False
    except Exception as e:
        logger.error(f"[Canal {channel}] Erro ao enviar áudio/PTT para {recipient}: {e}")
        return False

__all__ = [
    "extract_evolution_message",
    "send_evolution_message",
    "send_evolution_media",
    "send_evolution_audio_ptt",
    "extract_telegram_message",
    "send_telegram_message",
    "send_telegram_media",
    "send_channel_media",
    "send_channel_audio"
]
