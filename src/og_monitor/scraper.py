"""Resolução de URL e extração do texto da notícia (newspaper4k -> cloudscraper -> resumo do RSS)."""
import logging
import re
import time
import urllib.parse

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

DOMINIOS_MIDIA = ["lh3.googleusercontent.com", "lh4.googleusercontent.com", "yt3.ggpht.com", "googleusercontent.com"]
EXTENSOES_MIDIA = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
DOMINIOS_INVALIDOS = ["google.com", "w3.org", "schema.org"]
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def url_navegavel(url) -> bool:
    """True apenas para URL http(s) válida e que não seja do Google/schemas."""
    try:
        if not url or not isinstance(url, str):
            return False
        p = urllib.parse.urlparse(url)
        if p.scheme not in ("http", "https") or not p.netloc or "." not in p.netloc:
            return False
        return not any(d in p.netloc.lower() for d in DOMINIOS_INVALIDOS)
    except Exception:
        return False


def decodificar_url_google(url: str) -> str:
    """Converte link do Google News na URL real do portal. Retorna a original se falhar.

    O googlenewsdecoder mudou o formato do retorno: versões antigas (0.1.x) usam {"status": ..., "decoded_url": ...}
    e as atuais (0.2.x) usam {"success": ..., "decoded_url": ...}. Aqui as duas são aceitas. Em caso de falha
    (bloqueio/limite do Google), tenta mais uma vez e registra o motivo, para não cair em silêncio no resumo do RSS.
    """
    if not isinstance(url, str) or "news.google.com" not in url:
        return url
    try:
        from googlenewsdecoder import gnewsdecoder
    except ImportError:
        log.warning("googlenewsdecoder não instalado (pip install googlenewsdecoder); mantendo o link do Google News.")
        return url

    motivo = "sem resposta"
    for tentativa in range(3):
        try:
            resultado = gnewsdecoder(url, interval=1)
            if isinstance(resultado, list):  # versões novas aceitam lista de links; aqui é sempre um só
                resultado = resultado[0] if resultado else {}
            ok = resultado.get("success", resultado.get("status"))
            if ok and resultado.get("decoded_url"):
                return resultado["decoded_url"]
            motivo = str(resultado.get("message") or resultado)[:120]
        except Exception as e:  # biblioteca depende de endpoint do Google
            motivo = f"{type(e).__name__}: {str(e)[:100]}"
        time.sleep(2 * (tentativa + 1))
    log.warning("Não foi possível decodificar o link do Google News (%s): %s", url[:70], motivo)
    return url


def resolver_url(url_noticia: str, resumo_html: str) -> str:
    """Decodifica o link do Google News e corrige URLs que apontam para imagem/mídia."""
    url = decodificar_url_google(str(url_noticia or "").strip())
    eh_midia = any(d in url.lower() for d in DOMINIOS_MIDIA) or any(e in url.lower() for e in EXTENSOES_MIDIA)
    if eh_midia and resumo_html:
        for link in re.findall(r'href=["\'](https?://[^"\']+)["\']', str(resumo_html)):
            if not any(d in link for d in DOMINIOS_MIDIA) and not any(e in link.lower() for e in EXTENSOES_MIDIA):
                return decodificar_url_google(link)
    return url


def _via_newspaper(url: str) -> str:
    try:
        from newspaper import Article, Config

        cfg = Config()
        cfg.browser_user_agent = USER_AGENT
        cfg.request_timeout = 15
        artigo = Article(url, language="pt", config=cfg)
        artigo.download()
        artigo.parse()
        texto = artigo.text.strip()
        return texto if len(texto) > 400 else ""
    except Exception as e:
        log.info("newspaper4k falhou (%s): %s", url[:70], str(e)[:80])
        return ""


def _via_cloudscraper(url: str) -> str:
    try:
        import cloudscraper

        scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
        resp = scraper.get(url, timeout=15)
        if resp.status_code != 200:
            log.info("cloudscraper HTTP %s (%s)", resp.status_code, url[:70])
            return ""
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")
        for el in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
            el.extract()
        texto = " ".join(soup.get_text(separator=" ").split())
        return texto if len(texto) > 200 else ""
    except Exception as e:
        log.info("cloudscraper falhou (%s): %s", url[:70], str(e)[:80])
        return ""


def obter_texto(url: str, resumo_html: str):
    """Retorna (texto, fonte_texto) tentando o portal real e caindo para o resumo do RSS."""
    if url_navegavel(url):
        texto = _via_newspaper(url)
        if texto:
            return texto[:8000], "newspaper4k"
        texto = _via_cloudscraper(url)
        if texto:
            return texto[:8000], "beautifulsoup_cloudflare"
        log.warning("Matéria não pôde ser lida (%s); usando só a manchete/resumo do RSS.", url[:80])
    else:
        log.warning("URL da matéria não navegável (%s); usando só a manchete/resumo do RSS.", str(url)[:80])

    resumo = BeautifulSoup(str(resumo_html or ""), "html.parser").get_text(separator=" ")
    return " ".join(resumo.split())[:2000], "rss_feed"