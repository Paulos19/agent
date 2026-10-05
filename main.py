import asyncio
import time
import json
from datetime import datetime
import logging
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header, WebSocket, WebSocketDisconnect, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pathlib import Path
import urllib.parse
import re
import mimetypes
from pydantic import BaseModel
import uvicorn

from config import settings
from tools.scheduler import init_scheduler
from agent import run_agent_loop, memory, task_manager
from agent.nodes import node_manager
from channels import (
    extract_evolution_message,
    send_evolution_message,
    send_evolution_media,
    extract_telegram_message,
    send_telegram_message,
    send_telegram_media,
    send_channel_media
)

# Configuração de logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("assistente-cli")

async def send_channel_message(recipient: str, channel: str, text: str):
    """Despacha mensagem de texto para o canal do usuário (WhatsApp ou Telegram)."""
    try:
        if channel == "whatsapp":
            await send_evolution_message(recipient, text)
        elif channel == "telegram":
            await send_telegram_message(recipient, text)
    except Exception as e:
        logger.error(f"[Canal {channel}] Erro ao enviar mensagem para {recipient}: {e}")

async def handle_scheduled_job(user_id: str, channel: str, prompt: str):
    """Callback invocado pelo agendador (APScheduler) quando uma tarefa dispara."""
    logger.info(f"[Scheduler] Disparando tarefa agendada para {user_id} via {channel}: {prompt}")
    await process_user_request(user_id, channel, prompt)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialização do agendador
    init_scheduler(handle_scheduled_job)
    
    # Limpeza e agendamento de storage temporário (48 horas)
    try:
        from tools.temp_storage import cleanup_expired_files
        from tools.scheduler import scheduler
        from apscheduler.triggers.interval import IntervalTrigger
        cleaned = cleanup_expired_files()
        if cleaned:
            logger.info(f"[TempStorage] {cleaned} arquivo(s) temporário(s) expirado(s) removido(s) na inicialização.")
        scheduler.add_job(
            cleanup_expired_files,
            trigger=IntervalTrigger(hours=1),
            id="cleanup_temp_storage_job",
            replace_existing=True
        )
    except Exception as e:
        logger.error(f"[TempStorage] Erro ao configurar limpeza de storage temporário: {e}")

    logger.info("====================================================")
    logger.info("   Assistente CLI / DevOps Agent Inicializado!      ")
    logger.info(f"   Workspace: {settings.workspace_path}")
    logger.info(f"   Usuários autorizados: {settings.allowed_users_set or 'TODOS (Atenção!)'}")
    logger.info("====================================================")
    yield
    logger.info("Encerrando assistente...")

app = FastAPI(title="Assistente CLI & DevOps Agent", lifespan=lifespan)

# Servir arquivos de download diretamente via HTTP
downloads_dir = settings.workspace_path / "downloads"
downloads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/downloads", StaticFiles(directory=str(downloads_dir)), name="downloads")

@app.get("/download/{filename}")
async def download_file_direct(filename: str):
    """
    Endpoint de download direto com Content-Disposition: attachment.
    Força o navegador do celular (Chrome/Safari) a fazer o download direto
    para a pasta 'Download' do aparelho (onde os apps de música e galeria enxergam),
    em vez de abrir apenas para reprodução na aba.
    """
    decoded_name = urllib.parse.unquote(filename)
    downloads_path = (settings.workspace_path / "downloads").resolve()
    file_path = (downloads_path / decoded_name).resolve()

    # Prevenção de Path Traversal
    if not str(file_path).startswith(str(downloads_path)):
        raise HTTPException(status_code=403, detail="Acesso não autorizado.")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado ou já expirado.")

    ext = file_path.suffix.lower()
    if ext == ".mp3":
        mime = "audio/mpeg"
    elif ext == ".mp4":
        mime = "video/mp4"
    elif ext == ".m4a":
        mime = "audio/mp4"
    else:
        mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

