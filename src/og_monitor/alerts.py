"""Alertas por e-mail (Outlook/SMTP) dos incidentes novos em ouro.fato_incidente (a mesma fato que o Power BI lê, com as dimensões)."""
import html
import logging
from datetime import datetime

from psycopg2.extras import RealDictCursor

from og_monitor import config
from og_monitor.db import get_conn
from og_monitor.mailer import send_email

log = logging.getLogger(__name__)

ORDEM_SEVERIDADE = {"CRÍTICO": 0, "ALTO": 1, "MÉDIO": 2, "INFORMATIVO": 3}
COR_SEVERIDADE = {"CRÍTICO": "#c0392b", "ALTO": "#e67e22", "MÉDIO": "#f1c40f", "INFORMATIVO": "#2980b9"}

SQL_PENDENTES = """
SELECT
    f.id_incidente,
    f.titulo,
    f.url_noticia,
    f.motivo,
    f.sonda,
    f.campo,
    f.vitimas,
    f.num_incidente_siso,
    f.data_publicacao,
    f.data_fato,
    fo.fonte,
    sv.severidade,
    te.tipo_evento,
    st.status_cruzamento,
    NULLIF(i.instalacao, 'Não Informada')         AS instalacao,
    NULLIF(isiso.instalacao, 'Não Informada')     AS instalacao_siso,
    l.municipio,
    l.estado,
    NULLIF(ec.empresa, 'Não Informada')           AS operadora_contrato
FROM ouro.fato_incidente f
JOIN ouro.dim_status_cruzamento st ON st.id_status_cruzamento = f.id_status_cruzamento
JOIN ouro.dim_severidade sv        ON sv.id_severidade = f.id_severidade
JOIN ouro.dim_tipo_evento te       ON te.id_tipo_evento = f.id_tipo_evento
JOIN ouro.dim_fonte fo             ON fo.id_fonte = f.id_fonte
JOIN ouro.dim_localidade l         ON l.id_localidade = f.id_localidade
JOIN ouro.dim_instalacao i         ON i.id_instalacao = f.id_instalacao
JOIN ouro.dim_instalacao isiso     ON isiso.id_instalacao = f.id_instalacao_siso
JOIN ouro.dim_empresa ec           ON ec.id_empresa = f.id_empresa_contrato
LEFT JOIN raw.alertas_enviados a
       ON a.chave = md5(f.titulo)
WHERE a.chave IS NULL
"""


def _s(v) -> str:
    return html.escape("" if v is None else str(v))


def _linha(r: dict) -> str:
    cor = COR_SEVERIDADE.get(r["severidade"], "#7f8c8d")
    comunicado = (
        f"SISO nº {_s(r['num_incidente_siso'])} ({_s(r['instalacao_siso'])})"
        if r["num_incidente_siso"] else "<b>Sem correspondência no SISO</b>"
    )
    local = " / ".join(x for x in [r["instalacao"], r["sonda"], r["campo"], r["municipio"], r["estado"]]
                       if x and x != "Não Informado") or "Não informado"
    return f"""
    <tr>
      <td style="padding:6px;border:1px solid #ddd;background:{cor};color:#fff;font-weight:bold">{_s(r['severidade'])}</td>
      <td style="padding:6px;border:1px solid #ddd"><a href="{_s(r['url_noticia'])}">{_s(r['titulo'])}</a><br>
          <small>{_s(r['fonte'])} • publicada em {_s(r['data_publicacao'])}</small></td>
      <td style="padding:6px;border:1px solid #ddd">{_s(r['tipo_evento'])}<br><small>Fato: {_s(r['data_fato'])} • Vítimas: {_s(r['vitimas']) if r['vitimas'] is not None else 'n/i'}</small></td>
      <td style="padding:6px;border:1px solid #ddd">{_s(local)}<br><small>{_s(r['operadora_contrato'])}</small></td>
      <td style="padding:6px;border:1px solid #ddd">{comunicado}<br><small>{_s(r['status_cruzamento'])}</small></td>
      <td style="padding:6px;border:1px solid #ddd"><small>{_s(r['motivo'])}</small></td>
    </tr>"""


def enviar_alertas() -> int:
    if not config.ALERTA_DESTINATARIOS:
        log.warning("ALERTA_DESTINATARIOS vazio: nenhum e-mail enviado (incidentes continuam pendentes).")
        return 0

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(SQL_PENDENTES)
            pendentes = [r for r in cur.fetchall() if r["severidade"] in config.ALERTA_SEVERIDADES]

        if not pendentes:
            log.info("🟢 Nenhum incidente novo para alertar.")
            return 0

        with conn.cursor() as cur:
            cur.execute("SELECT count(*), max(dat_primeira_obs) FROM raw.siso_incidentes")
            linhas_siso, ultima_siso = cur.fetchone()

        pendentes.sort(key=lambda r: (ORDEM_SEVERIDADE.get(r["severidade"], 9), str(r["data_fato"])))
        criticos = sum(1 for r in pendentes if r["severidade"] == "CRÍTICO")
        nao_comunicados = sum(1 for r in pendentes if not r["num_incidente_siso"])

        defasagem = (datetime.now() - ultima_siso).days if ultima_siso else None
        if linhas_siso < config.SISO_MIN_LINHAS:
            aviso_siso = (f'<p style="color:#c0392b"><b>Atenção:</b> a base do SISO carregada tem só {linhas_siso} linha(s); '
                          "a coluna de cruzamento com o SISO não é confiável.</p>")
        elif defasagem is not None and defasagem > config.SISO_MAX_DEFASAGEM_DIAS:
            aviso_siso = (f'<p style="color:#c0392b"><b>Atenção:</b> o incidente mais recente do SISO carregado é de '
                          f"{ultima_siso:%d/%m/%Y} ({defasagem} dias atrás): a coluna de cruzamento com o SISO não é "
                          "confiável para notícias recentes. Atualize o incidentes.csv.</p>")
        else:
            aviso_siso = ""
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
            # A chave do alerta é o md5 do título do incidente (a notícia-raiz do evento, estável entre execuções).
            # Alertas antigos gravados com o hash do evento continuam valendo: o md5 do título sempre foi gravado junto.
            registros_alerta = [(r["titulo"], r["titulo"]) for r in pendentes]
            cur.executemany(
                "INSERT INTO raw.alertas_enviados (chave, titulo) VALUES (md5(%s), %s) ON CONFLICT DO NOTHING",
                registros_alerta,
            )
    log.info("📧 Alerta enviado com %d incidente(s) para %s", len(pendentes), config.ALERTA_DESTINATARIOS)
    return len(pendentes)
