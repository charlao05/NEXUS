"""
NEXUS — Limites centralizados por plano (Freemium)
=====================================================
Fonte única de verdade para todos os limites de cada plano.
Importado por limit_service.py, endpoints e testes.

ESTRATÉGIA DE PRECIFICAÇÃO (rev. 2026-05-28):
  Free     → CRM melhorado: isca de conversão. Sem IA de chat/automação.
             Degustação de IA: 3 dias após cadastro (trial_ai_days=3).
  Essencial → Entrada paga. IA de chat liberada. Automações básicas.
  Profissional → Profissional autônomo. Todos os agentes. Automações completas.
  Completo  → Empresas. Sem limites. Prioridade máxima.

CUSTO BASE (gpt-4o-mini, câmbio R$5.20):
  Chat msg  ≈ R$0.0018  | Automação ≈ R$0.008 (4-14x mais cara)
  Cada automação debita AUTOMATION_MSG_WEIGHT mensagens do contador diário.
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

# Peso de uma automação no contador diário de mensagens.
# 1 automação = 5 msgs equivalentes (alinha custo real com limite).
AUTOMATION_MSG_WEIGHT: int = 5

# Dias de degustação de IA para usuários Free após cadastro.
FREE_AI_TRIAL_DAYS: int = 3


PLAN_LIMITS: dict[Plan, dict[str, Any]] = {
    Plan.FREE: {
        # IA de chat: ZERO permanente (só durante trial de 3 dias após cadastro)
        "agent_messages_per_day": 0,
        # Degustação: 20 msgs/dia nos primeiros FREE_AI_TRIAL_DAYS dias
        "trial_ai_messages_per_day": 20,
        # CRM — núcleo do plano gratuito
        "crm_clients": 10,
        "crm_suppliers": 10,
        "invoices_per_month": 0,          # notas fiscais em breve
        # Automações: ZERO permanente (só durante trial)
        "automations_per_day": 0,
        "trial_automations_per_day": 2,   # 2 automações/dia durante trial
        # Agentes disponíveis no free (sem IA de chat — só CRM manual)
        # Durante trial: libera contabilidade e clientes com IA
        "available_agents": ["contabilidade", "clientes", "agenda"],
        "trial_available_agents": ["contabilidade", "clientes", "agenda"],
        "notifications": "basic",
        "data_export": False,
        "display_name": "Gratuito",
        "price": 0,
        # O que o free tem — descrição para UI
        "ui_features": [
            "CRM: até 10 clientes e 10 fornecedores",
            "Cadastro de produtos e serviços",
            "Agenda e compromissos básicos",
            "Degustação de IA por 3 dias (20 msgs/dia)",
            "Automação experimental por 3 dias",
            "Sem cartão de crédito",
        ],
        "ui_upsell": "Após 3 dias, assine para continuar com IA ilimitada",
    },
    Plan.ESSENCIAL: {
        "agent_messages_per_day": 150,    # msgs de chat/dia
        "automations_per_day": 20,        # automações web/dia
        "crm_clients": 100,
        "crm_suppliers": 100,
        "invoices_per_month": 0,
        "available_agents": ["contabilidade", "clientes", "cobranca", "agenda"],
        "notifications": "full",
        "data_export": True,
        "display_name": "Essencial",
        "price": 2990,                    # centavos = R$ 29,90
        "ui_features": [
            "150 mensagens de IA por dia",
            "20 automações web por dia",
            "4 agentes: Fiscal, Clientes, Cobranças e Agenda",
            "Até 100 clientes e 100 fornecedores",
            "Suporte a notas fiscais (em breve)",
            "Suporte prioritário por email",
        ],
    },
    Plan.PROFISSIONAL: {
        "agent_messages_per_day": 500,    # msgs de chat/dia
        "automations_per_day": 80,        # automações web/dia
        "crm_clients": 500,
        "crm_suppliers": 500,
        "invoices_per_month": -1,         # ilimitado
        "available_agents": ["contabilidade", "clientes", "cobranca",
                             "agenda", "assistente"],
        "notifications": "full",
        "data_export": True,
        "display_name": "Profissional",
        "price": 5990,                    # R$ 59,90
        "ui_features": [
            "500 mensagens de IA por dia",
            "80 automações web por dia",
            "Todos os 5 agentes de IA (+ Assistente Geral)",
            "Até 500 clientes e 500 fornecedores",
            "Notas fiscais ilimitadas",
            "Relatórios de clientes e finanças",
            "Suporte prioritário",
        ],
    },
    Plan.COMPLETO: {
        "agent_messages_per_day": -1,     # ilimitado
        "automations_per_day": -1,        # ilimitado
        "crm_clients": -1,
        "crm_suppliers": -1,
        "invoices_per_month": -1,
        "available_agents": "__all__",
        "notifications": "full",
        "data_export": True,
        "display_name": "Completo",
        "price": 8990,                    # R$ 89,90
        "ui_features": [
            "Mensagens e automações ilimitadas",
            "Todos os agentes de IA disponíveis",
            "Clientes e fornecedores ilimitados",
            "Notas fiscais ilimitadas",
            "Automação avançada de lembretes e cobranças",
            "Relatórios completos",
            "Suporte prioritário máximo",
        ],
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
    """Retorna True se o valor indica sem limite (-1)."""
    return value == -1


def is_in_ai_trial(user_created_at: Any) -> bool:
    """Retorna True se o usuário free ainda está no trial de IA (primeiros FREE_AI_TRIAL_DAYS dias)."""
    if user_created_at is None:
        return False
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if hasattr(user_created_at, 'tzinfo') and user_created_at.tzinfo is None:
        user_created_at = user_created_at.replace(tzinfo=timezone.utc)
    delta = now - user_created_at
    return delta.days < FREE_AI_TRIAL_DAYS
