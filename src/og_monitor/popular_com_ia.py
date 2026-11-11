"""Script para injetar casos reais/demonstrativos de incidentes, rodar a classificação com a IA Groq e compilar a camada ouro no dbt."""
import os
import sys
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# Ajusta path
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
sys.path.insert(0, str(BASE_DIR.parent))

from og_monitor import config
from og_monitor.db import get_conn
from og_monitor.classify import classificar_pendentes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("popular_com_ia")

NOTICIAS_DEMO = [
    {
        "titulo": "Incêndio em painel elétrico atinge FPSO Cidade de Angra dos Reis no Campo de Tupi",
        "data_publicacao": datetime(2026, 11, 9, 10, 30),
        "fonte": "Petronotícias",
        "url_noticia": "https://petronoticias.com.br/incendio-fpso-cidade-de-angra-dos-reis-tupi-2026",
        "resumo_html": (
            "Um princípio de incêndio foi registrado em um painel elétrico auxiliar no FPSO Cidade de Angra dos Reis, "
            "que opera no Campo de Tupi, na Bacia de Santos. A brigada de emergência da Petrobras combateu as chamas rapidamente "
            "e não houve feridos ou vazamento de óleo. A produção de petróleo foi temporariamente reduzida para inspeção de segurança."
        ),
    },
    {
        "titulo": "Vazamento de gás interrompe operação na plataforma P-53 da Petrobras na Bacia de Campos",
        "data_publicacao": datetime(2026, 11, 10, 14, 15),
        "fonte": "GNews Plataforma",
        "url_noticia": "https://g1.globo.com/rj/regiao-dos-lagos/noticia/2026/11/10/vazamento-gas-p53-petrobras.ghtml",
        "resumo_html": (
            "A Petrobras informou que paralisou preventivamente as atividades na plataforma P-53, localizada no Campo de "
            "Marlim Leste, na Bacia de Campos (RJ), após detecção de um vazamento de gás natural em linha de processo. "
            "A unidade foi despressurizada e a equipe de manutenção isolou a falha. Nenhum trabalhador ficou ferido."
        ),
    },
    {
        "titulo": "Vazamento de petróleo durante alívio no FPSO Almirante Barroso mobiliza contenção no Campo de Búzios",
        "data_publicacao": datetime(2026, 11, 8, 16, 45),
        "fonte": "Brasil Energia",
        "url_noticia": "https://brasilenergia.com.br/vazamento-oleo-fpso-almirante-barroso-buzios-2026",
        "resumo_html": (
            "Equipes de resposta à emergência da Petrobras e da Marinha do Brasil atuam na contenção de um vazamento de petróleo "
            "ocorrido durante operação de alívio entre o navio-plataforma FPSO Almirante Barroso e um navio aliviador no Campo de Búzios, "
            "Bacia de Santos. Estima-se o derramamento de aproximadamente 3 mil litros de óleo no mar. Barreiras de contenção foram acionadas."
        ),
    },
    {
        "titulo": "Explosão em unidade da Refinaria Replan deixa dois operários feridos em Paulínia",
        "data_publicacao": datetime(2026, 11, 10, 8, 30),
        "fonte": "GNews Incêndio",
        "url_noticia": "https://folha.uol.com.br/cotidiano/2026/11/explosao-refinaria-replan-petrobras-paulinia.shtml",
        "resumo_html": (
            "Uma explosão na unidade de craqueamento catalítico da Refinaria de Paulínia (Replan), pertencente à Petrobras, "
            "deixou dois trabalhadores feridos na manhã desta terça-feira em Paulínia (SP). As vítimas sofreram queimaduras "
            "e foram encaminhadas ao hospital municipal. A brigada interna controlou o fogo subsequente e a área foi interditada para perícia técnica da ANP."
        ),
    },
]

SISO_SIMULACAO = [
    {
        "num_incidente": "2611/000042",
        "dsc_empresa": "PETRÓLEO BRASILEIRO S.A. - PETROBRAS (33000167000101)",
        "nom_instalacao": "FPSO CIDADE DE ANGRA DOS REIS",
        "dat_primeira_obs": datetime(2026, 11, 9, 10, 15),
        "dsc_ende_instalacao": "CAMPO DE TUPI, BACIA DE SANTOS, SP",
        "dsc_incidente": "Princípio de incêndio originado em painel elétrico auxiliar da área de utilidades do FPSO Cidade de Angra dos Reis. Atuação da brigada de combate a incêndio com extinção do foco em 15 minutos. Sem vítimas ou dano ambiental.",
    },
    {
        "num_incidente": "2611/000045",
        "dsc_empresa": "PETRÓLEO BRASILEIRO S.A. - PETROBRAS (33000167000101)",
        "nom_instalacao": "PLATAFORMA P-53 / PETROBRAS",
        "dat_primeira_obs": datetime(2026, 11, 10, 13, 50),
        "dsc_ende_instalacao": "CAMPO DE MARLIM LESTE, BACIA DE CAMPOS, RJ",
        "dsc_incidente": "Vazamento de gás combustível em flange de linha de alta pressão. Acionamento do sistema de alarme e parada de emergência da unidade.",
    },
]


