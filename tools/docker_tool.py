import os
from pathlib import Path

NEXTJS_DOCKERFILE = """# =======================================================
# Dockerfile Multi-Stage Otimizado para Next.js Standalone
# =======================================================
FROM node:20-alpine AS base

FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json* yarn.lock* pnpm-lock.yaml* bun.lockb* ./
RUN \\
  if [ -f yarn.lock ]; then yarn --frozen-lockfile; \\
  elif [ -f package-lock.json ]; then npm ci; \\
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm i --frozen-lockfile; \\
  else npm install; \\
  fi

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

RUN npm run build

FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copia arquivos estáticos e build standalone
COPY --from=builder /app/public ./public
RUN mkdir .next && chown nextjs:nodejs .next

# Se o build gerou standalone, usa o servidor standalone; caso contrário, copia o build padrão
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

CMD ["node", "server.js"]
"""

VITE_DOCKERFILE = """# =======================================================
# Dockerfile Multi-Stage para Single Page Apps (Vite / React)
# =======================================================
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine AS runner
COPY --from=builder /app/dist /usr/share/nginx/html
# Configuração para suportar roteamento SPA no Nginx
RUN echo 'server { \\
    listen 80; \\
    location / { \\
        root /usr/share/nginx/html; \\
        index index.html index.htm; \\
        try_files $uri $uri/ /index.html; \\
    } \\
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
"""

