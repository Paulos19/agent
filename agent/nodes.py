import asyncio
import uuid
import logging
from typing import Optional, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger("assistente-nodes")

class NodeManager:
    """Gerencia a conexão WebSocket do computador pessoal (Worker Windows)."""

    def __init__(self):
        self.active_pc: Optional[WebSocket] = None
        self.pc_info: Dict[str, Any] = {}
        self.pending_calls: Dict[str, asyncio.Future] = {}
        self.progress_callbacks: Dict[str, Any] = {}

    def register_pc(self, websocket: WebSocket, info: Dict[str, Any]):
        self.active_pc = websocket
        self.pc_info = info
        logger.info(f"[NodeManager] PC Pessoal CONECTADO: {info.get('hostname')} ({info.get('os')})")

    def unregister_pc(self):
        self.active_pc = None
        self.pc_info = {}
        self.progress_callbacks.clear()
        # Cancela chamadas pendentes caso a conexão caia
        for call_id, future in self.pending_calls.items():
            if not future.done():
                future.set_result("[ERRO]: O computador pessoal desconectou durante a execução.")
        self.pending_calls.clear()
        logger.info("[NodeManager] PC Pessoal DESCONECTADO.")

    @property
    def is_connected(self) -> bool:
        return self.active_pc is not None

    def get_status_description(self) -> str:
        if self.is_connected:
            user = self.pc_info.get("user", "Usuario")
            hostname = self.pc_info.get("hostname", "PC-Windows")
            os_ver = self.pc_info.get("os", "Windows")
            return f"CONECTADO ({user}@{hostname}, OS: {os_ver})"
        return "DESCONECTADO (Offline)"

    def handle_response(self, data: Dict[str, Any]):
        """Recebe o retorno ou evento de progresso de uma ferramenta executada pelo PC."""
        call_id = data.get("id")
        msg_type = data.get("type")

        # Se for mensagem intermediária de progresso
        if msg_type == "progress":
            progress_msg = data.get("message", "")
            callback = self.progress_callbacks.get(call_id)
            if callback and progress_msg:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(progress_msg))
                    else:
                        callback(progress_msg)
                except Exception as e:
                    logger.error(f"[NodeManager] Erro no callback de progresso: {e}")
            return

        if call_id and call_id in self.pending_calls:
            self.progress_callbacks.pop(call_id, None)
            future = self.pending_calls.pop(call_id)
            if not future.done():
                result = data.get("result", "Sem retorno.")
                future.set_result(result)

    async def execute_on_pc(
        self,
        action: str,
        args: Dict[str, Any],
        timeout: int = 90,
        on_progress: Optional[Any] = None
    ) -> str:
        """Envia uma ordem para ser executada no PC pessoal via WebSocket."""
        if not self.is_connected or not self.active_pc:
            return "[ERRO]: O seu computador pessoal (Windows) está DESLIGADO ou DESCONECTADO no momento."

        call_id = f"call_{uuid.uuid4().hex[:8]}"
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.pending_calls[call_id] = future
        if on_progress:
            self.progress_callbacks[call_id] = on_progress

        payload = {
            "id": call_id,
            "action": action,
            "args": args
        }

        try:
            await self.active_pc.send_json(payload)
            result = await asyncio.wait_for(future, timeout=float(timeout))
            return result
        except asyncio.TimeoutError:
            self.pending_calls.pop(call_id, None)
            self.progress_callbacks.pop(call_id, None)
            return f"[ERRO]: O seu computador pessoal demorou mais de {timeout}s para responder e a tarefa expirou."
        except Exception as e:
            self.pending_calls.pop(call_id, None)
            self.progress_callbacks.pop(call_id, None)
            return f"[FALHA NA COMUNICAÇÃO COM O PC]: {str(e)}"

node_manager = NodeManager()
