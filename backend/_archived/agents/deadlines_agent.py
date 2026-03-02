"""
Agente de Prazos & DAS

Responsabilidade: Monitorar obrigações fiscais e prazos críticos do MEI.
Funcionalidades:
  1. Ler obrigações de um JSON
  2. Detectar o que vence em X dias (30d, 7d, 1d)
  3. Gerar mensagens humanizadas com LLM
  4. (Futuro) Abrir portais de governo via Playwright para pagar
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from backend.utils.logging_utils import get_logger
except ImportError:
    from ..utils.logging_utils import get_logger

logger = get_logger(__name__)


class DeadlineAlert:
    """Representa um alerta de prazo próximo."""

    def __init__(
        self,
        obligation_id: str,
        name: str,
        type_: str,
        due_date: str,
        days_remaining: int,
        estimated_value: Optional[float] = None,
        priority: str = "normal",
        url_payment: Optional[str] = None,
        notes: Optional[str] = None,
    ):
        self.obligation_id = obligation_id
        self.name = name
        self.type = type_
        self.due_date = due_date
        self.days_remaining = days_remaining
        self.estimated_value = estimated_value
        self.priority = priority
        self.url_payment = url_payment
        self.notes = notes

    def to_dict(self):
        return {
            "obligation_id": self.obligation_id,
            "name": self.name,
            "type": self.type,
            "due_date": self.due_date,
            "days_remaining": self.days_remaining,
            "estimated_value": self.estimated_value,
            "priority": self.priority,
            "url_payment": self.url_payment,
            "notes": self.notes,
        }

    def __repr__(self):
        return f"DeadlineAlert(name={self.name}, days={self.days_remaining}, priority={self.priority})"


def load_obligations(obligations_path: str) -> dict:
    """
    Carrega as obrigações do MEI de um arquivo JSON.

    Args:
        obligations_path: Caminho para o arquivo JSON com obrigações

    Returns:
        dict: Dados do arquivo JSON (mei_id, obligations, settings)
    """
    path = Path(obligations_path)
    if not path.exists():
        logger.error(f"Arquivo de obrigações não encontrado: {obligations_path}")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Obrigações carregadas: {len(data.get('obligations', []))} items")
        return data
    except Exception as e:
        logger.error(f"Erro ao carregar obrigações: {e}")
        return {}


def check_deadlines(
    obligations_path: str, alert_days: list[int] = [30, 14, 7, 1]
) -> list[DeadlineAlert]:
    """
    Verifica quais obrigações estão próximas de vencer.

    Args:
        obligations_path: Caminho para o arquivo JSON com obrigações
        alert_days: Lista de dias para gerar alertas (ex: [30, 7, 1])

    Returns:
        list[DeadlineAlert]: Lista de alertas ordenada por urgência
    """
    data = load_obligations(obligations_path)
    if not data:
        return []

    obligations = data.get("obligations", [])
    alerts = []
    today = datetime.now().date()

    for obligation in obligations:
        try:
            due_date = datetime.strptime(obligation["due_date"], "%Y-%m-%d").date()
            days_remaining = (due_date - today).days

            # Se está vencida ou está em um dos períodos de alerta
            if days_remaining <= 0:
                # Já vencida → prioridade crítica
                priority = "critical"
            elif days_remaining in alert_days or any(
                d <= days_remaining < (d + 1) for d in alert_days if days_remaining < d
            ):
                # Período de alerta → marca como high por padrão
                priority = obligation.get("priority", "high")
            else:
                continue  # Não gera alerta

            alert = DeadlineAlert(
                obligation_id=obligation["id"],
                name=obligation["name"],
                type_=obligation["type"],
                due_date=obligation["due_date"],
                days_remaining=days_remaining,
                estimated_value=obligation.get("estimated_value"),
                priority=priority,
                url_payment=obligation.get("url_payment"),
                notes=obligation.get("notes"),
            )
            alerts.append(alert)

        except (ValueError, KeyError) as e:
            logger.warning(f"Erro ao processar obrigação {obligation.get('id')}: {e}")
            continue

    # Ordena por urgência: crítico > high > normal, depois por dias restantes
    priority_order = {"critical": 0, "high": 1, "normal": 2}
    alerts.sort(key=lambda a: (priority_order.get(a.priority, 3), a.days_remaining))

    logger.info(f"Alertas gerados: {len(alerts)} obrigações próximas de vencer")
    return alerts


def generate_reminder_message(alerts: list[DeadlineAlert], mei_name: Optional[str] = None) -> str:
    """
    Gera uma mensagem humanizada com os alertas de prazos.

    Nota: Esta versão usa fallback direto (sem LLM para evitar overhead).
    Se precisar LLM, chamar generate_reminder_message_with_llm().

    Args:
        alerts: Lista de DeadlineAlert
        mei_name: Nome do MEI (para personalização)

    Returns:
        str: Mensagem formatada em português
    """
    if not alerts:
        return "Nenhum alerta de prazo no momento. Tudo em dia! ✅"

    # Usa fallback direto (mais eficiente)
    return generate_fallback_message(alerts)


def generate_reminder_message_with_llm(
    alerts: list[DeadlineAlert], mei_name: Optional[str] = None
) -> str:
    """
    Gera mensagem com LLM (mais custoso, mas mais personalizado).

    Args:
        alerts: Lista de DeadlineAlert
        mei_name: Nome do MEI

    Returns:
        str: Mensagem formatada pelo LLM
    """
    if not alerts:
        return "Nenhum alerta de prazo no momento. Tudo em dia! ✅"

    # Monta um resumo estruturado para o LLM
    alerts_lines = []
    for a in alerts[:5]:  # Limita aos 5 mais urgentes
        valor_str = f"R${a.estimated_value:.2f}" if a.estimated_value else "N/A"
        line = f"- {a.name} vence em {a.days_remaining} dias ({a.due_date}). Prioridade: {a.priority}. Valor: {valor_str}"
        alerts_lines.append(line)
    alerts_text = "\n".join(alerts_lines)

    prompt = f"""
