import asyncio
import os
import re
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional
import imageio_ffmpeg
import yt_dlp
from config import settings
from channels import send_channel_media

def _format_duration(seconds: Optional[int]) -> str:
    """Formata duração em segundos para HH:MM:SS ou MM:SS."""
    if not seconds:
        return "Desconhecido"
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

def _format_size(size_bytes: Optional[int]) -> str:
    """Formata tamanho de arquivo em MB ou KB."""
    if not size_bytes:
        return "0 MB"
    mb = size_bytes / (1024 * 1024)
    if mb < 1.0:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{mb:.2f} MB"

def _get_public_download_urls(filename: str) -> Dict[str, str]:
    """Gera links HTTP para download direto do arquivo."""
    encoded_name = urllib.parse.quote(filename)
    urls = {
        "local": f"http://localhost:{settings.PORT}/downloads/{encoded_name}"
    }
    
    # Se houver VPS_WS_URL configurada (ex: wss://agent.phdev.top/ws/worker), extrai o domínio HTTP
    if settings.VPS_WS_URL:
        domain_match = re.search(r'wss?://([^/]+)', settings.VPS_WS_URL)
        if domain_match:
            vps_host = domain_match.group(1)
            urls["public"] = f"https://{vps_host}/downloads/{encoded_name}"
            
    return urls

def _run_yt_dlp(url: str, format_type: str, quality: str, out_dir: Path) -> Dict[str, Any]:
    """Execução síncrona do yt-dlp em thread separada com binário ffmpeg embutido."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    out_template = str(out_dir / "%(title).200s.%(ext)s")
    
    ydl_opts: Dict[str, Any] = {
        "outtmpl": out_template,
        "ffmpeg_location": ffmpeg_exe,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    if format_type.lower() == "mp3":
        # Extração de áudio convertida para MP3
        audio_quality = "320" if "320" in quality else ("128" if "128" in quality else "192")
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": audio_quality,
            }],
        })
    else:
        # Extração de vídeo MP4 com melhor combinação de áudio e vídeo
        ydl_opts.update({
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # O info retornado pode vir como lista se for playlist, pega o primeiro
        if "entries" in info:
            info = info["entries"][0]
            
        title = info.get("title", "video_extraido")
        duration = info.get("duration", 0)
        uploader = info.get("uploader", "Desconhecido")
        view_count = info.get("view_count", 0)
        webpage_url = info.get("webpage_url", url)

        # Procura o arquivo gerado
        expected_ext = "mp3" if format_type.lower() == "mp3" else "mp4"
        downloaded_file = None
        
        # 1. Tenta pelo _filename do yt-dlp ajustando a extensão
        if "_filename" in info:
            cand = Path(info["_filename"]).with_suffix(f".{expected_ext}")
            if cand.exists():
                downloaded_file = cand

        # 2. Busca o arquivo mais recente com a extensão no out_dir
        if not downloaded_file:
            candidates = sorted(out_dir.glob(f"*.{expected_ext}"), key=lambda f: f.stat().st_mtime, reverse=True)
            if candidates:
                downloaded_file = candidates[0]

        if not downloaded_file or not downloaded_file.exists():
            raise FileNotFoundError(f"Arquivo {expected_ext.upper()} não foi encontrado após o download.")

        file_size = downloaded_file.stat().st_size
        return {
            "title": title,
            "duration": duration,
            "uploader": uploader,
            "view_count": view_count,
            "webpage_url": webpage_url,
            "file_path": downloaded_file,
            "file_name": downloaded_file.name,
            "file_size": file_size,
            "format": expected_ext.upper()
        }

async def download_youtube_media(
    url: str,
    format_type: str = "mp3",
    quality: str = "best",
    destination_folder: Optional[str] = None,
    send_to_chat: bool = True,
    user_id: Optional[str] = None,
    channel: Optional[str] = "whatsapp"
) -> str:
    """
    Baixa vídeo ou áudio do YouTube por meio da URL, converte para MP3 (ou MP4)
    em alta qualidade e gera links para download além de enviar o arquivo de mídia
    direto para o usuário via WhatsApp ou Telegram.
    """
    clean_url = url.strip()
    if not clean_url.startswith("http"):
        return f"[ERRO]: URL inválida: '{clean_url}'. Envie um link válido do YouTube (ex: https://www.youtube.com/watch?v=...)."

    # Define pasta de destino
    if destination_folder:
        out_dir = Path(destination_folder).resolve()
    else:
        out_dir = settings.workspace_path / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Executa o download em thread separada para não bloquear o loop de eventos
        result = await asyncio.to_thread(_run_yt_dlp, clean_url, format_type, quality, out_dir)
    except Exception as e:
        return f"[ERRO AO EXTRAIR DO YOUTUBE]: {str(e)}"

    file_path = result["file_path"]
    file_name = result["file_name"]
    file_size_formatted = _format_size(result["file_size"])
    duration_formatted = _format_duration(result["duration"])
    title = result["title"]
    uploader = result["uploader"]
    fmt = result["format"]

    urls = _get_public_download_urls(file_name)
    download_links_text = ""
    if "public" in urls:
        download_links_text += f"\n• Link direto (Nuvem/Web): {urls['public']}"
    download_links_text += f"\n• Link direto (Local/Rede): {urls['local']}"

    # Envio direto para o WhatsApp/Telegram
    sent_media_status = "Não solicitado."
    if send_to_chat and user_id:
        caption = f"🎵 *{title}*\nCanal: {uploader} | Duração: {duration_formatted} | Tamanho: {file_size_formatted}"
        media_type = "audio" if fmt == "MP3" else "video"
        try:
            ok = await send_channel_media(
                recipient=user_id,
                channel=channel or "whatsapp",
                file_path=str(file_path),
                caption=caption,
                media_type=media_type,
                file_name=file_name
            )
            if ok:
                sent_media_status = f"✅ Arquivo {fmt} enviado diretamente no seu {channel.capitalize()} com sucesso!"
            else:
                sent_media_status = "⚠️ Não foi possível despachar o arquivo via chat (possível limite de tamanho), mas o link de download está disponível."
        except Exception as send_err:
            sent_media_status = f"⚠️ Erro ao enviar para o chat: {send_err}"

    response = (
        f"🎬 *Extração do YouTube Concluída com Sucesso!*\n\n"
        f"📌 *Título:* {title}\n"
        f"👤 *Canal/Autor:* {uploader}\n"
        f"⏱️ *Duração:* {duration_formatted}\n"
        f"📦 *Formato:* {fmt} ({file_size_formatted})\n"
        f"📁 *Salvo no PC em:* `{str(file_path)}`\n\n"
        f"📲 *Envio para o Chat:* {sent_media_status}\n\n"
        f"🌐 *Links para Download Imediato:*{download_links_text}\n"
    )
    return response
