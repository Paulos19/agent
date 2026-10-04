import asyncio
import json
import os
import platform
import sys
import getpass
from pathlib import Path
import base64
import websockets
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from dotenv import load_dotenv

# Garante suporte completo a UTF-8 no Windows (evita UnicodeEncodeError em consoles cp1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Garante que o diretório de execução seja sempre a pasta do script
os.chdir(Path(__file__).parent.resolve())

import re
import time
from datetime import datetime

load_dotenv()

console = Console(legacy_windows=False)
LOG_FILE = Path(__file__).parent / "worker.log"

def log_event(message):
    """Grava o evento no arquivo worker.log com timestamp."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(message, Panel):
            clean_text = f"Worker Daemon Iniciado (Host: {platform.node()}, OS: {platform.system()} {platform.release()})"
        else:
            clean_text = re.sub(r'\[/?[a-zA-Z0-9_\s#]+\]', '', str(message)).strip()
        if clean_text:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {clean_text}\n")
    except Exception:
        pass

def log_print(msg: str):
    """Imprime no console e registra no arquivo worker.log."""
    try:
        console.print(msg)
    except Exception:
        pass
    log_event(msg)

# URL e token do WebSocket da VPS
VPS_WS_URL = os.getenv("VPS_WS_URL", "wss://agent.phdev.top/ws/worker")
WORKER_SECRET = os.getenv("WORKER_SECRET", "devops_secret_token_123")

async def run_local_command(command: str, working_directory: str = None, timeout: int = 90) -> str:
    """
    Executa o comando localmente no Windows com PowerShell via EncodedCommand (Base64 UTF-16LE).
    Elimina problemas de escape de aspas do cmd.exe, suporta múltiplos comandos separados por ponto e vírgula
    e converte '&&' para ';' evitando erro de sintaxe do PowerShell 5.1.
    """
    cwd = working_directory
    
    # Se working_directory não foi passado, tenta extrair de comandos como 'Set-Location' ou 'cd'
    if not cwd:
        m = re.match(r'^(?:Set-Location|cd)\s+[\'"]?([A-Za-z]:\\[^\'";]+)[\'"]?', command.strip(), re.IGNORECASE)
        if m:
            potential_dir = m.group(1).strip()
            if os.path.exists(potential_dir):
                cwd = potential_dir
    
    cwd = cwd or os.getcwd()
    try:
        cwd_path = Path(os.path.expanduser(cwd)).resolve()
        cwd_path.mkdir(parents=True, exist_ok=True)
        cwd = str(cwd_path)
    except Exception:
        cwd = os.getcwd()

    # Prepara o comando PowerShell
    clean_cmd = command.strip()
    
    # Converte ' && ' para '; ' e ' || ' para '; ' para total compatibilidade com PowerShell 5.1
    clean_cmd = re.sub(r'\s*&&\s*', '; ', clean_cmd)
    clean_cmd = re.sub(r'\s*\|\|\s*', '; ', clean_cmd)

    # Identidade do Git e Token de Autenticação
    git_token = os.getenv("GITHUB_TOKEN", "").strip()
    
    ps_header = [
        "$ProgressPreference = 'SilentlyContinue'",
        "$env:GIT_TERMINAL_PROMPT = '0'",
        "$env:GCM_INTERACTIVE = 'never'"
    ]
    
    # Se for comando que usa git, garante configuração de usuário e token
    if "git" in clean_cmd.lower():
        ps_header.append('git config user.name "Paulo Henrique"')
        ps_header.append('git config user.email "paulohenrique.012araujo@gmail.com"')
        ps_header.append('git config credential.helper ""')
        if git_token and any(k in clean_cmd.lower() for k in ["push", "remote", "clone", "pull"]):
            ps_header.append(
                f'try {{ '
                f'  $url = git remote get-url origin 2>$null; '
                f'  if ($url -and ($url -match "github\\.com") -and -not ($url -match "{git_token}")) {{ '
                f'    $authUrl = $url -replace "https://(?:[^@]+@)?github\\.com", "https://{git_token}@github.com"; '
                f'    git remote set-url origin $authUrl '
                f'  }} '
                f'}} catch {{}}'
            )

    full_script = "\n".join(ps_header) + "\n" + clean_cmd
    encoded = base64.b64encode(full_script.encode("utf-16le")).decode("ascii")

    try:
        process = await asyncio.create_subprocess_exec(
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-EncodedCommand", encoded,
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

        # Remove eventuais linhas de aviso inócuas do PowerShell CLIXML
        if "#< CLIXML" in err_str:
            err_str = re.sub(r'#< CLIXML.*?</Objs>', '', err_str, flags=re.DOTALL).strip()

        if len(out_str) > 8000:
            out_str = out_str[:8000] + f"\n\n[...saída truncada no worker local ({len(out_str)} caracteres no total)...]"
        if len(err_str) > 4000:
            err_str = err_str[:4000] + f"\n\n[...stderr truncado no worker local ({len(err_str)} caracteres no total)...]"

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

def take_pc_screenshot(out_path: str = None) -> Path:
    """Captura o screenshot da tela principal do Windows com suporte a troca de desktop."""
    import ctypes
    from PIL import ImageGrab, Image

    u32 = ctypes.windll.user32
    k32 = ctypes.windll.kernel32

    # Garante acesso ao desktop 'default' do usuário interativo
    old_desk = u32.GetThreadDesktop(k32.GetCurrentThreadId())
    h_default = u32.OpenDesktopW("default", 0, False, 0x01FF)
    switched = False
    if h_default:
        switched = bool(u32.SetThreadDesktop(h_default))

    try:
        img = ImageGrab.grab(all_screens=True)
        if img.width > 1920 or img.height > 1080:
            img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)

        save_target = Path(out_path) if out_path else Path(__file__).parent / "storage" / "temp_local" / f"screenshot_{int(time.time())}.jpg"
        save_target.parent.mkdir(parents=True, exist_ok=True)
        img.save(save_target, "JPEG", quality=85, optimize=True)
        return save_target
    finally:
        if switched and old_desk:
            u32.SetThreadDesktop(old_desk)
        if h_default:
            u32.CloseDesktop(h_default)

def manage_pc_power(action: str, timer_minutes: int = 0) -> str:
    """Controla bloqueio de tela, suspensão e desligamento do Windows."""
    act = action.lower().strip()
    if act == "lock":
        import ctypes
        res = ctypes.windll.user32.LockWorkStation()
        if res:
            return "🔒 Tela do Windows bloqueada com sucesso!"
        return "⚠️ Não foi possível bloquear a estação de trabalho."
    elif act == "suspend":
        import subprocess
        ps_cmd = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState([System.Windows.Forms.PowerState]::Suspend, $false, $false)"
        subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_cmd])
        return "🌙 Comando de suspensão enviado ao Windows. O computador entrará em repouso."
    elif act == "shutdown":
        import subprocess
        seconds = max(0, timer_minutes * 60)
        cmd = f'shutdown.exe /s /t {seconds} /c "Desligamento agendado pelo Assistente"'
        subprocess.run(cmd, shell=True)
        if timer_minutes > 0:
            return f"⏳ Desligamento do PC agendado para daqui a {timer_minutes} minuto(s) ({seconds}s). Use /cancelardesligar para abortar."
        return "🛑 Desligando o computador imediatamente."
    elif act in ["cancel_shutdown", "abort"]:
        import subprocess
        subprocess.run("shutdown.exe /a", shell=True)
        return "✅ Desligamento agendado cancelado com sucesso no Windows!"
    return f"Ação de energia desconhecida: '{action}'"

async def handle_action(action: str, args: dict, ws=None, call_id: str = None) -> str:
    """Roteia as ações recebidas da VPS para as funções locais com suporte a streaming de progresso."""
    log_print(f"[bold cyan]⚡ Executando ação local:[/bold cyan] [yellow]{action}[/yellow]")
    if args:
        log_print(f"   [dim]Parâmetros: {args}[/dim]")

    async def send_progress(msg: str):
        if ws and call_id:
            try:
                await ws.send(json.dumps({
                    "id": call_id,
                    "type": "progress",
                    "message": msg
                }))
            except Exception:
                pass

    if action == "execute_terminal_command":
        cmd = args.get("command", "")
        # Emite progresso se for comando de scaffold, build ou pacote
        if any(k in cmd.lower() for k in ["npm", "pnpm", "yarn", "build", "npx", "install", "clone"]):
            clean_cmd = cmd.split("\n")[0][:45]
            await send_progress(f"⚡ Rodando comando no seu Windows: `{clean_cmd}...`")
        res = await run_local_command(
            command=cmd,
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
    elif action == "git_status":
        res = await run_local_command("git status", working_directory=args.get("repo_path", "."))
    elif action == "git_diff":
        res = await run_local_command("git diff", working_directory=args.get("repo_path", "."))
    elif action == "git_pull":
        b = args.get("branch", "main")
        await send_progress(f"🔄 Puxando atualizações do GitHub (git pull origin {b})...")
        res = await run_local_command(f"git pull origin {b}", working_directory=args.get("repo_path", "."))
    elif action == "git_commit_and_push":
        repo_dir = args.get("repo_path", ".")
        msg = args.get("message", "update").replace('"', '\\"')
        b = args.get("branch", "main")
        git_token = os.getenv("GITHUB_TOKEN", "").strip()

        await send_progress(f"📦 Verificando e commitando alterações no Git local ({b})...")
        git_script = f"""
