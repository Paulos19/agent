import os
import logging
import httpx
from typing import Optional, Dict, Any, List
from config import settings

logger = logging.getLogger("assistente-mobbin")

MOBBIN_API_BASE = "https://api.mobbin.com"

# Biblioteca curada de padrões visuais e benchmarks de design (fallback de alto nível)
CURATED_DESIGN_BENCHMARKS = {
    "dashboard": {
        "archetype": "Cyber-Minimalismo & Dark Analytical SaaS (Ref: Linear, Stripe, Raycast)",
        "surface": "Dark Mode profundo (#090A0F) com camadas elevadas em #11141D e bordas sutis border-white/10.",
        "typography": "Sans-serif geométrica com tracking-tight nos números e métricas (ex: Geist, Inter ou Plus Jakarta Sans).",
        "layout": "Grid modular Bento com cards arredondados (rounded-2xl ou rounded-3xl), filtros rápidos em pílula e gráficos sparkline com gradientes suaves de opacidade.",
        "interactions": "Hover suave nos cards (hover:border-white/20, hover:-translate-y-0.5), tooltips contextuais, badges de status com dot animado (animate-ping)."
    },
    "landing": {
        "archetype": "Editorial AI & Luxury Glow (Ref: Apple, Vercel, Supabase, Autonix)",
        "surface": "Fundo limpo e atmosférico com gradientes radiais profundos em lilás/ciano com desfoque blur-3xl.",
        "typography": "Títulos monumentais em h1 com tracking-tighter e leading-none, subtítulo muted em 18-20px com max-w-2xl.",
        "hero_element": "Cena 3D interativa Three.js (orbe translúcido, malha física ou constelação de partículas) ou Floating Glass Dock.",
        "interactions": "Entrada em cascata (stagger < 400ms), botões CTA em pílula com brilho sutil (shadow-[0_0_30px_rgba(...)]) e hover com micro-translação."
    },
    "checkout": {
        "archetype": "Zero Friction & High Trust (Ref: Stripe Elements, Lemon Squeezy, Apple Pay)",
        "surface": "Layout em 2 colunas: esquerda com resumo do plano e garantias/badges de segurança; direita com formulário limpo.",
        "typography": "Rótulos de campos discretos e compactos (text-xs uppercase tracking-wider text-neutral-400), números de cartão espaçados.",
        "interactions": "Validação em tempo real, seleção de planos com cards selecionáveis destacados (ring-2 ring-violet-500), botão de pagamento com feedback visual de carregamento."
    },
    "pricing": {
        "archetype": "Tiered Glass Cards & Highlight Feature (Ref: Linear Pricing, GitHub, Vercel)",
        "surface": "Cards de tiers com efeito glassmorphism (backdrop-blur-xl bg-white/5 border border-white/10). Card recomendado com badge 'Popular' e gradiente de borda iluminada.",
        "toggle": "Interruptor Mensal / Anual em pílula suave com badge de desconto ('Economize 20%').",
        "cta": "Botão principal de alto contraste na opção mais recomendada e botões outline nos outros tiers."
    },
    "settings": {
        "archetype": "Structured Side Navigation & Clean Forms (Ref: GitHub Settings, Notion, Supabase)",
        "surface": "Barra lateral vertical com seções agrupadas (Perfil, Segurança, Faturamento, Equipe, API).",
        "layout": "Cards de configurações com cabeçalho explicativo, descrição de apoio e botão de ação à direita (ex: 'Salvar alterações' ou 'Revogar').",
        "danger_zone": "Seção final destacada com borda avermelhada suave (border-red-500/20 bg-red-500/5) para ações irreversíveis."
    }
}