FASTAPI_DOCKERFILE = """# =======================================================
# Dockerfile para Aplicações Python / FastAPI
# =======================================================
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

DOCKERIGNORE_CONTENT = """node_modules
.next
.git
.gitignore
.env*.local
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
README.md
dist
build
.venv
__pycache__
"""

async def _ensure_nextjs_standalone(project_path: str, target: str = "pc") -> None:
    """Garante que 'output: standalone' esteja configurado no next.config.* para builds Docker multi-stage."""
    clean_path = project_path.rstrip("/\\\\")
    if target == "pc":
        from agent.nodes import node_manager
        if not node_manager.is_connected:
            return
        ps_script = (
            f"$files = @('next.config.ts', 'next.config.mjs', 'next.config.js'); "
            f"$found = $false; "
            f"foreach ($f in $files) {{ "
            f"  $p = Join-Path '{clean_path}' $f; "
            f"  if (Test-Path $p) {{ "
            f"    $found = $true; "
            f"    $content = Get-Content -Raw $p; "
            f"    if ($content -notmatch 'standalone') {{ "
            f"      if ($content -match '(const\\s+nextConfig\\s*(:\\s*NextConfig)?\\s*=\\s*\\{{)') {{ "
            f"        $content = $content -replace '(const\\s+nextConfig\\s*(:\\s*NextConfig)?\\s*=\\s*\\{{)', ('$1`n  output: \"standalone\",'); "
            f"      }} elseif ($content -match '(module\\.exports\\s*=\\s*\\{{)') {{ "
            f"        $content = $content -replace '(module\\.exports\\s*=\\s*\\{{)', ('$1`n  output: \"standalone\",'); "
            f"      }} else {{ "
            f"        $content = '/** @type {{import(\"next\").NextConfig}} */`nconst nextConfig = {{ output: \"standalone\" }};`nexport default nextConfig;'; "
            f"      }} "
            f"      Set-Content -Path $p -Value $content; "
            f"    }} "
            f"    break; "
            f"  }} "
            f"}}; "
            f"if (-not $found) {{ "
            f"  Set-Content -Path (Join-Path '{clean_path}' 'next.config.mjs') -Value '/** @type {{import(\"next\").NextConfig}} */`nconst nextConfig = {{`n  output: \"standalone\",`n}};`n`nexport default nextConfig;`n'; "
            f"}}"
        )
        await node_manager.execute_on_pc("execute_terminal_command", {
            "command": ps_script,
            "working_directory": clean_path
        })
    else:
        p = Path(project_path).resolve()
        found = False
        for cfg_name in ["next.config.ts", "next.config.mjs", "next.config.js"]:
            cfg_file = p / cfg_name
            if cfg_file.exists():
                found = True
                content = cfg_file.read_text(encoding="utf-8")
                if "standalone" not in content:
                    import re
                    if "const nextConfig" in content:
                        content = re.sub(r"(const\s+nextConfig\s*(?::\s*NextConfig)?\s*=\s*\{)", r'\1\n  output: "standalone",', content)
                    elif "module.exports" in content:
                        content = re.sub(r"(module\.exports\s*=\s*\{)", r'\1\n  output: "standalone",', content)
                    else:
                        content = '/** @type {import("next").NextConfig} */\nconst nextConfig = {\n  output: "standalone",\n};\nexport default nextConfig;\n'
                    cfg_file.write_text(content, encoding="utf-8")
                break
        if not found:
            (p / "next.config.mjs").write_text('/** @type {import("next").NextConfig} */\nconst nextConfig = {\n  output: "standalone",\n};\nexport default nextConfig;\n', encoding="utf-8")

async def setup_docker_deployment(
    project_path: str,
    project_type: str = "nextjs",
    port: int = 3000,
    target: str = "pc"
) -> str:
    """
    Cria os arquivos de produção Dockerfile e .dockerignore no projeto para que o Easypanel ou Docker da VPS possa buildar perfeitamente.
    """
    proj_type = project_type.lower().strip()
    is_next = "next" in proj_type
    if is_next:
        dockerfile = NEXTJS_DOCKERFILE
    elif any(k in proj_type for k in ["vite", "react", "vue"]):
        dockerfile = VITE_DOCKERFILE
    elif any(k in proj_type for k in ["python", "fastapi", "flask"]):
        dockerfile = FASTAPI_DOCKERFILE
    else:
        dockerfile = NEXTJS_DOCKERFILE

    if target == "pc":
        from agent.nodes import node_manager
        if not node_manager.is_connected:
            return "[ERRO]: O PC local está desconectado. Conecte o worker.py."

        clean_path = project_path.rstrip("/\\\\")
        if is_next:
            await _ensure_nextjs_standalone(clean_path, target="pc")

        # Grava Dockerfile e .dockerignore no PC
        df_res = await node_manager.execute_on_pc("write_file", {
            "path": f"{clean_path}/Dockerfile",
            "content": dockerfile
        })
        di_res = await node_manager.execute_on_pc("write_file", {
            "path": f"{clean_path}/.dockerignore",
            "content": DOCKERIGNORE_CONTENT
        })

        return (
            f"🐳 [DOCKER DEPLOYMENT CONFIGURADO NO PC COM SUCESSO!]:\n"
            f"- Projeto: {project_path}\n"
            f"- Tipo: {project_type.upper()}\n"
            f"- Porta Exposta: {port}\n"
            f"- Arquivos criados:\n"
            f"  • {project_path}/Dockerfile\n"
            f"  • {project_path}/.dockerignore\n\n"
            f"Próximos passos recomendados:\n"
            f"1. Fazer commit e push com 'push_project_to_github'\n"
            f"2. Vincular o repositório no Easypanel (ou disparar deploy webhook)"
        )
    else:
        # Gravação local na VPS
        p = Path(project_path).resolve()
        p.mkdir(parents=True, exist_ok=True)
        if is_next:
            await _ensure_nextjs_standalone(str(p), target="vps")

        (p / "Dockerfile").write_text(dockerfile, encoding="utf-8")
        (p / ".dockerignore").write_text(DOCKERIGNORE_CONTENT, encoding="utf-8")

        return (
            f"🐳 [DOCKER DEPLOYMENT CONFIGURADO NA VPS COM SUCESSO!]:\n"
            f"- Diretório: {p}\n"
            f"- Tipo: {project_type.upper()}\n"
            f"- Porta: {port}\n"
            f"- Dockerfile e .dockerignore criados."
        )