Você é um assistente financeiro para MEI (Microempreendedor Individual).

Gere uma mensagem CURTA, CLARA e MOTIVADORA sobre os seguintes prazos próximos de vencer:

{alerts_text}

Dicas:
1. Comece com um tom amigável.
2. Destaque os 2-3 mais urgentes com emoji ⚠️ ou 🔴.
3. Ofereça uma ação clara ("Quer que eu abra o portal?").
4. Mantenha tudo em português simples, como falando com um amigo.
5. Máximo 200 palavras.

Responda APENAS com a mensagem, sem explicações adicionais.
"""

    try:
        logger.info("Gerando mensagem com LLM...")
        from backend.utils.llm_client import gerar_plano_acao

        # Chama o cliente LLM
        message = gerar_plano_acao(
            site="mei_agenda",  # Site genérico
            objetivo=prompt,
            contexto_site={"tipo": "notificacao"},
        )
        logger.info("Mensagem gerada com sucesso")
        return generate_fallback_message(alerts)
    except Exception as e:
        logger.warning(f"Erro ao gerar mensagem com LLM: {e}. Usando fallback.")
        # Fallback: gera mensagem simples sem LLM
        return generate_fallback_message(alerts)


def generate_fallback_message(alerts: list[DeadlineAlert]) -> str:
    """
    Gera mensagem simples sem dependência de LLM (fallback).
    """
    if not alerts:
        return "Tudo em dia! ✅"

    critical_alerts = [a for a in alerts if a.priority == "critical"]
    high_alerts = [a for a in alerts if a.priority == "high"]

    lines = []

    if critical_alerts:
        lines.append("🔴 CRÍTICO - Ação imediata necessária:")
        for alert in critical_alerts[:2]:
            lines.append(f"  • {alert.name} vence em {alert.days_remaining} dias")

    if high_alerts:
        lines.append("\n⚠️ IMPORTANTE - Próximos dias:")
        for alert in high_alerts[:2]:
            lines.append(f"  • {alert.name} vence em {alert.days_remaining} dias")

    if len(alerts) > 4:
        lines.append(f"\n+ {len(alerts) - 4} outros alertas pendentes")

    lines.append("\nQuer ajuda para pagar ou declarar?")

    return "\n".join(lines)


def suggest_action(alert: DeadlineAlert) -> dict:
    """
    Sugere uma ação (e.g., "abrir portal gov") baseada no tipo de obrigação.

    Args:
        alert: DeadlineAlert

    Returns:
        dict: Estrutura com ação sugerida (tipo, URL, instruções)
    """
    actions_map = {
        "das": {
            "type": "open_portal",
            "label": "Gerar DAS",
            "url": "https://servicos.receita.federal.gov.br/",
            "steps": [
                "Clique em 'DAS'",
                "Insira seu CNPJ",
                "Gere o DAS para o mês correto",
                "Imprima ou pague online",
            ],
        },
        "dasn": {
            "type": "open_portal",
            "label": "Declarar DASN",
            "url": "https://www8.receita.federal.gov.br/simplesnacional/",
            "steps": [
                "Entre no Simples Nacional",
                "Selecione 'DASN Anual'",
                "Declare a receita bruta",
                "Assine e envie",
            ],
        },
        "fixed_expense": {
            "type": "manual_payment",
            "label": "Pagar conta",
            "url": alert.url_payment,
            "steps": [
                "Entre no app/site do provedor",
                "Procure por boleto ou link de pagamento",
                "Pague até {alert.due_date}",
            ],
        },
        "utility": {
            "type": "manual_payment",
            "label": "Pagar conta",
            "url": alert.url_payment,
            "steps": ["Entre na conta online", "Gere boleto ou pague direto"],
        },
        "registration": {
            "type": "open_portal",
            "label": "Manter CNPJ ativo",
            "url": "https://www.gov.br/empresas/pt-br/",
            "steps": [
                "Acesse o portal de governo",
                "Atualize dados cadastrais",
                "Confirme CNPJ ativo",
            ],
        },
    }

    action = actions_map.get(alert.type, {"type": "manual", "label": "Ação manual"})
    return {
        "obligation_id": alert.obligation_id,
        "suggested_action": action.get("label"),
        "action_type": action.get("type"),
        "url": action.get("url"),
        "steps": action.get("steps", []),
    }


# --- TESTES / MAIN ---

if __name__ == "__main__":
    # Teste local do agente
    obligations_file = "data/mei_obligations.json"

    logger.info("=== Teste: Agente de Prazos & DAS ===")

    # 1. Carregar obrigações
    logger.info("\n1. Carregando obrigações...")
    data = load_obligations(obligations_file)
    if data:
        logger.info(f"   MEI: {data.get('mei_name')}")
        logger.info(f"   Obrigações: {len(data.get('obligations', []))}")

    # 2. Detectar alertas
    logger.info("\n2. Verificando prazos próximos...")
    alerts = check_deadlines(obligations_file)
    for alert in alerts[:5]:
        logger.info(f"   {alert.name} - {alert.days_remaining}d restantes")

    # 3. Gerar mensagem
    logger.info("\n3. Gerando mensagem...")
    message = generate_reminder_message(alerts, mei_name=data.get("mei_name"))
    logger.info(f"\n   {message}")

    # 4. Sugerir ações
    logger.info("\n4. Sugestões de ação:")
    for alert in alerts[:2]:
        action = suggest_action(alert)
        logger.info(f"   {alert.name}: {action['suggested_action']}")
        if action.get("url"):
            logger.info(f"   URL: {action['url']}")
