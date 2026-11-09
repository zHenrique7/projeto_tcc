"""Testes unitários de normalização e deduplicação de títulos (classify.py)."""
import pytest

from og_monitor.classify import normalizar_titulo, similaridade


def test_normalizar_titulo_remove_sufixo_portal_e_acentos():
    t1 = "Incêndio atinge plataforma da Petrobras na Bacia de Campos - G1"
    t2 = "Incêndio atinge plataforma da Petrobras na Bacia de Campos | Folha de S.Paulo"
    assert normalizar_titulo(t1) == "incendio atinge plataforma da petrobras na bacia de campos"
    assert normalizar_titulo(t1) == normalizar_titulo(t2)


def test_similaridade_mesma_noticia_em_portais_diferentes():
    a = "Vazamento de óleo é registrado na plataforma P-52 na Bacia de Campos - O Globo"
    b = "Vazamento de óleo é registrado na plataforma P-52 na Bacia de Campos | Petronotícias"
    assert similaridade(a, b) > 0.85


def test_similaridade_plataformas_com_numeros_diferentes_retorna_zero():
    """Regra crítica: molde idêntico mas em instalações de números diferentes NÃO é duplicata."""
    a = "Trabalhador morre em acidente na plataforma P-52 da Petrobras - G1"
    b = "Trabalhador morre em acidente na plataforma P-76 da Petrobras - G1"
    assert similaridade(a, b) == 0.0


def test_similaridade_quantidades_diferentes_no_titulo_retorna_zero():
    a = "Explosão em refinaria deixa 2 feridos no Rio de Janeiro"
    b = "Explosão em refinaria deixa 5 feridos no Rio de Janeiro"
    assert similaridade(a, b) == 0.0


def test_similaridade_assuntos_distintos_retorna_zero():
    a = "Petrobras anuncia novo plano de investimentos para 2027"
    b = "Incêndio atinge usina de etanol no interior de São Paulo"
    assert similaridade(a, b) == 0.0


@pytest.mark.parametrize("a,b", [("", "Título válido"), (None, "Título válido"), ("", "")])
def test_similaridade_entradas_vazias_ou_nulas(a, b):
    assert similaridade(a, b) == 0.0
