import os
import base64
import asyncio
import logging
from pathlib import Path
from typing import Optional
from openai import AsyncOpenAI
from config import settings

logger = logging.getLogger("assistente-visual-inspector")

async def capture_and_analyze_design(url: str, focus: str = "layout, cores e componentes de destaque") -> str:
    """
    Abre a URL em um navegador headless (Playwright / Chromium / Edge), captura um screenshot
    em alta resolução da interface e utiliza a visão multimodal do Gemini para dissecar
    a estética: paleta de cores (hex), tipografia, espaçamento, componentes e classes Tailwind CSS.
    """
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"https://{clean_url}"

    logger.info(f"[VisualInspector] Navegando até '{clean_url}' para captura visual e análise...")

    screenshot_bytes: Optional[bytes] = None

    # 1. Captura com Playwright
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            # Tenta usar o Edge ou Chrome nativo da máquina, com fallback para Chromium padrão
            browser = None
            launch_channels = ["msedge", "chrome", None]
            
            for channel in launch_channels:
                try:
                    kwargs = {"headless": True}
                    if channel:
                        kwargs["channel"] = channel
                    browser = await p.chromium.launch(**kwargs)
                    break
                except Exception:
                    continue

            if not browser:
                browser = await p.chromium.launch(headless=True)

            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # Navega e aguarda renderização básica
            await page.goto(clean_url, wait_until="domcontentloaded", timeout=30000)
            
            # Aguarda 1.5s para transições de CSS, fontes e animações carregarem
            await asyncio.sleep(1.5)

            # Captura screenshot em formato PNG
            screenshot_bytes = await page.screenshot(type="png", full_page=False)
            await browser.close()

    except Exception as browser_err:
        logger.error(f"[VisualInspector] Falha ao capturar screenshot via navegador: {browser_err}")
        return (
            f"[ERRO AO ABRIR NAVEGADOR]: Não foi possível capturar o screenshot de '{clean_url}'.\n"
            f"Detalhe técnico: {str(browser_err)}\n"
            f"Dica: Verifique se a URL está online e acessível publicamente."
        )

    if not screenshot_bytes:
        return f"[ERRO]: Screenshot vazio capturado de '{clean_url}'."

    logger.info(f"[VisualInspector] Screenshot capturado ({len(screenshot_bytes)} bytes). Enviando para análise do Gemini Vision...")

    # Salva cópia temporária no scratch para referência/inspeção se necessário
    try:
        scratch_dir = Path("scratch")
        scratch_dir.mkdir(parents=True, exist_ok=True)
        img_path = scratch_dir / "latest_design_reference.png"
        with open(img_path, "wb") as f:
            f.write(screenshot_bytes)
    except Exception:
        pass

    # 2. Análise Multimodal com Gemini Vision
    try:
        client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
        b64_image = base64.b64encode(screenshot_bytes).decode("utf-8")

        prompt = f"""Você é um Engenheiro de Design Frontend e Diretor de Arte sênior de nível Awwwards.
Analise detalhadamente o screenshot desta interface web capturada da URL '{clean_url}'.
Foco da análise: {focus}.

Por favor, forneça um raio-x visual completo e pronto para ser codificado:
1. **Identidade Estética & Arquétipo:** (ex: Dark Analytical SaaS, Minimalist Apple, Bento Grid Suíço, etc.)
2. **Paleta de Cores Exata:**
   - Cor de fundo primária (código hex aproximado)
   - Cor de superfície dos cards/painéis
   - Cores de destaque (accent / gradientes)
   - Tratamento de bordas (ex: border-white/10, contrastes)
3. **Tipografia e Hierarquia:**
   - Estilo da fonte (geométrica, moderna, serif)
   - Proporção entre títulos grandes (tracking, weight) e textos auxiliares
4. **Layout e Espaçamento:**
   - Tipo de grid (Bento, 12 colunas, centralizado)
   - Ritmo de paddings, gaps e curvatura dos cantos (rounded-xl, rounded-2xl, rounded-3xl)
5. **Componentes-Chave Identificados:**
   - Descreva a estrutura dos 2 a 3 componentes visuais mais impactantes (ex: Hero section, cards com glow, badges, docks)
6. **Receita Pronta em Tailwind CSS & React:**
   - Forneça classes Tailwind CSS exatas e um snippet conciso de código demonstrando como reproduzir fielmente essa mesma estética no projeto do usuário.
"""

        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
                ]
            }],
            temperature=0.2
        )

        analysis = response.choices[0].message.content or "Nenhuma análise retornada pela visão multimodal."
        
        return (
            f"📸 *Inspeção Visual Concluída com Sucesso para:* `{clean_url}`\n\n"
            f"{analysis}\n\n"
            f"💡 *Diretriz*: Use essas classes e diretrizes visuais exatas para codificar a interface solicitada pelo usuário."
        )

    except Exception as vision_err:
        logger.error(f"[VisualInspector] Erro na análise visual com Gemini: {vision_err}")
        return f"[ERRO NA ANÁLISE DE IMAGEM DO GEMINI]: {str(vision_err)}"
