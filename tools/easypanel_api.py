import os
import json
import uuid
import httpx
from typing import Optional, Dict, Any, List, Tuple
from config import settings

def _get_base_url() -> str:
    return getattr(settings, "EASYPANEL_URL", "") or os.getenv("EASYPANEL_URL", "http://179.197.77.183:3000")

def _get_default_domain() -> str:
    return getattr(settings, "EASYPANEL_DOMAIN", "") or os.getenv("EASYPANEL_DOMAIN", "khdya3.easypanel.host")

async def _get_auth_token() -> Optional[str]:
    """Obtém o token de autenticação do Easypanel via API Key ou login por e-mail/senha."""
    api_key = getattr(settings, "EASYPANEL_API_KEY", "") or os.getenv("EASYPANEL_API_KEY")
    if api_key:
        return str(api_key).strip()

    email = getattr(settings, "EASYPANEL_EMAIL", "") or os.getenv("EASYPANEL_EMAIL")
    password = getattr(settings, "EASYPANEL_PASSWORD", "") or os.getenv("EASYPANEL_PASSWORD")
    if not email or not password:
        return None

    base_url = _get_base_url()
    login_url = f"{base_url.rstrip('/')}/api/trpc/auth.login"
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

async def list_easypanel_domains(client: Optional[httpx.AsyncClient] = None) -> List[Dict[str, Any]]:
    """Lista todos os domínios registrados no cluster Easypanel."""
    token = await _get_auth_token()
    if not token:
        return []
    base = f"{_get_base_url().rstrip('/')}/api/trpc"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    if client:
        r = await client.post(f"{base}/domains.listDomains", json={"json": {}})
        if r.status_code == 200:
            return r.json().get("json", [])
        return []
    else:
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as c:
            r = await c.post(f"{base}/domains.listDomains", json={"json": {}})
            if r.status_code == 200:
                return r.json().get("json", [])
            return []

async def get_service_domains(
    service_name: str,
    project_name: str = "services",
    client: Optional[httpx.AsyncClient] = None
) -> List[str]:
    """Retorna a lista de hosts (ex: 'app.khdya3.easypanel.host') apontados para este serviço."""
    all_domains = await list_easypanel_domains(client)
    hosts = []
    for d in all_domains:
        dest = d.get("serviceDestination", {})
        if dest.get("projectName") == project_name and dest.get("serviceName") == service_name:
            h = d.get("host")
            if h and h not in hosts:
                hosts.append(h)
    return hosts

