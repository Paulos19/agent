import os
import json
import httpx
from typing import Optional, Dict, List
from config import settings

def _get_deploy_webhook(service_name_or_url: str) -> Optional[str]:
    """Resolve a URL do webhook de deploy a partir do nome do serviço ou URL direta."""
    target = service_name_or_url.strip()
    if target.startswith("http://") or target.startswith("https://"):
        return target

    # Tenta ler do mapa JSON em EASYPANEL_DEPLOY_WEBHOOKS
    raw_map = os.getenv("EASYPANEL_DEPLOY_WEBHOOKS", "{}")
    try:
        webhooks_map: Dict[str, str] = json.loads(raw_map)
        if target.lower() in webhooks_map:
            return webhooks_map[target.lower()]
    except Exception:
        pass

    # Tenta ler de variável de ambiente individual: EASYPANEL_DEPLOY_WEBHOOK_<SERVICO>
    env_var_name = f"EASYPANEL_DEPLOY_{target.upper().replace('-', '_')}_WEBHOOK"
    found = os.getenv(env_var_name)
    if found:
        return found

    # Tenta fallback para webhook genérico
    return os.getenv("EASYPANEL_DEPLOY_WEBHOOK")

async def trigger_easypanel_deploy(service_name_or_url: str) -> str:
    """
    Dispara o build e deploy automático de um projeto/serviço no Easypanel.
    Garante obrigatoriamente que o serviço possui ao menos um domínio público apontado antes de disparar o deploy.
    """
    target = service_name_or_url.strip()
    is_direct_url = target.startswith("http://") or target.startswith("https://")
    service_name = "" if is_direct_url else target
    active_domains: List[str] = []

    # 1. Se for nome de serviço, garante e valida obrigatoriamente os domínios
    if service_name:
        try:
            from tools.easypanel_api import ensure_service_has_domains
            active_domains = await ensure_service_has_domains(
                project_name="services",
                service_name=service_name
            )
        except Exception as e:
            return (
                f"❌ [DEPLOY BLOQUEADO]: O serviço '{service_name}' não possui nenhum domínio público apontado "
                f"no Easypanel ({str(e)}). O deploy foi cancelado porque todo projeto precisa ter ao menos um domínio configurado!"
            )

    # 2. Resolve a URL do webhook
    webhook_url = _get_deploy_webhook(target)
    if not webhook_url and service_name:
        # Tenta resolver dinamicamente via inspectService na API do Easypanel
        try:
            from tools.easypanel_api import _get_auth_token, _get_base_url
            token = await _get_auth_token()
            if token:
                base = f"{_get_base_url().rstrip('/')}/api/trpc"
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                    resp = await client.post(f"{base}/services.app.inspectService", json={
                        "json": {"projectName": "services", "serviceName": service_name}
                    })
                    if resp.status_code == 200:
                        token_hook = resp.json().get("json", {}).get("token")
                        if token_hook:
                            webhook_url = f"{_get_base_url().rstrip('/')}/api/deploy/{token_hook}"
        except Exception:
            pass

    if not webhook_url:
        return (
            f"[ERRO DEPLOY EASYPANEL]: Nenhuma URL de Deploy Webhook foi encontrada para '{service_name_or_url}'.\n"
            f"Adicione a variável EASYPANEL_DEPLOY_{service_name_or_url.upper().replace('-', '_')}_WEBHOOK no .env "
            f"ou forneça a URL completa do Webhook copiada do Easypanel."
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Tenta via POST
            resp = await client.post(webhook_url, json={})
            
            # Se retornar 405, tenta via GET
            if resp.status_code == 405:
                resp = await client.get(webhook_url)

            if resp.status_code in [200, 201, 202, 204]:
                domains_text = ""
                if active_domains:
                    domains_text = "\n- Domínios Apontados (SSL Let's Encrypt):\n" + "\n".join(f"  - {d}" for d in active_domains)
                return (
                    f"🚀 [DEPLOY INICIADO NO EASYPANEL]:\n"
                    f"- Serviço: {service_name_or_url}\n"
                    f"- Status HTTP: {resp.status_code}"
                    f"{domains_text}\n"
                    f"- O Easypanel iniciou o build e atualização do container com sucesso!"
                )
            else:
                return (
                    f"[FALHA AO DISPARAR DEPLOY ({resp.status_code})]:\n"
                    f"{resp.text[:300]}"
                )
    except Exception as e:
        return f"[ERRO AO CHAMAR WEBHOOK DO EASYPANEL]: {str(e)}"
