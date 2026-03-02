from __future__ import annotations

from pathlib import Path
try:
    from backend.agents.collections_agent import find_overdue, generate_collection_message
    from backend.utils.logging_utils import get_logger
except ImportError:
    from ..agents.collections_agent import find_overdue, generate_collection_message
    from ..utils.logging_utils import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"


def executar_cobranca_demo(collections_path: str | Path | None = None) -> dict:
    if collections_path is None:
        collections_path = DATA_DIR / "mei_collections.json"

    logger.info("Executando cobrança automática (demo)...")
    overdue = find_overdue(collections_path)

    results = []
    for inv in overdue:
        msg = generate_collection_message(inv)
        print("=" * 40)
        print(f"Para: {inv.get('client')} ({inv.get('phone')})")
        print(msg)
        results.append({"invoice_id": inv.get("id"), "message": msg})

    return {"count": len(results), "results": results}


if __name__ == "__main__":
    executar_cobranca_demo()
