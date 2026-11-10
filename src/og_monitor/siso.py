"""Carga das bases oficiais da ANP (SISO + dimensões) em CSV -> schema raw.

Os arquivos ficam em OG_SISO_DIR. Aceita UTF-8 (com ou sem BOM) ou Latin-1/Windows-1252 (a exportação do SISO da ANP
vem em Latin-1), separador ; , tab ou |, e nomes de coluna com ou sem acento, maiúsculos ou minúsculos.

  incidentes.csv        exportação da ANP (Numero, Empresa, Instalacao, Data_da_primeira_observacao,
                        Hora_da_primeira_observacao, Endereco...) ou o formato simples
                        (NUM_INCIDENTE, DSC_EMPRESA, NOM_INSTALACAO, DAT_PRIMEIRA_OBS, DSC_ENDE_INSTALACAO)
  dm_instalacao.csv     NOM_IDENTIFICACAO, SIG_INSTALACAO
  dados-abertos-plataformas-operacao.csv   (opcional) [NOME DA INSTALAÇÃO], [SIGLA DA INSTALAÇÃO]: as plataformas em
                        operação (dados abertos da ANP) são SOMADAS a dm_instalacao.csv
  dm_duto.csv           NOM_INSTALACAO

Os demais CSVs da pasta (situação de poços, campos) não são carregados.
"""
import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from og_monitor import config
from og_monitor.db import get_engine

log = logging.getLogger(__name__)

# coluna de destino -> nomes aceitos no CSV (já normalizados: minúsculas, sem acento, sem colchetes, com "_")
ALIASES = {
    "num_incidente": ["num_incidente", "numero"],
    "dsc_empresa": ["dsc_empresa", "empresa"],
    "nom_instalacao": ["nom_instalacao", "instalacao"],
    "dat_primeira_obs": ["dat_primeira_obs", "data_da_primeira_observacao"],
    "dsc_ende_instalacao": ["dsc_ende_instalacao", "endereco"],
    "nom_identificacao": ["nom_identificacao", "nome_da_instalacao"],
    "sig_instalacao": ["sig_instalacao", "sigla_da_instalacao"],
}
# a exportação da ANP separa a data e a hora da primeira observação em duas colunas
COLUNA_HORA = {"dat_primeira_obs": "hora_da_primeira_observacao"}

# (tabela, arquivos que alimentam a tabela, colunas)
ARQUIVOS = [
    ("siso_incidentes", ["incidentes.csv"],
     ["num_incidente", "dsc_empresa", "nom_instalacao", "dat_primeira_obs", "dsc_ende_instalacao"]),
    ("dm_ssm_wbs_instalacao", ["dm_instalacao.csv", "dados-abertos-plataformas-operacao.csv"],
     ["nom_identificacao", "sig_instalacao"]),
    ("dm_ssm_wbs_duto", ["dm_duto.csv"], ["nom_instalacao"]),
]


def _normalizar_coluna(nome: str) -> str:
    s = unicodedata.normalize("NFKD", str(nome)).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def _detectar_encoding(caminho) -> str:
    """UTF-8 se o arquivo inteiro decodifica como UTF-8; senão Windows-1252 (Latin-1 do Excel/ANP)."""
    dados = Path(caminho).read_bytes()
    try:
        dados.decode("utf-8-sig")
        return "utf-8-sig"
    except UnicodeDecodeError:
        pass
    try:
        dados.decode("cp1252")
        return "cp1252"
    except UnicodeDecodeError:
        return "latin-1"


def _detectar_separador(caminho, encoding: str) -> str:
    """Escolhe o separador mais frequente no cabeçalho (o sniffer do pandas erra em CSV de uma coluna)."""
    with open(caminho, encoding=encoding) as f:
        cabecalho = f.readline()
    candidatos = [";", ",", "\t", "|"]
    melhor = max(candidatos, key=cabecalho.count)
    return melhor if cabecalho.count(melhor) > 0 else ";"


def _converter_data(coluna: pd.Series) -> pd.Series:
    """ISO (2026-10-25 14:30) é lido como está; dia-mês-ano (26-06-2013 18:20 ou 25/10/2026) por formatos explícitos."""
    datas = pd.to_datetime(coluna, errors="coerce", format="ISO8601")
    for fmt in ("%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d-%m-%Y", "%d/%m/%Y"):
        resto = datas.isna() & coluna.notna()
        if not resto.any():
            break
        datas[resto] = pd.to_datetime(coluna[resto], format=fmt, errors="coerce")
    return datas


