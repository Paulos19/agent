import asyncio
import os
import re
import time
import zipfile
import shutil
import logging
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional
import imageio_ffmpeg
import yt_dlp
from tools.music_tagger import enrich_mp3_metadata
from config import settings
from channels import send_channel_media

logger = logging.getLogger(__name__)

MEDIA_URL_REGEX = re.compile(
    r'https?://(?:www\.)?(?:[a-zA-Z0-9-]+\.)*(?:youtube\.com|youtu\.be|instagram\.com|tiktok\.com|twitter\.com|x\.com|facebook\.com|fb\.watch|soundcloud\.com|pinterest\.com|pin\.it)[^\s>"\')]*',
    re.IGNORECASE
)

def extract_media_url(text: str) -> Optional[str]:
    """Extrai URL suportada de mídia (YouTube, Instagram, TikTok, Twitter/X, etc.) presente no texto."""
    if not text:
        return None
    match = MEDIA_URL_REGEX.search(text)
    if match:
        url = match.group(0).rstrip('.,;!?)]}"\'')
        return url
    return None


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

import socket

def _get_local_ip() -> str:
    """Obtém o IP local na rede Wi-Fi/Ethernet."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def _get_public_download_urls(filename: str) -> Dict[str, str]:
    """Gera links HTTP para download direto do arquivo com header de anexo."""
    encoded_name = urllib.parse.quote(filename)
    local_ip = _get_local_ip()
    urls = {
        "local": f"http://{local_ip}:{settings.PORT}/download/{encoded_name}"
    }
    
    # Se houver VPS_WS_URL configurada (ex: wss://agent.phdev.top/ws/worker), extrai o domínio HTTP público
    vps_ws = getattr(settings, "VPS_WS_URL", None) or os.getenv("VPS_WS_URL", "wss://agent.phdev.top/ws/worker")
    if vps_ws:
        domain_match = re.search(r'wss?://([^/]+)', vps_ws)
        if domain_match:
            vps_host = domain_match.group(1)
            urls["public"] = f"https://{vps_host}/download/{encoded_name}"
            
    return urls

import shutil

def _get_ffmpeg_location() -> Optional[str]:
    """Descobre o executável ou diretório do ffmpeg com suporte a ffprobe."""
    # 1. Verifica se ffmpeg e ffprobe estão no PATH do sistema
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        bin_dir = Path(sys_ffmpeg).parent
        if (bin_dir / "ffprobe.exe").is_file() or (bin_dir / "ffprobe").is_file():
            return str(bin_dir)

    # 2. Verifica locais padrão do WinGet (Gyan.FFmpeg)
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_pkgs = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_pkgs.exists():
            for p in winget_pkgs.glob("Gyan.FFmpeg*/**/bin"):
                if (p / "ffmpeg.exe").is_file() and (p / "ffprobe.exe").is_file():
                    return str(p)

    # 3. Verifica PATH atualizado do Registro do Windows
    try:
        import winreg
        for root in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
            sub = r"Environment" if root == winreg.HKEY_CURRENT_USER else r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
            try:
                with winreg.OpenKey(root, sub) as key:
                    path_val, _ = winreg.QueryValueEx(key, "Path")
                    for part in path_val.split(";"):
                        p = Path(part.strip())
                        if (p / "ffmpeg.exe").is_file() and (p / "ffprobe.exe").is_file():
                            return str(p)
            except Exception:
                pass
    except Exception:
        pass

    # 4. Linux nativo (/usr/bin)
    if Path("/usr/bin/ffmpeg").is_file() and Path("/usr/bin/ffprobe").is_file():
        return "/usr/bin"

    # 5. Fallback para imageio_ffmpeg
    try:
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).is_file():
            return str(Path(exe).parent)
    except Exception:
        pass
    return None

def _get_youtube_cookies() -> Optional[str]:
    """Localiza arquivo de cookies do YouTube para contornar bloqueios de bots em datacenter."""
    candidates = [
        os.getenv("YOUTUBE_COOKIES_PATH"),
        Path("/workspace/cookies.txt"),
        Path("/workspace/storage/cookies.txt"),
        Path(__file__).parent.parent / "cookies.txt",
        Path(__file__).parent / "cookies.txt",
        Path.cwd() / "cookies.txt"
    ]
    for c in candidates:
        if c and Path(c).is_file() and Path(c).stat().st_size > 0:
            return str(Path(c).resolve())
    return None

def _detect_platform(url: str) -> str:
    """Identifica a plataforma da URL de mídia."""
    u = url.lower()
    if any(k in u for k in ["youtube.com", "youtu.be"]):
        return "YouTube"
    if "instagram.com" in u:
        return "Instagram"
    if "tiktok.com" in u:
        return "TikTok"
    if any(k in u for k in ["twitter.com", "x.com"]):
        return "Twitter/X"
    if any(k in u for k in ["facebook.com", "fb.watch"]):
        return "Facebook"
    if "pinterest.com" in u:
        return "Pinterest"
    return "Mídia Online"

def _run_yt_dlp(url: str, format_type: str, quality: str, out_dir: Path) -> Dict[str, Any]:
    """Execução síncrona do yt-dlp com suporte universal (YouTube, Instagram Reels, TikTok, Twitter/X)."""
    ffmpeg_loc = _get_ffmpeg_location()
    out_template = str(out_dir / "%(title).200s.%(ext)s")

    platform = _detect_platform(url)
    is_youtube = platform == "YouTube"

    if is_youtube:
        # Estratégias de bypass específicas para YouTube
        strategies = [
            {"extractor_args": {"youtube": {"player_client": ["visionos"]}}},
            {"extractor_args": {"youtube": {"player_client": ["web_creator"]}}},
            {"extractor_args": {"youtube": {"player_client": ["tv_downgraded"]}}},
            {"extractor_args": {"youtube": {"player_client": ["web"]}}},
        ]
        cookies_file = _get_youtube_cookies()
        if cookies_file:
            strategies.append({"cookiefile": cookies_file})
    else:
        # Instagram Reels, TikTok (sem marca d'água), Twitter/X, etc.
        strategies = [
            {
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                }
            }
        ]

    last_error = None
    for strat in strategies:
        ydl_opts: Dict[str, Any] = {
            "outtmpl": out_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }
        if ffmpeg_loc:
            ydl_opts["ffmpeg_location"] = ffmpeg_loc
        ydl_opts.update(strat)

        if format_type.lower() == "mp3":
            # Extração de áudio convertida para MP3 (aceita qualquer codec e converte para MP3)
            audio_quality = "320" if "320" in quality else ("128" if "128" in quality else "192")
            ydl_opts.update({
                "format": "ba/b",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": audio_quality,
                }],
            })
        else:
            # Extração de vídeo universal (bv*+ba/b) com merge automático para MP4 via FFmpeg
            ydl_opts.update({
                "format": "bv*+ba/b",
                "merge_output_format": "mp4",
            })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if "entries" in info:
                    info = info["entries"][0]

                title = info.get("title", "video_extraido")
                duration = info.get("duration", 0)
                uploader = info.get("uploader", "Desconhecido")
                view_count = info.get("view_count", 0)
                webpage_url = info.get("webpage_url", url)

                expected_ext = "mp3" if format_type.lower() == "mp3" else "mp4"
                downloaded_file = None

                if "_filename" in info:
                    cand = Path(info["_filename"]).with_suffix(f".{expected_ext}")
                    if cand.exists():
                        downloaded_file = cand

                if not downloaded_file:
                    candidates = sorted(out_dir.glob(f"*.{expected_ext}"), key=lambda f: f.stat().st_mtime, reverse=True)
                    if candidates:
                        downloaded_file = candidates[0]

                if downloaded_file and downloaded_file.exists():
                    # Enriquece metadados ID3 do MP3 (capa, artista, álbum, ano, gênero)
                    tag_result = None
                    if expected_ext == "mp3":
                        try:
                            tag_result = enrich_mp3_metadata(downloaded_file, info)
                            # Usa o título enriquecido (limpo e validado pelo MusicBrainz)
                            title = tag_result.get("title") or title
                            uploader = tag_result.get("artist") or uploader
                        except Exception as tag_err:
                            import logging
                            logging.getLogger(__name__).warning(f"[Tagger] Falha ao enriquecer metadados: {tag_err}")

                    thumbnail_url = None
                    if expected_ext == "mp3" and isinstance(tag_result, dict):
                        thumbnail_url = tag_result.get("cover_url")
                    if not thumbnail_url:
                        from tools.music_tagger import _best_thumbnail_url
                        thumbnail_url = _best_thumbnail_url(info)

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
                        "format": expected_ext.upper(),
                        "thumbnail": thumbnail_url
                    }
        except Exception as e:
            last_error = e
            continue

    if last_error:
        raise last_error
def is_playlist_url(url: str) -> bool:
    """Verifica se a URL aponta para uma playlist ou álbum de músicas."""
    if not url:
        return False
    u = url.lower()
    if "youtube.com/playlist" in u or "music.youtube.com/playlist" in u:
        return True
    if ("youtube.com" in u or "youtu.be" in u) and ("list=" in u):
        return True
    return False

def _sanitize_folder_name(name: str) -> str:
    """Remove caracteres inválidos para pastas e arquivos no Windows/Linux."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:80] or "playlist"

