"""
Action Firewall — Políticas declarativas de segurança.
Cada ação proposta pelo LLM passa por aqui antes de executar.

Princípio: o LLM é um planner NÃO confiável.
O executor só roda ações aprovadas pela política.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from backend.orchestrator.state import (
    ActionRisk,
    PlannedAction,
    PolicyDecision,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domínios sensíveis — browser_type proibido em campos de login/CPF/senha
# ---------------------------------------------------------------------------

SENSITIVE_DOMAINS: list[str] = [
    "receita.fazenda.gov.br",
    "cav.receita.fazenda.gov.br",
    "www8.receita.fazenda.gov.br",
    "servicos.receita.fazenda.gov.br",
    "gov.br",
    "www.gov.br",
    "acesso.gov.br",
    "sso.acesso.gov.br",
    "bb.com.br",
    "caixa.gov.br",
    "itau.com.br",
    "bradesco.com.br",
    "santander.com.br",
    "nubank.com.br",
    "nfe.prefeitura.sp.gov.br",
    "prefeitura.sp.gov.br",
    "pbh.gov.br",
    "rio.rj.gov.br",
]

# Campos que nunca devem ser preenchidos pelo agente em domínios sensíveis
SENSITIVE_FIELD_LABELS: list[str] = [
    "cpf", "cnpj", "senha", "password", "nascimento",
    "codigo_acesso", "código de acesso", "chave", "captcha",
    "anti-robo", "anti-robô", "token", "pin", "otp",
    "codigo_verificacao", "código de verificação",
]

# ---------------------------------------------------------------------------
# Políticas declarativas (Action CSP)
# ---------------------------------------------------------------------------

# Domínios permitidos para navegação
ALLOWED_DOMAINS: list[str] = [
    "localhost",
    "127.0.0.1",
    "*.nexus.com",
    # Gov.br e Receita Federal
    "*.gov.br",
    "*.fazenda.gov.br",
    "*.receita.fazenda.gov.br",
    # Simples Nacional / PGMEI
    "*.receita.fazenda.gov.br",
    # NFS-e (prefeituras usam subdomínios variados)
    "*.prefeitura.sp.gov.br",
    "*.pbh.gov.br",
    "*.rio.rj.gov.br",
    # Comunicação
    "web.whatsapp.com",
    "calendar.google.com",
    "mail.google.com",
    # Ferramentas de negócio comuns
    "*.linkedin.com",
    "*.google.com",
    "*.microsoft.com",
]

# Ações e suas regras
ACTION_POLICIES: dict[str, dict[str, Any]] = {
    # --- Browser actions (baixo risco) ---
    "browser_navigate": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "allowed_domains": ALLOWED_DOMAINS,
        "max_per_task": 50,
    },
    "browser_click": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 100,
    },
    "browser_type": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 50,
        "forbidden_fields": [
            "password", "senha", "credit_card", "cartao",
            "credit-card", "card-number", "cvv", "cvc",
            "card_number", "cardnumber", "cc-number",
            "secret", "token", "api_key", "apikey",
            "ssn", "social-security",
        ],
    },
    "browser_wait": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_seconds": 30,
    },
    "browser_screenshot": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 20,
    },
    "browser_press_key": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 50,
    },
    "browser_wait_selector": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 50,
    },
    "browser_get_text": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 50,
    },
    "browser_close": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 5,
    },

    # --- Novas browser actions (Blueprint Comet) ---
    "browser_scroll": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 100,
    },
    "browser_hover": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 50,
    },
    "browser_select_option": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 30,
    },
    "browser_check_checkbox": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 30,
    },
    "browser_submit_form": {
        "risk": ActionRisk.MEDIUM,
        "requires_approval": False,
        "max_per_task": 10,
    },
    "browser_upload_file": {
        "risk": ActionRisk.MEDIUM,
        "requires_approval": True,
        "max_per_task": 5,
    },
    "browser_go_back": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 20,
    },
    "browser_go_forward": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 20,
    },
    "browser_get_attribute": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 50,
    },
    "browser_extract_table": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 20,
    },
    "browser_find_by_text": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 50,
    },
    "browser_evaluate_js": {
        "risk": ActionRisk.MEDIUM,
        "requires_approval": False,
        "max_per_task": 20,
        "blocked_expressions": ["fetch(", "XMLHttpRequest", "eval(", "Function(", "document.cookie"],
    },
    "browser_handle_dialog": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 10,
    },
    "browser_drag_drop": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 10,
    },
    "browser_get_page_state": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 50,
    },

    # --- CRM actions (médio risco) ---
    "crm_list_clients": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
    },
    "crm_get_client": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
    },
    "crm_create_client": {
        "risk": ActionRisk.MEDIUM,
        "requires_approval": False,
        "max_per_task": 10,
    },
    "crm_update_client": {
        "risk": ActionRisk.MEDIUM,
        "requires_approval": False,
        "max_per_task": 10,
    },
    "crm_delete_client": {
        "risk": ActionRisk.HIGH,
        "requires_approval": True,
    },
    "crm_create_appointment": {
        "risk": ActionRisk.MEDIUM,
        "requires_approval": False,
        "max_per_task": 5,
    },
    "crm_create_transaction": {
        "risk": ActionRisk.MEDIUM,
        "requires_approval": False,
        "max_per_task": 10,
    },

    # --- Comunicação (alto risco) ---
    "send_email": {
        "risk": ActionRisk.HIGH,
        "requires_approval": True,
        "allowed_recipients_pattern": r".+",  # Pode restringir domínio
        "max_per_task": 3,
    },
    "send_whatsapp": {
        "risk": ActionRisk.HIGH,
        "requires_approval": True,
        "max_per_task": 3,
    },

    # --- Financeiro (crítico) ---
    "create_invoice": {
        "risk": ActionRisk.HIGH,
        "requires_approval": True,
        "max_per_task": 5,
    },
    "process_payment": {
        "risk": ActionRisk.CRITICAL,
        "requires_approval": True,
        "max_per_task": 1,
    },

    # --- Resposta ao usuário (sem risco) ---
    "respond_to_user": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
    },

    # --- Human-in-the-loop: pausa para input do usuário (sem risco) ---
    "wait_for_user_login": {
        "risk": ActionRisk.LOW,
        "requires_approval": False,
        "max_per_task": 5,
    },
}

# Ações bloqueadas — nunca são permitidas
BLOCKED_ACTIONS: set[str] = {
    "delete_database",
    "drop_table",
    "format_disk",
    "execute_shell",
    "download_executable",
    "modify_env",
}


# ---------------------------------------------------------------------------
# Validação de domínio
# ---------------------------------------------------------------------------

def _domain_matches(url: str, patterns: list[str]) -> bool:
    """Verifica se URL pertence a um domínio permitido."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
    except Exception:
        return False

    for pattern in patterns:
        if pattern.startswith("*."):
            suffix = pattern[1:]  # .nexus.com
            if hostname.endswith(suffix) or hostname == pattern[2:]:
                return True
        else:
            if hostname == pattern:
                return True
    return False