def _make_content_disposition(filename: str, fallback_prefix: str = "download") -> str:
    """Gera cabeçalho Content-Disposition 100% compatível com RFC 5987 / RFC 6266 (Latin-1 safe)."""
    import unicodedata
    ext = Path(filename).suffix.lower()
    # Remove acentos e caracteres não-ASCII (coreano, japonês, etc.) para o filename legado
    ascii_clean = unicodedata.normalize('NFKD', str(filename)).encode('ascii', 'ignore').decode('ascii')
    safe_ascii = re.sub(r'[^a-zA-Z0-9_\.-]', '_', ascii_clean)
    safe_ascii = re.sub(r'_+', '_', safe_ascii).strip('_')
    if not safe_ascii or safe_ascii.startswith('.'):
        safe_ascii = f"{fallback_prefix}{ext or '.mp3'}"
    quoted_utf8 = urllib.parse.quote(str(filename))
    return f'attachment; filename="{safe_ascii}"; filename*=UTF-8\'\'{quoted_utf8}'

@app.get("/download/{filename}")
async def download_file(filename: str):
    """
    Endpoint legado para download direto de arquivos do projeto no workspace.
    """
    file_path = (settings.workspace_path / filename).resolve()
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    ext = file_path.suffix.lower()
    if ext == ".mp3":
        mime = "audio/mpeg"
    elif ext == ".mp4":
        mime = "video/mp4"
    elif ext == ".m4a":
        mime = "audio/mp4"
    else:
        mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

    content_disposition = _make_content_disposition(file_path.name)

    return FileResponse(
        path=str(file_path),
        media_type=mime,
        headers={
            "Content-Disposition": content_disposition,
            "Cache-Control": "public, max-age=3600",
            "Accept-Ranges": "bytes"
        }
    )

