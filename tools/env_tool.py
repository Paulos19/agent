import os
import re
from pathlib import Path
from typing import Optional, Dict, List
from config import settings

def _load_env_file() -> Dict[str, str]:
    """Lê o arquivo .env da raiz do projeto ou variáveis do sistema."""
    env_vars = {}
    
    # Procura arquivo .env no diretório atual, pai ou na raiz do app
    candidates = [
        Path(".env"),
        Path(__file__).parent.parent / ".env",
        Path("/app/.env"),
        Path(os.getcwd()) / ".env"
    ]
    
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            try:
                with open(candidate, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            env_vars[k.strip()] = v.strip().strip("'\"")
            except Exception:
                pass
            break

    # Mescla com variáveis do sistema
    for k, v in os.environ.items():
        if k not in env_vars:
            env_vars[k] = v

    return env_vars

async def get_vps_env_var(key: Optional[str] = None) -> str:
    """
    Busca variáveis de ambiente e chaves reais no .env da VPS.
    
    Args:
        key: Opcional. Nome exato da variável (ex: 'DATABASE_URL', 'GITHUB_TOKEN', 'EASYPANEL_API_KEY').
             Se fornecido, retorna o valor real para uso em configurações.
             Se omitido, lista todas as chaves existentes com valores mascarados.
    """
    env_vars = _load_env_file()

    if key:
        clean_key = key.strip()
        val = env_vars.get(clean_key) or os.getenv(clean_key)
        if val is not None:
            return f"[ENV VPS]: {clean_key} = {val}"
        
        # Busca aproximada caso não seja exato
        matches = [k for k in env_vars.keys() if clean_key.lower() in k.lower()]
        if matches:
            return f"[ENV VPS]: A chave '{clean_key}' nao foi encontrada exatamente. Chaves semelhantes encontradas: {', '.join(matches)}"
        return f"[ENV VPS]: A chave '{clean_key}' nao existe no .env da VPS."

    # Se key for None, lista todas as chaves configuradas com valores sensíveis mascarados
    lines = ["🔑 [VARIÁVEIS DE AMBIENTE DISPONÍVEIS NA VPS]:"]
    
    # Ordena as chaves
    sorted_keys = sorted(env_vars.keys())
    for k in sorted_keys:
        v = env_vars[k]
        # Mascara segredos para visualização geral
        if any(secret_word in k.lower() for secret_word in ["key", "token", "pass", "secret", "auth", "pwd"]):
            if len(v) > 8:
                masked = f"{v[:4]}...{v[-4:]}"
            else:
                masked = "********"
        else:
            masked = v if len(v) <= 60 else f"{v[:57]}..."
        lines.append(f"• {k} = {masked}")

    lines.append("\n💡 Dica: Chame 'get_vps_env_var(key=\"NOME_DA_VARIAVEL\")' para obter o valor real completo.")
    return "\n".join(lines)
