import asyncio
import time
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

    # RFC 5987 / 6266 encoding para cabeçalho de download
    safe_ascii_name = re.sub(r'[^\w\s\.-]', '_', file_path.name)
    quoted_name = urllib.parse.quote(file_path.name)
    content_disposition = f'attachment; filename="{safe_ascii_name}"; filename*=UTF-8\'\'{quoted_name}'

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
@app.get("/d/{token}/{filename}")
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

        # Nome seguro para cabeçalhos HTTP
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

        safe_ascii_name = re.sub(r'[^\w\s\.-]', '_', actual_filename).strip()
        if not safe_ascii_name:
            safe_ascii_name = f"download_{token}{ext}"
        quoted_name = urllib.parse.quote(actual_filename)
        content_disposition = f'attachment; filename="{safe_ascii_name}"; filename*=UTF-8\'\'{quoted_name}'

        return FileResponse(
            path=str(file_path.resolve()),
            media_type=mime,
            filename=safe_ascii_name,
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

async def process_user_request(user_id: str, channel: str, prompt: str):
    """Executa a solicitação do usuário com suporte a streaming de progresso e concorrência."""
    logger.info(f"[Iniciando Processamento] Usuário: {user_id} | Canal: {channel} | Prompt: {prompt[:60]}...")
    
    # 1. Comandos especiais de manutenção de memória
    if prompt.strip().lower() in ["/limpar", "/reset", "/clear"]:
        memory.clear(user_id)
        task_manager.finish_task(user_id)
        msg_reset = "🧹 Memória da conversa e tarefas ativas resetadas com sucesso, chefe! Começando do zero."
        await send_channel_message(user_id, channel, msg_reset)
        return

    # 2. Se JÁ HOUVER uma tarefa ativa para este usuário
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
        node_manager.unregister_pc()

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

    # Verificação de segurança: Whitelist
    allowed = settings.allowed_users_set
    if allowed and clean_number not in allowed:
        logger.warning(f"[ACESSO BLOQUEADO WHATSAPP]: Número '{clean_number}' não está em ALLOWED_USERS: {allowed}")
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

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=False)
