import os
import json
import httpx
from typing import Optional, Dict
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
    
    Args:
        service_name_or_url: Nome do serviço no Easypanel (ex: 'phdev') ou a URL completa do Deploy Webhook.
    """
    webhook_url = _get_deploy_webhook(service_name_or_url)
    if not webhook_url:
        return (
            f"[ERRO DEPLOY EASYPANEL]: Nenhuma URL de Deploy Webhook foi encontrada para '{service_name_or_url}'.\n"
            f"Adicione a variável EASYPANEL_DEPLOY_{service_name_or_url.upper().replace('-', '_')}_WEBHOOK no .env "
            f"ou forneça a URL completa do Webhook copiada do Easypanel."
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Tenta via POST (padrão de webhooks de deploy)
            resp = await client.post(webhook_url)
            
            # Se retornar 405 (Method Not Allowed), tenta via GET
            if resp.status_code == 405:
                resp = await client.get(webhook_url)

            if resp.status_code in [200, 201, 202, 204]:
                return (
                    f"🚀 [DEPLOY INICIADO NO EASYPANEL]:\n"
                    f"- Serviço: {service_name_or_url}\n"
                    f"- Status HTTP: {resp.status_code}\n"
                    f"- O Easypanel iniciou o build e atualização do container com sucesso!"
                )
            else:
                return (
                    f"[FALHA AO DISPARAR DEPLOY ({resp.status_code})]:\n"
                    f"{resp.text[:300]}"
                )
    except Exception as e:
        return f"[ERRO AO CHAMAR WEBHOOK DO EASYPANEL]: {str(e)}"
