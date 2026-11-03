"""Configurações centralizadas, lidas de variáveis de ambiente (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]  # raiz do repositório (src/og_monitor -> src -> raiz)

# Carrega o .env da raiz (variáveis já definidas no ambiente têm prioridade)
load_dotenv(PROJECT_ROOT / ".env", encoding="utf-8")

PROMPT_PATH = BASE_DIR / "prompts" / "system_prompt.md"

FEEDS_PATH = Path(os.environ.get("OG_FEEDS_PATH", PROJECT_ROOT / "config" / "feeds.yml"))
SISO_DIR = Path(os.environ.get("OG_SISO_DIR", PROJECT_ROOT / "data" / "siso"))
# Abaixo disso a base do SISO é considerada incompleta (aviso no log e no e-mail de alerta).
SISO_MIN_LINHAS = int(os.environ.get("SISO_MIN_LINHAS", "50"))

# --- dbt (roda como subprocesso, em venv próprio) ---
DBT_BIN = os.environ.get("DBT_BIN", "dbt")
DBT_DIR = Path(os.environ.get("OG_DBT_DIR", PROJECT_ROOT / "dbt"))

# --- Banco de dados (PostgreSQL) ---
DB_HOST = os.environ.get("OG_DB_HOST", "localhost")
DB_PORT = int(os.environ.get("OG_DB_PORT", "5432"))
DB_NAME = os.environ.get("OG_DB_NAME", "og_monitor")
DB_USER = os.environ.get("OG_DB_USER", "og_user")
DB_PASSWORD = os.environ.get("OG_DB_PASSWORD", "og_password")

# --- Coleta ---
DIAS_RETROATIVOS = int(os.environ.get("DIAS_RETROATIVOS", "7"))

# --- Groq ---
GROQ_API_KEYS = [k.strip() for k in os.environ.get("GROQ_API_KEYS", "").split(",") if k.strip()]
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_TEMPERATURE = float(os.environ.get("GROQ_TEMPERATURE", "0.1"))
# Padrões pensados para o plano gratuito da Groq (~30 req/min e ~8 mil tokens/min no gpt-oss-120b): o gargalo é o TOKEN
# por minuto (prompt de ~4 mil tokens + matéria + o máximo reservado para a resposta), não o número de requisições.
GROQ_SLEEP_SECONDS = float(os.environ.get("GROQ_SLEEP_SECONDS", "45"))
# gpt-oss gasta tokens de "raciocínio" dentro de max_completion_tokens: com esforço "low", 2000 bastam; com "medium"
# ou "high" suba este valor, senão o JSON de notícias longas vem truncado.
GROQ_MAX_COMPLETION_TOKENS = int(os.environ.get("GROQ_MAX_COMPLETION_TOKENS", "2000"))
GROQ_REASONING_EFFORT = os.environ.get("GROQ_REASONING_EFFORT", "low")  # low | medium | high (só modelos gpt-oss)
MAX_NOTICIAS_POR_EXECUCAO = int(os.environ.get("MAX_NOTICIAS_POR_EXECUCAO", "40"))
TEXTO_MAX_CHARS = int(os.environ.get("TEXTO_MAX_CHARS", "3500"))  # trecho da matéria enviado à IA
# Duplicata por título só quando os títulos (sem o sufixo " - Portal") são quase idênticos.
# Era 0.65, o que descartava notícias NOVAS apenas parecidas com outras (ex.: "Incêndio atinge ... da Petrobras").
LIMIAR_SIMILARIDADE_TITULO = float(os.environ.get("LIMIAR_SIMILARIDADE_TITULO", "0.85"))

# --- Alertas ---
ALERTA_DESTINATARIOS = [e.strip() for e in os.environ.get("ALERTA_DESTINATARIOS", "").split(",") if e.strip()]
ALERTA_SEVERIDADES = [
    s.strip().upper()
    for s in os.environ.get("ALERTA_SEVERIDADES", "CRÍTICO,ALTO,MÉDIO,INFORMATIVO").split(",")
    if s.strip()
]

# --- SMTP (substitui o send_email do Airflow) ---
SMTP_HOST = os.environ.get("SMTP_HOST", "localhost")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "1025"))
SMTP_STARTTLS = os.environ.get("SMTP_STARTTLS", "False").strip().lower() in ("1", "true", "yes")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_MAIL_FROM = os.environ.get("SMTP_MAIL_FROM", "monitor-incidentes@exemplo.com")
