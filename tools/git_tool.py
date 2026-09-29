import os
import platform
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
    Garante autenticação com token para evitar travamentos de prompt de credenciais.
    
    Args:
        repo_path: Caminho da pasta do repositório (ex: 'D:\\testes\\phdev' ou '.').
        message: Mensagem descritiva do commit.
        branch: Nome da branch de destino (padrão: 'main').
    """
    from config import settings
    token = settings.GITHUB_TOKEN or os.getenv("GITHUB_TOKEN", "")
    clean_message = message.replace('"', '\\"')
    is_windows = platform.system().lower() == "windows"

    if is_windows:
        commands = [
            '$ProgressPreference = "SilentlyContinue"',
            '$env:GIT_TERMINAL_PROMPT = "0"',
            '$env:GCM_INTERACTIVE = "never"',
            'git config user.name "Paulo Henrique"',
            'git config user.email "paulohenrique.012araujo@gmail.com"',
            'git config credential.helper ""',
            'git add -A',
            f'git commit -m "{clean_message}" 2>$null; if ($LASTEXITCODE -ne 0) {{ Write-Output "Nenhuma nova alteracao detectada para commitar" }}'
        ]

        if token:
            token_script = (
                f'try {{ '
                f'  $url = git remote get-url origin 2>$null; '
                f'  if ($url -and ($url -match "github\\.com") -and -not ($url -match "{token}")) {{ '
                f'    $authUrl = $url -replace "https://(?:[^@]+@)?github\\.com", "https://{token}@github.com"; '
                f'    git remote set-url origin $authUrl '
                f'  }} '
                f'}} catch {{}}'
            )
            commands.append(token_script)

        commands.append(f'git branch -M {branch}')
        commands.append(f'git push origin {branch}')
        cmd = ";\n".join(commands)
    else:
        commands = [
            'export GIT_TERMINAL_PROMPT=0',
            'git config user.name "Paulo Henrique"',
            'git config user.email "paulohenrique.012araujo@gmail.com"',
            'git config credential.helper ""',
            'git add -A',
            f'git commit -m "{clean_message}" || echo "Sem novas alteracoes"'
        ]
        if token:
            commands.append(
                f'CURRENT_URL=$(git remote get-url origin 2>/dev/null || true); '
                f'if [[ "$CURRENT_URL" =~ github\\.com ]] && [[ ! "$CURRENT_URL" =~ "{token}" ]]; then '
                f'  AUTH_URL=$(echo "$CURRENT_URL" | sed "s|https://.*@github\\.com|https://{token}@github.com|" | sed "s|https://github\\.com|https://{token}@github.com|"); '
                f'  git remote set-url origin "$AUTH_URL" 2>/dev/null || true; '
                f'fi'
            )
        commands.append(f'git branch -M {branch}')
        commands.append(f'git push origin {branch}')
        cmd = " && ".join(commands)

    result = await execute_terminal_command(cmd, working_directory=repo_path, timeout=120)
    
    if "[Exit Code]: 0" in result or "Everything up-to-date" in result or "branch" in result or "-> main" in result:
        return f"[GIT SUCESSO]: Alterações commitadas e enviadas para 'origin {branch}'!\n\n{result}"
    return f"[GIT ATENÇÃO]:\n{result}"

async def git_pull(repo_path: str = ".", branch: str = "main") -> str:
    """Puxa as últimas atualizações do repositório remoto."""
    cmd = f"git pull origin {branch}"
    return await execute_terminal_command(cmd, working_directory=repo_path, timeout=60)
