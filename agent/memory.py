from typing import Dict, List, Any

class ConversationMemory:
    """Gerencia a memória de conversas dos usuários em memória com limite seguro de tokens."""
    
    def __init__(self, max_history: int = 6):
        self.max_history = max_history
        self._conversations: Dict[str, List[Dict[str, Any]]] = {}

    def get_history(self, user_id: str) -> List[Dict[str, Any]]:
        return self._conversations.get(user_id, [])

    def add_message(self, user_id: str, message: Dict[str, Any]):
        if user_id not in self._conversations:
            self._conversations[user_id] = []

        # Faz uma cópia para não alterar o objeto original
        msg_copy = dict(message)
        content = msg_copy.get("content")
        
        # Compacta mensagens muito longas no histórico para evitar estourar o limite de tokens em mensagens seguintes
        if isinstance(content, str) and len(content) > 2500:
            msg_copy["content"] = content[:2500] + "\n\n[...conteúdo extenso resumido para preservar contexto...]"

        self._conversations[user_id].append(msg_copy)
        
        # Mantém apenas os últimos turnos mais recentes
        max_items = self.max_history * 2
        if len(self._conversations[user_id]) > max_items:
            self._conversations[user_id] = self._conversations[user_id][-max_items:]

    def clear(self, user_id: str):
        if user_id in self._conversations:
            del self._conversations[user_id]

memory = ConversationMemory()