async def search_mobbin_screens(query: str, platform: str = "web", limit: int = 5) -> str:
    """
    Busca telas e padrões visuais de UI no Mobbin utilizando a REST API / MCP oficial.
    Se a chave de API não estiver configurada ou a conta Mobbin for gratuita, utiliza um
    mecanismo inteligente de fallback com os princípios visuais dos 5 arquétipos de design
    de produtos líderes para garantir que o assistente construa sempre interfaces de padrão mundial.
    """
    api_key = settings.MOBBIN_API_KEY or os.getenv("MOBBIN_API_KEY") or os.getenv("MOBBIN_TOKEN")
    clean_query = query.strip()
    
    # 1. Tentativa de consulta direta à API do Mobbin caso a chave exista
    if api_key:
        logger.info(f"[Mobbin] Consultando API Mobbin para '{clean_query}' (plataforma: {platform})...")
        try:
            async with httpx.AsyncClient(timeout=15.0) as http_client:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "query": clean_query,
                    "platform": platform.lower(),
                    "limit": min(limit, 10)
                }
                
                resp = await http_client.post(
                    f"{MOBBIN_API_BASE}/v1/screens/search",
                    headers=headers,
                    json=payload
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    screens = data.get("screens", [])
                    if screens:
                        lines = [
                            f"🎨 *Referências Visuais Oficiais do Mobbin para: '{clean_query}'*\n"
                        ]
                        for idx, s in enumerate(screens[:limit], 1):
                            app_name = s.get("app_name") or s.get("app", {}).get("name", "App")
                            screen_name = s.get("name") or s.get("screen_name", "Tela de UI")
                            mobbin_url = s.get("mobbin_url") or s.get("url", "")
                            image_url = s.get("image_url") or s.get("preview_url", "")
                            tags = ", ".join(s.get("tags", [])[:5]) or "UI/UX moderno"
                            
                            lines.append(f"🔹 **{idx}. {app_name}** - _{screen_name}_")
                            if tags:
                                lines.append(f"   • Padrões identificados: {tags}")
                            if mobbin_url:
                                lines.append(f"   • Link Mobbin: {mobbin_url}")
                            if image_url:
                                lines.append(f"   • Imagem de Referência: {image_url}")
                            lines.append("")
                        
                        lines.append("💡 *Diretriz de Execução*: Utilize a disposição de elementos, ritmo de espaçamentos e hierarquia visual destas referências ao codificar os componentes.")
                        return "\n".join(lines)
                elif resp.status_code in [401, 402, 403]:
                    logger.warning(f"[Mobbin] API retornou status {resp.status_code}: Requer plano Pro/Team ou token válido. Aplicando benchmark inteligente.")
        except Exception as e:
            logger.warning(f"[Mobbin] Erro na requisição à API Mobbin: {e}. Aplicando benchmark inteligente.")

    # 2. Mecanismo de Inteligência Visual e Benchmark Arquitetural (Fallback Avançado)
    logger.info(f"[Mobbin] Gerando inteligência de benchmark de design para: '{clean_query}'...")
    
    # Identifica o nicho da tela solicitada
    query_lower = clean_query.lower()
    matched_key = "dashboard"
    if any(k in query_lower for k in ["landing", "home", "hero", "apresentação", "site"]):
        matched_key = "landing"
    elif any(k in query_lower for k in ["checkout", "pagamento", "compra", "carrinho", "pay"]):
        matched_key = "checkout"
    elif any(k in query_lower for k in ["pricing", "preço", "planos", "tabela", "tier"]):
        matched_key = "pricing"
    elif any(k in query_lower for k in ["settings", "config", "perfil", "conta", "profile"]):
        matched_key = "settings"
    elif any(k in query_lower for k in ["dashboard", "painel", "analytics", "admin", "tabela", "métricas"]):
        matched_key = "dashboard"
        
    bench = CURATED_DESIGN_BENCHMARKS[matched_key]
    
    result = [
        f"🎨 *Benchmark de Design Visual & UI/UX (Padrão Mobbin / Líderes do Mercado)*",
        f"🔍 *Busca Solicitada:* '{clean_query}' (Plataforma: {platform.upper()})\n",
        f"🏛️ *Arquétipo Recomendado:* {bench['archetype']}",
        f"• **Superfície & Cores:** {bench['surface']}",
        f"• **Tipografia & Legibilidade:** {bench['typography']}",
        f"• **Padrão de Layout:** {bench.get('layout') or bench.get('hero_element', 'Estrutura em Bento Grid ou colunas bem definidas.')}",
        f"• **Microinterações & Feedback:** {bench['interactions']}\n",
        f"🛠️ *Regras Práticas para Implementação no Projeto:*",
        f"1. **Sem Minimalismo Vazio:** Adicione contraste de pesos de fonte, bordas sutis translúcidas (border-white/10 ou border-neutral-200) e sombras com difusão suave.",
        f"2. **Componentes Prontos de Destaque:** Integre componentes avançados como o *FloatingGlassDock* ou cena Three.js 3D (disponíveis em `agent/design_system.py`) se for uma Landing ou Hero.",
        f"3. **Estados Interativos:** Garanta que cada botão ou card clicável possua feedback de hover (`hover:scale-[1.01]` ou `hover:border-primary/40`) e estados de foco nítidos."
    ]
    
    return "\n".join(result)
