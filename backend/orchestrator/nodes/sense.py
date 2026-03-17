"""
Node SENSE — Coleta contexto do ambiente.
Para agentes CRM: busca dados do banco (clientes, agenda, financeiro).
Para browser agent: captura DOM/screenshot da página.
Inclui detecção de tela sensível (human-in-the-loop).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from backend.orchestrator.state import AgentState, TaskStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domínios e padrões de tela sensível (human-in-the-loop)
# ---------------------------------------------------------------------------

# Domínios onde o agente NUNCA deve digitar em campos de login/CPF/senha
SENSITIVE_DOMAINS: list[str] = [
    "receita.fazenda.gov.br",
    "cav.receita.fazenda.gov.br",   # e-CAC
    "www8.receita.fazenda.gov.br",  # Simples / PGMEI
    "servicos.receita.fazenda.gov.br",
    "gov.br",
    "www.gov.br",
    "acesso.gov.br",
    "sso.acesso.gov.br",
    # Bancos
    "bb.com.br",
    "caixa.gov.br",
    "itau.com.br",
    "bradesco.com.br",
    "santander.com.br",
    "nubank.com.br",
    # Prefeituras (NFS-e)
    "nfe.prefeitura.sp.gov.br",
    "prefeitura.sp.gov.br",
    "pbh.gov.br",
    "rio.rj.gov.br",
]

# Labels/placeholders que indicam campo sensível na página
_SENSITIVE_FIELD_PATTERNS: list[str] = [
    r"\bcpf\b", r"\bcnpj\b", r"\bsenha\b", r"\bpassword\b",
    r"\bc[oó]digo de acesso\b", r"\bchave de acesso\b",
    r"\bcertificado digital\b", r"\bcaptcha\b", r"\banti[- ]?rob[oô]\b",
    r"\bdata de nascimento\b", r"\bnascimento\b",
    r"\bc[oó]digo de verifica[cç][aã]o\b",
    r"\btoken\b", r"\bpin\b", r"\botp\b",
    r"\busu[aá]rio\b.*\bsenha\b", r"\blogin\b.*\bsenha\b",
]

# Textos de erro / avisos que indicam tela com proteção anti-robô
_ANTIBOT_PATTERNS: list[str] = [
    r"anti[- ]?rob[oô].*n[aã]o.*preenchido",
    r"anti[- ]?rob[oô].*incorret",
    r"captcha.*inv[aá]lid",
    r"captcha.*incorrect",
    r"verificar.*que.*n[aã]o.*rob[oô]",
    r"prove.*n[aã]o.*rob[oô]",
    r"challenge.*required",
    r"hcaptcha",
    r"recaptcha",
    r"cloudflare.*challenge",
]


def _is_sensitive_domain(url: str) -> bool:
    """Verifica se a URL pertence a um domínio sensível."""
    from urllib.parse import urlparse
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return False
    for domain in SENSITIVE_DOMAINS:
        if hostname == domain or hostname.endswith("." + domain):
            return True
    return False


def _detect_sensitive_screen(page_observation: str, page_url: str = "") -> dict[str, Any] | None:
    """Detecta se a página atual contém campos sensíveis que requerem input humano.
    
    Retorna dict com reason, hint e snapshot se detectado, None caso contrário.
    
    Inteligência de detecção:
    1. Verifica se está em domínio sensível
    2. Procura labels/placeholders de campos sensíveis (CPF, senha, captcha)
    3. Procura mensagens de anti-robô / captcha
    """
    obs_lower = page_observation.lower()
    
    # 1. Verificar domínio sensível
    is_sensitive = _is_sensitive_domain(page_url)
    
    # 2. Detectar campos sensíveis na observação da página
    sensitive_fields_found: list[str] = []
    for pattern in _SENSITIVE_FIELD_PATTERNS:
        if re.search(pattern, obs_lower):
            sensitive_fields_found.append(pattern.replace(r"\b", "").replace("\\b", ""))
    
    # 3. Detectar mensagens de anti-robô / captcha
    antibot_detected = False
    for pattern in _ANTIBOT_PATTERNS:
        if re.search(pattern, obs_lower):
            antibot_detected = True
            break
    
    # Decisão: se está em domínio sensível E encontrou campos sensíveis OU anti-robô
    has_login_fields = any(
        kw in obs_lower for kw in ["cpf", "cnpj", "senha", "password", "captcha", "anti-robô", "anti-robo"]
    )
    
    if (is_sensitive and (has_login_fields or antibot_detected)) or antibot_detected:
        # Montar a razão
        reasons = []
        if is_sensitive:
            reasons.append(f"domínio sensível ({page_url})")
        if sensitive_fields_found:
            fields = ", ".join(set(f.strip() for f in sensitive_fields_found[:5]))
            reasons.append(f"campos sensíveis detectados: {fields}")
        if antibot_detected:
            reasons.append("proteção anti-robô / captcha detectada")
        
        reason = "Handoff para humano — " + "; ".join(reasons)
        
        # Montar instrução simples para o MEI
        hint_parts = ["Agora é a parte que só você pode fazer."]
        if has_login_fields:
            hint_parts.append("Digite seus dados (CPF, senha ou data de nascimento) na tela que foi aberta.")
        if antibot_detected:
            hint_parts.append("Pode ser preciso resolver uma verificação anti-robô (captcha).")
        hint_parts.append("Depois de preencher e clicar no botão do site (ex: 'Consultar', 'Entrar'), volte aqui e clique em 'Continuar Automação'.")
        hint_parts.append("O robô não vê nem guarda seu CPF ou senha. Isso é só entre você e o site.")
        
        hint = "\n".join(hint_parts)
        
        # Snapshot textual da tela (sem dados sensíveis — apenas estrutura)
        snapshot = page_observation[:500] if len(page_observation) > 500 else page_observation
        
        logger.info(f"🔒 SENSE: Tela sensível detectada — {reason}")
        
        return {
            "reason": reason,
            "hint": hint,
            "snapshot": snapshot,
        }
    
    return None


def sense_node(state: AgentState) -> dict[str, Any]:
    """Coleta contexto relevante para o agente tomar decisões.
    
    - CRM agents: busca dados reais do banco
    - Browser agent: captura estado da página
    - NF agent: carrega dados de vendas
    """
    agent_type = state.get("agent_type", "")
    user_id = state.get("user_id", 0)
    
    logger.info(f"👁️ SENSE: coletando contexto para agent={agent_type}, user={user_id}")
    
    updates: dict[str, Any] = {
        "status": TaskStatus.SENSING.value,
        "updated_at": datetime.now().isoformat(),
    }
    
    try:
        if agent_type in ("clientes", "financeiro", "contabilidade", "cobranca", "agenda"):
            updates["crm_context"] = _get_crm_context(user_id)
            
        elif agent_type == "browser":
            # Percepção DOM — estilo Steward/Comet
            # Na primeira iteração, apenas prepara config.
            # Em iterações subsequentes, captura estado real da página.
            iteration = state.get("iteration", 0)
            if iteration > 0:
                observation = _get_browser_perception()
                updates["page_observation"] = observation
                
                # --- Human-in-the-loop: detectar tela sensível ---
                # Extrair URL atual do browser (se possível)
                current_url = _get_current_browser_url()
                sensitive = _detect_sensitive_screen(observation, current_url)
                if sensitive:
                    updates["awaiting_user_input"] = True
                    updates["awaiting_user_reason"] = sensitive["reason"]
                    updates["resume_hint"] = sensitive["hint"]
                    updates["sensitive_screen_snapshot"] = sensitive["snapshot"]
                    logger.info(
                        f"🔒 SENSE: Handoff humano ativado — {sensitive['reason']}"
                    )
                else:
                    # Limpar flags de handoff se a tela não é mais sensível (retomada pós-login)
                    if state.get("awaiting_user_input"):
                        updates["awaiting_user_input"] = False
                        updates["awaiting_user_reason"] = ""
                        updates["resume_hint"] = ""
                        updates["sensitive_screen_snapshot"] = ""
                        logger.info("✅ SENSE: Tela pós-login detectada — retomando automação")
            else:
                site_config = state.get("site_config", {})
                updates["page_observation"] = (
                    f"Configuração do site carregada: {site_config.get('name', 'N/A')}. "
                    f"Aguardando primeira navegação."
                )
            
        elif agent_type == "nf":
            updates["crm_context"] = _get_nf_context(user_id)
            
        elif agent_type == "assistente":
            updates["crm_context"] = _get_assistant_context(user_id)
            
        else:
            updates["crm_context"] = "Nenhum contexto específico disponível."
            
    except Exception as e:
        logger.error(f"Erro no sense: {e}")
        updates["error"] = f"Erro ao coletar contexto: {e}"
        
    return updates


def _get_crm_context(user_id: int) -> str:
    """Busca contexto CRM do banco de dados."""
    try:
        from backend.database.models import SessionLocal, Client, Appointment, Transaction
        from sqlalchemy import func
        from datetime import date
        
        db = SessionLocal()
        try:
            # Contagem de clientes
            total = db.query(func.count(Client.id)).filter(
                Client.user_id == user_id
            ).scalar() or 0
            
            active = db.query(func.count(Client.id)).filter(
                Client.user_id == user_id,
                Client.is_active == True  # noqa: E712
            ).scalar() or 0
            
            # Agendamentos de hoje
            today = date.today()
            appts_today = db.query(func.count(Appointment.id)).filter(
                Appointment.user_id == user_id,
                func.date(Appointment.scheduled_at) == today
            ).scalar() or 0
            
            # Receita do mês
            from datetime import datetime as dt
            first_day = today.replace(day=1)
            month_revenue = db.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id,
                Transaction.type == "receita",
                Transaction.date >= first_day
            ).scalar() or 0
            
            lines = [
                f"👥 Você tem {total} clientes ({active} ativos)",
                f"📅 Hoje: {appts_today} compromissos",
                f"💰 Receita do mês: R$ {month_revenue:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            ]
            
            return "\n".join(lines)
        finally:
            db.close()
            
    except Exception as e:
        logger.warning(f"Não consegui acessar CRM: {e}")
        return "Dados do CRM indisponíveis no momento."


def _get_nf_context(user_id: int) -> str:
    """Contexto para emissão de NF."""
    try:
        from backend.database.models import SessionLocal, Client, Transaction
        from sqlalchemy import func
        
        db = SessionLocal()
        try:
            pending_invoices = db.query(func.count(Transaction.id)).filter(
                Transaction.user_id == user_id,
                Transaction.type == "income",
            ).scalar() or 0
            
            return f"📄 Transações registradas: {pending_invoices}"
        finally:
            db.close()
    except Exception as e:
        return f"Contexto NF indisponível: {e}"


def _get_assistant_context(user_id: int) -> str:
    """Contexto resumido para o assistente geral."""
    crm = _get_crm_context(user_id)
    return f"Resumo geral:\n{crm}"


def _get_browser_perception() -> str:
    """Captura percepção DOM da página aberta (se houver browser ativo).
    
    Usa a camada de percepção estilo Steward para extrair:
    - URL e título atuais
    - Elementos interativos filtrados e numerados
    - Tipo de página (form, table, login, etc.)
    """
    try:
        from backend.orchestrator.tools.browser import _browser_state
        from backend.browser.perception import get_compact_observation

        page = _browser_state.get("page")
        if page is None:
            return "Browser não está aberto. Navegue para uma URL primeiro."

        observation = get_compact_observation(page)
        return observation

    except Exception as e:
        logger.warning(f"Erro na percepção do browser: {e}")
        return f"Erro ao capturar percepção do browser: {e}"


def _get_current_browser_url() -> str:
    """Obtém a URL atual do browser ativo (para verificação de domínio sensível)."""
    try:
        from backend.orchestrator.tools.browser import _browser_state
        page = _browser_state.get("page")
        if page is not None:
            return page.url or ""
    except Exception:
        pass
    return ""
