"""Script para fundir os dados do backup do Carlos com a base local, ignorando duplicatas (ON CONFLICT DO NOTHING), e rodar o dbt pos_ia para atualizar a camada ouro."""
import os
import sys
import subprocess
import logging
from pathlib import Path
import psycopg2

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
sys.path.insert(0, str(BASE_DIR.parent))

from og_monitor import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fundir_dados")

BACKUP_FILE = Path(r"C:\Users\psvox\.gemini\antigravity\brain\7564ea10-9f90-4f5b-bbb2-4472c76a9861\.user_uploaded\media_1794426783848_1a3b68d2.sql")


def parse_val(v):
    if v == r"\N" or v is None:
        return None
    return v


def main():
    if not BACKUP_FILE.exists():
        log.error("Arquivo de backup não encontrado: %s", BACKUP_FILE)
        return

    conn = psycopg2.connect(
        dbname=os.getenv("OG_DB_NAME", "db_incidentes"),
        user=os.getenv("OG_DB_USER", "postgres"),
        password=os.getenv("OG_DB_PASSWORD", "postgres"),
        host="localhost",
        port=5432,
    )
    conn.autocommit = False

    log.info("Lendo arquivo de backup e fundindo tabelas...")

    with open(BACKUP_FILE, "r", encoding="utf-8", errors="replace") as f:
        in_table = None
        cols = []
        counts = {"noticias": 0, "classificacoes_ia": 0, "siso_incidentes": 0}

        cur = conn.cursor()

        for line in f:
            line_str = line.rstrip("\r\n")
            if line_str.startswith("COPY "):
                parts = line_str.split(" ", 2)
                in_table = parts[1]  # ex: raw.noticias
                header_part = line_str[line_str.find("(") + 1 : line_str.find(")")]
                cols = [c.strip() for c in header_part.split(",")]
                continue
            elif in_table and line_str == r"\.":
                in_table = None
                cols = []
                continue
            elif in_table:
                vals = [parse_val(x) for x in line_str.split("\t")]
                row_dict = dict(zip(cols, vals))

                if in_table == "raw.noticias":
                    cur.execute(
                        """
                        INSERT INTO raw.noticias (titulo, data_publicacao, fonte, resumo_html, url_noticia, url_fonte, coletado_em)
                        VALUES (%(titulo)s, %(data_publicacao)s, %(fonte)s, %(resumo_html)s, %(url_noticia)s, %(url_fonte)s, %(coletado_em)s)
                        ON CONFLICT (titulo, data_publicacao) DO NOTHING;
                        """,
                        row_dict,
                    )
                    counts["noticias"] += 1

                elif in_table == "raw.classificacoes_ia":
                    cur.execute(
                        """
                        INSERT INTO raw.classificacoes_ia (
                            titulo, data_publicacao, url_noticia, fonte_texto, relevante, severidade, confianca,
                            motivo, tipo_evento, sonda, instalacao, poco, campo, municipio, estado,
                            operadora_contrato, operadora_instalacao, vitimas, data_fato, classificado_em
                        )
                        VALUES (
                            %(titulo)s, %(data_publicacao)s, %(url_noticia)s, %(fonte_texto)s, %(relevante)s, %(severidade)s, %(confianca)s,
                            %(motivo)s, %(tipo_evento)s, %(sonda)s, %(instalacao)s, %(poco)s, %(campo)s, %(municipio)s, %(estado)s,
                            %(operadora_contrato)s, %(operadora_instalacao)s, %(vitimas)s, %(data_fato)s, %(classificado_em)s
                        )
                        ON CONFLICT (titulo, data_publicacao) DO NOTHING;
                        """,
                        row_dict,
                    )
                    counts["classificacoes_ia"] += 1

                elif in_table == "raw.siso_incidentes":
                    # Já temos 30.744 no SISO, mas insere se faltar algum
                    cur.execute(
                        """
                        INSERT INTO raw.siso_incidentes (
                            num_incidente, dsc_empresa, nom_instalacao, dat_primeira_obs, dsc_ende_instalacao, dsc_incidente
                        )
                        VALUES (
                            %(num_incidente)s, %(dsc_empresa)s, %(nom_instalacao)s, %(dat_primeira_obs)s, %(dsc_ende_instalacao)s, %(dsc_incidente)s
                        )
                        ON CONFLICT DO NOTHING;
                        """,
                        row_dict,
                    )
                    counts["siso_incidentes"] += 1

    conn.commit()
    log.info("Fusão de dados concluída! Linhas processadas: %s", counts)

    # Verifica quantas classificações relevantes temos agora
    cur.execute("SELECT COUNT(*) FROM raw.classificacoes_ia WHERE relevante = true;")
    total_relevantes = cur.fetchone()[0]
    log.info("Total de incidentes relevantes no banco agora: %d", total_relevantes)

    # Roda dbt pos_ia para atualizar ouro.fato_incidente
    log.info("Compilando camada ouro no dbt...")
    dbt_exe = sys.executable.replace("python.exe", "dbt.exe")
    args = [
        dbt_exe, "run",
        "--project-dir", str(config.DBT_DIR),
        "--profiles-dir", str(config.DBT_DIR),
        "--select", "tag:pos_ia",
    ]
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1", "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"},
    )
    if proc.returncode != 0:
        log.error("Erro dbt:\n%s", proc.stdout + proc.stderr)
        return

    cur.execute("SELECT COUNT(*) FROM ouro.fato_incidente;")
    total_fatos = cur.fetchone()[0]
    log.info("=== SUCESSO! TOTAL DE INCIDENTES NA TABELA FATO: %d ===", total_fatos)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
