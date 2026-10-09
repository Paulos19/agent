"""
Ferramentas de integração e consulta ao Canvas UI & MCP Server (https://canvasui.dev/docs)
Permite ao agente consultar o catálogo oficial de shaders WebGL/WebGPU,
inspecionar metadados e props ao vivo da registry e orientar a instalação via MCP ou CLI.
"""

import json
import logging
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger("CanvasTool")

CANVAS_UI_REGISTRY_BASE = "https://canvasui.dev/r"

# ==============================================================================
# CANVAS UI SHADER & COMPONENT CATALOG (https://canvasui.dev/docs)
# ==============================================================================
CANVAS_UI_FULL_CATALOG = {
    # Fluidos e Simulações Líquidas
    "liquid": {"cmd": "npx shadcn@latest add @canvas-ui/liquid-react", "desc": "Simulação fluida de ponteiro com distorção sobre texto e cards reais do HTML."},
    "liquid-object": {"cmd": "npx shadcn@latest add @canvas-ui/liquid-object-react", "desc": "Objeto 3D com física de fluido e refração dinâmica."},
    "ripple": {"cmd": "npx shadcn@latest add @canvas-ui/ripple-react", "desc": "Ondas de água concêntricas interativas que propagam ao mover ou clicar."},
    "droplets": {"cmd": "npx shadcn@latest add @canvas-ui/droplets-react", "desc": "Gotas de condensação líquida que escorrem e refratam o fundo."},
    "bubble": {"cmd": "npx shadcn@latest add @canvas-ui/bubble-react", "desc": "Bolhas orgânicas translúcidas com aberração cromática flutuando."},

    # Física, Força e Energia
    "force-field": {"cmd": "npx shadcn@latest add @canvas-ui/force-field-react", "desc": "Campo magnético de força que deforma e repele elementos ao passar do cursor."},
    "flame-wrap": {"cmd": "npx shadcn@latest add @canvas-ui/flame-wrap-react", "desc": "Chamas energéticas de shader envolvendo botões, badges ou cards."},
    "cloth": {"cmd": "npx shadcn@latest add @canvas-ui/cloth-react", "desc": "Tecido 3D interativo com física de vento, gravidade e arrasto."},
    "laser": {"cmd": "npx shadcn@latest add @canvas-ui/laser-react", "desc": "Feixe de laser de alta voltagem escaneando tipografias e bordas."},

    # Óptica, 3D e Refração Vítrea
    "glass": {"cmd": "npx shadcn@latest add @canvas-ui/glass-react", "desc": "Refração cáustica de vidro fosco de altíssimo realismo sobre o DOM."},
    "glass-object": {"cmd": "npx shadcn@latest add @canvas-ui/glass-object-react", "desc": "Objeto 3D vítreo com aberração cromática orbitando a interface."},
    "displacement": {"cmd": "npx shadcn@latest add @canvas-ui/displacement-react", "desc": "Distorção vetorial orgânica que estica a tipografia no hover."},
    "bend": {"cmd": "npx shadcn@latest add @canvas-ui/bend-react", "desc": "Curvatura 3D cilíndrica deformando a perspectiva do container."},

    # Revelação, Partículas e Cyberpunk
    "decrypt-reveal": {"cmd": "npx shadcn@latest add @canvas-ui/decrypt-reveal-react", "desc": "Descriptografia cibernética de títulos com caracteres aleatórios."},
    "particle-reveal": {"cmd": "npx shadcn@latest add @canvas-ui/particle-reveal-react", "desc": "Revelação espetacular de textos e imagens via vórtice de partículas WebGL."},
    "particle-scroll": {"cmd": "npx shadcn@latest add @canvas-ui/particle-scroll-react", "desc": "Nuvem de partículas que reage ao scroll e profundidade do mouse."},
    "particle-object": {"cmd": "npx shadcn@latest add @canvas-ui/particle-object-react", "desc": "Malha de partículas volumétrica montando modelos 3D."},
    "glyph-rain": {"cmd": "npx shadcn@latest add @canvas-ui/glyph-rain-react", "desc": "Chuva digital de glifos estilo Matrix com iluminação neon."},

    # Retrô, Dither e ASCII
    "ascii-object": {"cmd": "npx shadcn@latest add @canvas-ui/ascii-object-react", "desc": "Renderizador volumétrico em tempo real em caracteres ASCII interativos."},
    "ascii-sweep": {"cmd": "npx shadcn@latest add @canvas-ui/ascii-sweep-react", "desc": "Varredura de transição convertendo texto moderno em arte ASCII."},
    "asciify": {"cmd": "npx shadcn@latest add @canvas-ui/asciify-react", "desc": "Filtro shader ASCII completo sobre qualquer componente HTML."},
    "retro-dither": {"cmd": "npx shadcn@latest add @canvas-ui/retro-dither-react", "desc": "Dithering Bayer de 1-bit / 8-bit para estética brutalista/lo-fi."},
    "dithered-object": {"cmd": "npx shadcn@latest add @canvas-ui/dithered-object-react", "desc": "Objeto 3D dithered com estética de hardware dos anos 90."},
    "vhs": {"cmd": "npx shadcn@latest add @canvas-ui/vhs-react", "desc": "Distorção de fita VHS com tracking noise e linhas CRT analógicas."},
    "glitch": {"cmd": "npx shadcn@latest add @canvas-ui/glitch-react", "desc": "Glitch digital de canal RGB com pulso e tremor nos eixos X/Y."},

    # Atmosfera e Ambiente
    "clouds": {"cmd": "npx shadcn@latest add @canvas-ui/clouds-react", "desc": "Nuvens volumétricas procedurais em constante deriva com luz ambiente."},
    "frost": {"cmd": "npx shadcn@latest add @canvas-ui/frost-react", "desc": "Cristais de gelo que se espalham pelas bordas da interface no hover."},
    "grid": {"cmd": "npx shadcn@latest add @canvas-ui/grid-react", "desc": "Grid cibernético em perspectiva tridimensional com pulso de luz."},
    "hex-float": {"cmd": "npx shadcn@latest add @canvas-ui/hex-float-react", "desc": "Células hexagonais flutuantes com gradientes de profundidade."},
    "ink-object": {"cmd": "npx shadcn@latest add @canvas-ui/ink-object-react", "desc": "Dispersão fluida de tinta / aquarela orgânica suspensa em água."},
    "shatter": {"cmd": "npx shadcn@latest add @canvas-ui/shatter-react", "desc": "Efeito de estilhaçamento geométrico com quebra em múltiplos fragmentos."}
}

