"""Flow Prefect do Monitor de Incidentes P&G.

Coleta (Python) -> raw -> dbt (filtro/histórico) -> Groq (Python) -> dbt (marts + cruzamento SISO) -> alertas.

Mesma topologia do antigo DAG do Airflow:

    coletar_noticias -> dbt_pre_ia -> classificar_com_ia --\
    carregar_siso -----------------------------------------+-> dbt_pos_ia -> enviar_alertas

(preparar_banco roda antes de coletar_noticias: aplica as migrações de schema idempotentes.)
"""
import logging
import os
import subprocess

from prefect import flow, get_run_logger, task

from og_monitor import config

# O Prefect só mostra no painel os logs do og_monitor se o logger estiver em INFO (por padrão herdaria WARNING
# e as linhas "[001/40] ✅ ..." de cada notícia ficariam escondidas).
logging.getLogger("og_monitor").setLevel(logging.INFO)

RETRY_PADRAO = {"retries": 2, "retry_delay_seconds": 300}  # 2 tentativas, 5 min entre elas


def _rodar_dbt(comando: str, selecao: str) -> None:
    """Executa `dbt <comando> --select <selecao>` como subprocesso (sem shell: funciona igual no Windows)."""
    logger = get_run_logger()
    args = [
        config.DBT_BIN, comando,
        "--project-dir", str(config.DBT_DIR),
        "--profiles-dir", str(config.DBT_DIR),
        "--select", selecao,
    ]
    logger.info("Executando: %s", " ".join(args))
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1", "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"},
    )
    saida = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        logger.error(saida)
        raise RuntimeError(f"dbt {comando} --select {selecao} falhou (código {proc.returncode})")
    logger.info(saida)


@task(name="preparar_banco", **RETRY_PADRAO)
def preparar_banco() -> None:
    from og_monitor.db import garantir_schema

    garantir_schema()


@task(name="coletar_noticias", **RETRY_PADRAO)
def coletar_noticias() -> int:
    from og_monitor.collect import coletar_noticias as _coletar

    return _coletar()


@task(name="carregar_siso", **RETRY_PADRAO)
def carregar_siso() -> dict:
    from og_monitor.siso import carregar_siso as _carregar

    return _carregar()


@task(name="dbt_pre_ia", **RETRY_PADRAO)
def dbt_pre_ia() -> None:
    _rodar_dbt("run", "tag:pre_ia")


# Sem retries: o classificador grava cada notícia logo após classificar e as falhas
# técnicas voltam como candidatas na próxima rodada.
# Sem timeout_seconds: em tarefa síncrona o Prefect não consegue interromper chamadas bloqueantes
# (rede, sleep), então o limite real de duração é MAX_NOTICIAS_POR_EXECUCAO x GROQ_SLEEP_SECONDS.
@task(name="classificar_com_ia", retries=0)
def classificar_com_ia() -> dict:
    from og_monitor.classify import classificar_pendentes

    return classificar_pendentes()


@task(name="dbt_pos_ia", **RETRY_PADRAO)
def dbt_pos_ia() -> None:
    _rodar_dbt("build", "tag:pos_ia")


@task(name="enviar_alertas", **RETRY_PADRAO)
def enviar_alertas() -> int:
    from og_monitor.alerts import enviar_alertas as _enviar

    return _enviar()


@flow(
    name="og_incident_pipeline",
    description="Monitoramento de incidentes de P&G: coleta, IA (Groq), cruzamento com o SISO e alertas.",
)
def og_incident_pipeline() -> None:
    logger = get_run_logger()

    banco = preparar_banco.submit()  # migrações de schema (idempotentes) antes de tudo
    noticias = coletar_noticias.submit(wait_for=[banco])
    siso = carregar_siso.submit()  # roda em paralelo com a coleta
    pre = dbt_pre_ia.submit(wait_for=[noticias])
    ia = classificar_com_ia.submit(wait_for=[pre])

    # Equivalente ao trigger_rule="all_done" do Airflow: o dbt pós-IA roda mesmo se a IA
    # (ou o SISO) falhar, recalculando com o que já foi gravado.
    ia.wait()
    siso.wait()
    if ia.state.is_failed():
        logger.warning("classificar_com_ia falhou; seguindo com o dbt pós-IA usando o que já foi gravado.")
    if siso.state.is_failed():
        logger.warning("carregar_siso falhou; seguindo com a base do SISO da última carga.")

    dbt_pos_ia()
    enviar_alertas()

    # Mantém a execução marcada como falha quando alguma etapa de dados falhou
    for nome, futuro in (("classificar_com_ia", ia), ("carregar_siso", siso)):
        if futuro.state.is_failed():
            raise RuntimeError(f"Etapa '{nome}' falhou; as demais etapas foram executadas com os dados disponíveis.")


if __name__ == "__main__":
    og_incident_pipeline()