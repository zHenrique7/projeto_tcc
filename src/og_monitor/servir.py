"""Mantém o pipeline agendado no Prefect.

Uso (deixe este processo rodando; ele dispara o flow nos horários abaixo):
    python -m og_monitor.servir

Requisito: SQLAlchemy 2.0.x na venv (`pip install -c constraints.txt -r requirements.txt` ou
`pip install "sqlalchemy[asyncio]>=2.0,<2.1"`). Com o SQLAlchemy 2.1 o agendador do servidor Prefect falha ao criar as
execuções ("Can't evaluate bulk DML statement") e nada roda no horário.

Variáveis opcionais no .env:
    AGENDA_CRON       expressão cron (padrão: 3x ao dia, 07h, 13h e 18h)
    AGENDA_TIMEZONE   fuso horário (padrão: America/Sao_Paulo)
"""
import logging
import os

from prefect.schedules import Cron

from og_monitor.pipeline import og_incident_pipeline

AGENDA_CRON = os.getenv("AGENDA_CRON", "0 7,13,18 * * *")
AGENDA_TIMEZONE = os.getenv("AGENDA_TIMEZONE", "America/Sao_Paulo")


def main() -> None:
    logging.getLogger("og_monitor").setLevel(logging.INFO)
    og_incident_pipeline.serve(
        name="og-incident-pipeline-agendado",
        schedule=Cron(AGENDA_CRON, timezone=AGENDA_TIMEZONE),
        # nunca duas execuções ao mesmo tempo: a Groq tem limite de tokens por minuto
        global_limit=1,
        tags=["og-monitor", "producao"],
    )


if __name__ == "__main__":
    main()