async def add_service_domain(
    project_name: str,
    service_name: str,
    host: str,
    port: int = 3000,
    client: Optional[httpx.AsyncClient] = None
) -> Tuple[bool, str]:
    """Cria e aponta um domínio para o serviço no Easypanel com terminação SSL automática."""
    token = await _get_auth_token()
    if not token:
        return False, "Token de autenticação do Easypanel não configurado"
    base = f"{_get_base_url().rstrip('/')}/api/trpc"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    domain_id = f"dom_{uuid.uuid4().hex[:12]}"
    payload = {
        "json": {
            "certificateResolver": "",
            "destinationType": "service",
            "host": host,
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
    
    async def _post(c: httpx.AsyncClient):
        r = await c.post(f"{base}/domains.createDomain", json=payload)
        if r.status_code == 200:
            return True, "Domínio criado com sucesso"
        err = r.text
        if "already used" in err and f"{project_name}/{service_name}" in err:
            return True, "Domínio já apontado para este serviço"
        return False, err

    if client:
        return await _post(client)
    else:
        async with httpx.AsyncClient(timeout=15.0, headers=headers) as c:
            return await _post(c)

async def ensure_service_has_domains(
    project_name: str = "services",
    service_name: str = "",
    port: int = 3000,
    custom_domain: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None
) -> List[str]:
    """
    Garante que o serviço tenha obrigatoriamente domínios públicos com SSL apontados no Easypanel.
    Se não existirem, cria automaticamente o domínio padrão e o canônico namespaced.
    Lança ValueError caso nenhum domínio consiga ser vinculado, impedindo deploy sem domínio.
    """
    if not project_name or project_name.lower().strip() in ["phdev", "default"]:
        project_name = "services"
        
    default_domain = _get_default_domain()
    existing_hosts = await get_service_domains(service_name, project_name, client)
    
    desired_hosts = []
    if custom_domain and custom_domain.strip():
        desired_hosts.append(custom_domain.strip())
    
    canonical_short = f"{service_name}.{default_domain}"
    canonical_std = f"{project_name}-{service_name}.{default_domain}"
    
    if canonical_short not in desired_hosts:
        desired_hosts.append(canonical_short)
    if canonical_std not in desired_hosts:
        desired_hosts.append(canonical_std)
        
    for h in desired_hosts:
        if h not in existing_hosts:
            ok, msg = await add_service_domain(project_name, service_name, h, port, client)
            if ok and h not in existing_hosts:
                existing_hosts.append(h)
                
    confirmed_hosts = await get_service_domains(service_name, project_name, client)
    if not confirmed_hosts:
        raise ValueError(
            f"O serviço '{service_name}' no projeto '{project_name}' não possui nenhum domínio público apontado no Easypanel. "
            f"O deploy foi BLOQUEADO porque todo projeto precisa obrigatoriamente ter um domínio público apontado antes do deploy."
        )
    return [f"https://{h}" for h in confirmed_hosts]

async def create_and_deploy_easypanel_app(
    project_name: str = "services",
    service_name: str = "",
    git_repo: str = "",
    env_vars: Optional[Dict[str, str]] = None,
    branch: str = "main",
    domain: Optional[str] = None,
    port: int = 3000
) -> str:
    """
    Cria uma nova aplicação no Easypanel, vincula o repositório GitHub, configura Dockerfile,
    define variáveis de ambiente, cria obrigatoriamente os domínios com SSL e dispara o deploy.
    """
    if not project_name or project_name.lower().strip() in ["phdev", "default"]:
        project_name = "services"
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

    base = f"{_get_base_url().rstrip('/')}/api/trpc"
    target_domain = domain or f"{service_name}.{_get_default_domain()}"

    # Extrai owner e repo da URL do git (ex: https://github.com/Paulos19/shiftsync)
    clean_repo = git_repo.rstrip("/").removesuffix(".git")
    parts = clean_repo.split("/")
    owner = parts[-2] if len(parts) >= 2 else "Paulos19"
    repo_name = parts[-1] if len(parts) >= 1 else service_name

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

            # 5. OBRIGATÓRIO: Garante e aponta os domínios com SSL antes de deployar
            try:
                active_domains = await ensure_service_has_domains(
                    project_name=project_name,
                    service_name=service_name,
                    port=port,
                    custom_domain=domain,
                    client=client
                )
            except Exception as dom_err:
                return (
                    f"❌ [DEPLOY BLOQUEADO]: O serviço '{service_name}' não pôde ser publicado porque a configuração "
                    f"do domínio falhou ({str(dom_err)}). Todo projeto precisa obrigatoriamente ter um domínio público apontado!"
                )

            # 6. Dispara o Deploy através do webhook direto do serviço
            inspect_resp = await client.post(f"{base}/services.app.inspectService", json={
                "json": {
                    "projectName": project_name,
                    "serviceName": service_name
                }
            })
            token_webhook = inspect_resp.json().get("json", {}).get("token")
            if token_webhook:
                webhook_url = f"{_get_base_url().rstrip('/')}/api/deploy/{token_webhook}"
                try:
                    await client.post(webhook_url, json={})
                except Exception:
                    pass
            await client.post(f"{base}/services.app.deployService", json={
                "json": {
                    "projectName": project_name,
                    "serviceName": service_name
                }
            })

            domains_list_str = "\n".join(f"  - {d}" for d in active_domains)
            return (
                f"🚀 [APLICAÇÃO CRIADA E PUBLICADA NO EASYPANEL!]:\n"
                f"- Projeto: {project_name}\n"
                f"- Serviço: {service_name}\n"
                f"- Repositório GitHub: https://github.com/{owner}/{repo_name}\n"
                f"- Domínios Apontados (SSL Let's Encrypt):\n{domains_list_str}\n"
                f"- O Easypanel iniciou o build e deploy em container com sucesso!"
            )
    except Exception as e:
        return f"[ERRO AO PROVISIONAR NO EASYPANEL]: {str(e)}"
