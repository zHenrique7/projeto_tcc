"""Zera as tabelas de notícias para um teste completo do pipeline, do zero.

Esvazia (TRUNCATE): raw.noticias, raw.classificacoes_ia e raw.alertas_enviados.
NÃO mexe em raw.siso_incidentes, raw.dm_ssm_wbs_instalacao e raw.dm_ssm_wbs_duto (o pipeline as recarrega dos CSVs
a cada execução) nem na estrutura das tabelas. As tabelas do dbt (prata e ouro) são refeitas na próxima execução.

Antes de apagar, copia as 3 tabelas para um schema de backup (backup_AAAAMMDD_HHMMSS). Sem --executar, só mostra
quantas linhas existem.

Atenção: depois de zerar, o pipeline vai reclassificar TUDO (gasta tokens e tempo da Groq) e, como raw.alertas_enviados
fica vazia, vai ENVIAR E-MAIL de todos os incidentes aprovados. Para testar sem e-mail, deixe ALERTA_DESTINATARIOS vazio
no .env (o pipeline só registra no log).

Uso (raiz do projeto, venv ativo):
    python -m og_monitor.limpar_banco              # simulação
    python -m og_monitor.limpar_banco --executar   # faz backup e zera
    python -m og_monitor.limpar_banco --executar --sem-backup
"""
import argparse
import logging
from datetime import datetime

from og_monitor.db import get_conn

log = logging.getLogger(__name__)

TABELAS = ["noticias", "classificacoes_ia", "alertas_enviados"]


def limpar(executar: bool, backup: bool) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        for t in TABELAS:
            cur.execute(f"SELECT count(*) FROM raw.{t}")
            log.info("   raw.%-20s %6d linhas", t, cur.fetchone()[0])
        if not executar:
            log.info("🔎 Simulação: nada foi apagado. Use --executar para zerar essas tabelas.")
            return

        if backup:
            schema = datetime.now().strftime("backup_%Y%m%d_%H%M%S")
            cur.execute(f"CREATE SCHEMA {schema}")
            for t in TABELAS:
                cur.execute(f"CREATE TABLE {schema}.{t} AS SELECT * FROM raw.{t}")
            log.info("💾 Backup criado no schema %s", schema)

        cur.execute("TRUNCATE TABLE " + ", ".join(f"raw.{t}" for t in TABELAS))
    log.info("🧹 Tabelas zeradas. Agora rode: python -m og_monitor.pipeline")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--executar", action="store_true", help="apaga de fato (sem isso, só simula)")
    ap.add_argument("--sem-backup", action="store_true", help="não copia as tabelas antes de apagar")
    args = ap.parse_args()
    limpar(args.executar, not args.sem_backup)


if __name__ == "__main__":
    main()
