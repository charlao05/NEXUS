"""Utilitários de logging com saída em console e arquivo."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

_LOG_FILE = Path("logs/automation.log")
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Formato textual para o arquivo, mantendo rastreabilidade completa.
_FILE_FORMAT = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Mantemos cache de loggers para evitar handlers duplicados.
_LOGGER_CACHE: dict[str, logging.Logger] = {}


def get_logger(nome: str) -> logging.Logger:
    """Retorna um logger configurado com Rich no console e arquivo rotativo."""

    if nome in _LOGGER_CACHE:
        return _LOGGER_CACHE[nome]

    logger = logging.getLogger(nome)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        console_handler = RichHandler(rich_tracebacks=True, markup=False)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("%(message)s"))

        file_handler = RotatingFileHandler(_LOG_FILE, maxBytes=2_000_000, backupCount=3)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(_FILE_FORMAT)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    _LOGGER_CACHE[nome] = logger
    return logger
