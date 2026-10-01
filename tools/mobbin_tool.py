import os
import logging
import asyncio
import httpx
from typing import Optional, Dict, Any, List
from config import settings
from .web_tool import search_technical_docs

logger = logging.getLogger("assistente-mobbin")

MOBBIN_API_BASE = "https://api.mobbin.com"

# Biblioteca curada de padrões visuais e benchmarks de design de altíssimo padrão
CURATED_DESIGN_BENCHMARKS = {
    "dashboard": {
        "archetype": "Cyber-Minimalismo & Dark Analytical SaaS (Ref: Linear, Stripe, Raycast)",
        "surface": "Dark Mode profundo (#090A0F) com camadas elevadas em #11141D e bordas sutis border-white/10.",
        "typography": "Sans-serif geométrica com tracking-tight nos números e métricas (ex: Geist, Inter ou Plus Jakarta Sans).",
        "layout": "Grid modular Bento com cards assimétricos arredondados (rounded-2xl ou rounded-3xl), filtros rápidos em pílula e gráficos com gradientes suaves de opacidade.",
        "interactions": "Hover suave nos cards (hover:border-white/20, hover:-translate-y-0.5), tooltips contextuais, badges de status com dot pulsante (animate-ping).",
        "recommended_components": ["BentoGrid", "MetricSparklineCard", "StatusBadge", "FloatingFilterDock"]
    },
    "landing": {
        "archetype": "Editorial AI & Luxury Glow (Ref: Apple, Vercel, Supabase, Autonix, Aceternity)",
        "surface": "Fundo limpo e atmosférico com gradientes radiais profundos em lilás/ciano com desfoque blur-3xl e efeito Aurora sutil.",
        "typography": "Títulos monumentais em h1 com tracking-tighter e leading-none, subtítulo muted em 18-20px com max-w-2xl.",
        "hero_element": "Cena 3D interativa Three.js (orbe translúcido, malha física ou constelação de partículas) ou Floating Glass Dock.",
        "interactions": "Entrada em cascata (stagger < 400ms), botões CTA em pílula com brilho sutil (shadow-[0_0_30px_rgba(...)]) e hover com micro-translação.",
        "recommended_components": ["ThreeHeroScene", "FloatingGlassDock", "AuroraBackground", "ShimmerButton"]
    },
    "checkout": {
        "archetype": "Zero Friction & High Trust (Ref: Stripe Elements, Lemon Squeezy, Apple Pay)",
        "surface": "Layout em 2 colunas: esquerda com resumo do plano e garantias/badges de segurança; direita com formulário limpo.",
        "typography": "Rótulos de campos discretos e compactos (text-xs uppercase tracking-wider text-neutral-400), números de cartão espaçados.",
        "interactions": "Validação em tempo real, seleção de planos com cards selecionáveis destacados (ring-2 ring-violet-500), botão de pagamento com feedback visual de carregamento.",
        "recommended_components": ["OrderSummaryCard", "TrustBadgeList", "PlanSelectorRadioGroup"]
    },
    "pricing": {
        "archetype": "Tiered Glass Cards & Highlight Feature (Ref: Linear Pricing, GitHub, Vercel)",
        "surface": "Cards de tiers com efeito glassmorphism (backdrop-blur-xl bg-white/5 border border-white/10). Card recomendado com badge 'Popular' e gradiente de borda iluminada.",
        "toggle": "Interruptor Mensal / Anual em pílula suave com badge de desconto ('Economize 20%').",
        "cta": "Botão principal de alto contraste na opção mais recomendada e botões outline nos outros tiers.",
        "recommended_components": ["PricingTierCard", "BillingCycleToggle", "FeatureCheckList"]
    },
    "settings": {
        "archetype": "Structured Side Navigation & Clean Forms (Ref: GitHub Settings, Notion, Supabase)",
        "surface": "Barra lateral vertical com seções agrupadas (Perfil, Segurança, Faturamento, Equipe, API).",
        "layout": "Cards de configurações com cabeçalho explicativo, descrição de apoio e botão de ação à direita (ex: 'Salvar alterações' ou 'Revogar').",
        "danger_zone": "Seção final destacada com borda avermelhada suave (border-red-500/20 bg-red-500/5) para ações irreversíveis.",
        "recommended_components": ["VerticalTabNavigation", "SettingCardRow", "DangerZoneBox"]
    }
}

