"""Acesso ao PostgreSQL."""
import logging
from contextlib import contextmanager

import psycopg2
from sqlalchemy import create_engine

from og_monitor import config

log = logging.getLogger(__name__)


@contextmanager
def get_conn():
    """Conexão psycopg2 com commit automático ao sair sem erro e rollback em caso de exceção."""
    conn = psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_engine():
    """Engine SQLAlchemy (usada para cargas via pandas)."""
    url = (
        f"postgresql+psycopg2://{config.DB_USER}:{config.DB_PASSWORD}"
        f"@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
    )
    return create_engine(url)


# Estrutura da camada raw (landing): o que o Python escreve. Tudo idempotente (IF NOT EXISTS): num banco novo cria as
# tabelas; num banco que já as tem, não faz nada. Os schemas bronze/prata/ouro são criados pelo dbt, mas existem aqui
# para o banco ficar utilizável (e os utilitários não falharem) antes da primeira rodada do dbt.
DDL_SCHEMA = [
    "CREATE SCHEMA IF NOT EXISTS raw",
    "CREATE SCHEMA IF NOT EXISTS bronze",
    "CREATE SCHEMA IF NOT EXISTS prata",
    "CREATE SCHEMA IF NOT EXISTS ouro",
    """
    CREATE TABLE IF NOT EXISTS raw.noticias (
        titulo          text      NOT NULL,
        data_publicacao timestamp NOT NULL,
        fonte           text,
        resumo_html     text,
        url_noticia     text,
        url_fonte       text,
        coletado_em     timestamp NOT NULL DEFAULT now(),
        PRIMARY KEY (titulo, data_publicacao)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw.classificacoes_ia (
        titulo               text      NOT NULL,
        data_publicacao      timestamp NOT NULL,
        url_noticia          text,
        fonte_texto          text,
        relevante            boolean   NOT NULL,
        severidade           text,
        confianca            text,
        motivo               text,
        tipo_evento          text,
        sonda                text,
        instalacao           text,
        poco                 text,
        campo                text,
        municipio            text,
        estado               text,
        operadora_contrato   text,
        operadora_instalacao text,
        vitimas              integer,
        data_fato            date,
        classificado_em      timestamp NOT NULL DEFAULT now(),
        PRIMARY KEY (titulo, data_publicacao)
    )
    """,
    "ALTER TABLE raw.classificacoes_ia ADD COLUMN IF NOT EXISTS confianca text",
    """
    CREATE TABLE IF NOT EXISTS raw.alertas_enviados (
        chave       text PRIMARY KEY,
        titulo      text,
        enviado_em  timestamp NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw.siso_incidentes (
        num_incidente       text,
        dsc_empresa         text,
        nom_instalacao      text,
        dat_primeira_obs    timestamp,
        dsc_ende_instalacao text
    )
    """,
    "CREATE TABLE IF NOT EXISTS raw.dm_ssm_wbs_instalacao (nom_identificacao text, sig_instalacao text)",
    "CREATE TABLE IF NOT EXISTS raw.dm_ssm_wbs_duto (nom_instalacao text)",
]


def garantir_schema() -> None:
    """Cria/ajusta a estrutura que o código e os modelos dbt esperam. Pode rodar quantas vezes quiser."""
    with get_conn() as conn, conn.cursor() as cur:
        for ddl in DDL_SCHEMA:
            cur.execute(ddl)
    # A extensão unaccent é exigida pelo dbt (pré-filtro e cruzamento). Normalmente já existe; se o usuário do banco
    # não tiver permissão para criá-la, só avisa (o dbt falhará com uma mensagem clara se ela realmente faltar).
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    except Exception as e:  # noqa: BLE001
        log.warning("Não foi possível garantir a extensão unaccent (%s). Peça a um administrador: "
                    "CREATE EXTENSION unaccent;", str(e)[:100])
