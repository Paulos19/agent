from typing import Dict, List, Any

class ConversationMemory:
    """Gerencia a memória de conversas dos usuários em memória."""
    
    def __init__(self, max_history: int = 15):
        self.max_history = max_history
        self._conversations: Dict[str, List[Dict[str, Any]]] = {}

    def get_history(self, user_id: str) -> List[Dict[str, Any]]:
        return self._conversations.get(user_id, [])

    def add_message(self, user_id: str, message: Dict[str, Any]):
        if user_id not in self._conversations:
            self._conversations[user_id] = []
        self._conversations[user_id].append(message)
        
        # Limita o histórico para não estourar o limite de contexto
        if len(self._conversations[user_id]) > self.max_history * 2:
            # Mantém as mensagens mais recentes
            self._conversations[user_id] = self._conversations[user_id][-self.max_history * 2:]

    def clear(self, user_id: str):
        if user_id in self._conversations:
            del self._conversations[user_id]

memory = ConversationMemory()
