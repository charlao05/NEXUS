# src/utils/config_loader.py

from pathlib import Path
import yaml

from .logging_utils import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config"
SITES_CONFIG_DIR = CONFIG_DIR / "sites"
SITES_CONFIG_FILE = CONFIG_DIR / "sites.yaml"  # compatibilidade com formato antigo


def carregar_config_site(site: str) -> dict:
    """
    Carrega a configuração de um site específico.

    Prioridade:
    1. Arquivo individual em config/sites/{site}.yaml (novo formato)
    2. Entrada em config/sites.yaml (compatibilidade)
    """

    # Tentar arquivo individual primeiro
    site_yaml = SITES_CONFIG_DIR / f"{site}.yaml"
    if site_yaml.exists():
        try:
            with open(site_yaml, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            logger.info(f"Configuração do site '{site}' carregada de {site_yaml}")
            return config
        except Exception as exc:
            logger.warning(f"Erro ao carregar {site_yaml}: {exc}")

    # Fallback: carregar de sites.yaml (formato antigo)
    try:
        if not SITES_CONFIG_FILE.exists():
            logger.warning(
                f"Arquivo de configuração de sites não encontrado: {SITES_CONFIG_FILE}. "
                "Usando configuração vazia."
            )
            return {}

        with open(SITES_CONFIG_FILE, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        config_site: dict = {}

        if isinstance(raw, dict):
            if site in raw and isinstance(raw[site], dict):
                config_site = raw[site]
            elif "sites" in raw and isinstance(raw["sites"], dict):
                config_site = raw["sites"].get(site, {}) or {}

        if not config_site:
            logger.warning(
                f"Configuração para o site '{site}' não encontrada em {SITES_CONFIG_FILE}. "
                "Usando configuração vazia."
            )

        return config_site

    except Exception as exc:
        logger.exception(f"Erro ao carregar configuração do site '{site}': {exc}")
        return {}
