"""Testes unitários de validação e resolução de URLs do scraper (scraper.py)."""
import pytest

from og_monitor.scraper import resolver_url, url_navegavel


@pytest.mark.parametrize(
    "url,esperado",
    [
        ("https://petronoticias.com.br/acidente-em-plataforma/", True),
        ("http://g1.globo.com/rj/noticia.ghtml", True),
        ("https://news.google.com/rss/articles/CBMi123", False),
        ("https://www.w3.org/2005/Atom", False),
        ("https://schema.org/NewsArticle", False),
        ("ftp://arquivos.exemplo.com/dados.csv", False),
        ("", False),
        (None, False),
    ],
)
def test_url_navegavel(url, esperado):
    assert url_navegavel(url) is esperado


def test_resolver_url_substitui_link_de_imagem_pelo_href_do_resumo():
    url_imagem = "https://lh3.googleusercontent.com/proxy/imagem_thumb.jpg"
    resumo_html = (
        '<img src="https://lh3.googleusercontent.com/proxy/imagem_thumb.jpg" />'
        '<a href="https://fup.org.br/noticia-real-sobre-plataforma/">Leia mais</a>'
    )
    assert resolver_url(url_imagem, resumo_html) == "https://fup.org.br/noticia-real-sobre-plataforma/"


def test_resolver_url_mantem_url_valida_quando_nao_eh_midia():
    url = "https://sindipetronf.org.br/incendio-em-sonda/"
    assert resolver_url(url, "<p>Resumo qualquer</p>") == url
