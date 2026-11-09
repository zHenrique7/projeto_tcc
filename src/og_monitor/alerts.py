"""Alertas por e-mail (Outlook/SMTP) dos incidentes novos em ouro.incidentes_cruzados."""
import html
import logging

from psycopg2.extras import RealDictCursor

from og_monitor import config
from og_monitor.db import get_conn
from og_monitor.mailer import send_email

log = logging.getLogger(__name__)

ORDEM_SEVERIDADE = {"CRÍTICO": 0, "ALTO": 1, "MÉDIO": 2, "INFORMATIVO": 3}
COR_SEVERIDADE = {"CRÍTICO": "#c0392b", "ALTO": "#e67e22", "MÉDIO": "#f1c40f", "INFORMATIVO": "#2980b9"}

SQL_PENDENTES = """
SELECT c.*
FROM ouro.incidentes_cruzados c
LEFT JOIN raw.alertas_enviados a
       ON a.chave IN (md5(c.titulo), COALESCE(c.chave_evento, md5(c.titulo)))
WHERE a.chave IS NULL
"""


def _s(v) -> str:
    return html.escape("" if v is None else str(v))


def _linha(r: dict) -> str:
    cor = COR_SEVERIDADE.get(r["ia_severidade"], "#7f8c8d")
    comunicado = (
        f"SISO nº {_s(r['num_incidente'])} ({_s(r['nom_instalacao'])})"
        if r["num_incidente"] else "<b>Sem correspondência no SISO</b>"
    )
    local = " / ".join(x for x in [r["ia_instalacao"], r["ia_sonda"], r["ia_campo"], r["ia_municipio"], r["ia_estado"]]
                       if x and x != "Não Informado") or "Não informado"
    return f"""
    <tr>
      <td style="padding:6px;border:1px solid #ddd;background:{cor};color:#fff;font-weight:bold">{_s(r['ia_severidade'])}</td>
      <td style="padding:6px;border:1px solid #ddd"><a href="{_s(r['url_noticia'])}">{_s(r['titulo'])}</a><br>
          <small>{_s(r['fonte'])} • publicada em {_s(r['data_publicacao'])}</small></td>
      <td style="padding:6px;border:1px solid #ddd">{_s(r['ia_tipo_evento'])}<br><small>Fato: {_s(r['ia_data_fato'])} • Vítimas: {_s(r['ia_vitimas'])}</small></td>
      <td style="padding:6px;border:1px solid #ddd">{_s(local)}<br><small>{_s(r['ia_operadora_contrato'])}</small></td>
      <td style="padding:6px;border:1px solid #ddd">{comunicado}<br><small>{_s(r['status_cruzamento'])}</small></td>
      <td style="padding:6px;border:1px solid #ddd"><small>{_s(r['ia_motivo'])}</small></td>
    </tr>"""


def enviar_alertas() -> int:
    if not config.ALERTA_DESTINATARIOS:
        log.warning("ALERTA_DESTINATARIOS vazio: nenhum e-mail enviado (incidentes continuam pendentes).")
        return 0

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(SQL_PENDENTES)
            pendentes = [r for r in cur.fetchall() if r["ia_severidade"] in config.ALERTA_SEVERIDADES]

        if not pendentes:
            log.info("🟢 Nenhum incidente novo para alertar.")
            return 0

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM raw.siso_incidentes")
            linhas_siso = cur.fetchone()[0]

        pendentes.sort(key=lambda r: (ORDEM_SEVERIDADE.get(r["ia_severidade"], 9), str(r["ia_data_fato"])))
        criticos = sum(1 for r in pendentes if r["ia_severidade"] == "CRÍTICO")
        nao_comunicados = sum(1 for r in pendentes if not r["num_incidente"])

        aviso_siso = (
            f'<p style="color:#c0392b"><b>Atenção:</b> a base do SISO carregada tem só {linhas_siso} linha(s); '
            "a coluna de cruzamento com o SISO não é confiável.</p>"
            if linhas_siso < config.SISO_MIN_LINHAS else ""
        )
        corpo = f"""
        <h3>Monitor de Incidentes P&amp;G - {len(pendentes)} novo(s) incidente(s)</h3>
        <p>{criticos} crítico(s) • {nao_comunicados} sem correspondência no SISO.</p>
        {aviso_siso}
        <table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px">
          <tr style="background:#f2f2f2">
            <th>Severidade</th><th>Notícia</th><th>Evento</th><th>Local</th><th>Cruzamento SISO</th><th>Motivo (IA)</th>
          </tr>
          {''.join(_linha(r) for r in pendentes)}
        </table>
        <p><small>Gerado automaticamente pelo pipeline Prefect + dbt + Groq (CDADOS/SSO).</small></p>
        """
        assunto = f"[Monitor P&G] {len(pendentes)} novo(s) incidente(s) - {criticos} crítico(s)"
        send_email(to=config.ALERTA_DESTINATARIOS, subject=assunto, html_content=corpo)

        with conn.cursor() as cur:
            registros_alerta = []
            for r in pendentes:
                registros_alerta.append((r["titulo"], r["titulo"]))
                if r.get("chave_evento"):
                    cur.execute(
                        "INSERT INTO raw.alertas_enviados (chave, titulo) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (r["chave_evento"], r["titulo"]),
                    )
            cur.executemany(
                "INSERT INTO raw.alertas_enviados (chave, titulo) VALUES (md5(%s), %s) ON CONFLICT DO NOTHING",
                registros_alerta,
            )
    log.info("📧 Alerta enviado com %d incidente(s) para %s", len(pendentes), config.ALERTA_DESTINATARIOS)
    return len(pendentes)