# ---------------------------------------------------------------------------
# Validador de campo proibido
# ---------------------------------------------------------------------------

def _contains_forbidden_field(params: dict, forbidden: list[str]) -> str | None:
    """Retorna o nome do campo proibido se encontrado."""
    selector = str(params.get("selector", "")).lower()
    field_name = str(params.get("field", "")).lower()
    combined = f"{selector} {field_name}"
    for f in forbidden:
        if f in combined:
            return f
    return None


# ---------------------------------------------------------------------------
# Engine de políticas
# ---------------------------------------------------------------------------

# Contadores por task (resetados a cada tarefa)
_action_counts: dict[str, dict[str, int]] = {}


def reset_counters(task_id: str) -> None:
    """Reseta contadores de ações para uma nova tarefa."""
    _action_counts[task_id] = {}


def evaluate_action(
    task_id: str,
    action: PlannedAction,
) -> PolicyDecision:
    """Avalia uma ação contra as políticas declaradas.
    
    Retorna PolicyDecision com:
    - allowed: se a ação pode ser executada
    - reason: motivo do bloqueio/aprovação
    - modified_params: parâmetros ajustados (se necessário)
    """
    tool = action.tool

    # 1. Ação explicitamente bloqueada
    if tool in BLOCKED_ACTIONS:
        logger.warning(f"🚫 Ação bloqueada por política: {tool}")
        return PolicyDecision(
            action=action,
            allowed=False,
            reason=f"Ação '{tool}' está na lista de bloqueio permanente",
        )

    # 2. Ação não conhecida
    if tool not in ACTION_POLICIES:
        logger.warning(f"⚠️ Ação desconhecida: {tool}")
        return PolicyDecision(
            action=action,
            allowed=False,
            reason=f"Ação '{tool}' não está registrada nas políticas",
        )

    policy = ACTION_POLICIES[tool]

    # 3. Verificar limite de execuções
    if task_id not in _action_counts:
        _action_counts[task_id] = {}
    counts = _action_counts[task_id]
    counts[tool] = counts.get(tool, 0) + 1

    max_per_task = policy.get("max_per_task")
    if max_per_task and counts[tool] > max_per_task:
        logger.warning(f"⚠️ Limite de {tool} excedido: {counts[tool]}/{max_per_task}")
        return PolicyDecision(
            action=action,
            allowed=False,
            reason=f"Limite de '{tool}' excedido ({max_per_task} por tarefa)",
        )

    # 4. Verificar domínio (browser_navigate)
    allowed_domains = policy.get("allowed_domains")
    if allowed_domains:
        url = action.params.get("url", "")
        if url and not _domain_matches(url, allowed_domains):
            logger.warning(f"🚫 Domínio não permitido: {url}")
            return PolicyDecision(
                action=action,
                allowed=False,
                reason=f"Domínio de '{url}' não está na lista permitida",
            )

    # 5. Verificar campos proibidos (browser_type)
    forbidden = policy.get("forbidden_fields", [])
    if forbidden:
        bad_field = _contains_forbidden_field(action.params, forbidden)
        if bad_field:
            logger.warning(f"🚫 Campo sensível detectado: {bad_field}")
            return PolicyDecision(
                action=action,
                allowed=False,
                reason=f"Campo sensível detectado: '{bad_field}'. Use variáveis de ambiente.",
            )

    # 5b. Bloqueio extra: browser_type em campos de login/CPF/senha em domínios sensíveis
    if tool == "browser_type":
        selector = str(action.params.get("selector", "")).lower()
        text_param = str(action.params.get("text", "")).lower()
        # Se o selector ou o texto indicam campo sensível em domínio sensível
        for label in SENSITIVE_FIELD_LABELS:
            if label in selector or label in text_param:
                logger.warning(
                    f"🚫 Policy: browser_type bloqueado em campo sensível '{label}' — "
                    "handoff para humano necessário"
                )
                return PolicyDecision(
                    action=action,
                    allowed=False,
                    reason=(
                        f"Digitação bloqueada em campo sensível ('{label}'). "
                        "O usuário deve preencher este campo manualmente."
                    ),
                )

    # 6. Verificar tempo de espera
    max_seconds = policy.get("max_seconds")
    if max_seconds:
        wait = action.params.get("seconds", 0) or action.params.get("timeout", 0)
        if wait > max_seconds:
            return PolicyDecision(
                action=action,
                allowed=True,
                reason=f"Tempo de espera reduzido de {wait}s para {max_seconds}s",
                modified_params={**action.params, "seconds": max_seconds},
            )

    # 7. Verificar padrão de destinatário (email/whatsapp)
    recipient_pattern = policy.get("allowed_recipients_pattern")
    if recipient_pattern:
        recipient = action.params.get("to", "") or action.params.get("recipient", "")
        if recipient and not re.match(recipient_pattern, recipient):
            return PolicyDecision(
                action=action,
                allowed=False,
                reason=f"Destinatário '{recipient}' não corresponde ao padrão permitido",
            )

    # 8. Ação permitida (com ou sem aprovação)
    requires_approval = policy.get("requires_approval", False)
    risk = policy.get("risk", ActionRisk.LOW)

    return PolicyDecision(
        action=action,
        allowed=True,
        reason=f"Permitida (risco: {risk.value})"
        + (" — requer aprovação humana" if requires_approval else ""),
    )


