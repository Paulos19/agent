import os
import re
import json
import time
import uuid
import mimetypes
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, Any
from config import settings

def get_storage_dir() -> Path:
    """Retorna e garante a existência do diretório de armazenamento temporário."""
    base = settings.workspace_path / "storage" / "temp_downloads"
    base.mkdir(parents=True, exist_ok=True)
    return base

def _get_registry_path() -> Path:
    """Retorna o caminho do arquivo JSON que mantém o índice de arquivos e expirações."""
    reg_dir = settings.workspace_path / "storage"
    reg_dir.mkdir(parents=True, exist_ok=True)
    return reg_dir / "storage_registry.json"

def _load_registry() -> Dict[str, Any]:
    reg_file = _get_registry_path()
    if not reg_file.exists():
        return {}
    try:
        with open(reg_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_registry(registry: Dict[str, Any]):
    reg_file = _get_registry_path()
    try:
        with open(reg_file, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[TempStorage] Erro ao salvar registro: {e}")

def register_temp_file(
    file_path: Any,
    filename: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ttl_hours: int = 48
) -> Dict[str, Any]:
    """
    Registra um arquivo no storage temporário com validade de 48 horas (ou ttl_hours).
    Retorna o dicionário de registro contendo o token e as URLs.
    """
    token = uuid.uuid4().hex[:12]
    p_path = Path(file_path).resolve()
    clean_filename = str(filename or p_path.name)
    now = time.time()
    expires_at = now + (ttl_hours * 3600)

    # Garante que o arquivo esteja dentro do storage_dir
    storage_dir = get_storage_dir().resolve()
    if p_path.parent != storage_dir:
        target_path = storage_dir / f"{token}_{clean_filename}"
        try:
            p_path.rename(target_path)
            actual_file = target_path
        except Exception:
            import shutil
            shutil.copy2(p_path, target_path)
            actual_file = target_path
    else:
        actual_file = p_path

    record = {
        "token": token,
        "filename": clean_filename,
        "stored_filename": actual_file.name,
        "file_path": str(actual_file.resolve()),
        "size_bytes": actual_file.stat().st_size if actual_file.exists() else 0,
        "format": actual_file.suffix.lstrip(".").lower(),
        "created_at": now,
        "expires_at": expires_at,
        "ttl_hours": ttl_hours,
        "metadata": metadata or {}
    }

    registry = _load_registry()
    registry[token] = record
    _save_registry(registry)

    return record

def get_temp_file(token: str) -> Optional[Dict[str, Any]]:
    """
    Recupera as informações de um arquivo pelo token.
    Se estiver expirado ou o arquivo não existir fisicamente, remove do índice e retorna None.
    """
    registry = _load_registry()
    record = registry.get(token)
    if not record:
        return None

    now = time.time()
    # Verifica expiração
    if now > record.get("expires_at", 0):
        # Expirado: remove arquivo e registro
        _delete_record_file(record)
        registry.pop(token, None)
        _save_registry(registry)
        return None

    raw_path = record.get("file_path", "")
    p = Path(raw_path) if raw_path else None
    if not p or not p.exists() or not p.is_file():
        # Fallback: tenta localizar na pasta storage_dir
        storage_dir = get_storage_dir()
        stored_name = record.get("stored_filename") or record.get("filename")
        if stored_name and (storage_dir / stored_name).is_file():
            actual = storage_dir / stored_name
            record["file_path"] = str(actual.resolve())
            registry[token] = record
            _save_registry(registry)
            return record

        for cand in storage_dir.glob(f"*{token}*"):
            if cand.is_file():
                record["file_path"] = str(cand.resolve())
                registry[token] = record
                _save_registry(registry)
                return record

        # Arquivo físico realmente não existe
        registry.pop(token, None)
        _save_registry(registry)
        return None

    return record

def _delete_record_file(record: Dict[str, Any]):
    """Exclui o arquivo físico com segurança."""
    try:
        p = Path(record.get("file_path", ""))
        if p.exists() and p.is_file():
            p.unlink()
    except Exception as e:
        print(f"[TempStorage] Erro ao deletar arquivo expirado: {e}")

def cleanup_expired_files() -> int:
    """
    Varre o registro e apaga todos os arquivos com mais de 48 horas (ou expirados).
    Também limpa arquivos órfãos sem registro na pasta com mais de 48h.
    Retorna o número de arquivos expurgados.
    """
    registry = _load_registry()
    now = time.time()
    expired_tokens = []
    removed_count = 0

    for token, record in list(registry.items()):
        if now > record.get("expires_at", 0):
            _delete_record_file(record)
            expired_tokens.append(token)
            removed_count += 1
        else:
            # Verifica se o arquivo ainda existe
            p = Path(record.get("file_path", ""))
            if not p.exists():
                expired_tokens.append(token)

    for t in expired_tokens:
        registry.pop(t, None)

    if expired_tokens:
        _save_registry(registry)

    # Varre arquivos órfãos soltos na pasta com mais de 48h (172800s)
    try:
        storage_dir = get_storage_dir()
        known_paths = {r.get("file_path") for r in registry.values()}
        for f in storage_dir.glob("*"):
            if f.is_file() and str(f.resolve()) not in known_paths:
                file_age = now - f.stat().st_mtime
                if file_age > (48 * 3600):
                    try:
                        f.unlink()
                        removed_count += 1
                    except Exception:
                        pass
    except Exception as e:
        print(f"[TempStorage] Erro ao varrer arquivos órfãos: {e}")

    return removed_count

def get_download_url(token: str) -> str:
    """Gera a URL pública direta para o token temporário."""
    vps_ws = getattr(settings, "VPS_WS_URL", None) or os.getenv("VPS_WS_URL", "wss://agent.phdev.top/ws/worker")
    if vps_ws:
        domain_match = re.search(r'wss?://([^/]+)', vps_ws)
        if domain_match:
            vps_host = domain_match.group(1)
            return f"https://{vps_host}/d/{token}"
            
    return f"http://localhost:{settings.PORT}/d/{token}"
