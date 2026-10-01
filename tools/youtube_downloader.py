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

def _run_yt_dlp(url: str, format_type: str, quality: str, out_dir: Path) -> Dict[str, Any]:
    """Execução síncrona do yt-dlp com detecção de ffmpeg, cookies e bypass de clientes móveis."""
    ffmpeg_loc = _get_ffmpeg_location()
    out_template = str(out_dir / "%(title).200s.%(ext)s")
    
    ydl_opts: Dict[str, Any] = {
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "mweb"]
            }
        }
    }

    if ffmpeg_loc:
        ydl_opts["ffmpeg_location"] = ffmpeg_loc

    cookies_file = _get_youtube_cookies()
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file

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

from tools.temp_storage import register_temp_file, get_download_url, get_storage_dir

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
            return f"[ERRO AO EXTRAIR DO YOUTUBE]: {err_str}"

    file_path = result["file_path"]
    file_name = result["file_name"]
    file_size_formatted = _format_size(result["file_size"])
    duration_formatted = _format_duration(result["duration"])
    title = result["title"]
    uploader = result["uploader"]
    fmt = result["format"]

    # Registra no storage temporário da VPS com retenção de 48 horas
    storage_record = register_temp_file(
        file_path=file_path,
        filename=file_name,
        metadata={
            "title": title,
            "uploader": uploader,
            "duration": duration_formatted
        },
        ttl_hours=48
    )
    token = storage_record["token"]
    main_download_link = get_download_url(token)

    # Envio opcional direto para o WhatsApp/Telegram se solicitado (documento ou player)
    sent_media_status = ""
    if send_to_chat and user_id and send_mode != "link":
        ch = channel or "whatsapp"
        results_sent = []

        if send_mode in ["document", "both"]:
            doc_caption = (
                f"📁 *{title}*\n"
                f"👤 Canal: {uploader} | ⏱️ {duration_formatted} | 📦 {file_size_formatted}"
            )
            try:
                ok_doc = await send_channel_media(
                    recipient=user_id,
                    channel=ch,
                    file_path=str(file_path),
                    caption=doc_caption,
                    media_type="document",
                    file_name=file_name
                )
                if ok_doc:
                    results_sent.append("📁 Arquivo anexado")
            except Exception:
                pass

        if send_mode in ["chat_player", "both"]:
            chat_type = "audio" if fmt == "MP3" else "video"
            chat_caption = f"🎧 *{title}* (Player no Chat)"
            try:
                ok_player = await send_channel_media(
                    recipient=user_id,
                    channel=ch,
                    file_path=str(file_path),
                    caption=chat_caption,
                    media_type=chat_type,
                    file_name=file_name
                )
                if ok_player:
                    results_sent.append("🎧 Player no chat")
            except Exception:
                pass

        if results_sent:
            sent_media_status = f"\n📲 *Envio no Chat:* ✅ {' e '.join(results_sent)} entregue(s)!"

    response = (
        f"🎬 *Extração do YouTube Concluída com Sucesso!*\n\n"
        f"📌 *Título:* {title}\n"
        f"👤 *Canal/Autor:* {uploader}\n"
        f"⏱️ *Duração:* {duration_formatted}\n"
        f"📦 *Formato:* {fmt} ({file_size_formatted})\n"
        f"⏳ *Validade:* 48 horas (Armazenamento temporário na VPS)\n\n"
        f"⬇️ *CLIQUE NO LINK PARA BAIXAR NO SEU CELULAR:*\n"
        f"{main_download_link}\n\n"
        f"💡 _Ao tocar no link acima, o download iniciará direto na pasta **Download** do seu smartphone. "
        f"Assim, tocadores como Samsung Music, Xiaomi e YouTube Music reconhecem a faixa na hora "
        f"e você pode enviá-la como áudio nativo quando quiser!_{sent_media_status}"
    )
    return response
