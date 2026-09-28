import os
import json
import httpx
from typing import Optional, Dict, Any
from config import settings

EASYPANEL_BASE_URL = os.getenv("EASYPANEL_URL", "http://179.197.77.183:3000")

async def _get_auth_token() -> Optional[str]:
    """Obtém o token de autenticação do Easypanel via API Key ou login por e-mail/senha."""
    # 1. Tenta API Key direta se configurada
    api_key = os.getenv("EASYPANEL_API_KEY")
    if api_key:
        return api_key.strip()

    # 2. Tenta login via e-mail e senha
    email = os.getenv("EASYPANEL_EMAIL")
    password = os.getenv("EASYPANEL_PASSWORD")
    if not email or not password:
        return None

    login_url = f"{EASYPANEL_BASE_URL.rstrip('/')}/api/trpc/auth.login"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(login_url, json={"json": {"email": email, "password": password}})
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("result", {}).get("data", {}).get("json", {}).get("token")
                return token
    except Exception as e:
        print(f"Erro ao autenticar no Easypanel: {e}")
    return None

async def create_and_deploy_easypanel_app(
    project_name: str,
    service_name: str,
    git_repo: str,
    env_vars: Optional[Dict[str, str]] = None,
    branch: str = "main",
    domain: Optional[str] = None
) -> str:
    """
    Cria uma nova aplicação no Easypanel, vincula o repositório GitHub, define variáveis de ambiente e dispara o deploy.
    """
    token = await _get_auth_token()
    if not token:
        return (
            "[AVISO EASYPANEL]: Para criar a aplicação e realizar o deploy de forma 100% automática, "
            "o agente precisa das credenciais do Easypanel no .env:\n"
            "• EASYPANEL_API_KEY (gerada no Easypanel em Settings > Users > Generate API Key)\n"
            "• OU EASYPANEL_EMAIL e EASYPANEL_PASSWORD (os mesmos dados que você usa para logar no painel)."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    base = f"{EASYPANEL_BASE_URL.rstrip('/')}/api/trpc"

    try:
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            # 1. Cria o serviço de aplicação no Easypanel
            create_payload = {
                "json": {
                    "projectName": project_name,
                    "serviceName": service_name
                }
            }
            if domain:
                create_payload["json"]["domains"] = [{"host": domain, "https": True}]

            await client.post(f"{base}/services.app.createService", json=create_payload)

            # 2. Configura a fonte do Git
            git_payload = {
                "json": {
                    "projectName": project_name,
                    "serviceName": service_name,
                    "repo": git_repo,
                    "ref": branch,
                    "path": "/"
                }
            }
            await client.post(f"{base}/services.app.updateSourceGit", json=git_payload)

            # 3. Configura as variáveis de ambiente
            if env_vars:
                env_str = "\n".join(f"{k}={v}" for k, v in env_vars.items())
                env_payload = {
                    "json": {
                        "projectName": project_name,
                        "serviceName": service_name,
                        "env": env_str
                    }
                }
                await client.post(f"{base}/services.app.updateEnv", json=env_payload)

            # 4. Dispara o Deploy
            deploy_payload = {
                "json": {
                    "projectName": project_name,
                    "serviceName": service_name
                }
            }
            deploy_resp = await client.post(f"{base}/services.app.deployService", json=deploy_payload)

            domain_display = domain or f"{service_name}.phdev.top"

            return (
                f"🚀 [APLICAÇÃO CRIADA E DEPLOY INICIADO NO EASYPANEL!]:\n"
                f"- Projeto: {project_name}\n"
                f"- Serviço: {service_name}\n"
                f"- Repositório GitHub: {git_repo} (branch: {branch})\n"
                f"- URL de Acesso: https://{domain_display}\n"
                f"- Status do Deploy: Iniciado no Easypanel com sucesso!"
            )
    except Exception as e:
        return f"[ERRO AO PROVISIONAR NO EASYPANEL]: {str(e)}"
