"""Testes unitários do módulo de avaliação científica e métricas do TCC (avaliar.py)."""
import pytest

from og_monitor.avaliar import avaliar_golden_dataset, calcular_metricas, pontuar_pre_filtro


def test_calcular_metricas_matriz_confusao_exata():
    y_true = [True, True, False, False]
    y_pred = [True, False, True, False]
    m = calcular_metricas(y_true, y_pred)
    assert m["vp"] == 1
    assert m["fn"] == 1
    assert m["fp"] == 1
    assert m["vn"] == 1
    assert m["acuracia"] == 0.5
    assert m["precisao"] == 0.5
    assert m["recall"] == 0.5
    assert m["f1"] == 0.5


def test_calcular_metricas_listas_invalidas_dispara_erro():
    with pytest.raises(ValueError):
        calcular_metricas([], [])
    with pytest.raises(ValueError):
        calcular_metricas([True], [True, False])


def test_pontuar_pre_filtro_admite_acidente_real_e_barra_ruido_bolsa():
    acidente = pontuar_pre_filtro(
        "Incêndio atinge plataforma P-53 da Petrobras na Bacia de Campos",
        "Brigada controlou as chamas na unidade offshore.",
        "Sindipetro-NF",
    )
    bolsa = pontuar_pre_filtro(
        "Ações da Petrobras caem 3% na bolsa B3 e Ibovespa recua com dividendos",
        "Cotação e valor de mercado recuam no pregão.",
        "GNews Petrobras",
    )
    assert acidente["admitida"] is True
    assert bolsa["admitida"] is False


def test_avaliar_golden_dataset_demonstra_ganho_arquitetura_hibrida():
    res = avaliar_golden_dataset()
    sql = res["pre_filtro_sql"]
    hib = res["hibrido_sql_ia"]
    assert sql["total"] == 40
    assert sql["recall"] >= 0.95
    # A arquitetura híbrida (SQL + IA) deve ter precisão e F1 superiores ao filtro léxico isolado
    assert hib["precisao"] > sql["precisao"]
    assert hib["f1"] > sql["f1"]
    assert hib["f1"] >= 0.95
