"""Carga das bases oficiais da ANP (SISO + dimensões) em CSV -> schema raw.

Arquivos esperados em OG_SISO_DIR (separador ; ou ,, UTF-8):
  incidentes.csv      NUM_INCIDENTE, DSC_EMPRESA, NOM_INSTALACAO, DAT_PRIMEIRA_OBS, DSC_ENDE_INSTALACAO
  dm_instalacao.csv   NOM_IDENTIFICACAO, SIG_INSTALACAO
  dm_duto.csv         NOM_INSTALACAO
"""
import logging

import pandas as pd
from sqlalchemy import text

from og_monitor import config
from og_monitor.db import get_engine

log = logging.getLogger(__name__)

ARQUIVOS = [
    ("incidentes.csv", "siso_incidentes",
     ["num_incidente", "dsc_empresa", "nom_instalacao", "dat_primeira_obs", "dsc_ende_instalacao"]),
    ("dm_instalacao.csv", "dm_ssm_wbs_instalacao", ["nom_identificacao", "sig_instalacao"]),
    ("dm_duto.csv", "dm_ssm_wbs_duto", ["nom_instalacao"]),
]


def _detectar_separador(caminho) -> str:
    """Escolhe o separador mais frequente no cabeçalho (o sniffer do pandas erra em CSV de uma coluna)."""
    with open(caminho, encoding="utf-8-sig") as f:
        cabecalho = f.readline()
    candidatos = [";", ",", "\t", "|"]
    melhor = max(candidatos, key=cabecalho.count)
    return melhor if cabecalho.count(melhor) > 0 else ";"


def _converter_data(coluna: pd.Series) -> pd.Series:
    """Datas ISO (2026-10-25 14:30) são lidas como estão; as demais (25/10/2026) são lidas como dia/mês/ano."""
    datas = pd.to_datetime(coluna, errors="coerce", format="ISO8601")
    resto = datas.isna() & coluna.notna()
    if resto.any():
        datas[resto] = pd.to_datetime(coluna[resto], dayfirst=True, errors="coerce")
    return datas


def carregar_siso() -> dict:
    """Recarrega (TRUNCATE + INSERT) cada tabela cujo CSV existir. Retorna {tabela: linhas}."""
    engine = get_engine()
    resumo = {}
    for arquivo, tabela, colunas in ARQUIVOS:
        caminho = config.SISO_DIR / arquivo
        if not caminho.exists():
            log.warning("⚠️ %s não encontrado em %s - tabela raw.%s mantida como está.", arquivo, config.SISO_DIR, tabela)
            continue

        df = pd.read_csv(caminho, sep=_detectar_separador(caminho), encoding="utf-8-sig", dtype=str)
        df.columns = [c.strip().lower() for c in df.columns]
        faltando = [c for c in colunas if c not in df.columns]
        if faltando:
            raise ValueError(f"{arquivo}: colunas ausentes {faltando}. Encontradas: {list(df.columns)}")
        df = df[colunas].copy()
        if "dat_primeira_obs" in df.columns:
            df["dat_primeira_obs"] = _converter_data(df["dat_primeira_obs"])

        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE raw.{tabela}"))
            df.to_sql(tabela, con=conn, schema="raw", if_exists="append", index=False, method="multi", chunksize=1000)
        resumo[tabela] = len(df)
        log.info("🏛️ raw.%s recarregada com %d linhas", tabela, len(df))

    with engine.connect() as conn:
        n = conn.execute(text("SELECT count(*) FROM raw.siso_incidentes")).scalar()
    if n == 0:
        log.warning("🚨 raw.siso_incidentes está vazia: todos os incidentes sairão como 'Não Comunicado'.")
    elif n < config.SISO_MIN_LINHAS:
        log.warning("⚠️ raw.siso_incidentes tem só %d linhas (esperado ao menos %d): o cruzamento com o SISO não é "
                    "confiável. Confira os CSVs em %s.", n, config.SISO_MIN_LINHAS, config.SISO_DIR)
    return resumo