def _run_playlist_dlp(url: str, quality: str, out_dir: Path, max_tracks: int = 50) -> Dict[str, Any]:
    """Executa o download de playlist completa, converte faixas para MP3 320kbps, enriquece metadados e gera .ZIP."""
    import zipfile
    import shutil
    import logging
    logger = logging.getLogger(__name__)

    ffmpeg_loc = _get_ffmpeg_location()
    cookies_file = _get_youtube_cookies()

    # 1. Obtém metadados da playlist com extract_flat
    flat_opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "noplaylist": False,
    }
    if cookies_file:
        flat_opts["cookiefile"] = cookies_file

    playlist_title = "Playlist"
    uploader = "Desconhecido"

    try:
        with yt_dlp.YoutubeDL(flat_opts) as ydl:
            flat_info = ydl.extract_info(url, download=False)
            if flat_info:
                playlist_title = flat_info.get("title") or "Playlist"
                uploader = flat_info.get("uploader") or flat_info.get("channel") or "Desconhecido"
    except Exception as e:
        logger.warning(f"[Playlist] Falha ao extrair info flat da playlist: {e}")

    safe_title = _sanitize_folder_name(playlist_title)
    timestamp = int(time.time())
    pl_dir = out_dir / f"pl_{timestamp}_{safe_title}"
    pl_dir.mkdir(parents=True, exist_ok=True)

    out_template = str(pl_dir / "%(playlist_index|00)02d - %(title).100s.%(ext)s")
    audio_quality = "320" if "320" in quality else ("128" if "128" in quality else "192")

    strategies = [
        {"extractor_args": {"youtube": {"player_client": ["visionos"]}}},
        {"extractor_args": {"youtube": {"player_client": ["web_creator"]}}},
        {"extractor_args": {"youtube": {"player_client": ["tv_downgraded"]}}},
        {"extractor_args": {"youtube": {"player_client": ["web"]}}},
    ]
    if cookies_file:
        strategies.append({"cookiefile": cookies_file})

    downloaded = False
    last_error = None

    for strat in strategies:
        ydl_opts: Dict[str, Any] = {
            "outtmpl": out_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": False,
            "playlistend": max_tracks,
            "format": "ba/b",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": audio_quality,
            }],
            "ignoreerrors": True,  # Continua mesmo se 1 vídeo da lista for indisponível
        }
        if ffmpeg_loc:
            ydl_opts["ffmpeg_location"] = ffmpeg_loc
        ydl_opts.update(strat)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
                downloaded = True
                break
        except Exception as err:
            last_error = err
            continue

    if not downloaded and last_error:
        raise last_error

    # 2. Localiza os arquivos MP3 gerados
    mp3_files = sorted(list(pl_dir.glob("*.mp3")), key=lambda f: f.name)
    if not mp3_files:
        raise RuntimeError("Nenhuma faixa pôde ser extraída na VPS (possível bloqueio antibot do YouTube: sign in to confirm you're not a bot).")

    total_count = len(mp3_files)

    # 3. Enriquece tags ID3 em cada MP3
    for idx, mp3_file in enumerate(mp3_files, 1):
        try:
            clean_name = re.sub(r'^\d+\s*[-–—]\s*', '', mp3_file.stem)
            fake_info = {
                "title": clean_name,
                "uploader": uploader,
                "track_number": f"{idx}/{total_count}",
                "album": playlist_title,
                "webpage_url": url,
            }
            enrich_mp3_metadata(mp3_file, fake_info)
        except Exception as tag_err:
            logger.warning(f"[Playlist Tagger] Erro ao enriquecer {mp3_file.name}: {tag_err}")

    # 4. Compacta todas as faixas em um arquivo .ZIP de alta qualidade
    zip_filename = f"{safe_title}.zip"
    zip_path = out_dir / zip_filename
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for mp3_file in mp3_files:
            zipf.write(mp3_file, arcname=mp3_file.name)

    # 5. Remove a pasta de MP3s descompactados para economizar espaço
    try:
        shutil.rmtree(pl_dir, ignore_errors=True)
    except Exception:
        pass

    zip_size = zip_path.stat().st_size
    return {
        "title": playlist_title,
        "uploader": uploader,
        "track_count": total_count,
        "file_path": zip_path,
        "file_name": zip_filename,
        "file_size": zip_size,
        "format": "ZIP"
    }

