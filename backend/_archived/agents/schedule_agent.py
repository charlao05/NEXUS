"""
Agente de Agenda Ativa - Compromissos do Usuário
Gerencia compromissos ATIVOS do usuário (pagamentos, vencimentos, NFs, fornecedores, compras)
A IA monitora e dá seguimento automaticamente.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ScheduleAgent:
    """
    Agente de Agenda Ativa
    
    Gerencia compromissos que O USUÁRIO precisa cumprir:
    - Pagamentos (DAS, fornecedores, salários)
    - Vencimentos (boletos, contas)
    - Notas Fiscais (emissão, entrega)
    - Fornecedores (reuniões, compras)
    - Compras (pedidos, entregas)
    
    A IA monitora prazos e envia lembretes automáticos.
    """
    
    def __init__(self):
        self.name = "schedule_agent"
        self.display_name = "📆 Agenda Ativa (Seus Compromissos)"
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa o agente de agenda ativa.
        
        Parâmetros:
            - commitment_type: tipo de compromisso (payment, deadline, invoice, supplier, purchase)
            - description: descrição do compromisso
            - due_date: data de vencimento (YYYY-MM-DD)
            - priority: prioridade (critical, high, normal, low)
            - client_id: ID do cliente relacionado (opcional)
            - reminder_days: dias de antecedência para lembrete (padrão: 3)
            - auto_notify: enviar notificações automáticas (padrão: true)
        """
        try:
            commitment_type = parameters.get("commitment_type", "payment")
            description = parameters.get("description", "Compromisso sem descrição")
            due_date_str = parameters.get("due_date")
            priority = parameters.get("priority", "normal")
            reminder_days = int(parameters.get("reminder_days", 3))
            auto_notify = parameters.get("auto_notify", True)
            
            if not due_date_str:
                return {
                    "status": "error",
                    "message": "due_date é obrigatório (formato: YYYY-MM-DD)"
                }
            
            # Parse due_date
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
            today = datetime.now()
            days_remaining = (due_date - today).days
            
            # Calcular data do lembrete
            reminder_date = due_date - timedelta(days=reminder_days)
            
            # Determinar urgência
            urgency = self._calculate_urgency(days_remaining, priority)
            
            # Gerar ações recomendadas
            actions = self._generate_actions(commitment_type, days_remaining, urgency)
            
            # Gerar lembrete
            reminder = self._generate_reminder(
                commitment_type=commitment_type,
                description=description,
                due_date=due_date,
                days_remaining=days_remaining,
                priority=priority,
                urgency=urgency
            )
            
            # Resultado
            result = {
                "status": "ok",
                "commitment": {
                    "type": commitment_type,
                    "description": description,
                    "due_date": due_date_str,
                    "priority": priority,
                    "days_remaining": days_remaining,
                    "urgency": urgency
                },
                "reminder": reminder,
                "reminder_date": reminder_date.strftime("%Y-%m-%d"),
                "actions": actions,
                "auto_notify": auto_notify,
                "notification_channels": ["email", "whatsapp", "sms"] if auto_notify else []
            }
            
            logger.info(f"Compromisso criado: {commitment_type} - {description} (vence em {days_remaining} dias)")
            return result
        
        except Exception as e:
            logger.exception(f"Erro no schedule_agent: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _calculate_urgency(self, days_remaining: int, priority: str) -> str:
        """Calcula urgência baseado em dias restantes e prioridade."""
        if days_remaining < 0:
            return "overdue"
        elif days_remaining == 0:
            return "today"
        elif days_remaining <= 1:
            return "critical"
        elif days_remaining <= 3:
            return "urgent"
        elif days_remaining <= 7:
            return "soon"
        elif priority == "critical":
            return "urgent"
        else:
            return "normal"
    
    def _generate_actions(self, commitment_type: str, days_remaining: int, urgency: str) -> List[str]:
        """Gera ações recomendadas por tipo de compromisso."""
        actions = []
        
        if commitment_type == "payment":
            if days_remaining <= 1:
                actions.append("🚨 Efetuar pagamento HOJE para evitar multa")
                actions.append("💰 Verificar saldo disponível")
            elif days_remaining <= 3:
                actions.append("💳 Separar valor para pagamento")
                actions.append("📋 Confirmar dados bancários")
            else:
                actions.append("📅 Marcar data no calendário")
        
        elif commitment_type == "invoice":
            if days_remaining <= 1:
                actions.append("📄 Emitir nota fiscal URGENTE")
                actions.append("📧 Enviar NF para cliente")
            else:
                actions.append("📝 Preparar dados para emissão")
                actions.append("✅ Verificar informações do cliente")
        
        elif commitment_type == "supplier":
            actions.append("📞 Confirmar reunião/entrega com fornecedor")
            actions.append("📋 Preparar lista de pedidos")
        
        elif commitment_type == "purchase":
            actions.append("🛒 Realizar pedido de compra")
            actions.append("💵 Verificar orçamento disponível")
        
        elif commitment_type == "deadline":
            if urgency in ["critical", "urgent", "today", "overdue"]:
                actions.append("⚠️ PRAZO CRÍTICO - Ação imediata necessária")
            actions.append("✅ Completar tarefa antes do vencimento")
        
        return actions
    
    def _generate_reminder(
        self,
        commitment_type: str,
        description: str,
        due_date: datetime,
        days_remaining: int,
        priority: str,
        urgency: str
    ) -> str:
        """Gera mensagem de lembrete personalizada."""
        
        type_emoji = {
            "payment": "💰",
            "deadline": "⏰",
            "invoice": "📄",
            "supplier": "🏢",
            "purchase": "🛒"
        }
        
        emoji = type_emoji.get(commitment_type, "📌")
        
        if urgency == "overdue":
            return f"🚨 ATRASADO! {emoji} {description} - Venceu há {abs(days_remaining)} dias"
        elif urgency == "today":
            return f"⚠️ HOJE! {emoji} {description} - Vence HOJE ({due_date.strftime('%d/%m/%Y')})"
        elif urgency == "critical":
            return f"🔴 URGENTE! {emoji} {description} - Vence AMANHÃ ({due_date.strftime('%d/%m/%Y')})"
        elif urgency == "urgent":
            return f"🟠 ATENÇÃO! {emoji} {description} - Vence em {days_remaining} dias ({due_date.strftime('%d/%m/%Y')})"
        elif urgency == "soon":
            return f"🟡 Em breve: {emoji} {description} - Vence em {days_remaining} dias ({due_date.strftime('%d/%m/%Y')})"
        else:
            return f"📅 {emoji} {description} - Vence em {days_remaining} dias ({due_date.strftime('%d/%m/%Y')})"


def run_schedule_agent(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Função helper para executar o agente."""
    agent = ScheduleAgent()
    return agent.execute(parameters)
