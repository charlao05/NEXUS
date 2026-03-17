"""Utilitários de logging com saída em console e arquivo.

Inclui filtro _SecretSanitizer que mascara automaticamente chaves de API,
tokens e senhas em URLs antes de gravá-los em qualquer handler.
"""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

_LOG_FILE = Path("logs/automation.log")
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Formato textual para o arquivo, mantendo rastreabilidade completa.
_FILE_FORMAT = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# ── Filtro de segredos ─────────────────────────────────────────────
# Padrões de chaves / tokens conhecidos que NUNCA devem aparecer em logs.
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}"),      # OpenAI project keys
    re.compile(r"sk-[A-Za-z0-9]{20,}"),               # OpenAI legacy keys
    re.compile(r"sk_live_[A-Za-z0-9]{20,}"),           # Stripe live secret
    re.compile(r"sk_test_[A-Za-z0-9]{20,}"),           # Stripe test secret
    re.compile(r"pk_live_[A-Za-z0-9]{20,}"),           # Stripe live publishable
    re.compile(r"pk_test_[A-Za-z0-9]{20,}"),           # Stripe test publishable
    re.compile(r"whsec_[A-Za-z0-9]{20,}"),             # Stripe webhook secret
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}"),    # Bearer tokens
    re.compile(r"APP_USR-[A-Za-z0-9\-]{20,}"),        # MercadoPago tokens
    re.compile(r"re_[A-Za-z0-9]{20,}"),                # Resend API keys
    re.compile(r"EAA[A-Za-z0-9]{20,}"),                # Facebook/Meta tokens
]

# Senhas embutidas em URLs de banco de dados (ex.: postgresql://user:SENHA@host)
_URL_PASSWORD_PATTERN = re.compile(r"(://[^:]+:)([^@]+)(@)")


def _sanitize(text: str) -> str:
    """Substitui segredos encontrados no texto por '***'."""
    for pat in _SECRET_PATTERNS:
        text = pat.sub("***", text)
    text = _URL_PASSWORD_PATTERN.sub(r"\1***\3", text)
    return text


class _SecretSanitizer(logging.Filter):
    """Filtro de logging que mascara segredos em msg e args."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _sanitize(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _sanitize(str(v)) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(_sanitize(str(a)) if isinstance(a, str) else a for a in record.args)
        return True


_SECRET_FILTER = _SecretSanitizer()

# Mantemos cache de loggers para evitar handlers duplicados.
_LOGGER_CACHE: dict[str, logging.Logger] = {}


def get_logger(nome: str) -> logging.Logger:
    """Retorna um logger configurado com Rich no console e arquivo rotativo.

    Ambos os handlers aplicam _SecretSanitizer para evitar vazamento de
    chaves de API, tokens e senhas em logs.
    """

    if nome in _LOGGER_CACHE:
        return _LOGGER_CACHE[nome]

    logger = logging.getLogger(nome)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        console_handler = RichHandler(rich_tracebacks=True, markup=False)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        console_handler.addFilter(_SECRET_FILTER)

        file_handler = RotatingFileHandler(_LOG_FILE, maxBytes=2_000_000, backupCount=3)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(_FILE_FORMAT)
        file_handler.addFilter(_SECRET_FILTER)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    _LOGGER_CACHE[nome] = logger
    return logger