def _ler_csv(caminho) -> pd.DataFrame:
    encoding = _detectar_encoding(caminho)
    df = pd.read_csv(caminho, sep=_detectar_separador(caminho, encoding), encoding=encoding, dtype=str)
    df.columns = [_normalizar_coluna(c) for c in df.columns]
    return df


def _mapear(df: pd.DataFrame, colunas: list, arquivo: str) -> pd.DataFrame:
    """Devolve só as colunas de destino, renomeadas a partir dos nomes aceitos (com data+hora juntas, se for o caso)."""
    saida = {}
    for destino in colunas:
        origem = next((a for a in ALIASES.get(destino, [destino]) if a in df.columns), None)
        if origem is None:
            raise ValueError(f"{arquivo}: coluna '{destino}' não encontrada (aceitos: {ALIASES.get(destino, [destino])}). "
                             f"Encontradas: {list(df.columns)}")
        serie = df[origem].str.strip()
        hora = COLUNA_HORA.get(destino)
        if hora and hora in df.columns:
            serie = (serie + " " + df[hora].fillna("").str.strip()).str.strip()
        saida[destino] = serie
    return pd.DataFrame(saida)


def preparar_tabela(arquivos: list, colunas: list, pasta: Path) -> tuple[pd.DataFrame | None, list]:
    """Lê e junta os CSVs que existirem. Devolve (DataFrame pronto para gravar ou None, arquivos que faltaram)."""
    partes, faltando = [], []
    for arquivo in arquivos:
        caminho = pasta / arquivo
        if not caminho.exists():
            faltando.append(arquivo)
            continue
        partes.append(_mapear(_ler_csv(caminho), colunas, arquivo))
    if not partes:
        return None, faltando
    df = pd.concat(partes, ignore_index=True).drop_duplicates()
    if "dat_primeira_obs" in df.columns:
        df["dat_primeira_obs"] = _converter_data(df["dat_primeira_obs"])
        invalidas = int(df["dat_primeira_obs"].isna().sum())
        if invalidas:
            log.warning("⚠️ %d linha(s) do SISO com data da primeira observação ilegível: nunca casarão no cruzamento.",
                        invalidas)
    return df, faltando


def carregar_siso() -> dict:
    """Recarrega (TRUNCATE + INSERT) cada tabela cujos CSVs existirem. Retorna {tabela: linhas}."""
    engine = get_engine()
    resumo = {}
    for tabela, arquivos, colunas in ARQUIVOS:
        df, faltando = preparar_tabela(arquivos, colunas, config.SISO_DIR)
        for arquivo in faltando:
            log.warning("⚠️ %s não encontrado em %s.", arquivo, config.SISO_DIR)
        if df is None:
            log.warning("⚠️ Nenhum CSV para raw.%s: tabela mantida como está.", tabela)
            continue

        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE raw.{tabela}"))
            df.to_sql(tabela, con=conn, schema="raw", if_exists="append", index=False, method="multi", chunksize=1000)
        resumo[tabela] = len(df)
        log.info("🏛️ raw.%s recarregada com %d linhas", tabela, len(df))

    with engine.connect() as conn:
        n, ultima = conn.execute(text("SELECT count(*), max(dat_primeira_obs) FROM raw.siso_incidentes")).one()
    if n == 0:
        log.warning("🚨 raw.siso_incidentes está vazia: todos os incidentes sairão como 'Não Comunicado'.")
    elif n < config.SISO_MIN_LINHAS:
        log.warning("⚠️ raw.siso_incidentes tem só %d linhas (esperado ao menos %d): o cruzamento com o SISO não é "
                    "confiável. Confira os CSVs em %s.", n, config.SISO_MIN_LINHAS, config.SISO_DIR)
    if ultima is not None:
        dias = (datetime.now() - ultima).days
        if dias > config.SISO_MAX_DEFASAGEM_DIAS:
            log.warning("🚨 O incidente mais recente do SISO é de %s (%d dias atrás; limite %d). Notícias recentes não têm "
                        "como casar: baixe um incidentes.csv novo no portal da ANP e substitua o arquivo em %s.",
                        ultima.date(), dias, config.SISO_MAX_DEFASAGEM_DIAS, config.SISO_DIR)
    return resumo
