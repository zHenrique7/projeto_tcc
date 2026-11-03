"""Mostra o que a IA fez nas últimas horas: o que foi classificado, o que ainda está na fila e exemplos.

Uso (raiz do projeto, venv ativo):
    python -m og_monitor.diagnostico            # últimas 2 horas
    python -m og_monitor.diagnostico --horas 6
"""
import argparse

from psycopg2.extras import RealDictCursor

from og_monitor.db import get_conn


def _mostrar(titulo: str, linhas: list) -> None:
    print(f"\n{titulo}")
    if not linhas:
        print("   (vazio)")
        return
    for linha in linhas:
        print("   " + " | ".join("-" if v is None else str(v) for v in linha.values()))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--horas", type=int, default=2, help="janela por classificado_em (padrão: 2)")
    horas = ap.parse_args().horas

    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT relevante, coalesce(fonte_texto, '-') AS fonte_texto, count(*) AS qtd
            FROM raw.classificacoes_ia
            WHERE classificado_em >= now() - make_interval(hours => %s)
            GROUP BY 1, 2 ORDER BY 1 DESC, 3 DESC
            """,
            (horas,),
        )
        _mostrar(f"Classificadas nas últimas {horas}h (relevante | como o texto foi obtido | qtd)", cur.fetchall())

        cur.execute(
            """
            SELECT c.prioridade, count(*) AS ainda_na_fila
            FROM prata.prata_noticias_candidatas c
            WHERE NOT EXISTS (SELECT 1 FROM raw.classificacoes_ia r WHERE r.titulo = c.titulo)
            GROUP BY 1 ORDER BY 1 DESC
            """
        )
        _mostrar("Candidatas ainda sem classificação (prioridade | qtd)", cur.fetchall())

        cur.execute(
            """
            SELECT severidade, confianca, left(titulo, 70) AS titulo, left(motivo, 70) AS motivo
            FROM raw.classificacoes_ia
            WHERE relevante AND classificado_em >= now() - make_interval(hours => %s)
            ORDER BY classificado_em DESC LIMIT 30
            """,
            (horas,),
        )
        _mostrar("Capturadas como acidente (severidade | confiança | título | motivo)", cur.fetchall())

        cur.execute(
            """
            SELECT left(titulo, 70) AS titulo, left(motivo, 80) AS motivo
            FROM raw.classificacoes_ia
            WHERE NOT relevante AND fonte_texto IS DISTINCT FROM 'dedup'
              AND classificado_em >= now() - make_interval(hours => %s)
            ORDER BY classificado_em DESC LIMIT 25
            """,
            (horas,),
        )
        _mostrar("Rejeitadas pela IA, com o motivo (confira se alguma era acidente de verdade)", cur.fetchall())


if __name__ == "__main__":
    main()
