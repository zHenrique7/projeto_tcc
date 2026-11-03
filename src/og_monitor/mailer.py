"""Envio de e-mail via SMTP puro (biblioteca padrão), sem depender do Airflow."""
import logging
import smtplib
from email.message import EmailMessage

from og_monitor import config

log = logging.getLogger(__name__)


def send_email(to: list[str], subject: str, html_content: str) -> None:
    msg = EmailMessage()
    msg["From"] = config.SMTP_MAIL_FROM
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content("Este e-mail requer um cliente com suporte a HTML.")
    msg.add_alternative(html_content, subtype="html")

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as smtp:
        if config.SMTP_STARTTLS:
            smtp.starttls()
        if config.SMTP_USER:
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
        smtp.send_message(msg)
