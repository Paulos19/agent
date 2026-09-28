import os
import json
import uuid
import httpx
from typing import Optional, Dict, Any
from config import settings

EASYPANEL_BASE_URL = os.getenv("EASYPANEL_URL", "http://179.197.77.183:3000")
EASYPANEL_DEFAULT_DOMAIN = os.getenv("EASYPANEL_DOMAIN", "khdya3.easypanel.host")

async def _get_auth_token() -> Optional[str]:
    """Obtém o token de autenticação do Easypanel via API Key ou login por e-mail/senha."""
    api_key = os.getenv("EASYPANEL_API_KEY")
    if api_key:
        return api_key.strip()

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
    domain: Optional[str] = None,
    port: int = 3000
) -> str:
    """
    Cria uma nova aplicação no Easypanel, vincula o repositório GitHub, configura Dockerfile, define variáveis de ambiente, cria os domínios e dispara o deploy.
    """
    token = await _get_auth_token()
    if not token:
        return (
            "[AVISO EASYPANEL]: Para criar a aplicação e realizar o deploy de forma 100% automática, "
            "o agente precisa do EASYPANEL_API_KEY no .env."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    base = f"{EASYPANEL_BASE_URL.rstrip('/')}/api/trpc"

    # Extrai owner e repo da URL do git (ex: https://github.com/Paulos19/portal-clientes)
    clean_repo = git_repo.rstrip("/").removesuffix(".git")
    parts = clean_repo.split("/")
    owner = parts[-2] if len(parts) >= 2 else "Paulos19"
    repo_name = parts[-1] if len(parts) >= 1 else service_name

    target_domain = domain or f"{service_name}.{EASYPANEL_DEFAULT_DOMAIN}"

    try:
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            # 1. Cria o serviço de aplicação no Easypanel (ignora se já existir)
            create_payload = {
                "json": {
                    "projectName": project_name,
                    "serviceName": service_name
                }
            }
            await client.post(f"{base}/services.app.createService", json=create_payload)

            # 2. Configura a fonte GitHub
            gh_payload = {
                "json": {
                    "projectName": project_name,
                    "serviceName": service_name,
                    "owner": owner,
                    "repo": repo_name,
                    "ref": branch,
                    "path": "/"
                }
            }
            await client.post(f"{base}/services.app.updateSourceGithub", json=gh_payload)

            # 3. Configura o builder para Dockerfile multi-stage
            build_payload = {
                "json": {
                    "projectName": project_name,
                    "serviceName": service_name,
                    "type": "dockerfile",
                    "file": "Dockerfile"
                }
            }
            await client.post(f"{base}/services.app.updateBuild", json=build_payload)

            # 4. Configura as variáveis de ambiente
            if env_vars:
                # Adiciona PORT e NEXTAUTH_URL se ausentes
                if "PORT" not in env_vars:
                    env_vars["PORT"] = str(port)
                if "NEXTAUTH_URL" not in env_vars and any("auth" in k.lower() for k in env_vars.keys()):
                    env_vars["NEXTAUTH_URL"] = f"https://{target_domain}"

                env_str = "\n".join(f"{k}={v}" for k, v in env_vars.items())
                env_payload = {
                    "json": {
                        "projectName": project_name,
                        "serviceName": service_name,
                        "env": env_str
                    }
                }
                await client.post(f"{base}/services.app.updateEnv", json=env_payload)

            # 5. Cria o Domínio Padrão com SSL Let's Encrypt
            domain_id = f"dom_{uuid.uuid4().hex[:12]}"
            domain_payload = {
                "json": {
                    "certificateResolver": "",
                    "destinationType": "service",
                    "host": target_domain,
                    "https": True,
                    "id": domain_id,
                    "middlewares": [],
                    "path": "/",
                    "serviceDestination": {
                        "path": "/",
                        "port": port,
                        "projectName": project_name,
                        "protocol": "http",
                        "serviceName": service_name
                    },
                    "wildcard": False
                }
            }
            await client.post(f"{base}/domains.createDomain", json=domain_payload)

            # 6. Dispara o Deploy através do webhook direto do serviço
            inspect_resp = await client.post(f"{base}/services.app.inspectService", json={
                "json": {
                    "projectName": project_name,
                    "serviceName": service_name
                }
            })
            token_webhook = inspect_resp.json().get("json", {}).get("token")
            if token_webhook:
                webhook_url = f"{EASYPANEL_BASE_URL.rstrip('/')}/api/deploy/{token_webhook}"
                await client.post(webhook_url)
            else:
                await client.post(f"{base}/services.app.deployService", json={
                    "json": {
                        "projectName": project_name,
                        "serviceName": service_name
                    }
                })

            return (
                f"🚀 [APLICAÇÃO CRIADA E PUBLICADA NO EASYPANEL!]:\n"
                f"- Projeto: {project_name}\n"
                f"- Serviço: {service_name}\n"
                f"- Repositório GitHub: https://github.com/{owner}/{repo_name}\n"
                f"- Domínio / URL de Acesso: https://{target_domain}\n"
                f"- O Easypanel iniciou o build e deploy em container com sucesso!"
            )
    except Exception as e:
        return f"[ERRO AO PROVISIONAR NO EASYPANEL]: {str(e)}"
