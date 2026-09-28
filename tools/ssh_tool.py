import os
import asyncio
import paramiko
from typing import Optional
from config import settings

def _run_ssh_sync(
    command: str,
    host: str,
    port: int,
    user: str,
    password: Optional[str] = None,
    key_path: Optional[str] = None,
    timeout: int = 60
) -> str:
    """Execução síncrona do Paramiko rodada em thread pool para não travar o loop assíncrono."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": user,
            "timeout": 15.0
        }

        if password:
            connect_kwargs["password"] = password

        if key_path and os.path.exists(key_path):
            connect_kwargs["key_filename"] = key_path

        client.connect(**connect_kwargs)

        stdin, stdout, stderr = client.exec_command(command, timeout=float(timeout))
        exit_code = stdout.channel.recv_exit_status()

        out_decoded = stdout.read().decode("utf-8", errors="replace").strip()
        err_decoded = stderr.read().decode("utf-8", errors="replace").strip()

        result = [f"[SSH - Exit Code]: {exit_code}"]
        if out_decoded:
            result.append(f"[STDOUT]:\n{out_decoded}")
        if err_decoded:
            result.append(f"[STDERR]:\n{err_decoded}")
        if not out_decoded and not err_decoded:
            result.append("[Status]: Comando SSH executado com sucesso sem saída de texto.")

        return "\n\n".join(result)

    except Exception as e:
        return f"[ERRO CONEXÃO SSH]: {str(e)}"
    finally:
        try:
            client.close()
        except Exception:
            pass

async def execute_ssh_command(
    command: str,
    host: Optional[str] = None,
    port: int = 22,
    user: Optional[str] = None,
    password: Optional[str] = None,
    key_path: Optional[str] = None,
    timeout: int = 60
) -> str:
    """
    Executa um comando remotamente na VPS hospedeira via SSH com senha ou chave.
    Útil para comandos Docker no host, scripts de manutenção, reinicialização, etc.
    """
    ssh_host = host or getattr(settings, "VPS_SSH_HOST", None) or os.getenv("VPS_SSH_HOST")
    ssh_user = user or getattr(settings, "VPS_SSH_USER", "root") or os.getenv("VPS_SSH_USER", "root")
    ssh_pass = password or getattr(settings, "VPS_SSH_PASS", None) or os.getenv("VPS_SSH_PASS")
    ssh_port = port or int(getattr(settings, "VPS_SSH_PORT", 22) or os.getenv("VPS_SSH_PORT", 22))
    ssh_key = key_path or getattr(settings, "VPS_SSH_KEY", None) or os.getenv("VPS_SSH_KEY")

    if not ssh_host:
        return (
            "[ERRO SSH]: Host da VPS não informado. "
            "Passe o parâmetro 'host' ou configure VPS_SSH_HOST no .env."
        )

    # Executa em uma thread separada para não bloquear o event loop assíncrono
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        _run_ssh_sync,
        command,
        ssh_host,
        ssh_port,
        ssh_user,
        ssh_pass,
        ssh_key,
        timeout
    )
