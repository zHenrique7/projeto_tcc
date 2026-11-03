"""Classificação de notícias com a API Groq (rodízio de chaves, backoff e validação do JSON)."""
import json
import logging
import re
import time
from datetime import date

from groq import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    Groq,
    InternalServerError,
    RateLimitError,
)

from og_monitor import config

log = logging.getLogger(__name__)

SEVERIDADES = {"CRÍTICO", "ALTO", "MÉDIO", "INFORMATIVO"}
_SEV_SEM_ACENTO = {"CRITICO": "CRÍTICO", "MEDIO": "MÉDIO"}
CONFIANCAS = {"alta", "média", "baixa"}
_CONF_SEM_ACENTO = {"media": "média"}
CAMPOS_TEXTO = ["tipo_evento", "sonda", "instalacao", "poco", "campo", "municipio",
                "operadora_contrato", "operadora_instalacao"]
VAZIOS = {"", "null", "none", "n/a", "não informado", "nao informado", "não informada"}


class ClassificationError(Exception):
    """Falha técnica (API/JSON). Nada é gravado, a notícia será reprocessada na próxima execução."""


def carregar_prompt() -> str:
    return config.PROMPT_PATH.read_text(encoding="utf-8")


class KeyPool:
    """Rodízio circular entre as chaves da Groq."""

    def __init__(self, chaves):
        if not chaves:
            raise RuntimeError("Nenhuma chave Groq configurada. Defina GROQ_API_KEYS no .env (separadas por vírgula).")
        self.chaves = chaves
        self.i = 0

    @property
    def atual(self) -> str:
        return self.chaves[self.i]

    def girar(self) -> int:
        self.i = (self.i + 1) % len(self.chaves)
        return self.i + 1


def montar_prompt_usuario(titulo, data_publicacao, url, fonte_texto, texto) -> str:
    aviso = ""
    if fonte_texto == "rss_feed":
        aviso = (
            "\nATENÇÃO: não foi possível ler a matéria completa; abaixo só há a manchete/resumo do RSS. "
            "Julgue pela manchete (veja [PRINCÍPIO DE DECISÃO])."
        )
    return f"""DATA DE REFERÊNCIA (Data de Publicação da Notícia): {data_publicacao}
Título: {titulo}
URL da Fonte Original: {url}
Fonte do texto: {fonte_texto}{aviso}

Texto Extraído do Site:
{str(texto or "")[: config.TEXTO_MAX_CHARS]}

Classifique esta notícia em formato JSON. Seja extremamente conciso na propriedade 'motivo' (MÁXIMO 150 caracteres)."""


def _chamar_groq(system_prompt: str, user_prompt: str, pool: KeyPool) -> str:
    n = len(pool.chaves)
    for tentativa in range(n * 3):
        client = Groq(api_key=pool.atual, timeout=90, max_retries=0)
        extras = {}
        if "gpt-oss" in config.GROQ_MODEL.lower() and config.GROQ_REASONING_EFFORT:
            extras["extra_body"] = {"reasoning_effort": config.GROQ_REASONING_EFFORT}
        try:
            resp = client.chat.completions.create(
                model=config.GROQ_MODEL,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                temperature=config.GROQ_TEMPERATURE,
                max_completion_tokens=config.GROQ_MAX_COMPLETION_TOKENS,
                **extras,
            )
            return (resp.choices[0].message.content or "").strip()
        except (RateLimitError, AuthenticationError) as e:
            nova = pool.girar()
            ciclo_completo = (tentativa + 1) % n == 0
            espera = min(90, 10 * 2 ** (tentativa // n)) if ciclo_completo else 3
            log.warning("⏳ %s - alternando para a chave %d (aguardando %ds)", type(e).__name__, nova, espera)
            time.sleep(espera)
        except (APIConnectionError, APITimeoutError, InternalServerError) as e:
            espera = 5 * (tentativa + 1)
            log.warning("🌐 %s - nova tentativa em %ds", type(e).__name__, espera)
            time.sleep(espera)
        except BadRequestError as e:
            raise ClassificationError(f"BadRequest: {str(e)[:150]}") from e
    raise ClassificationError("Limite de tentativas da Groq esgotado")


def _texto_ou_none(v):
    if v is None:
        return None
    s = str(v).strip()
    return None if s.lower() in VAZIOS else s


def normalizar_resultado(bruto: dict) -> dict:
    """Valida e normaliza o JSON da IA para o schema de raw.classificacoes_ia."""
    rel = bruto.get("relevante")
    relevante = rel is True or str(rel).strip().lower() == "true"

    severidade = None
    if relevante:
        s = str(bruto.get("severidade") or "").strip().upper()
        s = _SEV_SEM_ACENTO.get(s, s)
        if s not in SEVERIDADES:
            log.warning("Severidade inválida '%s' em notícia relevante; usando ALTO (padrão conservador).", s)
            s = "ALTO"
        severidade = s

    confianca = None
    if relevante:
        c = str(bruto.get("confianca") or "").strip().lower()
        c = _CONF_SEM_ACENTO.get(c, c)
        confianca = c if c in CONFIANCAS else "baixa"  # sem informação confiável -> revisar

    out = {"relevante": relevante, "severidade": severidade, "confianca": confianca}
    out["motivo"] = (str(bruto.get("motivo") or "").strip())[:150] or None
    for campo in CAMPOS_TEXTO:
        out[campo] = _texto_ou_none(bruto.get(campo))

    uf = _texto_ou_none(bruto.get("estado"))
    out["estado"] = uf.upper() if uf and re.fullmatch(r"[A-Za-z]{2}", uf) else None

    try:
        v = int(float(bruto.get("vitimas")))
        out["vitimas"] = v if v >= 0 else None
    except (TypeError, ValueError):
        out["vitimas"] = None

    df = _texto_ou_none(bruto.get("data_fato"))
    out["data_fato"] = None
    if df and re.fullmatch(r"\d{4}-\d{2}-\d{2}", df):
        try:
            out["data_fato"] = date.fromisoformat(df)
        except ValueError:
            pass

    if not relevante:  # irrelevantes não carregam campos de extração
        for campo in CAMPOS_TEXTO + ["estado", "vitimas", "data_fato"]:
            out[campo] = None
    return out


def classificar_noticia(system_prompt, pool, titulo, data_publicacao, url, fonte_texto, texto) -> dict:
    bruto = _chamar_groq(system_prompt, montar_prompt_usuario(titulo, data_publicacao, url, fonte_texto, texto), pool)
    ini, fim = bruto.find("{"), bruto.rfind("}")
    if ini == -1 or fim == -1:
        raise ClassificationError(f"Resposta sem JSON: {bruto[:100]}")
    try:
        return normalizar_resultado(json.loads(bruto[ini:fim + 1]))
    except json.JSONDecodeError as e:
        raise ClassificationError(f"JSON inválido: {str(e)[:100]}") from e
