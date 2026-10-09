import os
import base64
import asyncio
import logging
import urllib.parse
from pathlib import Path
from typing import Optional
from openai import AsyncOpenAI
from config import settings

logger = logging.getLogger("assistente-visual-inspector")

async def _launch_browser(playwright_instance):
    """Lança o navegador Edge ou Chrome instalado nativamente no Windows com fallback para Chromium."""
    launch_channels = ["msedge", "chrome", None]
    browser = None
    for channel in launch_channels:
        try:
            kwargs = {"headless": True}
            if channel:
                kwargs["channel"] = channel
            browser = await playwright_instance.chromium.launch(**kwargs)
            return browser
        except Exception:
            continue
    return await playwright_instance.chromium.launch(headless=True)

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

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await _launch_browser(p)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            await page.goto(clean_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2.0)

            # Captura screenshot em JPEG otimizado (rápido e leve)
            screenshot_bytes = await page.screenshot(type="jpeg", quality=75, full_page=False)
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

    logger.info(f"[VisualInspector] Screenshot capturado ({len(screenshot_bytes)} bytes). Enviando para análise visual...")

    # Salva cópia no scratch
    try:
        scratch_dir = Path("scratch")
        scratch_dir.mkdir(parents=True, exist_ok=True)
        img_path = scratch_dir / "latest_design_reference.jpg"
        with open(img_path, "wb") as f:
            f.write(screenshot_bytes)
    except Exception:
        pass

    try:
        client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
        b64_image = base64.b64encode(screenshot_bytes).decode("utf-8")

        prompt = f"""Você é um Engenheiro de Design Frontend e Diretor de Arte sênior de nível Awwwards.
Analise detalhadamente o screenshot desta interface web capturada da URL '{clean_url}'.
Foco da análise: {focus}.

Por favor, forneça um raio-x visual completo e pronto para ser codificado:
1. **Identidade Estética & Arquétipo:** (ex: Dark Analytical SaaS, Minimalist Apple, Bento Grid Suíço, Canvas UI WebGL)
2. **Paleta de Cores Exata:**
   - Cor de fundo primária (código hex aproximado)
   - Cor de superfície dos cards/painéis
   - Cores de destaque (accent / gradientes neon)
   - Tratamento de bordas (ex: border-white/10, contrastes sutis)
3. **Tipografia e Hierarquia:**
   - Estilo da fonte (geométrica, moderna, monospace)
   - Proporção entre títulos grandes (tracking, weight) e textos de apoio
4. **Layout e Espaçamento:**
   - Tipo de grid (Bento, 12 colunas, modular)
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
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                ]
            }],
            temperature=0.2
        )

        analysis = response.choices[0].message.content or "Nenhuma análise retornada pela visão multimodal."
        return (
            f"📸 *Inspeção Visual Concluída com Sucesso para:* `{clean_url}`\n\n"
            f"{analysis}\n\n"
            f"💡 *Diretriz*: Use essas classes e diretrizes visuais exatas para codificar a interface no projeto do usuário."
        )

    except Exception as vision_err:
        logger.error(f"[VisualInspector] Erro na análise visual com IA: {vision_err}")
        return f"[ERRO NA ANÁLISE DE IMAGEM]: {str(vision_err)}"

async def search_pinterest_and_analyze_ui(query: str, project_path: Optional[str] = None) -> str:
    """
    Abre o Pinterest em um navegador invisível (Playwright / Edge / Chrome headless), pesquisa por templates
    e referências visuais de UI/UX (ex: 'SaaS dashboard dark mode', 'fintech app UI', 'landing page AI'),
    remove modais de login/popups, captura o grid de pins em alta resolução e usa visão multimodal
    com IA para dissecar as melhores referências e gerar um blueprint completo em Tailwind CSS e React
    para melhorar o projeto do usuário.
    """
    clean_query = query.strip()
    encoded_query = urllib.parse.quote(clean_query)
    pinterest_url = f"https://www.pinterest.com/search/pins/?q={encoded_query}"

    logger.info(f"[PinterestInspector] Acessando Pinterest headless para pesquisar: '{clean_query}'...")

    screenshot_bytes: Optional[bytes] = None

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await _launch_browser(p)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # Navega até o Pinterest
            await page.goto(pinterest_url, wait_until="domcontentloaded", timeout=35000)
            await asyncio.sleep(3.5)

            # Remove popups de login/cadastro ou modais que bloqueiam a visualização dos pins
            try:
                await page.evaluate("""() => {
                    const elements = document.querySelectorAll('[role="dialog"], [data-test-id*="modal"], [data-test-id*="signup"], [data-test-id*="login"]');
                    elements.forEach(el => el.remove());
                    document.body.style.overflow = "auto";
                }""")
            except Exception:
                pass

            # Rola levemente para baixo para carregar os pins de forma nítida
            try:
                await page.evaluate("window.scrollBy(0, 300);")
                await asyncio.sleep(1.0)
            except Exception:
                pass

            screenshot_bytes = await page.screenshot(type="jpeg", quality=75, full_page=False)
            await browser.close()

    except Exception as browser_err:
        logger.error(f"[PinterestInspector] Falha ao navegar no Pinterest: {browser_err}")
        return f"[ERRO AO ACESSAR PINTEREST]: Não foi possível pesquisar no Pinterest: {str(browser_err)}"

    if not screenshot_bytes:
        return f"[ERRO]: Falha ao capturar os pins do Pinterest para '{clean_query}'."

    # Salva screenshot no scratch para histórico
    try:
        scratch_dir = Path("scratch")
        scratch_dir.mkdir(parents=True, exist_ok=True)
        img_path = scratch_dir / "pinterest_latest_search.jpg"
        with open(img_path, "wb") as f:
            f.write(screenshot_bytes)
    except Exception:
        pass

    logger.info(f"[PinterestInspector] Captura dos pins realizada ({len(screenshot_bytes)} bytes). Enviando para análise de design...")

    try:
        client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
        b64_image = base64.b64encode(screenshot_bytes).decode("utf-8")

        prompt = f"""Você é um Diretor de Arte e Especialista em UI/UX de nível internacional.
