import httpx
from bs4 import BeautifulSoup
import urllib.parse
from typing import Optional, List, Dict

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
}

async def fetch_webpage_content(url: str, max_chars: int = 4000) -> str:
    """Baixa uma página web e extrai o texto principal limpo de tags desnecessárias."""
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return f"[ERRO AO ACESSAR PÁGINA]: Código HTTP {resp.status_code} ao acessar {url}"

            html = resp.text
            soup = BeautifulSoup(html, "html.parser")

            # Remove elementos irrelevantes
            for tag in soup.find_all(["nav", "footer", "script", "style", "header", "svg", "noscript", "aside"]):
                tag.decompose()

            # Tenta pegar a tag principal do conteúdo
            main_content = (
                soup.find("article") or
                soup.find("main") or
                soup.find("div", {"role": "main"}) or
                soup.find("div", class_=lambda c: c and any(k in str(c).lower() for k in ["content", "markdown", "doc", "page"])) or
                soup.body
            )

            if not main_content:
                return "[AVISO]: Nenhum conteúdo de texto identificável foi encontrado na página."

            # Extrai texto preservando quebras de linha importantes
            lines = []
            for elem in main_content.find_all(["h1", "h2", "h3", "h4", "p", "pre", "code", "li"]):
                txt = elem.get_text().strip()
                if not txt:
                    continue
                tag_name = elem.name
                if tag_name in ["h1", "h2"]:
                    lines.append(f"\n### {txt}\n")
                elif tag_name in ["h3", "h4"]:
                    lines.append(f"\n#### {txt}\n")
                elif tag_name == "li":
                    lines.append(f"- {txt}")
                elif tag_name in ["pre", "code"]:
                    lines.append(f"```\n{txt}\n```")
                else:
                    lines.append(txt)

            extracted = "\n".join(lines).strip()
            if not extracted:
                extracted = " ".join(main_content.get_text().split())

            if len(extracted) > max_chars:
                extracted = extracted[:max_chars] + f"\n\n[...conteúdo adicional da documentação truncado para caber no contexto...]"

            return f"📄 [DOCUMENTAÇÃO EXTRAÍDA DE {url}]:\n\n{extracted}"
    except Exception as e:
        return f"[ERRO AO EXTRAIR DOCUMENTAÇÃO DE {url}]: {str(e)}"

async def search_technical_docs(query: str, max_results: int = 5) -> str:
    """Busca documentações técnicas, bibliotecas ou soluções na web via DuckDuckGo."""
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return f"[ERRO NA BUSCA]: Status {resp.status_code}"

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []

            for body in soup.find_all("div", class_="result__body")[:max_results]:
                url_elem = body.find("a", class_="result__url")
                snippet_elem = body.find("a", class_="result__snippet")
                title_elem = body.find("h2", class_="result__title") or body.find("a", class_="result__title")

                title = title_elem.get_text().strip() if title_elem else "Sem título"
                snippet = snippet_elem.get_text().strip() if snippet_elem else ""

                # Decodifica o link real
                raw_href = url_elem.get("href", "") if url_elem else ""
                dest_url = raw_href
                if "uddg=" in raw_href:
                    try:
                        parsed = urllib.parse.urlparse(raw_href)
                        dest_url = urllib.parse.parse_qs(parsed.query).get("uddg", [raw_href])[0]
                    except Exception:
                        pass

                if not dest_url.startswith("http"):
                    dest_url = f"https://{dest_url.lstrip('/')}"

                results.append(f"• *{title}*\n  URL: {dest_url}\n  Resumo: {snippet}\n")

            if not results:
                return f"Nenhum resultado encontrado para a busca: '{query}'."

            return f"🔍 [RESULTADOS DE PESQUISA ONLINE PARA: '{query}']:\n\n" + "\n".join(results) + "\n💡 Dica: Você pode usar 'fetch_webpage_content' com a URL desejada para ler o artigo completo."
    except Exception as e:
        return f"[ERRO AO PESQUISAR ONLINE]: {str(e)}"

async def search_and_read_documentation(query: str = "", url: str = "") -> str:
    """
    Pesquisa documentações técnicas online ou lê diretamente o conteúdo de uma URL de documentação.
    """
    if url:
        return await fetch_webpage_content(url)
    elif query:
        return await search_technical_docs(query)
    else:
        return "[ERRO]: Forneça um termo de busca ('query') ou uma URL direta ('url')."