from tools.temp_storage import register_temp_file, get_download_url, get_storage_dir

async def download_playlist_media(
    url: str,
    quality: str = "320",
    max_tracks: int = 50,
    user_id: Optional[str] = None,
    channel: Optional[str] = "whatsapp"
) -> str:
    """
    Baixa uma playlist completa do YouTube (até 50 faixas), converte cada faixa
    para MP3 320kbps com tags e capas oficiais embutidas, compacta em um pacote
    .ZIP organizado e gera o link direto de download temporário de 48 horas.
    """
    clean_url = url.strip()
    if not clean_url.startswith("http"):
        return f"[ERRO]: URL inválida: '{clean_url}'."

    out_dir = get_storage_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    result = None
    try:
        result = await asyncio.to_thread(_run_playlist_dlp, clean_url, quality, out_dir, max_tracks)
    except Exception as e:
        err_str = str(e)
        from agent.nodes import node_manager
        # Se falhou na VPS e o worker do PC pessoal estiver online, desvia para a conexão residencial!
        if node_manager.is_connected:
            try:
                if user_id:
                    await send_channel_message(
                        user_id,
                        channel or "whatsapp",
                        "🔄 _Bloqueio do YouTube detectado no servidor. Desviando o download da playlist automaticamente pelo seu PC pessoal via conexão residencial..._"
                    )
                import json
                pc_res = await node_manager.execute_on_pc(
                    action="download_playlist_media_local",
                    args={
                        "url": clean_url,
                        "quality": quality,
                        "max_tracks": max_tracks,
                        "upload_to_vps": True
                    },
                    timeout=600
                )
                res_data = json.loads(pc_res) if isinstance(pc_res, str) else pc_res
                if res_data.get("success"):
                    result = res_data["result"]
                    result["file_path"] = Path(result["file_path"])
                else:
                    raise RuntimeError(res_data.get("error", pc_res))
            except Exception as pc_err:
                return f"❌ *Falha ao extrair playlist pelo PC:* `{pc_err}`"
        else:
            return (
                f"⚠️ *Bloqueio Antibot do YouTube no Servidor!*\n\n"
                f"O YouTube bloqueou o IP do datacenter da VPS exigindo autenticação (`Sign in to confirm you're not a bot`).\n\n"
                f"💡 *Como resolver de forma definitiva:*\n"
                f"1. Mantenha o script `worker.py` rodando no seu PC Windows para o assistente usar sua internet residencial automaticamente!\n"
                f"2. Ou coloque o arquivo `cookies.txt` do seu YouTube logado na pasta `/workspace/cookies.txt` da VPS."
            )

    file_path = result["file_path"]
    file_name = result["file_name"]
    file_size_formatted = _format_size(result["file_size"])
    title = result["title"]
    uploader = result["uploader"]
    track_count = result["track_count"]
    file_size_mb = result.get("file_size", 0) / (1024 * 1024)

    # Registra no storage temporário de 48 horas da VPS
    storage_record = register_temp_file(
        file_path=file_path,
        filename=file_name,
        metadata={
            "title": title,
            "uploader": uploader,
            "track_count": track_count,
            "type": "playlist_zip"
        },
        ttl_hours=48
    )
    token = storage_record["token"]
    download_link = get_download_url(token)

    sent_status = ""
    if user_id and file_size_mb <= 25.0:
        try:
            ok_media = await send_channel_media(
                recipient=user_id,
                channel=channel or "whatsapp",
                file_path=str(file_path),
                caption=f"📦 *Playlist: {title}* ({track_count} faixas em .ZIP)",
                media_type="document",
                file_name=file_name
            )
            if ok_media:
                sent_status = "\n📲 *Arquivo no Chat:* ✅ O pacote .ZIP foi enviado acima diretamente para você!"
        except Exception:
            pass

    response = (
        f"📦 *Playlist Completa Extraída com Sucesso!*\n\n"
        f"📌 *Playlist:* {title}\n"
        f"👤 *Canal/Autor:* {uploader}\n"
        f"🎵 *Faixas Baixadas:* {track_count} músicas em MP3 320kbps\n"
        f"📦 *Tamanho do Pacote:* {file_size_formatted} (.ZIP)\n"
        f"⏳ *Validade:* 48 horas (Armazenamento na VPS)\n\n"
        f"⬇️ *CLIQUE NO LINK PARA SALVAR O PACOTE .ZIP NA PASTA DOWNLOADS:*\n"
        f"{download_link}\n\n"
        f"💡 _Todas as músicas estão numeradas em ordem (01, 02...), renomeadas e com capas de álbum em alta resolução embutidas. Basta descompactar no celular ou PC para curtir!_"
        f"{sent_status}"
    )
    return response

