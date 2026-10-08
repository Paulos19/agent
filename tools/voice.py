import os
import re
import time
import uuid
import base64
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from config import settings

logger = logging.getLogger("assistente-voice")

def get_voice_temp_dir() -> Path:
    """Garante diretório de arquivos temporários de áudio."""
    temp_dir = settings.workspace_path / "storage" / "temp_voice"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir

def clean_text_for_speech(text: str) -> str:
    """
    Higieniza texto formatado em Markdown para uma fala fluida, natural e expressiva.
    Remove blocos de código extensos, URLs longas, asteriscos e caracteres especiais do terminal.
    """
    if not text:
        return ""

    t = text

    # Remove blocos de código grandes (substitui por aviso amigável)
    t = re.sub(r'```[a-zA-Z]*\n[\s\S]*?\n```', ' (código gerado exibido no texto) ', t)
    t = re.sub(r'`([^`]+)`', r'\1', t)

    # Substitui URLs completas por menção limpa
    t = re.sub(r'https?://[^\s]+', 'o link enviado', t)

    # Converte marcações de cabeçalho e negrito
    t = re.sub(r'#{1,6}\s+', '', t)
    t = re.sub(r'\*\*(.*?)\*\*', r'\1', t)
    t = re.sub(r'\*(.*?)\*', r'\1', t)
    t = re.sub(r'_(.*?)_', r'\1', t)

    # Limpa listas e marcadores
    t = re.sub(r'^\s*[-•*]\s+', '', t, flags=re.MULTILINE)
    t = re.sub(r'^\s*\d+\.\s+', '', t, flags=re.MULTILINE)

    # Remove emojis excessivos ou caracteres técnicos
    t = re.sub(r'[🤖🚀💻📁⏰✉️🧠🛠️📦📲✈️💡📸🌙🔒🛑✅❌⚠️⏳]', '', t)
    t = re.sub(r'\s{2,}', ' ', t)

    return t.strip()

def is_audio_requested(text: str) -> bool:
    """Detecta se o usuário pediu explicitamente para o assistente responder com áudio."""
    if not text:
        return False
    clean = text.lower()
    patterns = [
        r"\b(me\s+)?(responde|responda|manda|mande|grava|grave|fala)\s+(por|em|no|com|um)?\s*([aá]udio|voz)\b",
        r"\b(manda|mande|envie|grava|grave)\s+(um\s+)?([aá]udio)\b",
        r"\b(quero\s+(ouvir|escutar))\b",
        r"\b(pode\s+falar|fala\s+a[ií])\b"
    ]
    return any(re.search(p, clean) for p in patterns)

async def generate_tts_audio(
    text: str,
    output_path: Optional[Path] = None,
    voice: Optional[str] = None
) -> Optional[Path]:
    """
    Sintetiza texto em áudio MP3 realista em português brasileiro usando edge-tts.
    Fallback para OpenAI TTS se necessário.
    """
    spoken_text = clean_text_for_speech(text)
    if not spoken_text:
        return None

    # Limita tamanho para fala natural (se for muito longo, fala a síntese principal)
    if len(spoken_text) > 1200:
        spoken_text = spoken_text[:1150] + "... Te mandei todos os detalhes completos no texto aqui acima!"

    selected_voice = voice or settings.TTS_VOICE or "pt-BR-AntonioNeural"
    dest_path = output_path or (get_voice_temp_dir() / f"reply_{uuid.uuid4().hex[:8]}.mp3")
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Tentativa com edge-tts (Gratuito, rápido, voz neural de altíssima qualidade)
    try:
        import edge_tts
        communicate = edge_tts.Communicate(
            spoken_text,
            voice=selected_voice,
            rate=getattr(settings, "TTS_SPEED", "+0%")
        )
        await communicate.save(str(dest_path))
        if dest_path.exists() and dest_path.stat().st_size > 0:
            logger.info(f"[TTS] Áudio gerado com sucesso via edge-tts ({dest_path.name}, {dest_path.stat().st_size} bytes)")
            return dest_path
    except Exception as e:
        logger.warning(f"[TTS] Falha ao sintetizar com edge-tts ({e}). Tentando fallback...")

    # 2. Fallback via OpenAI Audio API caso configurado
    if settings.LLM_API_KEY and "generativelanguage" not in settings.LLM_BASE_URL:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
            response = await client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=spoken_text
            )
            response.stream_to_file(str(dest_path))
            if dest_path.exists() and dest_path.stat().st_size > 0:
                logger.info(f"[TTS] Áudio gerado com sucesso via OpenAI TTS ({dest_path.name})")
                return dest_path
        except Exception as e_openai:
            logger.error(f"[TTS] Falha no fallback OpenAI TTS: {e_openai}")

    return None

async def transcribe_audio_bytes(
    audio_bytes: bytes,
    mime_type: str = "audio/ogg"
) -> str:
    """
    Transcreve áudio falado em português utilizando a visão multimodal e de áudio do Gemini.
    """
    if not audio_bytes:
        return ""

    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL
    )

    b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
    
    # Determina formato suportado pelo payload
    fmt = "mp3"
    if "ogg" in mime_type.lower() or "opus" in mime_type.lower():
        fmt = "mp3" # Se necessário, mas o Gemini aceita os formatos comuns ou via input_audio

    try:
        resp = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Você é um transcritor de alta precisão em português do Brasil. Transcreva exatamente tudo o que foi falado neste áudio. Não invente nada e retorne APENAS o texto falado."
                        },
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": b64_audio,
                                "format": "mp3"
                            }
                        }
                    ]
                }
            ],
            temperature=0.0
        )
        transcription = (resp.choices[0].message.content or "").strip()
        logger.info(f"[STT] Áudio transcrito com sucesso: '{transcription[:60]}...'")
        return transcription
    except Exception as e:
        logger.error(f"[STT] Falha ao transcrever áudio via input_audio: {e}")
        
        # Fallback via google-genai se instalado
        try:
            from google import genai
            from google.genai import types
            gclient = genai.Client(api_key=settings.LLM_API_KEY)
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
            result = gclient.models.generate_content(
                model=settings.LLM_MODEL,
                contents=[
                    "Transcreva exatamente o que foi dito neste áudio em português. Retorne apenas o texto transcrito.",
                    audio_part
                ]
            )
            return (result.text or "").strip()
        except Exception as e_genai:
            logger.error(f"[STT] Falha no fallback google-genai: {e_genai}")
            return ""
