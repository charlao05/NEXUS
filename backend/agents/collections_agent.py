from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

try:
    from backend.utils.logging_utils import get_logger
except ImportError:
    from ..utils.logging_utils import get_logger
from backend.utils.llm_client import gerar_texto_simples

logger = get_logger(__name__)


def load_collections(path: str | Path) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        logger.error("Arquivo de cobranças não encontrado: %s", path)
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_overdue(path: str | Path) -> List[Dict[str, Any]]:
    data = load_collections(path)
    if not data:
        return []
    overdue = []
    for inv in data.get("open_invoices", []):
        if inv.get("status") == "overdue":
            overdue.append(inv)
    return overdue


def generate_collection_message(invoice: Dict[str, Any]) -> str:
    client = invoice.get("client")
    amount = invoice.get("amount")
    due_date = invoice.get("due_date")
    
    # Type guard para due_date
    if not due_date:
        return f"Cobrança pendente para {client}. Valor: R$ {amount:.2f}"
    
    days_over = (
        datetime.now().date() - datetime.fromisoformat(due_date).date()
    ).days

    prompt = f"Gere uma mensagem curta e educada para cobrar o cliente {client} sobre uma fatura de R$ {amount:.2f} vencida há {days_over} dias."

    try:
        texto = gerar_texto_simples(prompt)
    except Exception as e:
        logger.warning("LLM falhou: %s", e)
        texto = f"Olá {client}, sua fatura de R$ {amount:.2f} está em atraso há {days_over} dias. Por favor, entre em contato para regularizar."

    return texto


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[2] / "data" / "mei_collections.json"
    overdue = find_overdue(path)
    for inv in overdue:
        print(generate_collection_message(inv))
