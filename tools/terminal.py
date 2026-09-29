import asyncio
import os
import platform
import sys
import re
import base64
from typing import Optional
from config import settings

async def execute_terminal_command(
    command: str,
    working_directory: Optional[str] = None,
    timeout: int = 90
) -> str:
    """
    Executa um comando de terminal (Bash no Linux/VPS ou PowerShell com EncodedCommand no Windows).
    
    Args:
        command: O comando a ser executado.
        working_directory: Opcional. Pasta onde o comando deve rodar. Por padrão, usa o workspace do agente.
        timeout: Tempo máximo em segundos antes de cancelar o comando (padrão: 90s).
    """
    cwd = working_directory or str(settings.workspace_path)
    try:
        if not os.path.exists(cwd):
            os.makedirs(cwd, exist_ok=True)
    except Exception:
        cwd = os.getcwd()

    is_windows = platform.system().lower() == "windows"

    try:
        if is_windows:
            # Converte ' && ' e ' || ' para ';' para total compatibilidade com PowerShell 5.1
            clean_cmd = command.strip()
            clean_cmd = re.sub(r'\s*&&\s*', '; ', clean_cmd)
            clean_cmd = re.sub(r'\s*\|\|\s*', '; ', clean_cmd)

            ps_script = (
                "$ProgressPreference = 'SilentlyContinue'\n"
                "$env:GIT_TERMINAL_PROMPT = '0'\n"
                "$env:GCM_INTERACTIVE = 'never'\n"
                f"{clean_cmd}"
            )
            encoded = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")

            process = await asyncio.create_subprocess_exec(
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-EncodedCommand", encoded,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
        else:
            # Usa bash no Linux (padrão em VPS / Easypanel)
            executable = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                executable=executable
            )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=float(timeout))
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            return f"[ERRO]: O comando excedeu o tempo limite de {timeout} segundos e foi abortado."

        out_decoded = stdout.decode("utf-8", errors="replace").strip()
        err_decoded = stderr.decode("utf-8", errors="replace").strip()

        # Remove ruído do CLIXML do PowerShell se presente
        if "#< CLIXML" in err_decoded:
            err_decoded = re.sub(r'#< CLIXML.*?</Objs>', '', err_decoded, flags=re.DOTALL).strip()

        result_lines = []
        result_lines.append(f"[Exit Code]: {process.returncode}")
        
        if out_decoded:
            result_lines.append(f"[STDOUT]:\n{out_decoded}")
        if err_decoded:
            result_lines.append(f"[STDERR]:\n{err_decoded}")

        if not out_decoded and not err_decoded:
            result_lines.append("[Status]: Comando executado com sucesso (sem saída no terminal).")

        return "\n\n".join(result_lines)

    except Exception as e:
        return f"[FALHA NA EXECUÇÃO]: {str(e)}"
