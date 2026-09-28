import os
import asyncio
from typing import Optional
from .terminal import execute_terminal_command

async def git_status(repo_path: str = ".") -> str:
    """Retorna o status atual do repositório Git (arquivos modificados, branch atual)."""
    cmd = "git status"
    return await execute_terminal_command(cmd, working_directory=repo_path)

async def git_diff(repo_path: str = ".") -> str:
    """Mostra as diferenças não commitadas nos arquivos do repositório."""
    cmd = "git diff"
    return await execute_terminal_command(cmd, working_directory=repo_path)

async def git_commit_and_push(
    repo_path: str,
    message: str,
    branch: str = "main"
) -> str:
    """
    Executa o ciclo completo de Git: adiciona todas as alterações, faz o commit e envia (push) para o remoto.
    
    Args:
        repo_path: Caminho da pasta do repositório (ex: 'D:\\testes\\phdev' ou '.').
        message: Mensagem descritiva do commit.
        branch: Nome da branch de destino (padrão: 'main').
    """
    # Escapa aspas na mensagem
    clean_message = message.replace('"', '\\"')

    # Executa git add, commit e push em sequência
    cmd = f'git add . && git commit -m "{clean_message}" && git push origin {branch}'
    result = await execute_terminal_command(cmd, working_directory=repo_path, timeout=120)
    
    if "[Exit Code]: 0" in result or "Everything up-to-date" in result or "branch" in result:
        return f"✔ [GIT SUCESSO]: Alterações commitadas e enviadas para 'origin {branch}'!\n\n{result}"
    return f"⚠ [GIT ATENÇÃO]:\n{result}"

async def git_pull(repo_path: str = ".", branch: str = "main") -> str:
    """Puxa as últimas atualizações do repositório remoto."""
    cmd = f"git pull origin {branch}"
    return await execute_terminal_command(cmd, working_directory=repo_path, timeout=60)
