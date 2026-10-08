import os
from pathlib import Path
from typing import Optional
from config import settings

def _resolve_path(user_path: str) -> Path:
    """Resolve caminhos relativos para dentro do workspace_path."""
    p = Path(user_path)
    if not p.is_absolute():
        p = settings.workspace_path / p
    return p.resolve()

def list_directory(path: str = ".") -> str:
    """
    Lista arquivos e diretórios de um caminho especificado.
    
    Args:
        path: Caminho da pasta (padrão é a raiz do workspace).
    """
    target = _resolve_path(path)
    if not target.exists():
        return f"[ERRO]: O caminho '{path}' não existe."
    if not target.is_dir():
        return f"[ERRO]: '{path}' não é um diretório."

    try:
        entries = sorted(list(target.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
        if not entries:
            return f"O diretório '{path}' está vazio."

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
        return f"[ERRO AO LISTAR DIRETÓRIO]: {str(e)}"

def read_file(path: str, max_lines: int = 400) -> str:
    """
    Lê o conteúdo de um arquivo de texto.
    
    Args:
        path: Caminho do arquivo a ser lido.
        max_lines: Número máximo de linhas a ler (padrão: 400).
    """
    target = _resolve_path(path)
    if not target.exists():
        return f"[ERRO]: O arquivo '{path}' não existe."
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
            output.append(f"\n[Aviso: Exibindo apenas as primeiras {max_lines} linhas de {total}.]")

        return "\n".join(output)
    except Exception as e:
        return f"[ERRO AO LER ARQUIVO]: {str(e)}"

def write_file(path: str, content: str) -> str:
    """
    Cria ou sobrescreve um arquivo com o conteúdo fornecido.
    
    Args:
        path: Caminho do arquivo a ser gravado.
        content: O conteúdo completo a ser salvo no arquivo.
    """
    target = _resolve_path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[SUCESSO]: Arquivo '{target.name}' gravado com sucesso ({len(content)} caracteres)."
    except Exception as e:
        return f"[ERRO AO GRAVAR ARQUIVO]: {str(e)}"

def create_directory(path: str) -> str:
    """
    Cria um novo diretório (e pastas intermediárias, se necessário).
    
    Args:
        path: Caminho do diretório a ser criado.
    """
    target = _resolve_path(path)
    try:
        target.mkdir(parents=True, exist_ok=True)
        return f"[SUCESSO]: Diretório '{target}' criado com sucesso."
    except Exception as e:
        return f"[ERRO AO CRIAR DIRETÓRIO]: {str(e)}"

def replace_in_file(path: str, target_text: str, replacement_text: str) -> str:
    """
    Substitui um trecho específico de texto dentro de um arquivo existente.
    Ideal para correções e edições cirúrgicas sem precisar reescrever o arquivo inteiro.
    """
    target = _resolve_path(path)
    if not target.exists():
        return f"[ERRO]: O arquivo '{path}' não existe."
    if not target.is_file():
        return f"[ERRO]: '{path}' é um diretório, não um arquivo."

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        if target_text not in content:
            return f"[ERRO]: O trecho exato a substituir não foi encontrado em '{target.name}'. Certifique-se de passar o trecho exato."

        occurrences = content.count(target_text)
        new_content = content.replace(target_text, replacement_text, 1)
        target.write_text(new_content, encoding="utf-8")
        extra_note = f" (Aviso: havia {occurrences} ocorrências; a primeira foi substituída)." if occurrences > 1 else ""
        return f"[SUCESSO]: Arquivo '{target.name}' editado com sucesso{extra_note}."
    except Exception as e:
        return f"[ERRO AO SUBSTITUIR EM ARQUIVO]: {str(e)}"
