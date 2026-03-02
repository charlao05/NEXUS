from __future__ import annotations

from pathlib import Path
try:
    from backend.agents.finance_agent import summarize_finances
    from backend.utils.logging_utils import get_logger
except ImportError:
    from ..agents.finance_agent import summarize_finances
    from ..utils.logging_utils import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"


def executar_relatorio_financeiro(finances_path: str | Path | None = None) -> dict:
    if finances_path is None:
        finances_path = DATA_DIR / "mei_finances_example.json"

    logger.info("Executando relatório financeiro...")
    resumo = summarize_finances(finances_path)

    print("=" * 60)
    print("RELATÓRIO FINANCEIRO")
    print("=" * 60)
    print(resumo.get("texto"))

    return resumo


if __name__ == "__main__":
    executar_relatorio_financeiro()
