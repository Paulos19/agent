import asyncio
import json
import os
import platform
import sys
import getpass
from pathlib import Path
import websockets
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from dotenv import load_dotenv

load_dotenv()

console = Console()

# URL e token do WebSocket da VPS
VPS_WS_URL = os.getenv("VPS_WS_URL", "wss://agent.phdev.top/ws/worker")
WORKER_SECRET = os.getenv("WORKER_SECRET", "devops_secret_token_123")

async def run_local_command(command: str, working_directory: str = None, timeout: int = 90) -> str:
    """Executa o comando localmente no Windows (PowerShell/CMD)."""
    cwd = working_directory or os.getcwd()
    if not os.path.exists(cwd):
        os.makedirs(cwd, exist_ok=True)

    cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{command}"'
    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=float(timeout))
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            return f"[ERRO]: O comando local excedeu o tempo limite de {timeout}s e foi cancelado."

        out_str = stdout.decode("utf-8", errors="replace").strip()
        err_str = stderr.decode("utf-8", errors="replace").strip()

        result = []
        result.append(f"[Exit Code]: {process.returncode}")
        if out_str:
            result.append(f"[STDOUT]:\n{out_str}")
        if err_str:
            result.append(f"[STDERR]:\n{err_str}")
        if not out_str and not err_str:
            result.append("[Status]: Comando executado com sucesso (sem retorno de texto).")

        return "\n\n".join(result)
    except Exception as e:
        return f"[ERRO LOCAL]: {str(e)}"

def local_list_directory(path: str = ".") -> str:
    """Lista pasta local no PC."""
    target = Path(os.path.expanduser(path)).resolve()
    if not target.exists():
        return f"[ERRO]: O caminho '{path}' não existe no PC."
    if not target.is_dir():
        return f"[ERRO]: '{path}' não é um diretório."

    try:
        entries = sorted(list(target.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
        if not entries:
            return f"O diretório '{target}' está vazio."

        lines = [f"Conteúdo de '{target}':"]
        for entry in entries:
            kind = "[DIR] " if entry.is_dir() else "[FILE]"
            size = ""
            if entry.is_file():
                sz = entry.stat().st_size
                if sz < 1024:
                    size = f" ({sz} B)"
                elif sz < 1024 * 1024:
                    size = f" ({sz / 1024:.1f} KB)"
                else:
                    size = f" ({sz / (1024 * 1024):.1f} MB)"
            lines.append(f"  {kind} {entry.name}{size}")
        return "\n".join(lines)
    except Exception as e:
        return f"[ERRO AO LISTAR]: {str(e)}"

def local_read_file(path: str, max_lines: int = 400) -> str:
    """Lê arquivo local no PC."""
    target = Path(os.path.expanduser(path)).resolve()
    if not target.exists():
        return f"[ERRO]: O arquivo '{path}' não existe no PC."
    if not target.is_file():
        return f"[ERRO]: '{path}' é um diretório, não um arquivo."

    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        total = len(lines)
        truncated = False
        if total > max_lines:
            lines = lines[:max_lines]
            truncated = True
        output = [f"--- Conteúdo de '{target.name}' ({total} linhas no total) ---"]
        for idx, line in enumerate(lines, 1):
            output.append(f"{idx:4d} | {line.rstrip()}")
        if truncated:
            output.append(f"\n[Aviso: Exibindo apenas as primeiras {max_lines} linhas.]")
        return "\n".join(output)
    except Exception as e:
        return f"[ERRO AO LER]: {str(e)}"

def local_write_file(path: str, content: str) -> str:
    """Escreve arquivo local no PC."""
    target = Path(os.path.expanduser(path)).resolve()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[SUCESSO]: Arquivo '{target}' gravado com sucesso no PC ({len(content)} caracteres)."
    except Exception as e:
        return f"[ERRO AO GRAVAR]: {str(e)}"

def local_create_directory(path: str) -> str:
    """Cria pasta local no PC."""
    target = Path(os.path.expanduser(path)).resolve()
    try:
        target.mkdir(parents=True, exist_ok=True)
        return f"[SUCESSO]: Pasta '{target}' criada com sucesso no PC."
    except Exception as e:
        return f"[ERRO AO CRIAR PASTA]: {str(e)}"

async def handle_action(action: str, args: dict) -> str:
    """Roteia as ações recebidas da VPS para as funções locais."""
    console.print(f"[bold cyan]⚡ Executando ação local:[/bold cyan] [yellow]{action}[/yellow]")
    if args:
        console.print(f"   [dim]Parâmetros: {args}[/dim]")

    if action == "execute_terminal_command":
        res = await run_local_command(
            command=args.get("command", ""),
            working_directory=args.get("working_directory")
        )
    elif action == "list_directory":
        res = local_list_directory(args.get("path", "."))
    elif action == "read_file":
        res = local_read_file(args.get("path", ""), args.get("max_lines", 400))
    elif action == "write_file":
        res = local_write_file(args.get("path", ""), args.get("content", ""))
    elif action == "create_directory":
        res = local_create_directory(args.get("path", ""))
    else:
        res = f"[ERRO]: Ação local '{action}' desconhecida."

    console.print(f"[green]✔ Concluído[/green] (tamanho da resposta: {len(res)} chars)")
    return res

async def worker_loop():
    """Loop principal com reconexão automática."""
    ws_url = f"{VPS_WS_URL.rstrip('/')}?token={WORKER_SECRET}"
    
    desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    user_name = getpass.getuser()
    hostname = platform.node()
    os_info = f"{platform.system()} {platform.release()}"

    system_info = {
        "user": user_name,
        "hostname": hostname,
        "os": os_info,
        "desktop": desktop_dir,
        "workdir": os.getcwd()
    }

    console.print(Panel.fit(
        f"[bold green]Assistente Local Worker (Daemon PC)[/bold green]\n"
        f"Usuário: [yellow]{user_name}[/yellow] | Máquina: [yellow]{hostname}[/yellow]\n"
        f"OS: [cyan]{os_info}[/cyan] | Desktop: [dim]{desktop_dir}[/dim]\n"
        f"Conectando a: [bold blue]{VPS_WS_URL}[/bold blue]",
        title="🤖 PC Node Agent",
        border_style="cyan"
    ))

    while True:
        try:
            console.print(f"[dim]Tentando conectar ao servidor WebSocket na VPS...[/dim]")
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                console.print(f"[bold green]✔ CONECTADO COM SUCESSO À VPS![/bold green] O agente agora tem controle total deste PC.")
                
                # Envia handshake com informações do PC
                await ws.send(json.dumps({"type": "handshake", "info": system_info}))

                while True:
                    raw_msg = await ws.recv()
                    data = json.loads(raw_msg)
                    
                    call_id = data.get("id")
                    action = data.get("action")
                    args = data.get("args", {})

                    if not call_id or not action:
                        continue

                    # Executa a ação
                    result = await handle_action(action, args)

                    # Envia a resposta de volta à VPS
                    response_payload = {
                        "id": call_id,
                        "status": "success",
                        "result": result
                    }
                    await ws.send(json.dumps(response_payload))

        except websockets.exceptions.ConnectionClosed:
            console.print("[yellow]⚠ Conexão perdida com a VPS. Reconectando em 5 segundos...[/yellow]")
        except Exception as e:
            console.print(f"[red]❌ Erro de conexão: {str(e)}. Tentando novamente em 5 segundos...[/red]")

        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        console.print("\n[bold red]Worker encerrado pelo usuário.[/bold red]")