def rodar_dbt(comando: str, selecao: str) -> None:
    dbt_exe = sys.executable.replace("python.exe", "dbt.exe")
    args = [
        dbt_exe, comando,
        "--project-dir", str(config.DBT_DIR),
        "--profiles-dir", str(config.DBT_DIR),
        "--select", selecao,
    ]
    log.info("Executando dbt: %s", " ".join(args))
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUTF8": "1", "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"},
    )
    if proc.returncode != 0:
        log.error("Erro dbt:\n%s\n%s", proc.stdout, proc.stderr)
        raise RuntimeError(f"dbt {comando} --select {selecao} falhou.")
    log.info("dbt concluído com sucesso.")


def main():
    log.info("=== 1. Inserindo notícias e registros simulados de SISO ===")
    with get_conn() as conn:
        with conn.cursor() as cur:
            for n in NOTICIAS_DEMO:
                cur.execute(
                    """
                    INSERT INTO raw.noticias
                        (titulo, data_publicacao, fonte, resumo_html, url_noticia, url_fonte, coletado_em)
                    VALUES
                        (%(titulo)s, %(data_publicacao)s, %(fonte)s, %(resumo_html)s, %(url_noticia)s, %(url_noticia)s, now())
                    ON CONFLICT (titulo, data_publicacao) DO UPDATE
                    SET resumo_html = EXCLUDED.resumo_html,
                        url_noticia = EXCLUDED.url_noticia;
                    """,
                    n,
                )
            for s in SISO_SIMULACAO:
                cur.execute(
                    """
                    DELETE FROM raw.siso_incidentes WHERE num_incidente = %(num_incidente)s;
                    INSERT INTO raw.siso_incidentes
                        (num_incidente, dsc_empresa, nom_instalacao, dat_primeira_obs, dsc_ende_instalacao, dsc_incidente)
                    VALUES
                        (%(num_incidente)s, %(dsc_empresa)s, %(nom_instalacao)s, %(dat_primeira_obs)s, %(dsc_ende_instalacao)s, %(dsc_incidente)s);
                    """,
                    s,
                )
        conn.commit()
    log.info("Notícias e registros SISO inseridos com sucesso!")

    log.info("=== 2. Rodando dbt pre_ia (preparação das candidatas) ===")
    rodar_dbt("run", "tag:pre_ia")

    log.info("=== 3. Executando classificação via IA Groq (Llama 3 / gpt-oss) ===")
    # Reduz temporariamente o tempo de espera entre chamadas
    config.GROQ_SLEEP_SECONDS = 3.0
    resumo = classificar_pendentes()
    log.info("Resumo da classificação: %s", resumo)

    log.info("=== 4. Rodando dbt pos_ia (prata + ouro + cruzamento SISO) ===")
    rodar_dbt("build", "tag:pos_ia")

    log.info("=== 5. Consultando tabela fato_incidente populada ===")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    f.id_incidente,
                    f.titulo,
                    sev.severidade,
                    te.tipo_evento,
                    sc.status_cruzamento,
                    f.vitimas,
                    inst.instalacao,
                    f.data_fato
                FROM ouro.fato_incidente f
                LEFT JOIN ouro.dim_severidade sev ON sev.id_severidade = f.id_severidade
                LEFT JOIN ouro.dim_tipo_evento te ON te.id_tipo_evento = f.id_tipo_evento
                LEFT JOIN ouro.dim_status_cruzamento sc ON sc.id_status_cruzamento = f.id_status_cruzamento
                LEFT JOIN ouro.dim_instalacao inst ON inst.id_instalacao = f.id_instalacao
                ORDER BY f.id_incidente;
                """
            )
            rows = cur.fetchall()
            print("\n" + "=" * 90)
            print(f"TABELA OURO.FATO_INCIDENTE: {len(rows)} INCIDENTES REGISTRADOS")
            print("=" * 90)
            for r in rows:
                print(f"ID #{r[0]}: {r[1][:60]}...")
                print(f"   -> Data: {r[7]} | Tipo: {r[3]} | Severidade: {r[2]} | Vítimas: {r[5]}")
                print(f"   -> Ativo: {r[6]} | Status Cruzamento SISO: {r[4]}")
                print("-" * 90)


if __name__ == "__main__":
    main()