async def download_youtube_media(
    url: str,
    format_type: str = "mp3",
    quality: str = "best",
    destination_folder: Optional[str] = None,
    send_to_chat: bool = True,
    send_mode: str = "link",
    user_id: Optional[str] = None,
    channel: Optional[str] = "whatsapp"
) -> str:
    """
    Baixa vídeo ou áudio do YouTube por meio da URL, converte para MP3 (ou MP4)
    em alta qualidade na VPS, armazena no storage temporário com validade de 48 horas
    (estilo Drive) e gera o link direto para download no celular/computador.
    """
    clean_url = url.strip()
    if not clean_url.startswith("http"):
        return f"[ERRO]: URL inválida: '{clean_url}'. Envie um link válido do YouTube (ex: https://www.youtube.com/watch?v=...)."

    # Se for link de playlist e o formato não for vídeo explícito, baixa o pacote .ZIP completo
    if is_playlist_url(clean_url) and format_type != "mp4":
        return await download_playlist_media(
            url=clean_url,
            quality="320" if "320" in quality else "best",
            max_tracks=50,
            user_id=user_id,
            channel=channel
        )

    # Define pasta de destino na VPS (storage temporário)
    if destination_folder:
        out_dir = Path(destination_folder).resolve()
    else:
        out_dir = get_storage_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    result = None
    try:
        # Executa o download em thread separada para não bloquear o loop de eventos
        result = await asyncio.to_thread(_run_yt_dlp, clean_url, format_type, quality, out_dir)
    except Exception as e:
        err_str = str(e)
        from agent.nodes import node_manager
        # Se for bloqueio antibot e o worker do PC estiver online, tenta delegar para o IP residencial do PC
        is_bot_block = any(k in err_str.lower() for k in ["not a bot", "sign in", "bot", "403", "forbidden"])
        if is_bot_block and node_manager.is_connected:
            try:
                import json
                pc_res = await node_manager.execute_on_pc("download_youtube_media_local", {
                    "url": clean_url,
                    "format_type": format_type,
                    "quality": quality,
                    "upload_to_vps": True
                })
                if isinstance(pc_res, str):
                    try:
                        res_data = json.loads(pc_res)
                    except Exception:
                        res_data = {}
                    if res_data.get("success"):
                        result = res_data["result"]
                        result["file_path"] = Path(result["file_path"])
                    else:
                        raise RuntimeError(res_data.get("error", pc_res))
                else:
                    raise RuntimeError(f"Resposta inesperada do PC: {pc_res}")
            except Exception as pc_err:
                return (
                    f"⚠️ *Bloqueio Antibot do YouTube no Servidor!*\n\n"
                    f"O YouTube bloqueou o IP do servidor em nuvem (Easypanel/Datacenter) exigindo autenticação.\n"
                    f"Tentativa de contorno pelo PC local falhou com: `{pc_err}`\n\n"
                    f"💡 *Solução Definitiva:* Exporte seus cookies do YouTube usando a extensão *Get cookies.txt LOCALLY* "
                    f"e coloque no servidor como `cookies.txt`."
                )
        else:
            if is_bot_block:
                return (
                    f"⚠️ *Bloqueio Antibot do YouTube no Servidor!*\n\n"
                    f"O YouTube identificou o IP do datacenter da VPS e solicitou confirmação de login (`Sign in to confirm you're not a bot`).\n\n"
                    f"💡 *Como resolver de forma definitiva:*\n"
                    f"1. Instale a extensão *Get cookies.txt LOCALLY* no Chrome/Firefox.\n"
                    f"2. Acesse o YouTube logado e exporte o arquivo `cookies.txt`.\n"
                    f"3. Coloque o `cookies.txt` na pasta `/workspace/cookies.txt` da VPS (ou envie no chat).\n"
                    f"4. Ou mantenha o script `worker.py` rodando no seu PC local para o assistente usar sua internet residencial automaticamente!"
                )
            return f"[ERRO AO EXTRAIR MÍDIA]: {err_str}"

    file_path = result["file_path"]
    file_name = result["file_name"]
    file_size_formatted = _format_size(result["file_size"])
    duration_formatted = _format_duration(result["duration"])
    title = result["title"]
    uploader = result["uploader"]
    fmt = result["format"]
    platform = _detect_platform(clean_url)
    file_size_bytes = result.get("file_size", 0)
    file_size_mb = file_size_bytes / (1024 * 1024)

    # Registra no storage temporário da VPS com retenção de 48 horas
    storage_record = register_temp_file(
        file_path=file_path,
        filename=file_name,
        metadata={
            "title": title,
            "uploader": uploader,
            "duration": duration_formatted,
            "platform": platform
        },
        ttl_hours=48
    )
    token = storage_record["token"]
    main_download_link = get_download_url(token)

    # =========================================================================
    # ENTREGA DUPLA MANDATÓRIA (Player no WhatsApp se <= 25MB + Link de 48h)
    # =========================================================================
    sent_media_status = ""
    if send_to_chat and user_id:
        ch = channel or "whatsapp"
        if file_size_mb <= 25.0:
            media_type = "audio" if fmt == "MP3" else "video"
            media_caption = f"🎧 *{title}*" if fmt == "MP3" else f"🎬 *{title}*"
            try:
                ok_media = await send_channel_media(
                    recipient=user_id,
                    channel=ch,
                    file_path=str(file_path),
                    caption=media_caption,
                    media_type=media_type,
                    file_name=file_name
                )
                if ok_media:
                    action_word = "ouvir" if fmt == "MP3" else "assistir"
                    sent_media_status = f"\n📲 *Player no Chat:* ✅ Enviado acima para você {action_word} agora!"
            except Exception as send_err:
                import logging
                logging.getLogger(__name__).warning(f"[Download] Erro ao enviar mídia direta: {send_err}")
        else:
            sent_media_status = f"\n📲 *Envio no Chat:* ℹ️ Arquivo com {file_size_formatted} (acima do limite do chat de 25MB); use o link abaixo para baixar!"

    action_label = "ouvir" if fmt == "MP3" else "assistir"
    icon = "🎵" if fmt == "MP3" else "🎬"

    response = (
        f"{icon} *Extração Concluída com Sucesso!* ({platform})\n\n"
        f"📌 *Título:* {title}\n"
        f"👤 *Canal/Autor:* {uploader}\n"
        f"⏱️ *Duração:* {duration_formatted}\n"
        f"📦 *Formato:* {fmt} ({file_size_formatted})\n"
        f"⏳ *Validade:* 48 horas (Armazenamento na VPS)\n\n"
        f"⬇️ *CLIQUE NO LINK PARA SALVAR NA SUA PASTA DOWNLOADS:*\n"
        f"{main_download_link}\n\n"
        f"💡 _O arquivo foi enviado acima para você {action_label} na hora! "
        f"Para salvá-lo na pasta **Download** permanente do seu aparelho (sendo reconhecido em players nativos como Samsung Music, Xiaomi, Apple Music ou VLC), toque no link acima._"
        f"{sent_media_status}"
    )
    return response


