from __future__ import annotations

from pathlib import Path
try:
    from backend.agents.nf_agent import prepare_invoice_steps
    from backend.utils.logging_utils import get_logger
except ImportError:
    from ..agents.nf_agent import prepare_invoice_steps
    from ..utils.logging_utils import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"


def executar_nota_fiscal_demo(sale: dict | None = None) -> dict:
    if sale is None:
        sale = {"client_name": "João", "amount": 250.0}

    logger.info("Executando nota fiscal automática (demo)...")
    result = prepare_invoice_steps(sale)

    print("=" * 60)
    print("NOTA FISCAL - DEMO")
    print("=" * 60)
    print(result.get("texto"))
    print("Passos sugeridos:")
    for s in result.get("steps", []):
        print(f" - {s}")

    return result


if __name__ == "__main__":
    executar_nota_fiscal_demo()
