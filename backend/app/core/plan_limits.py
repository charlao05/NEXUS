"""
NEXUS — Limites centralizados por plano (Freemium)
=====================================================
Fonte única de verdade para todos os limites de cada plano.
Importado por limit_service.py, endpoints e testes.

ESTRATÉGIA DE PRECIFICAÇÃO (rev. 2026-05-28):
Free → CRM melhorado: isca de conversão. Sem IA de chat/automação.
Degustação de IA: 3 dias após cadastro (FREE_AI_TRIAL_DAYS=3).
Essencial → Entrada paga. IA de chat liberada. Automações básicas.
Profissional → Profissional autônomo. Todos os agentes. Automações completas.
Completo → Empresas. Sem limites. Prioridade máxima.

CUSTO BASE (gpt-4o-mini, câmbio R$5.20):
  Chat msg   ≈ R$0.0018  (800 tokens médios)
  Automação  ≈ R$0.0092  (3.500 tokens médios + Playwright context)
  Automação custa ~5x mais que chat → AUTOMATION_MSG_WEIGHT = 5

ANÁLISE COMBINATÓRIA DO TRIAL (decisão de negócio):
  Limite ATUAL   (20 chat + 2 auto/dia) → R$0.163/usuário/trial → muito exposto
  Limite ADOTADO (10 chat + 1 auto/dia) → R$0.082/usuário/trial → break-even em 158 addons
  Limite MÍNIMO  ( 5 chat + 1 auto/dia) → R$0.055/usuário/trial → demasiado restrito

  DECISÃO: trial_ai_messages_per_day = 10, trial_automations_per_day = 1
  Razão: suficiente para provar valor, custo controlado, metade do risco anterior.

ADDON R$12,90 (compra única):
  Expande: +10 clientes, +10 fornecedores (CRM apenas).
  NÃO expande mensagens de IA no plano free — trial continua sendo o bônus de IA.
  Addon é puro lucro: custo operacional = R$0 (só CRM storage).
  Break-even do addon vs custo trial: 158 free ativos cobrem 1 addon vendido.
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
        # Degustação: 10 msgs/dia nos primeiros FREE_AI_TRIAL_DAYS dias
        # (análise combinatória: 10 msgs + 1 auto/dia = R$0,082 total por usuário
        #  vs 20 msgs + 2 auto = R$0,163 — metade do custo, experiência suficiente)
        "trial_ai_messages_per_day": 10,
        # CRM — núcleo do plano gratuito
        "crm_clients": 10,
        "crm_suppliers": 10,
        "invoices_per_month": 0,
        # Automações: ZERO permanente (só durante trial)
        "automations_per_day": 0,
        # 1 automação/dia durante trial (custo máximo: 3 x R$0,0092 = R$0,028 total)
        "trial_automations_per_day": 1,
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
            "Degustação de IA por 3 dias (10 msgs/dia)",
            "1 automação web por dia na degustação",
            "Sem cartão de crédito",
        ],
        "ui_upsell": "Após 3 dias, assine para continuar com IA ilimitada",
    },
    Plan.ESSENCIAL: {
        "agent_messages_per_day": 150,
        "automations_per_day": 20,
        "crm_clients": 100,
        "crm_suppliers": 100,
        "invoices_per_month": 0,
        "available_agents": ["contabilidade", "clientes", "cobranca", "agenda"],
        "notifications": "full",
        "data_export": True,
        "display_name": "Essencial",
        "price": 2990,  # centavos = R$ 29,90
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
        "agent_messages_per_day": 500,
        "automations_per_day": 80,
        "crm_clients": 500,
        "crm_suppliers": 500,
        "invoices_per_month": -1,
        "available_agents": ["contabilidade", "clientes", "cobranca",
                             "agenda", "assistente"],
        "notifications": "full",
        "data_export": True,
        "display_name": "Profissional",
        "price": 5990,  # R$ 59,90
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
        "agent_messages_per_day": -1,
        "automations_per_day": -1,
        "crm_clients": -1,
        "crm_suppliers": -1,
        "invoices_per_month": -1,
        "available_agents": "__all__",
        "notifications": "full",
        "data_export": True,
        "display_name": "Completo",
        "price": 8990,  # R$ 89,90
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
    """Retorna True se o usuário free ainda está no trial de IA
    (dentro dos primeiros FREE_AI_TRIAL_DAYS dias após o cadastro).

    Custo máximo do trial (conservador): R$0,082 por usuário:
      - 10 msgs/dia x R$0,0018 x 3 dias = R$0,054
      - 1 auto/dia  x R$0,0092 x 3 dias = R$0,028
      TOTAL = R$0,082 / usuário no trial completo
    """
    if user_created_at is None:
        return False
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if hasattr(user_created_at, 'tzinfo') and user_created_at.tzinfo is None:
        user_created_at = user_created_at.replace(tzinfo=timezone.utc)
    delta = now - user_created_at
    return delta.days < FREE_AI_TRIAL_DAYS