Analise a captura de tela dos pins de design do Pinterest retornados para a busca: '{clean_query}'.

Forneça um raio-x arquitetural completo de design para transformar a interface do usuário:
1. **Padrões de Design Dominantes nos Pins:**
   - Destaque a composição visual dos 2 ou 3 melhores templates visíveis (ex: Bento Grid assimétrico, Dark Mode Obsidian, Glassmorphism com sombras internas, etc.).
2. **Paleta de Cores Hexadecimal Extraída:**
   - Fundo principal (ex: #090A0F ou #0A0A0F)
   - Cards/Superfícies (ex: rgba(255,255,255,0.03) ou #12121A)
   - Bordas sutis (ex: border-white/[0.08])
   - Cores de Acento/Glow (ex: Violeta neon, Ciano, Esmeralda)
3. **Tipografia e Hierarquia:**
   - Fontes recomendadas (Inter, Geist, Satoshi) e formatação de números/métricas (tabular-nums).
4. **Efeitos Visuais e Bibliotecas Recomendadas:**
   - Recomende componentes do **Canvas UI** (ex: Particle Reveal, Force Field, Glass Object, Flame Wrap, Frost) ou **Aceternity UI** que casam perfeitamente com essa estética.
5. **Blueprint Drop-In para o Projeto do Usuário (Tailwind CSS + React):**
   - Forneça a estrutura de código completa e estilizada pronta para o agente copiar e aplicar nos arquivos do projeto do usuário ({project_path or 'no projeto'}).
"""

        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                ]
            }],
            temperature=0.2
        )

        analysis = response.choices[0].message.content or "Nenhuma análise retornada pela visão multimodal."

        return (
            f"📌 *Inspiração Visual do Pinterest Extraída com Sucesso para:* `{clean_query}`\n"
            f"🔗 *URL da Pesquisa:* {pinterest_url}\n\n"
            f"{analysis}\n\n"
            f"🚀 *Aplicação*: O agente usará este blueprint para atualizar os componentes e estilização do seu projeto."
        )

    except Exception as vision_err:
        logger.error(f"[PinterestInspector] Erro na análise multimodal dos pins: {vision_err}")
        return f"[ERRO NA ANÁLISE DOS PINS]: {str(vision_err)}"


async def search_dribbble_and_analyze_ui(query: str, project_path: Optional[str] = None) -> str:
    """
    Abre um navegador headless (Playwright / Chromium / Edge), pesquisa shots de alta pontuação
    e designs premiados no Dribbble (https://dribbble.com/search/<query>), tira um screenshot limpo
    em alta definição dos melhores templates e utiliza a visão multimodal do Gemini para dissecar
    a estética: paleta de cores (hex), tipografia, microinterações GSAP (parallax/scroll), shaders
    do Canvas UI recomendados e classes Tailwind CSS v4 para aplicar diretamente no projeto.
    """
    clean_query = query.strip()
    encoded_query = urllib.parse.quote(clean_query)
    dribbble_url = f"https://dribbble.com/search/{encoded_query}"

    logger.info(f"[DribbbleInspector] Pesquisando shots de UI/UX no Dribbble para '{clean_query}'...")

    screenshot_bytes: Optional[bytes] = None

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await _launch_browser(p)
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # Navega até o Dribbble
            await page.goto(dribbble_url, wait_until="domcontentloaded", timeout=35000)
            await asyncio.sleep(3.5)

            # Remove popups de cookies, banners de signup ou modais que bloqueiam a visualização dos shots
            try:
                await page.evaluate("""() => {
                    const elements = document.querySelectorAll('[role="dialog"], [data-testid*="modal"], [id*="cookie"], [class*="cookie"], [class*="overlay"], [class*="signup-banner"]');
                    elements.forEach(el => el.remove());
                    document.body.style.overflow = "auto";
                }""")
            except Exception:
                pass

            # Rola levemente para baixo para carregar os shots com boa nitidez
            try:
                await page.evaluate("window.scrollBy(0, 350);")
                await asyncio.sleep(1.2)
            except Exception:
                pass

            screenshot_bytes = await page.screenshot(type="jpeg", quality=80, full_page=False)
            await browser.close()

    except Exception as browser_err:
        logger.error(f"[DribbbleInspector] Falha ao navegar no Dribbble: {browser_err}")
        return f"[ERRO AO ACESSAR DRIBBBLE]: Não foi possível pesquisar no Dribbble: {str(browser_err)}"

    if not screenshot_bytes:
        return f"[ERRO]: Falha ao capturar os shots do Dribbble para '{clean_query}'."

    # Salva screenshot no scratch para histórico
    try:
        scratch_dir = Path("scratch")
        scratch_dir.mkdir(parents=True, exist_ok=True)
        img_path = scratch_dir / "dribbble_latest_search.jpg"
        with open(img_path, "wb") as f:
            f.write(screenshot_bytes)
    except Exception:
        pass

    logger.info(f"[DribbbleInspector] Captura dos shots realizada ({len(screenshot_bytes)} bytes). Enviando para análise de design...")

    try:
        client = AsyncOpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
        b64_image = base64.b64encode(screenshot_bytes).decode("utf-8")

        prompt = f"""Você é um Diretor de Arte Web sênior e Engenheiro Frontend focado em designs de padrão internacional (Awwwards, Linear, Stripe, Apple).
Analise com olhar crítico e cirúrgico a captura de tela dos shots do Dribbble para o termo: '{clean_query}'.

Forneça um raio-x arquitetural completo de design (Zero AI-Slop) para o projeto:
1. **Padrões de Design Dominantes nos Shots Premiados:**
   - Destaque a composição visual dos 2 melhores templates visíveis (ex: Bento Grid assimétrico, Dark Mode Obsidian com superfícies translúcidas, Hero cinematográfico).
2. **Paleta de Cores Hexadecimal Extraída:**
   - Fundo principal (ex: #090A0F)
   - Cards/Superfícies (ex: #11141D ou rgba(255,255,255,0.04))
   - Bordas sutis (ex: border-white/10 ou rgba(255,255,255,0.08))
   - Cores de Acento/Glow (ex: Cyan neon, Violeta profundo, Esmeralda)
3. **Tipografia e Hierarquia:**
   - Fontes recomendadas (Geist, Outfit, Inter, Plus Jakarta Sans), tracking tight e contraste de pesos.
4. **Coreografia de Animação com GSAP (GreenSock):**
   - Efeito parallax suave com ScrollTrigger e scrub
   - Pinned sections com stagger de entrada
   - Microinterações de hover com cursor magnetic
5. **Shaders Recomendados do Canvas UI (https://canvasui.dev/docs):**
   - Indique quais componentes do Canvas UI casam com essa proposta (ex: 'liquid' para fluid pointer, 'force-field' para repulsão, 'decrypt-reveal' para títulos, 'glass-object' para refração 3D ou 'particle-reveal').
6. **Blueprint Drop-In para o Projeto ({project_path or 'no projeto'}):**
   - Estrutura pronta com Tailwind CSS v4, useGSAP e componentes prontos para copiar e colar no código.
"""

        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                ]
            }],
            temperature=0.2
        )

        analysis = response.choices[0].message.content or "Nenhuma análise retornada pela visão multimodal."

        return (
            f"🏀 *Inspiração Visual do Dribbble Extraída com Sucesso para:* `{clean_query}`\n"
            f"🔗 *URL da Pesquisa:* {dribbble_url}\n\n"
            f"{analysis}\n\n"
            f"🚀 *Aplicação*: O agente usará este blueprint para construir os componentes com GSAP, Canvas UI e Tailwind v4!"
        )

    except Exception as vision_err:
        logger.error(f"[DribbbleInspector] Erro na análise multimodal dos shots: {vision_err}")
        return f"[ERRO NA ANÁLISE DOS SHOTS DO DRIBBBLE]: {str(vision_err)}"

