"""Testes unitários de leitura e tratamento dos CSVs do SISO/ANP (siso.py)."""
import pandas as pd

from og_monitor.siso import _converter_data, _detectar_separador


def test_detectar_separador_ponto_e_virgula(tmp_path):
    arq = tmp_path / "incidentes.csv"
    arq.write_text("NUM_INCIDENTE;DSC_EMPRESA;NOM_INSTALACAO\n1;PETROBRAS;P-52\n", encoding="utf-8")
    assert _detectar_separador(arq, "utf-8") == ";"


def test_detectar_separador_virgula(tmp_path):
    arq = tmp_path / "dm_instalacao.csv"
    arq.write_text("NOM_IDENTIFICACAO,SIG_INSTALACAO\nPLATAFORMA 52,P-52\n", encoding="utf-8")
    assert _detectar_separador(arq, "utf-8") == ","


def test_detectar_separador_coluna_unica_usa_fallback(tmp_path):
    arq = tmp_path / "dm_duto.csv"
    arq.write_text("NOM_INSTALACAO\nGASBOL\n", encoding="utf-8")
    assert _detectar_separador(arq, "utf-8") == ";"


def test_converter_data_aceita_iso_e_padrao_brasileiro():
    s = pd.Series(["2026-10-25 14:30:00", "26/10/2026", "invalida", None])
    conv = _converter_data(s)
    assert conv.iloc[0] == pd.Timestamp(2026, 10, 25, 14, 30, 0)
    assert conv.iloc[1] == pd.Timestamp(2026, 10, 26, 0, 0, 0)
    assert pd.isna(conv.iloc[2])
    assert pd.isna(conv.iloc[3])
