import asyncio
import time
import logging
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
import uvicorn

from config import settings
from tools.scheduler import init_scheduler
from agent import run_agent_loop, memory, task_manager
from agent.nodes import node_manager
from channels import (
    extract_evolution_message,
    send_evolution_message,
    extract_telegram_message,
    send_telegram_message
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
    logger.info("====================================================")
    logger.info("   Assistente CLI / DevOps Agent Inicializado!      ")
    logger.info(f"   Workspace: {settings.workspace_path}")
    logger.info(f"   Usuários autorizados: {settings.allowed_users_set or 'TODOS (Atenção!)'}")
    logger.info("====================================================")
    yield
    logger.info("Encerrando assistente...")

app = FastAPI(title="Assistente CLI & DevOps Agent", lifespan=lifespan)

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
