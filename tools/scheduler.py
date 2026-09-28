import uuid
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger

# Instância global do agendador assíncrono
scheduler = AsyncIOScheduler()
_task_callback: Optional[Callable] = None

def init_scheduler(callback: Callable):
    """Inicializa o callback que será executado quando uma tarefa agendada disparar."""
    global _task_callback
    _task_callback = callback
    if not scheduler.running:
        scheduler.start()

async def _scheduled_job_runner(job_id: str, prompt: str, user_id: str, channel: str):
    """Executado quando o timer/cron dispara."""
    if _task_callback:
        await _task_callback(
            user_id=user_id,
            channel=channel,
            prompt=f"[TAREFA AGENDADA DISPARADA]: {prompt}"
        )

def schedule_timer(
    delay_minutes: int,
    task_description: str,
    user_id: str = "",
    channel: str = "whatsapp"
) -> str:
    """
    Agenda uma tarefa para rodar uma única vez após uma quantidade de minutos.
    
    Args:
        delay_minutes: Minutos a partir de agora para disparar a tarefa.
        task_description: O que o agente deve fazer ao disparar.
        user_id: ID do usuário solicitante (para devolver a resposta).
        channel: 'whatsapp' ou 'telegram'.
    """
    run_date = datetime.now() + timedelta(minutes=delay_minutes)
    job_id = f"timer_{uuid.uuid4().hex[:8]}"

    scheduler.add_job(
        _scheduled_job_runner,
        trigger=DateTrigger(run_date=run_date),
        args=[job_id, task_description, user_id, channel],
        id=job_id,
        name=task_description[:30],
        replace_existing=True
    )

    return f"[AGENDAMENTO CRIADO]: ID '{job_id}' programado para disparar em {run_date.strftime('%d/%m/%Y às %H:%M:%S')}."

def schedule_cron(
    cron_expression: str,
    task_description: str,
    user_id: str = "",
    channel: str = "whatsapp"
) -> str:
    """
    Agenda uma tarefa recorrente usando formato padrão cron (minuto hora dia mês dia-da-semana).
    Exemplo: '0 8 * * *' para todo dia às 08:00.
    
    Args:
        cron_expression: Expressão cron de 5 partes.
        task_description: O que o agente deve fazer periodicamente.
        user_id: ID do usuário solicitante.
        channel: 'whatsapp' ou 'telegram'.
    """
    parts = cron_expression.strip().split()
    if len(parts) != 5:
        return "[ERRO]: Expressão cron inválida. Use o formato padrão de 5 campos (min hora dia mês dia-da-semana)."

    minute, hour, day, month, day_of_week = parts
    job_id = f"cron_{uuid.uuid4().hex[:8]}"

    try:
        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week
        )
        scheduler.add_job(
            _scheduled_job_runner,
            trigger=trigger,
            args=[job_id, task_description, user_id, channel],
            id=job_id,
            name=task_description[:30],
            replace_existing=True
        )
        return f"[RECORRÊNCIA CRIADA]: ID '{job_id}' com cron '{cron_expression}' para a tarefa: '{task_description}'."
    except Exception as e:
        return f"[ERRO AO CRIAR CRON]: {str(e)}"

def list_scheduled_jobs() -> str:
    """Lista todas as tarefas atualmente agendadas."""
    jobs = scheduler.get_jobs()
    if not jobs:
        return "Nenhuma tarefa agendada no momento."

    lines = ["Tarefas ativas no agendador:"]
    for j in jobs:
        next_run = j.next_run_time.strftime('%d/%m/%Y %H:%M:%S') if j.next_run_time else "Pausado"
        lines.append(f"- ID: {j.id} | Próxima execução: {next_run} | Descrição: {j.name}")
    return "\n".join(lines)

def remove_scheduled_job(job_id: str) -> str:
    """Remove uma tarefa agendada pelo ID."""
    try:
        scheduler.remove_job(job_id)
        return f"[SUCESSO]: Tarefa '{job_id}' removida com sucesso."
    except Exception:
        return f"[ERRO]: Não foi encontrada tarefa com o ID '{job_id}'."