@app.get("/d/{token}")
@app.head("/d/{token}")
@app.get("/d/{token}/{filename}")
@app.head("/d/{token}/{filename}")
async def download_temp_file(token: str, filename: Optional[str] = None):
    """
    Download de arquivo temporário de 48 horas estilo Drive / WeTransfer.
    Verifica se o token é válido e não expirou.
    Força o download direto para a pasta de Downloads do dispositivo (Android/iOS/PC).
    """
    html_expired = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Link Expirado</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #090a0f; color: #ededed; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
    .card { background: #12141c; border: 1px solid #272a38; border-radius: 20px; padding: 36px; max-width: 440px; text-align: center; box-shadow: 0 20px 50px rgba(0,0,0,0.6); }
    .icon { font-size: 52px; margin-bottom: 20px; }
    h1 { font-size: 22px; margin: 0 0 12px 0; color: #f4f4f5; font-weight: 700; }
    p { font-size: 14px; line-height: 1.6; color: #94a3b8; margin: 0 0 20px 0; }
    .badge { display: inline-block; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); color: #f87171; padding: 6px 14px; border-radius: 9999px; font-size: 12px; font-weight: 600; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">⏳</div>
    <h1>Link Expirado</h1>
    <p>Este arquivo foi removido permanentemente após o período de <strong>48 horas</strong> por motivos de privacidade e economia de espaço no servidor.</p>
    <div class="badge">Retenção de 48h Expirada</div>
  </div>
</body>
</html>"""

    try:
        from tools.temp_storage import get_temp_file
        record = get_temp_file(token)
        if not record:
            return HTMLResponse(content=html_expired, status_code=410)

        raw_path = record.get("file_path")
        if not raw_path:
            return HTMLResponse(content=html_expired, status_code=410)

        file_path = Path(raw_path)
        if not file_path.exists() or not file_path.is_file():
            return HTMLResponse(content=html_expired, status_code=410)

        raw_name = record.get("filename") or filename or file_path.name or f"audio_{token}.mp3"
        actual_filename = str(raw_name)

        ext = file_path.suffix.lower()
        if ext == ".mp3":
            mime = "audio/mpeg"
        elif ext == ".mp4":
            mime = "video/mp4"
        elif ext == ".m4a":
            mime = "audio/mp4"
        else:
            mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

        content_disposition = _make_content_disposition(actual_filename, fallback_prefix=f"download_{token}")

        return FileResponse(
            path=str(file_path.resolve()),
            media_type=mime,
            headers={
                "Content-Disposition": content_disposition,
                "Cache-Control": "public, max-age=3600",
                "Accept-Ranges": "bytes"
            }
        )
    except Exception as e:
        logger.exception(f"[Download Error] Falha ao servir arquivo para token '{token}': {e}")
        return HTMLResponse(
            content=f"<!DOCTYPE html><html><body style='background:#090a0f;color:#ededed;font-family:sans-serif;padding:40px;text-align:center;'><h1>Erro ao processar download</h1><p>{str(e)}</p></body></html>",
            status_code=500
        )

@app.get("/api/debug_token/{token}")
async def debug_token(token: str):
    """Retorna detalhes do token para diagnóstico."""
    from tools.temp_storage import _load_registry, get_storage_dir
    reg = _load_registry()
    storage_dir = get_storage_dir()
    files = [f.name for f in storage_dir.glob("*")]
    return {
        "token": token,
        "record_in_registry": reg.get(token),
        "total_records": len(reg),
        "files_in_storage": files
    }

@app.post("/api/upload_temp")
async def upload_temp_file(
    file: UploadFile = File(...),
    token: str = Query(...)
):
    """
    Endpoint para o worker local (PC) enviar arquivos gerados diretamente
    para o storage temporário da VPS (/workspace/storage/temp_downloads).
    """
    if token != settings.WORKER_SECRET:
        raise HTTPException(status_code=403, detail="Token inválido")

    from tools.temp_storage import get_storage_dir, register_temp_file, get_download_url
    storage_dir = get_storage_dir()
    safe_filename = Path(file.filename).name
    dest_path = storage_dir / safe_filename

    # Salva o arquivo no storage
    with open(dest_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    record = register_temp_file(
        file_path=dest_path,
        filename=safe_filename,
        metadata={"uploaded_by": "worker_pc"},
        ttl_hours=48
    )
    download_link = get_download_url(record["token"])
    return {
        "status": "success",
        "token": record["token"],
        "download_url": download_link,
        "file_path": str(dest_path),
        "file_name": safe_filename,
        "file_size": dest_path.stat().st_size
    }

@app.post("/api/upload_cookies")
async def upload_cookies_file(
    file: UploadFile = File(...),
    token: str = Query(...)
):
    """Permite enviar o arquivo cookies.txt do YouTube diretamente para a VPS."""
    if token != settings.WORKER_SECRET:
        raise HTTPException(status_code=403, detail="Token inválido")

    workspace = settings.workspace_path
    dest = workspace / "cookies.txt"
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

    return {"status": "success", "message": "Arquivo cookies.txt salvo com sucesso no servidor!", "path": str(dest)}

class DownloadYouTubeRequest(BaseModel):
    url: str
    format_type: str = "mp3"
    quality: str = "best"
    send_to_chat: bool = False
    send_mode: str = "link"
    user_id: Optional[str] = None
    channel: Optional[str] = None


class AppLoginRequest(BaseModel):
    phone: str

class AppLoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    user_name: Optional[str] = None
    error: Optional[str] = None

@app.post("/api/auth/login", response_model=AppLoginResponse)
async def api_auth_login(req: AppLoginRequest):
    """Autentica o aplicativo mobile via telefone autorizado."""
    raw_phone = req.phone or ""
    cleaned_phone = "".join(c for c in raw_phone if c.isdigit())
    allowed = [p.strip() for p in settings.ALLOWED_USERS.split(",") if p.strip()]
    is_authorized = False
    for num in allowed:
        c_num = "".join(c for c in num if c.isdigit())
        if c_num and (cleaned_phone == c_num or cleaned_phone.endswith(c_num) or c_num.endswith(cleaned_phone)):
            is_authorized = True
            break
            
    if not is_authorized:
        return AppLoginResponse(
            success=False,
            error="Telefone não autorizado para acesso ao assistente."
        )
        
    return AppLoginResponse(
        success=True,
        token=settings.WORKER_SECRET,
        user_name="Paulo Henrique"
    )

@app.post("/api/download_youtube")
async def api_download_youtube(
    req: DownloadYouTubeRequest,
    token: str = Query(...)
):
    """Executa a extração do YouTube no servidor com o storage de 48h."""
    if token != settings.WORKER_SECRET:
        raise HTTPException(status_code=403, detail="Token inválido")

    from tools.youtube_downloader import download_youtube_media
    result_text = await download_youtube_media(
        url=req.url,
        format_type=req.format_type,
        quality=req.quality,
        send_to_chat=req.send_to_chat,
        send_mode=req.send_mode,
        user_id=req.user_id,
        channel=req.channel
    )
    return {"status": "success", "result": result_text}

@app.post("/api/upload_temp")
async def api_upload_temp(
    file: UploadFile = File(...),
    token: str = Query(...)
):
    """Permite ao worker local enviar arquivos (screenshots, áudios, .zip) para a VPS."""
    if token != settings.WORKER_SECRET:
        raise HTTPException(status_code=403, detail="Token inválido")

    from tools.temp_storage import get_storage_dir, register_temp_file, get_download_url
    storage_dir = get_storage_dir()
    save_path = storage_dir / file.filename

    content = await file.read()
    save_path.write_bytes(content)

    reg = register_temp_file(
        file_path=save_path,
        filename=file.filename,
        ttl_hours=48
    )

    return {
        "status": "success",
        "file_path": str(reg["actual_path"]),
        "download_url": get_download_url(reg["token"]),
        "token": reg["token"]
    }

async def process_user_request(user_id: str, channel: str, prompt: str):
    """Executa a solicitação do usuário com suporte a streaming de progresso e concorrência."""
    logger.info(f"[Iniciando Processamento] Usuário: {user_id} | Canal: {channel} | Prompt: {prompt[:60]}...")
    
    clean_num = re.sub(r"\D", "", user_id.split("@")[0])
    is_guest = (clean_num in settings.guest_users_set) and (clean_num not in settings.allowed_users_set)

    # =========================================================================
    # 0. CONVIDADO DE MÍDIA (ACESSO RESTRITO EXCLUSIVAMENTE A DOWNLOAD)
    # =========================================================================
    if is_guest:
        from tools.youtube_downloader import extract_media_url, download_youtube_media, is_playlist_url
        media_url = extract_media_url(prompt)
        if not media_url:
            # Sem link de mídia: silêncio absoluto (não gera conflito em chats pessoais)
            logger.info(f"[Guest Ignored] Mensagem sem link de mídia de convidado {user_id}: {prompt[:30]}")
            return

        is_pl = is_playlist_url(media_url)
        init_guest_msg = (
            "📦 *Opa! Recebi sua playlist!*\n_Já estou baixando todas as faixas em MP3 e preparando o pacote .ZIP... Aguenta só um segundinho!_"
            if is_pl else
            "🎵 *Opa! Recebi seu pedido de download!*\n_Já estou baixando e preparando a sua música em alta qualidade... Aguenta só um segundinho!_"
        )
        # Notifica o convidado exclusivamente no chat dele
        await send_channel_message(user_id, channel, init_guest_msg)

        try:
            p_lower = prompt.lower()
            format_type = "mp4" if any(w in p_lower for w in ["video", "vídeo", "clipe", "mp4", "assistir"]) else "mp3"
            reply = await download_youtube_media(
                url=media_url,
                format_type=format_type,
                quality="best",
                send_to_chat=True,
                send_mode="link",
                user_id=user_id,
                channel=channel
            )
            # Envia a mensagem completa com link de 48h exclusivamente no chat do convidado
            await send_channel_message(user_id, channel, reply)
        except Exception as e:
            logger.error(f"[Guest Download] Erro ao extrair mídia para {user_id}: {e}")
            await send_channel_message(
                user_id,
                channel,
                f"❌ *Desculpe, não consegui baixar essa mídia agora.*\n_Erro:_ {str(e)}"
            )
        return

    # =========================================================================
    # FAST-PATH DE DOWNLOAD DE MÍDIA (INSTANTÂNEO PARA O OPERADOR)
    # =========================================================================
    from tools.youtube_downloader import extract_media_url, download_youtube_media, is_playlist_url
    detected_url = extract_media_url(prompt)
    if detected_url:
        p_clean = prompt.replace(detected_url, "").strip().lower()
        p_clean_simple = re.sub(r'[^a-zA-Z0-9áéíóúâêîôûãõç]', ' ', p_clean).strip()
        words = p_clean_simple.split()
        allowed_cmd_words = {
            "baixe", "baixa", "baixar", "para", "pra", "mim", "essa", "esse",
            "o", "a", "de", "do", "da", "download", "musica", "música",
            "video", "vídeo", "clipe", "mp3", "mp4", "som", "favor", "por",
            "playlist", "album", "álbum", "coletanea", "coletânea", "disco"
        }
        is_download_cmd = not words or all(w in allowed_cmd_words for w in words)
        if is_download_cmd:
            is_pl = is_playlist_url(detected_url)
            if is_pl:
                format_type = "mp3"
                init_msg = "📦 _Identifiquei a playlist! Baixando todas as faixas em MP3 320kbps e compactando em .ZIP... Já te envio o link de 48h!_"
            else:
                format_type = "mp4" if any(w in prompt.lower() for w in ["video", "vídeo", "clipe", "mp4", "assistir"]) else "mp3"
                icon = "🎵" if format_type == "mp3" else "🎬"
                action = "música" if format_type == "mp3" else "vídeo"
                init_msg = f"{icon} _Identifiquei o link! Baixando sua {action} em alta qualidade agora... Já te envio o arquivo e o link de 48h!_"

            await send_channel_message(user_id, channel, init_msg)
            try:
                reply = await download_youtube_media(
                    url=detected_url,
                    format_type=format_type,
                    quality="best",
                    send_to_chat=True,
                    send_mode="link",
                    user_id=user_id,
                    channel=channel
                )
                await send_channel_message(user_id, channel, reply)
                return
            except Exception as e:
                logger.warning(f"[Media Fast-Path] Falha na rota rápida, redirecionando para agente: {e}")

    # 1. Comandos especiais de manutenção de memória
    if prompt.strip().lower() in ["/limpar", "/reset", "/clear"]:
        memory.clear(user_id)
        task_manager.finish_task(user_id)
        msg_reset = "🧹 Memória da conversa e tarefas ativas resetadas com sucesso, chefe! Começando do zero."
        await send_channel_message(user_id, channel, msg_reset)
        return

    # 2. Comando rápido de Screenshot do PC (/print, /screenshot, /tela)
    if prompt.strip().lower() in ["/print", "/screenshot", "/tela"]:
        if not node_manager.is_connected:
            await send_channel_message(
                user_id,
                channel,
                "⚠️ *Seu PC está offline no momento!*\n\nO worker local no Windows não está conectado à VPS agora. Ligue ou desperte o PC para que eu possa capturar a tela."
            )
            return

        await send_channel_message(user_id, channel, "📸 _Tirando print da tela do seu PC agora, aguenta um instante..._")
        try:
            pc_res = await node_manager.execute_on_pc("take_screenshot", {"upload_to_vps": True})
            res_data = json.loads(pc_res) if isinstance(pc_res, str) else pc_res
            if res_data.get("success"):
                file_info = res_data.get("result", {})
                vps_file_path = file_info.get("file_path")
                if vps_file_path and Path(vps_file_path).exists():
                    now_str = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                    ok = await send_channel_media(
                        recipient=user_id,
                        channel=channel,
                        file_path=str(vps_file_path),
                        caption=f"📸 *Screenshot do seu PC*\n⏱️ Capturado em: {now_str}",
                        media_type="image",
                        file_name="screenshot_pc.jpg"
                    )
                    if ok:
                        return
            err_msg = res_data.get("error", "Não foi possível processar a imagem.")
            await send_channel_message(user_id, channel, f"❌ Falha ao capturar screenshot: `{err_msg}`")
        except Exception as e:
            await send_channel_message(user_id, channel, f"❌ Erro ao capturar tela: `{str(e)}`")
        return

    # 3. Comandos rápidos de controle do PC (/bloquear, /suspender, /desligar, /cancelardesligar)
    cmd_lower = prompt.strip().lower()
    if cmd_lower in ["/bloquear", "/lock"]:
        if not node_manager.is_connected:
            await send_channel_message(user_id, channel, "⚠️ *Seu PC está offline no momento!*\n\nO worker local não está conectado à VPS.")
            return
        pc_res = await node_manager.execute_on_pc("manage_pc_power", {"power_action": "lock"})
        res_data = json.loads(pc_res) if isinstance(pc_res, str) else pc_res
        await send_channel_message(user_id, channel, res_data.get("message", "🔒 Tela do Windows bloqueada!"))
        return

    if cmd_lower in ["/suspender", "/dormir", "/sleep"]:
        if not node_manager.is_connected:
            await send_channel_message(user_id, channel, "⚠️ *Seu PC está offline no momento!*\n\nO worker local não está conectado à VPS.")
            return
        pc_res = await node_manager.execute_on_pc("manage_pc_power", {"power_action": "suspend"})
        res_data = json.loads(pc_res) if isinstance(pc_res, str) else pc_res
        await send_channel_message(user_id, channel, res_data.get("message", "🌙 PC entrando em repouso!"))
        return

    if cmd_lower in ["/cancelardesligar", "/cancelar_desligar", "/abort_shutdown"]:
        if not node_manager.is_connected:
            await send_channel_message(user_id, channel, "⚠️ *Seu PC está offline no momento!*")
            return
        pc_res = await node_manager.execute_on_pc("manage_pc_power", {"power_action": "cancel_shutdown"})
        res_data = json.loads(pc_res) if isinstance(pc_res, str) else pc_res
        await send_channel_message(user_id, channel, res_data.get("message", "✅ Desligamento cancelado com sucesso no Windows!"))
        return

    if cmd_lower.startswith(("/desligar", "/shutdown")):
        if not node_manager.is_connected:
            await send_channel_message(user_id, channel, "⚠️ *Seu PC está offline no momento!*")
            return
        parts = cmd_lower.split()
        minutes = 0
        if len(parts) > 1 and parts[1].isdigit():
            minutes = int(parts[1])
        pc_res = await node_manager.execute_on_pc("manage_pc_power", {"power_action": "shutdown", "timer_minutes": minutes})
        res_data = json.loads(pc_res) if isinstance(pc_res, str) else pc_res
        await send_channel_message(user_id, channel, res_data.get("message", "🛑 Comando de desligamento enviado."))
        return

    # 4. Se JÁ HOUVER uma tarefa ativa para este usuário
    if task_manager.is_busy(user_id):
        # A) Pergunta de status (ex: "como tá?", "status", "tá em que parte?", "falta muito?")
        if task_manager.is_status_query(prompt):
            status_reply = task_manager.build_status_response(user_id)
            await send_channel_message(user_id, channel, status_reply)
            return

        # B) Pedido de cancelamento (ex: "cancela", "para tudo", "abortar")
        if task_manager.is_cancel_query(prompt):
            cancelled = task_manager.cancel_task(user_id)
            if cancelled:
                cancel_reply = "🛑 *Parado, meu consagrado!* Cancelei a tarefa em andamento a seu pedido. Pode mandar a próxima missão quando quiser!"
            else:
                cancel_reply = "Não encontrei nenhuma tarefa rodando pra cancelar agora, chefe."
            await send_channel_message(user_id, channel, cancel_reply)
            return

        # C) Nova instrução enviada no meio do processo
        current_task = task_manager.get_task(user_id)
        elapsed = int(time.time() - current_task.started_at) if current_task else 0
        busy_reply = (
            f"⏳ *Opa, segura a emoção aí, chefe!*\n\n"
            f"Eu ainda tô no meio da tarefa anterior: *'{current_task.current_step if current_task else 'processando...'}'* (rodando há {elapsed}s).\n\n"
            f"Para não embolar o meio de campo, espera eu terminar essa rapidinho ou manda um *'cancela'* se quiser que eu aborte ela agora pra pegar a nova!"
        )
        await send_channel_message(user_id, channel, busy_reply)
        return

    # 3. Registra nova tarefa no TaskManager
    task_manager.start_task(user_id=user_id, prompt=prompt, channel=channel, task=asyncio.current_task())

    # Callback de notificação de progresso passo a passo
    async def on_step_notification(step_title: str, informal_message: Optional[str] = None):
        task_manager.update_step(user_id, step_title)
        if informal_message:
            await send_channel_message(user_id, channel, informal_message)

    try:
        reply = await run_agent_loop(
            user_prompt=prompt,
            user_id=user_id,
            channel=channel,
            on_step=on_step_notification
        )
        # Devolve a resposta final completa
        await send_channel_message(user_id, channel, reply)
    except asyncio.CancelledError:
        logger.info(f"Tarefa do usuário {user_id} cancelada com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao processar solicitação: {e}")
        err_msg = f"❌ *Eita, deu um tropeço aqui, chefe:*\n_{str(e)}_\n\nTenta de novo ou me passa mais detalhes!"
        await send_channel_message(user_id, channel, err_msg)
    finally:
        task_manager.finish_task(user_id)
        logger.info(f"[Concluído] Processamento finalizado para {user_id} via {channel}.")

@app.get("/")
async def root():
    return {
        "status": "online",
        "agent": "DevOps & CLI Assistant (Hybrid Node)",
        "vps_workspace": str(settings.workspace_path),
        "pc_connected": node_manager.is_connected,
        "pc_info": node_manager.pc_info if node_manager.is_connected else None,
        "model": settings.LLM_MODEL
    }

@app.websocket("/ws/worker")
async def worker_websocket(websocket: WebSocket, token: str = Query(...)):
    """Canal seguro WebSocket para o Worker do computador pessoal (Windows)."""
    if token != settings.WORKER_SECRET:
        logger.warning(f"[WebSocket] Tentativa de conexão com token inválido.")
        await websocket.close(code=1008)
        return

    await websocket.accept()
    logger.info("[WebSocket] Conexão WebSocket aceita. Aguardando identificação...")

    try:
        init_data = await websocket.receive_json()
        client_info = init_data.get("info", {})
        node_manager.register_pc(websocket, client_info)

        # Notificação proativa de conexão do PC no WhatsApp
        for target_user in settings.allowed_users_set:
            user_jid = target_user if "@" in target_user else f"{target_user}@s.whatsapp.net"
            h_name = client_info.get("hostname", "Windows")
            os_desc = client_info.get("os", "Windows")
            msg_conn = f"🟢 *Seu PC Pessoal Conectou!* ({h_name} - {os_desc})\n\nO assistente agora tem controle total deste computador (execução local, prints e comandos)."
            asyncio.create_task(send_channel_message(user_jid, "whatsapp", msg_conn))

        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong", "time": time.time()})
                continue
            node_manager.handle_response(data)
    except WebSocketDisconnect:
        logger.info("[WebSocket] Worker do PC desconectou.")
    except Exception as e:
        logger.error(f"[WebSocket] Erro na comunicação com o worker: {e}")
    finally:
        was_connected = node_manager.is_connected
        node_manager.unregister_pc()
        if was_connected:
            for target_user in settings.allowed_users_set:
                user_jid = target_user if "@" in target_user else f"{target_user}@s.whatsapp.net"
                msg_disc = "🟡 *Seu PC Pessoal Desconectou ou Suspendeu.*\n\nO assistente continua ativo na nuvem pela VPS."
                asyncio.create_task(send_channel_message(user_jid, "whatsapp", msg_disc))

@app.post("/webhook/evolution")
async def evolution_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe eventos de mensagens da Evolution API (WhatsApp).
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid_json"}

    remote_jid, clean_number, text = extract_evolution_message(body)
    if not remote_jid or not text:
        return {"status": "ignored"}

    logger.info(f"[Webhook Evolution] Recebido de {clean_number} ({remote_jid}): {text[:50]}")

    # Verificação de segurança: Whitelist de Administradores ou Convidados de Mídia
    allowed = settings.allowed_users_set
    guests = settings.guest_users_set
    if allowed and (clean_number not in allowed and clean_number not in guests):
        logger.warning(f"[ACESSO BLOQUEADO WHATSAPP]: Número '{clean_number}' não autorizado.")
        return {"status": "unauthorized"}

    # Processa em background para responder imediatamente 200 OK ao webhook da Evolution
    background_tasks.add_task(process_user_request, remote_jid, "whatsapp", text)
    return {"status": "queued"}

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe eventos de mensagens do bot do Telegram.
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid_json"}

    chat_id, text = extract_telegram_message(body)
    if not chat_id or not text:
        return {"status": "ignored"}

    logger.info(f"[Webhook Telegram] Recebido do chat_id {chat_id}: {text[:50]}")

    # Verificação de segurança: Whitelist
    allowed = settings.allowed_users_set
    if allowed and chat_id not in allowed:
        logger.warning(f"[ACESSO BLOQUEADO TELEGRAM]: Chat ID '{chat_id}' não está em ALLOWED_USERS: {allowed}")
        return {"status": "unauthorized"}

    # Processa em background para liberar o webhook do Telegram
    background_tasks.add_task(process_user_request, chat_id, "telegram", text)
    return {"status": "queued"}

class DirectExecRequest(BaseModel):
    user_id: str = "cli_admin"
    prompt: str

@app.post("/execute")
async def direct_execute(req: DirectExecRequest, background_tasks: BackgroundTasks, x_api_key: str = Header(None)):
    """Endpoint direto para testes via curl / Postman."""
    if settings.EVOLUTION_API_KEY and x_api_key != settings.EVOLUTION_API_KEY:
        raise HTTPException(status_code=403, detail="Chave de API inválida.")
    
    reply = await run_agent_loop(user_prompt=req.prompt, user_id=req.user_id, channel="direct")
    return {"response": reply}

@app.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe eventos de push do GitHub e dispara o redeploy automático no Easypanel.

    Configuração no GitHub (Settings → Webhooks → Add webhook):
      Payload URL  : https://agent.phdev.top/webhook/github
      Content type : application/json
      Secret       : valor de GITHUB_WEBHOOK_SECRET no .env
      Events       : Just the push event
    """
    import hmac
    import hashlib

    # 1. Lê o corpo raw (necessário para validar a assinatura HMAC)
    body = await request.body()

    # 2. Valida assinatura HMAC-SHA256 do GitHub (X-Hub-Signature-256)
    secret = settings.GITHUB_WEBHOOK_SECRET
    if secret:
        sig_header = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig_header, expected):
            logger.warning("[GitHub Webhook] Assinatura inválida — requisição ignorada.")
            raise HTTPException(status_code=401, detail="Assinatura inválida.")

    # 3. Parseia o payload
    try:
        import json as _json
        payload = _json.loads(body)
    except Exception:
        return {"status": "ignored", "reason": "invalid_json"}

    event = request.headers.get("X-GitHub-Event", "")
    ref = payload.get("ref", "")
    repo_name = payload.get("repository", {}).get("full_name", "?")
    pusher = payload.get("pusher", {}).get("name", "?")
    commits = payload.get("commits", [])
    commit_msg = commits[0].get("message", "").splitlines()[0] if commits else ""

    logger.info(f"[GitHub Webhook] event={event} ref={ref} repo={repo_name} pusher={pusher}")

    # 4. Só age em push para a branch main/master
    if event != "push" or ref not in ("refs/heads/main", "refs/heads/master"):
        return {"status": "ignored", "reason": f"event={event} ref={ref}"}

    # 5. Dispara redeploy no Easypanel em background
    deploy_webhook = settings.EASYPANEL_DEPLOY_WEBHOOK
    if not deploy_webhook:
        logger.warning("[GitHub Webhook] EASYPANEL_DEPLOY_WEBHOOK não configurado — redeploy ignorado.")
        return {"status": "no_deploy_webhook"}

    async def _trigger_deploy():
        import httpx as _httpx
        logger.info(f"[GitHub Webhook] Disparando redeploy no Easypanel para '{repo_name}' (commit: {commit_msg!r})")
        try:
            async with _httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(deploy_webhook)
                logger.info(f"[GitHub Webhook] Easypanel respondeu: {resp.status_code}")
        except Exception as deploy_err:
            logger.error(f"[GitHub Webhook] Erro ao chamar deploy webhook: {deploy_err}")

    background_tasks.add_task(_trigger_deploy)
    logger.info(f"[GitHub Webhook] Redeploy agendado para '{repo_name}' — push de '{pusher}': {commit_msg!r}")
    return {"status": "deploy_triggered", "repo": repo_name, "commit": commit_msg}

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=False)
