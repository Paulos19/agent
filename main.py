import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header
from pydantic import BaseModel
import uvicorn

from config import settings
from tools.scheduler import init_scheduler
from agent import run_agent_loop, memory
from channels import (
    extract_evolution_message,
    send_evolution_message,
    extract_telegram_message,
    send_telegram_message
)

# Configuração de logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("assistente-cli")

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
    """Executa a solicitação do usuário em background e envia a resposta."""
    logger.info(f"[Iniciando Processamento] Usuário: {user_id} | Canal: {channel} | Prompt: {prompt[:60]}...")
    
    # Comandos especiais de manutenção de memória
    if prompt.strip().lower() in ["/limpar", "/reset", "/clear"]:
        memory.clear(user_id)
        msg_reset = "Memória da conversa resetada com sucesso."
        if channel == "whatsapp":
            await send_evolution_message(user_id, msg_reset)
        else:
            await send_telegram_message(user_id, msg_reset)
        return

    # Executa o loop do agente com o Gemini
    reply = await run_agent_loop(user_prompt=prompt, user_id=user_id, channel=channel)

    # Devolve a resposta no canal apropriado
    if channel == "whatsapp":
        await send_evolution_message(user_id, reply)
    elif channel == "telegram":
        await send_telegram_message(user_id, reply)
    
    logger.info(f"[Concluído] Resposta enviada para {user_id} via {channel}.")

@app.get("/")
async def root():
    return {
        "status": "online",
        "agent": "DevOps & CLI Assistant",
        "workspace": str(settings.workspace_path),
        "model": settings.GEMINI_MODEL
    }

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