git config user.name "Paulo Henrique"
git config user.email "paulohenrique.012araujo@gmail.com"
git config credential.helper ""
$env:GIT_TERMINAL_PROMPT = '0'
$env:GCM_INTERACTIVE = 'never'

git add -A
$status = git status --porcelain
if ($status) {{
    git commit -m "{msg}"
}} else {{
    Write-Output "Nenhum arquivo modificado para commitar."
}}

try {{
    $url = git remote get-url origin 2>$null
    if ($url -and ($url -match "github\\.com") -and -not ($url -match "{git_token}")) {{
        $authUrl = $url -replace "https://(?:[^@]+@)?github\\.com", "https://{git_token}@github.com"
        git remote set-url origin $authUrl
    }}
}} catch {{}}

git branch -M {b}
git push origin {b}
"""
        await send_progress(f"🚀 Enviando commits para o GitHub (branch {b})...")
        res = await run_local_command(
            git_script,
            working_directory=repo_dir,
            timeout=120
        )
    elif action == "download_youtube_media_local":
        from tools.youtube_downloader import _run_yt_dlp
        url = args.get("url")
        fmt = args.get("format_type", "mp3")
        qual = args.get("quality", "best")

        await send_progress(f"🎵 Extraindo {fmt.upper()} no seu PC local (IP Residencial)...")
        local_temp = Path(__file__).parent / "storage" / "temp_local"
        local_temp.mkdir(parents=True, exist_ok=True)

        try:
            dl_result = await asyncio.to_thread(_run_yt_dlp, url, fmt, qual, local_temp)
            local_file_path = Path(dl_result["file_path"])
            if args.get("upload_to_vps"):
                await send_progress("☁️ Enviando arquivo para a VPS para gerar o link de 48h...")
                import httpx
                vps_url = VPS_WS_URL or "wss://agent.phdev.top/ws/worker"
                domain_match = re.search(r'wss?://([^/]+)', vps_url)
                vps_host = domain_match.group(1) if domain_match else "agent.phdev.top"
                upload_endpoint = f"https://{vps_host}/api/upload_temp?token={WORKER_SECRET}"

                with open(local_file_path, "rb") as f:
                    files = {"file": (dl_result["file_name"], f, "application/octet-stream")}
                    async with httpx.AsyncClient(timeout=180.0) as client:
                        resp = await client.post(upload_endpoint, files=files)
                        if resp.status_code == 200:
                            data = resp.json()
                            dl_result["download_url"] = data["download_url"]
                            dl_result["file_path"] = data["file_path"]
                            dl_result["token"] = data["token"]
                        else:
                            raise RuntimeError(f"Erro ao subir arquivo para a VPS ({resp.status_code}): {resp.text}")

                # Limpa arquivo temporário local para economizar espaço
                try:
                    if local_file_path.exists():
                        local_file_path.unlink()
                except Exception:
                    pass

            res = json.dumps({"success": True, "result": dl_result}, default=str)
        except Exception as e:
            res = json.dumps({"success": False, "error": str(e)})
    elif action == "download_playlist_media_local":
        from tools.youtube_downloader import _run_playlist_dlp
        url = args.get("url")
        qual = args.get("quality", "320")
        max_t = args.get("max_tracks", 50)

        await send_progress("📋 Extraindo Playlist no seu PC local (IP Residencial)...")
        local_temp = Path(__file__).parent / "storage" / "temp_local"
        local_temp.mkdir(parents=True, exist_ok=True)

        try:
            dl_result = await asyncio.to_thread(_run_playlist_dlp, url, qual, local_temp, max_t)
            local_file_path = Path(dl_result["file_path"])
            if args.get("upload_to_vps"):
                await send_progress("☁️ Enviando pacote .ZIP da playlist para a VPS...")
                import httpx
                vps_url = VPS_WS_URL or "wss://agent.phdev.top/ws/worker"
                domain_match = re.search(r'wss?://([^/]+)', vps_url)
                vps_host = domain_match.group(1) if domain_match else "agent.phdev.top"
                upload_endpoint = f"https://{vps_host}/api/upload_temp?token={WORKER_SECRET}"

                with open(local_file_path, "rb") as f:
                    files = {"file": (dl_result["file_name"], f, "application/zip")}
                    async with httpx.AsyncClient(timeout=300.0) as client:
                        resp = await client.post(upload_endpoint, files=files)
                        if resp.status_code == 200:
                            data = resp.json()
                            dl_result["download_url"] = data["download_url"]
                            dl_result["file_path"] = data["file_path"]
                            dl_result["token"] = data["token"]
                        else:
                            raise RuntimeError(f"Erro ao subir .ZIP para a VPS ({resp.status_code}): {resp.text}")

                try:
                    if local_file_path.exists():
                        local_file_path.unlink()
                except Exception:
                    pass

            res = json.dumps({"success": True, "result": dl_result}, default=str)
        except Exception as e:
            res = json.dumps({"success": False, "error": str(e)})
    elif action == "take_screenshot":
        await send_progress("📸 Capturando a tela do seu PC Windows...")
        try:
            img_path = await asyncio.to_thread(take_pc_screenshot)
            result_data = {
                "file_path": str(img_path.resolve()),
                "file_name": img_path.name,
                "size_bytes": img_path.stat().st_size
            }

            if args.get("upload_to_vps", True):
                await send_progress("☁️ Enviando screenshot para a VPS...")
                import httpx
                vps_url = VPS_WS_URL or "wss://agent.phdev.top/ws/worker"
                domain_match = re.search(r'wss?://([^/]+)', vps_url)
                vps_host = domain_match.group(1) if domain_match else "agent.phdev.top"
                upload_endpoint = f"https://{vps_host}/api/upload_temp?token={WORKER_SECRET}"

                with open(img_path, "rb") as f:
                    files = {"file": (img_path.name, f, "image/jpeg")}
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        resp = await client.post(upload_endpoint, files=files)
                        if resp.status_code == 200:
                            data = resp.json()
                            result_data["download_url"] = data.get("download_url")
                            result_data["file_path"] = data.get("file_path")
                            result_data["token"] = data.get("token")
                        else:
                            raise RuntimeError(f"Erro ao subir print para a VPS ({resp.status_code}): {resp.text}")

                try:
                    if img_path.exists():
                        img_path.unlink()
                except Exception:
                    pass

            res = json.dumps({"success": True, "result": result_data})
        except Exception as e:
            res = json.dumps({"success": False, "error": str(e)})
    elif action == "manage_pc_power":
        power_action = args.get("power_action") or args.get("action", "lock")
        timer_min = args.get("timer_minutes", 0)
        await send_progress(f"⚡ Executando comando de energia no PC: {power_action}...")
        try:
            msg = manage_pc_power(power_action, timer_min)
            res = json.dumps({"success": True, "message": msg})
        except Exception as e:
            res = json.dumps({"success": False, "error": str(e)})
    else:
        res = f"[ERRO]: Ação local '{action}' desconhecida."

    log_print(f"[green]✔ Concluído[/green] (tamanho da resposta: {len(res)} chars)")
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

    log_print(Panel.fit(
        f"[bold green]Assistente Local Worker (Daemon PC)[/bold green]\n"
        f"Usuário: [yellow]{user_name}[/yellow] | Máquina: [yellow]{hostname}[/yellow]\n"
        f"OS: [cyan]{os_info}[/cyan] | Desktop: [dim]{desktop_dir}[/dim]\n"
        f"Conectando a: [bold blue]{VPS_WS_URL}[/bold blue]",
        title="🤖 PC Node Agent",
        border_style="cyan"
    ))

    while True:
        try:
            log_print(f"[dim]Tentando conectar ao servidor WebSocket na VPS...[/dim]")
            async with websockets.connect(ws_url, ping_interval=15, ping_timeout=15) as ws:
                log_print(f"[bold green]✔ CONECTADO COM SUCESSO À VPS![/bold green] O agente agora tem controle total deste PC.")
                
                # Envia handshake com informações do PC
                await ws.send(json.dumps({"type": "handshake", "info": system_info}))

                # Heartbeat ativo a cada 12 segundos para manter o túnel do proxy (Traefik/Easypanel) sempre aquecido
                async def _heartbeat():
                    try:
                        while True:
                            await asyncio.sleep(12)
                            await ws.send(json.dumps({"type": "ping", "time": time.time()}))
                    except Exception:
                        pass

                heartbeat_task = asyncio.create_task(_heartbeat())

                try:
                    while True:
                        try:
                            raw_msg = await asyncio.wait_for(ws.recv(), timeout=35)
                        except asyncio.TimeoutError:
                            # Envia ping de conferência se passar 35s sem mensagens
                            await ws.send(json.dumps({"type": "ping", "time": time.time()}))
                            continue

                        data = json.loads(raw_msg)
                        if data.get("type") == "pong":
                            continue
                        
                        call_id = data.get("id")
                        action = data.get("action")
                        args = data.get("args", {})

                        if not call_id or not action:
                            continue

                        # Executa a ação passando ws e call_id para poder enviar mensagens de progresso
                        result = await handle_action(action, args, ws=ws, call_id=call_id)

                        # Envia a resposta de volta à VPS
                        response_payload = {
                            "id": call_id,
                            "status": "success",
                            "result": result
                        }
                        await ws.send(json.dumps(response_payload))
                finally:
                    heartbeat_task.cancel()

        except websockets.exceptions.ConnectionClosed:
            log_print("[yellow]⚠ Conexão perdida com a VPS. Reconectando em 3 segundos...[/yellow]")
        except Exception as e:
            log_print(f"[red]❌ Erro de conexão: {str(e)}. Tentando novamente em 3 segundos...[/red]")

        await asyncio.sleep(3)

if __name__ == "__main__":
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        log_print("\n[bold red]Worker encerrado pelo usuário.[/bold red]")