async def search_mobbin_screens(query: str, platform: str = "web", limit: int = 5) -> str:
    """
    Busca referências visuais de UI/UX no Mobbin (se chave de API configurada) OU realiza pesquisa
    autônoma ativa na web nos melhores catálogos abertos do mundo (Aceternity UI, Magic UI, 21st.dev,
    Godly Website e Lapa Ninja) para fornecer receitas de componentes, tokens e sugestões de design.
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
                    logger.warning(f"[Mobbin] API retornou status {resp.status_code}: Requer plano Pro/Team ou token válido. Acionando pesquisa web autônoma.")
        except Exception as e:
            logger.warning(f"[Mobbin] Erro na requisição à API Mobbin: {e}. Acionando pesquisa web autônoma.")

    # 2. Pesquisa Autônoma Ativa na Web (Aceternity UI, Magic UI, 21st.dev, Godly Website)
    logger.info(f"[DesignIntelligence] Pesquisando referências ao vivo na web para: '{clean_query}'...")
    
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
    
    # Faz buscas simultâneas na web para coletar componentes reais
    web_references = []
    try:
        search_terms = f"{clean_query} UI components site:canvasui.dev OR site:ui.aceternity.com OR site:magicui.design OR site:21st.dev"
        web_results = await search_technical_docs(search_terms, max_results=3)
        if web_results and "ERRO" not in web_results and "Nenhum resultado" not in web_results:
            web_references.append(web_results)
    except Exception as search_err:
        logger.warning(f"[DesignIntelligence] Aviso na busca de componentes: {search_err}")

    # Monta o relatório de Inteligência de Design
    result = [
        f"🎨 *Inteligência de Design & Benchmark Visual Autônomo*",
        f"🔍 *Busca:* '{clean_query}' (Plataforma: {platform.upper()})\n",
        f"🏛️ *Direção Criativa Recomendada:* **{bench['archetype']}**",
        f"• **Superfície & Camadas:** {bench['surface']}",
        f"• **Tipografia & Ritmo:** {bench['typography']}",
        f"• **Padrão de Layout:** {bench.get('layout') or bench.get('hero_element')}",
        f"• **Microinterações:** {bench['interactions']}",
        f"• **Componentes-Chave:** {', '.join(bench['recommended_components'])}\n"
    ]
    
    if web_references:
        result.append(f"🌐 *Referências Vivas Encontradas na Web (Canvas UI / Aceternity / Magic UI / 21st.dev):*\n{web_references[0]}\n")

        
    result.extend([
        f"💬 *Proposta de Alinhamento para Sugerir ao Usuário (WhatsApp):*",
        f"\"Fala meu consagrado! Para essa tela, vou aplicar o visual *{bench['archetype'].split('(')[0].strip()}*: "
        f"fundo escuro em camadas, bordas translúcidas sutis (`border-white/10`), cards elevados com microinterações no hover e "
        f"componentes de destaque como {bench['recommended_components'][0]}. Segura aí que vai ficar padrão Awwwards! 🚀\"\n",
        f"🛠️ *Regras Obrigatórias para a Construção:*",
        f"1. **Código sem Templates Genéricos:** Não faça botões simples azuis nem tabelas cruas. Use cantos arredondados orgânicos (`rounded-2xl`), gradientes sutis e sombras difusas.",
        f"2. **Componentes Prontos de Luxo:** Use Three.js 3D (`ThreeHeroScene`), Floating Dock (`FloatingGlassDock`) ou Bento Grid disponíveis em `agent/design_system.py`.",
        f"3. **Feedback Interativo:** Adicione `hover:-translate-y-0.5`, `transition-all duration-300` e estados de foco nítidos com Lucide Icons em todos os cards e botões."
    ])
    
    return "\n".join(result)
