"""Script para migrar todos os dados da base local (db_incidentes) para o Supabase (PostgreSQL na nuvem)."""
import os
import sys
import subprocess
import logging
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_batch

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
sys.path.insert(0, str(BASE_DIR.parent))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", encoding="utf-8")

from og_monitor import config
from og_monitor.db import garantir_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("migrar_supabase")

TABELAS_RAW = [
    "dm_ssm_wbs_duto",
    "dm_ssm_wbs_instalacao",
    "noticias",
    "classificacoes_ia",
    "siso_incidentes",
    "alertas_enviados",
]


def migrar():
    log.info("=== 1. Garantindo schemas e tabelas no Supabase ===")
    garantir_schema()

    log.info("=== 2. Conectando aos bancos ===")
    conn_local = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="db_incidentes",
        user="postgres",
        password="postgres",
    )
    conn_supa = psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
    )
    conn_supa.autocommit = False

    cur_local = conn_local.cursor()
    cur_supa = conn_supa.cursor()

    for tab in TABELAS_RAW:
        log.info("Migrando raw.%s...", tab)
        cur_local.execute(f"SELECT * FROM raw.{tab};")
        rows = cur_local.fetchall()
        if not rows:
            log.info("  -> Tabela vazia, pulando.")
            continue

        cols = [desc[0] for desc in cur_local.description]
        col_names = ", ".join(cols)
        col_placeholders = ", ".join(["%s"] * len(cols))

        # Trunca ou substitui na nuvem
        cur_supa.execute(f"TRUNCATE TABLE raw.{tab} CASCADE;")
        query = f"INSERT INTO raw.{tab} ({col_names}) VALUES ({col_placeholders});"

        execute_batch(cur_supa, query, rows, page_size=2000)
        conn_supa.commit()
        log.info("  -> %d linhas migradas com sucesso para raw.%s!", len(rows), tab)

    cur_local.close()
    conn_local.close()
    cur_supa.close()
    conn_supa.close()

    log.info("=== 3. Executando dbt build contra o Supabase ===")
    dbt_exe = sys.executable.replace("python.exe", "dbt.exe")
    args = [
        dbt_exe, "build",
        "--project-dir", str(config.DBT_DIR),
        "--profiles-dir", str(config.DBT_DIR),
        "--select", "tag:pos_ia",
    ]
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
        "OG_DB_HOST": config.DB_HOST,
        "OG_DB_PORT": str(config.DB_PORT),
        "OG_DB_NAME": config.DB_NAME,
        "OG_DB_USER": config.DB_USER,
        "OG_DB_PASSWORD": config.DB_PASSWORD,
    }
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if proc.returncode != 0:
        log.error("Erro dbt:\n%s\n%s", proc.stdout, proc.stderr)
        raise RuntimeError("dbt build falhou no Supabase")

    log.info("=== 4. Verificando camada ouro no Supabase ===")
    conn_supa = psycopg2.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
    )
    cur = conn_supa.cursor()
    cur.execute("SELECT COUNT(*) FROM ouro.fato_incidente;")
    total = cur.fetchone()[0]
    log.info("=== SUCESSO! TOTAL DE INCIDENTES NO SUPABASE: %d ===", total)
    conn_supa.close()


if __name__ == "__main__":
    migrar()
