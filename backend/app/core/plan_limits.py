"""
NEXUS — Limites centralizados por plano (Freemium)
=====================================================
Fonte única de verdade para todos os limites de cada plano.
Importado por limit_service.py, endpoints e testes.
"""

from enum import Enum
from typing import Any


class Plan(str, Enum):
    FREE = "free"
    ESSENCIAL = "essencial"
    PROFISSIONAL = "profissional"
    COMPLETO = "completo"


# Mapeamento de nomes antigos → novos (retro-compatibilidade)
_PLAN_ALIASES: dict[str, str] = {
    "pro": "essencial",
    "enterprise": "completo",
}


PLAN_LIMITS: dict[Plan, dict[str, Any]] = {
    Plan.FREE: {
        "agent_messages_per_day": 10,
        "crm_clients": 5,
        "crm_suppliers": 5,  # equiparado a clientes
        "invoices_per_month": 3,
        # Agentes, Clientes e Agenda = conjunto gratuito padrão
        "available_agents": ["contabilidade", "clientes", "agenda"],
        "notifications": "basic",
        "data_export": True,
        "display_name": "Gratuito",
        "price": 0,
    },
    Plan.ESSENCIAL: {
        "agent_messages_per_day": 200,
        "crm_clients": 100,
        "crm_suppliers": 100,  # equiparado a clientes
        "invoices_per_month": -1,
        "available_agents": ["contabilidade", "clientes", "cobranca"],
        "notifications": "full",
        "data_export": True,
        "display_name": "Essencial",
        "price": 2990,  # centavos
    },
    Plan.PROFISSIONAL: {
        "agent_messages_per_day": 1000,
        "crm_clients": 500,
        "crm_suppliers": 500,  # equiparado a clientes
        "invoices_per_month": -1,
        "available_agents": ["contabilidade", "clientes", "cobranca",
                             "agenda", "assistente"],
        "notifications": "full",
        "data_export": True,
        "display_name": "Profissional",
        "price": 5990,
    },
    Plan.COMPLETO: {
        "agent_messages_per_day": -1,
        "crm_clients": -1,
        "crm_suppliers": -1,  # equiparado a clientes
        "invoices_per_month": -1,
        "available_agents": "__all__",
        "notifications": "full",
        "data_export": True,
        "display_name": "Completo",
        "price": 8990,
    },
}


def resolve_plan(raw: str | None) -> Plan:
    """Resolve alias e retorna Plan enum. Fallback → FREE."""
    if not raw:
        return Plan.FREE
    raw = raw.strip().lower()
    raw = _PLAN_ALIASES.get(raw, raw)
    try:
        return Plan(raw)
    except ValueError:
        return Plan.FREE


def get_limit(plan: str | None, key: str) -> Any:
    """Retorna o valor do limite para um plano e chave."""
    p = resolve_plan(plan)
    return PLAN_LIMITS[p].get(key)


def is_unlimited(value: int) -> bool:
    """Retorna True se o valor indica ilimitado (-1)."""
    return value == -1
