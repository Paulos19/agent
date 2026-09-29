import asyncio
import time
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

@dataclass
class ActiveTask:
    user_id: str
    channel: str
    original_prompt: str
    started_at: float = field(default_factory=time.time)
    current_step: str = "Iniciando processamento da solicitação..."
    step_history: List[str] = field(default_factory=list)
    asyncio_task: Optional[asyncio.Task] = None
    is_cancelled: bool = False

class TaskManager:
    """
    Gerencia o ciclo de vida e estado das tarefas ativas por usuário,
    permitindo streaming de progresso em tempo real e resposta a perguntas
    do usuário durante a execução sem concorrência ou conflitos.
    """

    def __init__(self):
        self._active_tasks: Dict[str, ActiveTask] = {}

    def start_task(self, user_id: str, prompt: str, channel: str, task: Optional[asyncio.Task] = None) -> ActiveTask:
        active = ActiveTask(
            user_id=user_id,
            channel=channel,
            original_prompt=prompt,
            asyncio_task=task
        )
        self._active_tasks[user_id] = active
        return active

    def set_asyncio_task(self, user_id: str, task: asyncio.Task):
        if user_id in self._active_tasks:
            self._active_tasks[user_id].asyncio_task = task

    def is_busy(self, user_id: str) -> bool:
        task = self._active_tasks.get(user_id)
        return task is not None and not task.is_cancelled

    def get_task(self, user_id: str) -> Optional[ActiveTask]:
        return self._active_tasks.get(user_id)

    def update_step(self, user_id: str, step_title: str, detail: Optional[str] = None) -> Optional[ActiveTask]:
        task = self._active_tasks.get(user_id)
        if not task:
            return None
        
        task.current_step = step_title
        entry = f"{step_title} ({detail})" if detail else step_title
        if entry not in task.step_history:
            task.step_history.append(entry)
        return task

    def finish_task(self, user_id: str):
        self._active_tasks.pop(user_id, None)

    def cancel_task(self, user_id: str) -> bool:
        task = self._active_tasks.get(user_id)
        if not task:
            return False
        
        task.is_cancelled = True
        if task.asyncio_task and not task.asyncio_task.done():
            task.asyncio_task.cancel()
        self._active_tasks.pop(user_id, None)
        return True

    @staticmethod
    def is_status_query(text: str) -> bool:
        """Detecta se o usuário está perguntando sobre o andamento/status da tarefa."""
        clean = text.lower().strip()
        patterns = [
            r"\b(como\s+t[aá]|como\s+est[aá]|e\s+a[ií]|e\s+ai)\b",
            r"\b(status|progresso|andamento)\b",
            r"\b(em\s+que\s+(parte|p[eé])\s+t[aá])\b",
            r"\b(t[aá]\s+em\s+que\s+parte)\b",
            r"\b(falta\s+muito|demora\s+muito|quanto\s+tempo)\b",
            r"\b(t[aá]\s+rodando|t[aá]\s+vivo|travou)\b",
            r"\b(o\s+que\s+voc[eê]\s+t[aá]\s+fazendo)\b",
            r"^\?+$"
        ]
        return any(re.search(p, clean) for p in patterns)

    @staticmethod
    def is_cancel_query(text: str) -> bool:
        """Detecta se o usuário pediu para cancelar ou parar o processo."""
        clean = text.lower().strip()
        patterns = [
            r"^\b(cancela|cancelar|cancela\s+tudo|cancelar\s+tudo)\b",
            r"^\b(para|parar|para\s+tudo|parar\s+tudo)\b",
            r"^\b(abortar|interromper|stop)\b",
            r"^/cancel\b"
        ]
        return any(re.search(p, clean) for p in patterns)

    def build_status_response(self, user_id: str) -> str:
        """Monta uma resposta humana, irreverente e calma com o status atual da tarefa."""
        task = self._active_tasks.get(user_id)
        if not task:
            return "Tô de boa por aqui, sem nenhuma tarefa rodando no momento! O que manda, chefe?"

        elapsed = int(time.time() - task.started_at)
        mins = elapsed // 60
        secs = elapsed % 60
        time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

        history_lines = ""
        if task.step_history:
            # Pega as últimas 3 etapas concluídas
            recent = task.step_history[-4:-1] if len(task.step_history) > 1 else []
            if recent:
                items = "\n".join(f"  ✓ _{h}_" for h in recent)
                history_lines = f"\n\n*Etapas anteriores já concluídas:*\n{items}"

        reply = (
            f"🧘‍♂️ *Calma o coração, meu consagrado! Tô a todo vapor aqui.*\n\n"
            f"⏱️ *Tempo decorrido:* {time_str}\n"
            f"📌 *Etapa atual:* {task.current_step}"
            f"{history_lines}\n\n"
            f"_Fica sussa que já já te chamo com o resultado final! Se quiser parar tudo, só mandar *'cancela'*._"
        )
        return reply

task_manager = TaskManager()
