"""
Agente de Agenda Completa
=========================

Agente unificado que gerencia TODOS os compromissos do usuário:
- 📋 Prazos fiscais (DAS, DARF, tributos MEI)
- 💰 Pagamentos gerais (fornecedores, salários, contas)
- 📄 Notas Fiscais (emissão, entrega)
- 🏢 Reuniões e compromissos com fornecedores
- 🛒 Compras e pedidos
- ⏰ Outros deadlines e vencimentos

Funcionalidades:
- Cálculo inteligente de urgência (overdue, today, critical, urgent, soon, normal)
- Geração de lembretes humanizados
- Ações contextuais recomendadas por tipo
- Suporte a notificações multi-canal (WhatsApp, Email, SMS)
- Integração com dados de obrigações MEI
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class AgendaAgent:
    """
    Agente de Agenda Completa - Todos os Compromissos do Usuário
    
    Tipos de compromisso suportados:
    - fiscal: Obrigações fiscais (DAS, DARF, DASN, tributos)
    - payment: Pagamentos gerais (fornecedores, salários, contas)
    - invoice: Notas fiscais (emissão, entrega)
    - supplier: Fornecedores (reuniões, negociações)
    - purchase: Compras e pedidos
    - deadline: Outros prazos e vencimentos
    """
    
    # Mapeamento de emojis por tipo
    TYPE_EMOJI = {
        "fiscal": "📋",
        "payment": "💰",
        "invoice": "📄",
        "supplier": "🏢",
        "purchase": "🛒",
        "deadline": "⏰"
    }
    
    # Mapeamento de ações por tipo
    TYPE_ACTIONS = {
        "fiscal": [
            "📋 Acessar portal do governo",
            "💳 Separar valor para pagamento",
            "📧 Verificar se há atualizações de valores",
            "✅ Confirmar dados antes de pagar"
        ],
        "payment": [
            "💳 Separar valor para pagamento",
            "📋 Confirmar dados bancários",
            "📧 Notificar fornecedor do agendamento",
            "✅ Confirmar recebimento do boleto/PIX"
        ],
        "invoice": [
            "📄 Emitir nota fiscal URGENTE",
            "📧 Enviar NF para o cliente",
            "📋 Verificar dados cadastrais",
            "✅ Arquivar comprovante"
        ],
        "supplier": [
            "📞 Confirmar reunião com fornecedor",
            "📋 Preparar lista de pedidos",
            "💰 Revisar condições de pagamento",
            "✅ Enviar pauta prévia"
        ],
        "purchase": [
            "🛒 Confirmar pedido",
            "📦 Acompanhar rastreamento",
            "💰 Confirmar pagamento",
            "✅ Verificar prazo de entrega"
        ],
        "deadline": [
            "⚠️ PRAZO CRÍTICO - Ação imediata",
            "📋 Revisar pendências",
            "✅ Completar tarefa",
            "📧 Notificar stakeholders"
        ]
    }
    
    def __init__(self):
        self.name = "agenda_agent"
        self.display_name = "📆 Agenda Completa (Todos os Compromissos)"
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa o agente de agenda completa.
        
        Parâmetros:
            - commitment_type: tipo (fiscal, payment, invoice, supplier, purchase, deadline)
            - description: descrição do compromisso
            - due_date: data de vencimento (YYYY-MM-DD)
            - priority: prioridade (critical, high, normal, low)
            - estimated_value: valor estimado (opcional)
            - client_id: ID do cliente relacionado (opcional)
            - reminder_days: dias de antecedência para lembrete (padrão: 3)
            - auto_notify: enviar notificações automáticas (padrão: true)
            - obligations_json: JSON de obrigações MEI (opcional, para fiscal)
        """
        try:
            commitment_type = parameters.get("commitment_type", "deadline")
            description = parameters.get("description", "Compromisso sem descrição")
            due_date_str = parameters.get("due_date")
            priority = parameters.get("priority", "normal")
            estimated_value = parameters.get("estimated_value")
            reminder_days = int(parameters.get("reminder_days", 3))
            auto_notify = parameters.get("auto_notify", True)
            obligations_json = parameters.get("obligations_json")
            
            # Se obligations_json foi fornecido (modo fiscal/MEI)
            if obligations_json:
                return self._process_obligations(obligations_json, parameters)
            
            # Modo manual: compromisso único
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
                urgency=urgency,
                estimated_value=estimated_value
            )
            
            # Resultado
            result: Dict[str, Any] = {
                "status": "ok",
                "commitment": {
                    "type": commitment_type,
                    "description": description,
                    "due_date": due_date_str,
                    "priority": priority,
                    "days_remaining": days_remaining,
                    "urgency": urgency,
                    "estimated_value": estimated_value
                },
                "reminder": reminder,
                "reminder_date": reminder_date.strftime("%Y-%m-%d"),
                "actions": actions,
                "auto_notify": auto_notify,
                "notification_channels": ["email", "whatsapp", "sms"] if auto_notify else [],
                "emoji": self.TYPE_EMOJI.get(commitment_type, "⏰")
            }
            
            logger.info(f"Compromisso '{description}' processado: {urgency}, {days_remaining} dias")
            return result
            
        except ValueError as e:
            logger.error(f"Erro ao processar data: {e}")
            return {
                "status": "error",
                "message": f"Formato de data inválido: {e}"
            }
        except Exception as e:
            logger.exception(f"Erro no agente de agenda: {e}")
            return {
                "status": "error",
                "message": f"Erro ao processar compromisso: {e}"
            }
    
    def _process_obligations(self, obligations_json: str | List[Dict[str, Any]], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa múltiplas obrigações de um JSON (modo MEI/fiscal).
        
        Args:
            obligations_json: String JSON ou lista de obrigações
            parameters: Parâmetros adicionais
        
        Returns:
            Resultado com lista de alertas
        """
        try:
            # Parse JSON se for string
            obligations_data: Any
            if isinstance(obligations_json, str):
                obligations_data = json.loads(obligations_json)
            else:
                obligations_data = obligations_json
            
            # Extrair lista de obrigações
            obligations: List[Dict[str, Any]] = []
            if isinstance(obligations_data, dict):
                raw_obls: List[Any] = obligations_data.get("obligations", [])  # type: ignore[assignment]
                obligations = [o for o in raw_obls if isinstance(o, dict)]
            elif isinstance(obligations_data, list):
                obligations = [o for o in obligations_data if isinstance(o, dict)]  # type: ignore[misc]
            
            alert_days = parameters.get("alert_days", [30, 14, 7, 1])
            today = datetime.now()
            
            alerts: List[Dict[str, Any]] = []
            
            for obl_dict in obligations:
                due_date_str = obl_dict.get("due_date")
                if not due_date_str:
                    continue
                
                due_date = datetime.strptime(str(due_date_str), "%Y-%m-%d")
                days_remaining = (due_date - today).days
                
                # Verificar se está nos dias de alerta
                if days_remaining in alert_days or days_remaining <= 0:
                    priority_str = str(obl_dict.get("priority", "normal"))
                    urgency = self._calculate_urgency(days_remaining, priority_str)
                    
                    alert: Dict[str, Any] = {
                        "obligation_id": obl_dict.get("id"),
                        "name": obl_dict.get("name"),
                        "type": obl_dict.get("type", "fiscal"),
                        "due_date": due_date_str,
                        "days_remaining": days_remaining,
                        "estimated_value": obl_dict.get("estimated_value"),
                        "priority": priority_str,
                        "urgency": urgency,
                        "url_payment": obl_dict.get("url_payment"),
                        "notes": obl_dict.get("notes"),
                        "reminder": self._generate_reminder(
                            commitment_type="fiscal",
                            description=str(obl_dict.get("name", "Obrigação fiscal")),
                            due_date=due_date,
                            days_remaining=days_remaining,
                            priority=priority_str,
                            urgency=urgency,
                            estimated_value=obl_dict.get("estimated_value")
                        )
                    }
                    alerts.append(alert)
            
            return {
                "status": "ok",
                "alerts_count": len(alerts),
                "alerts": alerts,
                "message": f"{len(alerts)} obrigação(ões) próxima(s) de vencer"
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON inválido: {e}")
            return {
                "status": "error",
                "message": f"JSON de obrigações inválido: {e}"
            }
        except Exception as e:
            logger.exception(f"Erro ao processar obrigações: {e}")
            return {
                "status": "error",
                "message": f"Erro ao processar obrigações: {e}"
            }
    
    def _calculate_urgency(self, days_remaining: int, priority: str = "normal") -> str:
        """
        Calcula nível de urgência baseado em dias restantes e prioridade.
        
        Níveis:
        - overdue: já venceu
        - today: vence hoje
        - critical: ≤1 dia ou priority=critical
        - urgent: 2-3 dias ou priority=high
        - soon: 4-7 dias
        - normal: >7 dias
        """
        if days_remaining < 0:
            return "overdue"
        
        if days_remaining == 0:
            return "today"
        
        if priority == "critical" or days_remaining <= 1:
            return "critical"
        
        if priority == "high" or days_remaining <= 3:
            return "urgent"
        
        if days_remaining <= 7:
            return "soon"
        
        return "normal"
    
    def _generate_actions(self, commitment_type: str, days_remaining: int, urgency: str) -> List[str]:
        """
        Gera lista de ações recomendadas baseadas no tipo e urgência.
        """
        actions = self.TYPE_ACTIONS.get(commitment_type, self.TYPE_ACTIONS["deadline"])
        
        # Se está atrasado, adicionar ação crítica
        if urgency == "overdue":
            return ["🚨 ATRASADO - Ação imediata necessária!"] + actions[:2]
        
        # Se é hoje, retornar ações urgentes
        if urgency == "today":
            return actions[:3]
        
        # Retornar ações normais
        return actions[:2]
    
    def _generate_reminder(
        self,
        commitment_type: str,
        description: str,
        due_date: datetime,
        days_remaining: int,
        priority: str,
        urgency: str,
        estimated_value: Optional[float] = None
    ) -> str:
        """
        Gera mensagem de lembrete humanizada.
        """
        emoji = self.TYPE_EMOJI.get(commitment_type, "⏰")
        
        # Prefixo baseado em urgência
        if urgency == "overdue":
            prefix = f"🚨 ATRASADO! {emoji}"
            time_msg = f"Venceu há {abs(days_remaining)} dia(s)"
        elif urgency == "today":
            prefix = f"⚠️ HOJE! {emoji}"
            time_msg = "Vence HOJE"
        elif urgency == "critical":
            prefix = f"🔴 CRÍTICO! {emoji}"
            time_msg = f"Vence em {days_remaining} dia(s)"
        elif urgency == "urgent":
            prefix = f"🟠 ATENÇÃO! {emoji}"
            time_msg = f"Vence em {days_remaining} dia(s)"
        elif urgency == "soon":
            prefix = f"🟡 Em breve: {emoji}"
            time_msg = f"Vence em {days_remaining} dia(s)"
        else:
            prefix = f"📅 Lembrete: {emoji}"
            time_msg = f"Vence em {days_remaining} dia(s)"
        
        # Mensagem do valor (se fornecido)
        value_msg = f" - R$ {estimated_value:.2f}" if estimated_value else ""
        
        return f"{prefix} {description} - {time_msg}{value_msg}"


def run_agenda_agent(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Função helper para executar o agente de agenda.
    
    Args:
        parameters: Parâmetros do compromisso
    
    Returns:
        Resultado da execução
    """
    agent = AgendaAgent()
    return agent.execute(parameters)


# Função de compatibilidade para código legado que usa deadlines_agent
def check_deadlines(obligations_path: str, alert_days: list[int] = [30, 14, 7, 1]) -> Dict[str, Any]:
    """
    Função de compatibilidade para código legado.
    Carrega obrigações de arquivo e processa via AgendaAgent.
    """
    path = Path(obligations_path)
    if not path.exists():
        logger.error(f"Arquivo de obrigações não encontrado: {obligations_path}")
        return {"status": "error", "message": "Arquivo não encontrado"}
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            obligations_data = json.load(f)
        
        agent = AgendaAgent()
        # Usando método público para processar obrigações
        return agent.execute({
            "obligations_json": obligations_data,
            "alert_days": alert_days
        })
    except Exception as e:
        logger.exception(f"Erro ao processar obrigações: {e}")
        return {"status": "error", "message": str(e)}