def evaluate_plan(
    task_id: str,
    actions: list[PlannedAction],
) -> list[PolicyDecision]:
    """Avalia um plano completo e retorna decisões para cada ação."""
    reset_counters(task_id)
    return [evaluate_action(task_id, a) for a in actions]


def plan_requires_approval(decisions: list[PolicyDecision]) -> bool:
    """Verifica se alguma ação do plano requer aprovação humana."""
    for d in decisions:
        if d.allowed:
            policy = ACTION_POLICIES.get(d.action.tool, {})
            if policy.get("requires_approval", False):
                return True
    return False


def get_approval_summary(decisions: list[PolicyDecision]) -> str:
    """Gera resumo legível das ações que precisam de aprovação."""
    lines = ["⚠️ As seguintes ações precisam da sua aprovação:\n"]
    for i, d in enumerate(decisions, 1):
        if d.allowed:
            policy = ACTION_POLICIES.get(d.action.tool, {})
            if policy.get("requires_approval", False):
                risk = policy.get("risk", ActionRisk.LOW)
                icon = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}.get(
                    risk.value, "⚪"
                )
                lines.append(
                    f"{i}. {icon} **{d.action.tool}** — {d.action.reason}"
                )
                if d.action.params:
                    # Mostra params sem dados sensíveis
                    safe_params = {
                        k: v for k, v in d.action.params.items()
                        if k not in ("password", "senha", "token", "secret")
                    }
                    if safe_params:
                        lines.append(f"   Parâmetros: {safe_params}")
    lines.append("\nResponda **APROVADO** para continuar ou **RECUSAR** para cancelar.")
    return "\n".join(lines)
