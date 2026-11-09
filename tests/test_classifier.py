"""Testes unitários do classificador IA: sanitização do JSON, KeyPool e prompt (classifier.py)."""
from datetime import date

import pytest

from og_monitor.classifier import KeyPool, montar_prompt_usuario, normalizar_resultado


def test_keypool_rodizio_circular():
    pool = KeyPool(["key_1", "key_2", "key_3"])
    assert pool.atual == "key_1"
    assert pool.girar() == 2
    assert pool.atual == "key_2"
    assert pool.girar() == 3
    assert pool.atual == "key_3"
    assert pool.girar() == 1
    assert pool.atual == "key_1"


def test_keypool_sem_chaves_dispara_erro():
    with pytest.raises(RuntimeError, match="Nenhuma chave Groq configurada"):
        KeyPool([])


def test_normalizar_resultado_relevante_completo_e_sem_acentos():
    bruto = {
        "relevante": "true",
        "severidade": "critico",  # sem acento e minúsculo
        "confianca": "media",     # sem acento
        "motivo": "Fatalidade operacional na plataforma P-52.",
        "tipo_evento": "Fatalidade",
        "instalacao": "P-52",
        "sonda": "Não informado",
        "poco": "null",
        "campo": "Bacia de Campos",
        "municipio": "Macaé",
        "estado": "rj",
        "operadora_contrato": "Petrobras",
        "operadora_instalacao": "n/a",
        "vitimas": "1",
        "data_fato": "2026-10-25",
    }
    res = normalizar_resultado(bruto)
    assert res["relevante"] is True
    assert res["severidade"] == "CRÍTICO"
    assert res["confianca"] == "média"
    assert res["instalacao"] == "P-52"
    assert res["sonda"] is None
    assert res["poco"] is None
    assert res["operadora_instalacao"] is None
    assert res["estado"] == "RJ"
    assert res["vitimas"] == 1
    assert res["data_fato"] == date(2026, 10, 25)


def test_normalizar_resultado_fallback_conservador_quando_severidade_ou_confianca_invalida():
    res = normalizar_resultado({
        "relevante": True,
        "severidade": "GRAVISSIMO",  # fora do domínio
        "confianca": "certeza",      # fora do domínio
        "motivo": "Vazamento confirmado.",
    })
    assert res["severidade"] == "ALTO"
    assert res["confianca"] == "baixa"


def test_normalizar_resultado_irrelevante_limpa_todos_os_campos_extraidos():
    res = normalizar_resultado({
        "relevante": False,
        "severidade": "ALTO",
        "confianca": "alta",
        "motivo": "Notícia de mercado financeiro.",
        "instalacao": "REDUC",
        "estado": "RJ",
        "vitimas": 2,
        "data_fato": "2026-10-25",
    })
    assert res["relevante"] is False
    assert res["severidade"] is None
    assert res["confianca"] is None
    assert res["instalacao"] is None
    assert res["estado"] is None
    assert res["vitimas"] is None
    assert res["data_fato"] is None
    assert res["motivo"] == "Notícia de mercado financeiro."


def test_normalizar_resultado_uf_e_data_invalidas_viram_none():
    res = normalizar_resultado({
        "relevante": True,
        "severidade": "MÉDIO",
        "confianca": "alta",
        "estado": "Rio de Janeiro",  # não é sigla de 2 letras
        "vitimas": -3,               # negativo inválido
        "data_fato": "25/10/2026",   # fora do padrão ISO YYYY-MM-DD
    })
    assert res["estado"] is None
    assert res["vitimas"] is None
    assert res["data_fato"] is None


def test_montar_prompt_usuario_inclui_aviso_quando_fonte_eh_rss():
    prompt_rss = montar_prompt_usuario("Título", "2026-10-25", "https://site.com", "rss_feed", "Resumo curto")
    prompt_full = montar_prompt_usuario("Título", "2026-10-25", "https://site.com", "newspaper4k", "Texto completo")
    assert "ATENÇÃO: não foi possível ler a matéria completa" in prompt_rss
    assert "ATENÇÃO: não foi possível ler a matéria completa" not in prompt_full