async def process_media_for_api(
    url: str,
    format_type: str = "mp3",
    quality: str = "best"
) -> Dict[str, Any]:
    """
    Processa a extração de mídia (YouTube, Instagram, TikTok, etc.) especificamente para a API Mobile.
    - Suporta URLs com '//', sem esquema ou completas
    - Converte áudio para MP3 320kbps com tags ID3 e capa oficial embutida
    - Registra no storage temporário de 48h da VPS
    - Devolve o formato exato esperado pelo MediaItem do app Android
    """
    clean_url = (url or "").strip()
    if clean_url.startswith("//"):
        clean_url = "https:" + clean_url
    elif not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url

    fmt_lower = format_type.lower()
    if fmt_lower not in ["mp3", "mp4"]:
        fmt_lower = "mp3"

    # 1. Trata Playlist se aplicável
    if is_playlist_url(clean_url) and fmt_lower != "mp4":
        out_dir = get_storage_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = await asyncio.to_thread(_run_playlist_dlp, clean_url, "320" if "320" in quality else "best", out_dir, 50)
        except Exception as e:
            err_str = str(e)
            from agent.nodes import node_manager
            is_bot_block = any(k in err_str.lower() for k in ["not a bot", "sign in", "bot", "403", "forbidden"])
            if is_bot_block and node_manager.is_connected:
                import json
                pc_res = await node_manager.execute_on_pc("download_playlist_media_local", {
                    "url": clean_url,
                    "quality": "320" if "320" in quality else "best",
                    "max_tracks": 50,
                    "upload_to_vps": True
                }, timeout=600)
                res_data = json.loads(pc_res) if isinstance(pc_res, str) else pc_res
                if res_data.get("success"):
                    result = res_data["result"]
                    result["file_path"] = Path(result["file_path"])
                else:
                    raise RuntimeError(res_data.get("error", "Erro ao extrair playlist no PC local."))
            else:
                raise

        file_path = Path(result["file_path"])
        file_name = result["file_name"]
        file_size = result.get("file_size", 0)
        title = result["title"]
        uploader = result["uploader"]
        track_count = result.get("track_count", 0)

        storage_record = register_temp_file(
            file_path=file_path,
            filename=file_name,
            metadata={
                "title": title,
                "uploader": uploader,
                "track_count": track_count,
                "type": "playlist_zip"
            },
            ttl_hours=48
        )
        token = storage_record["token"]
        base_dl_url = get_download_url(token)
        download_url = f"{base_dl_url}/{urllib.parse.quote(file_name)}"

        return {
            "id": token,
            "title": title,
            "author": uploader,
            "duration": f"{track_count} faixas",
            "thumbnail": result.get("thumbnail"),
            "downloadUrl": download_url,
            "format": "zip",
            "fileSize": _format_size(file_size)
        }

    # 2. Mídia individual (Áudio MP3 ou Vídeo MP4)
    out_dir = get_storage_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    result = None
    try:
        result = await asyncio.to_thread(_run_yt_dlp, clean_url, fmt_lower, quality, out_dir)
    except Exception as e:
        err_str = str(e)
        from agent.nodes import node_manager
        is_bot_block = any(k in err_str.lower() for k in ["not a bot", "sign in", "bot", "403", "forbidden"])
        if is_bot_block and node_manager.is_connected:
            import json
            pc_res = await node_manager.execute_on_pc("download_youtube_media_local", {
                "url": clean_url,
                "format_type": fmt_lower,
                "quality": quality,
                "upload_to_vps": True
            })
            if isinstance(pc_res, str):
                try:
                    res_data = json.loads(pc_res)
                except Exception:
                    res_data = {}
                if res_data.get("success"):
                    result = res_data["result"]
                    result["file_path"] = Path(result["file_path"])
                else:
                    raise RuntimeError(res_data.get("error", pc_res))
            else:
                raise RuntimeError(f"Resposta inesperada do PC: {pc_res}")
        else:
            raise

    file_path = Path(result["file_path"])
    file_name = result["file_name"]
    file_size = result.get("file_size", 0)
    title = result["title"]
    uploader = result["uploader"]
    duration_formatted = _format_duration(result.get("duration"))
    file_size_formatted = _format_size(file_size)
    thumbnail = result.get("thumbnail")
    platform = _detect_platform(clean_url)

    token = result.get("token")
    if not token:
        storage_record = register_temp_file(
            file_path=file_path,
            filename=file_name,
            metadata={
                "title": title,
                "uploader": uploader,
                "duration": duration_formatted,
                "platform": platform
            },
            ttl_hours=48
        )
        token = storage_record["token"]

    base_dl_url = get_download_url(token)
    download_url = f"{base_dl_url}/{urllib.parse.quote(file_name)}"

    return {
        "id": token,
        "title": title,
        "author": uploader,
        "duration": duration_formatted,
        "thumbnail": thumbnail,
        "downloadUrl": download_url,
        "format": fmt_lower,
        "fileSize": file_size_formatted
    }

