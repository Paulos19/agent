import os
import json
import httpx
from typing import Optional, Dict, Any
from config import settings

GITHUB_API_BASE = "https://api.github.com"

def _get_headers() -> Dict[str, str]:
    token = settings.GITHUB_TOKEN or os.getenv("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "DevOps-Assistant-Paulos19"
    }
    if token:
        headers["Authorization"] = f"token {token.strip()}"
    return headers

async def create_github_repository(
    name: str,
    description: str = "",
    private: bool = False,
    auto_init: bool = False
) -> str:
    """
    Cria um novo repositório na conta do GitHub do usuário via API.
    """
    token = settings.GITHUB_TOKEN or os.getenv("GITHUB_TOKEN", "")
    if not token:
        return "[ERRO GITHUB]: GITHUB_TOKEN não configurado no .env."

    url = f"{GITHUB_API_BASE}/user/repos"
    payload = {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": auto_init
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=_get_headers(), json=payload)
            if resp.status_code in [200, 201]:
                data = resp.json()
                repo_url = data.get("html_url")
                clone_url = data.get("clone_url")
                return (
                    f"✔ [REPOSITÓRIO CRIADO NO GITHUB]:\n"
                    f"- Nome: {name}\n"
                    f"- URL: {repo_url}\n"
                    f"- Clone URL: {clone_url}\n"
                    f"- Visibilidade: {'Privado' if private else 'Público'}\n"
                    f"Repositório pronto para receber o código através de 'push_project_to_github'."
                )
            elif resp.status_code == 422:
                user = settings.GITHUB_USERNAME or "Paulos19"
                repo_url = f"https://github.com/{user}/{name}"
                return (
                    f"ℹ [REPOSITÓRIO JÁ EXISTE NO GITHUB]:\n"
                    f"- URL: {repo_url}\n"
                    f"Você pode enviar os commits diretamente para ele."
                )
            else:
                return f"[ERRO GITHUB {resp.status_code}]: {resp.text}"
    except Exception as e:
        return f"[ERRO AO CRIAR REPOSITÓRIO GITHUB]: {str(e)}"

async def push_project_to_github(
    repo_path: str,
    repo_name: str,
    commit_message: str = "feat: initial project commit by devops agent",
    branch: str = "main",
    target: str = "pc"
) -> str:
    """
    Inicializa git (se necessário), comita todos os arquivos e faz push para o GitHub usando o token configurado.
    """
    token = settings.GITHUB_TOKEN or os.getenv("GITHUB_TOKEN", "")
    user = settings.GITHUB_USERNAME or "Paulos19"

    if not token:
        return "[ERRO GITHUB]: GITHUB_TOKEN não configurado no .env."

    auth_remote_url = f"https://{token}@github.com/{user}/{repo_name}.git"
    public_url = f"https://github.com/{user}/{repo_name}"

    # Sequência de comandos git compatível com PowerShell (PC) e Bash (VPS)
    if target == "pc":
        from agent.nodes import node_manager
        git_cmds = (
            f'Set-Location -Path "{repo_path}"; '
            f'git init; '
            f'git config user.name "Paulo Henrique"; '
            f'git config user.email "paulohenrique.012araujo@gmail.com"; '
            f'git config credential.helper ""; '
            f'$env:GIT_TERMINAL_PROMPT="0"; '
            f'$env:GCM_INTERACTIVE="never"; '
            f'git add .; '
            f'git commit -m "{commit_message}"; '
            f'git branch -M {branch}; '
            f'if (git remote | Select-String -Pattern "^origin$") {{ '
            f'    git remote set-url origin "{auth_remote_url}"; '
            f'}} else {{ '
            f'    git remote add origin "{auth_remote_url}"; '
            f'}}; '
            f'git push -u origin {branch} --force'
        )
        if not node_manager.is_connected:
            return "[ERRO]: O PC local está desconectado. Inicie o worker.py no computador."
        res = await node_manager.execute_on_pc("execute_terminal_command", {"command": git_cmds})
        return (
            f"🚀 [PUSH PARA GITHUB REALIZADO]:\n"
            f"- Repositório: {public_url}\n"
            f"- Branch: {branch}\n"
            f"- Detalhes da Execução no PC:\n{res}"
        )
    else:
        # Execução na VPS
        import subprocess
        try:
            full_cmd = (
                f'cd "{repo_path}" && '
                f'git init && '
                f'git config user.name "Paulo Henrique" && '
                f'git config user.email "paulohenrique.012araujo@gmail.com" && '
                f'export GIT_TERMINAL_PROMPT=0 && '
                f'git add . && '
                f'git commit -m "{commit_message}" || true && '
                f'git branch -M {branch} && '
                f'git remote set-url origin "{auth_remote_url}" 2>/dev/null || git remote add origin "{auth_remote_url}" && '
                f'git push -u origin {branch} --force'
            )
            p = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=120)
            return (
                f"🚀 [PUSH PARA GITHUB REALIZADO NA VPS]:\n"
                f"- Repositório: {public_url}\n"
                f"- Branch: {branch}\n"
                f"- Exit Code: {p.returncode}\n"
                f"- Saída: {p.stdout}\n"
                f"- Erros: {p.stderr}"
            )
        except Exception as e:
            return f"[ERRO AO EXECUTAR PUSH NA VPS]: {str(e)}"