async def get_canvas_ui_shader_info(name_or_query: str) -> str:
    """
    Pesquisa e obtém informações detalhadas sobre shaders do Canvas UI.
    Se for um componente exato (ex: 'liquid', 'force-field', 'decrypt-reveal'),
    consulta a registry oficial do Canvas UI (https://canvasui.dev/r/{name}-react.json)
    para extrair props, descrição e comando de instalação.
    Se for um termo de busca (ex: 'agua', 'vidro', '3d', 'particulas', 'retro'),
    filtra os melhores shaders correspondentes no catálogo.
    """
    query_clean = name_or_query.strip().lower().replace("@canvas-ui/", "").replace("-react", "")
    
    # 1. Busca exata no catálogo
    if query_clean in CANVAS_UI_FULL_CATALOG:
        info = CANVAS_UI_FULL_CATALOG[query_clean]
        comp_name = query_clean
        registry_url = f"{CANVAS_UI_REGISTRY_BASE}/{comp_name}-react.json"
        
        # Tenta buscar os metadados ao vivo da registry
        live_data = None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(registry_url)
                if res.status_code == 200:
                    live_data = res.json()
        except Exception as e:
            logger.warning(f"Não foi possível buscar registry ao vivo para {comp_name}: {e}")
        
        output_lines = [
            f"✨ *Shader Canvas UI: {comp_name.upper()}*",
            f"📖 *Descrição:* {info.get('desc')}",
            f"📦 *Comando CLI:* `{info.get('cmd')}`",
            f"🌐 *Registro URL:* {registry_url}"
        ]
        
        if live_data:
            title = live_data.get("title", comp_name)
            desc = live_data.get("description", "")
            files = live_data.get("files", [])
            target = files[0].get("target", f"components/canvasui/{comp_name.title()}.tsx") if files else ""
            output_lines.append(f"🏷️ *Título:* {title}")
            if desc:
                output_lines.append(f"📝 *Detalhes:* {desc}")
            if target:
                output_lines.append(f"📁 *Arquivo Gerado:* `{target}`")
        
        output_lines.append("\n💡 *Uso via MCP / CLI:*")
        output_lines.append(f"- No terminal do projeto: `{info.get('cmd')}`")
        output_lines.append(f"- No cliente MCP (Claude/Cursor/Antigravity): 'Add {comp_name} from @canvas-ui registry'")
        
        return "\n".join(output_lines)

    # 2. Busca por palavra-chave no catálogo
    matches = []
    keywords = query_clean.split()
    for name, data in CANVAS_UI_FULL_CATALOG.items():
        score = 0
        desc_lower = data["desc"].lower()
        for kw in keywords:
            if kw in name:
                score += 3
            if kw in desc_lower:
                score += 1
        if score > 0:
            matches.append((score, name, data))
            
    matches.sort(key=lambda x: x[0], reverse=True)
    
    if matches:
        output_lines = [
            f"🎨 *Encontrados {len(matches)} Shaders do Canvas UI para '{name_or_query}':*",
            ""
        ]
        for _, name, data in matches[:6]:
            output_lines.append(f"🔹 *{name}*: {data['desc']}")
            output_lines.append(f"   Comando: `{data['cmd']}`")
            output_lines.append("")
        output_lines.append("💡 Instale qualquer um rodando o comando ou via MCP server.")
        return "\n".join(output_lines)

    # 3. Se nada bateu, lista os mais populares
    popular = ["liquid", "force-field", "flame-wrap", "glass", "decrypt-reveal", "particle-reveal", "ascii-object", "frost"]
    output_lines = [
        f"Nenhum shader específico encontrado para '{name_or_query}'. Aqui estão os destaques do Canvas UI:",
        ""
    ]
    for name in popular:
        if name in CANVAS_UI_FULL_CATALOG:
            d = CANVAS_UI_FULL_CATALOG[name]
            output_lines.append(f"🔹 *{name}*: {d['desc']} (`{d['cmd']}`)")
    return "\n".join(output_lines)
