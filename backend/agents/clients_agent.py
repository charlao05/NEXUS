"""
Agente de Gestão de Clientes (CRM Completo)
============================================

Gerencia cadastro completo de clientes com:
- Dados pessoais e contato
- Histórico de agendamentos e reuniões
- Aniversário e datas importantes
- Última oportunidade/interação
- Probabilidade de compra (score IA)
- Probabilidade de comparecimento (score IA)
- Notas e observações
- Segmentação e tags
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ClientsAgent:
    """
    Agente de Gestão de Clientes - CRM Completo
    
    Funcionalidades:
    - Cadastro completo de cliente
    - Agendamento de reuniões/atendimentos
    - Tracking de última interação
    - Score de probabilidade de compra (IA)
    - Score de probabilidade de comparecimento (IA)
    - Gestão de aniversários e datas importantes
    - Histórico completo de interações
    - Segmentação e tags
    """
    
    def __init__(self):
        self.name = "clients_agent"
        self.display_name = "👥 Clientes (CRM Completo)"
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa o agente de clientes.
        
        Parâmetros:
            - action: tipo de ação (create, update, schedule, analyze)
            
            # Dados do cliente
            - client_name: nome completo
            - phone: telefone
            - email: email
            - cpf_cnpj: CPF ou CNPJ
            - birth_date: data de aniversário
            - address: endereço completo
            - city: cidade
            - state: estado
            
            # Segmentação
            - segment: segmento (Premium, Standard, Lead)
            - tags: tags (vip, recorrente, novo, etc)
            - source: origem (indicação, instagram, google, etc)
            
            # Agendamento
            - appointment_datetime: data/hora do agendamento
            - appointment_type: tipo (consulta, reunião, atendimento)
            - appointment_notes: notas do agendamento
            
            # Oportunidade
            - opportunity_type: tipo de oportunidade
            - opportunity_value: valor estimado
            - opportunity_stage: estágio (prospecção, negociação, fechamento)
            
            # Notas
            - notes: observações gerais
        """
        try:
            action = parameters.get("action", "create")
            
            if action == "create":
                return self._create_client(parameters)
            elif action == "schedule":
                return self._schedule_appointment(parameters)
            elif action == "analyze":
                return self._analyze_client(parameters)
            elif action == "update":
                return self._update_client(parameters)
            else:
                return {
                    "status": "error",
                    "message": f"Ação desconhecida: {action}"
                }
                
        except Exception as e:
            logger.exception(f"Erro no clients_agent: {e}")
            return {
                "status": "error",
                "message": f"Erro ao processar cliente: {e}"
            }
    
    def _create_client(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Cria novo cadastro de cliente."""
        
        client_name = parameters.get("client_name")
        if not client_name:
            return {
                "status": "error",
                "message": "client_name é obrigatório"
            }
        
        # Dados básicos
        client_data = {
            "name": client_name,
            "phone": parameters.get("phone"),
            "email": parameters.get("email"),
            "cpf_cnpj": parameters.get("cpf_cnpj"),
            "birth_date": parameters.get("birth_date"),
            "address": parameters.get("address"),
            "city": parameters.get("city"),
            "state": parameters.get("state"),
            
            # Segmentação
            "segment": parameters.get("segment", "Standard"),
            "tags": parameters.get("tags", []),
            "source": parameters.get("source", "manual"),
            
            # Metadata
            "created_at": datetime.now().isoformat(),
            "last_interaction": datetime.now().isoformat(),
            "total_appointments": 0,
            "total_purchases": 0,
            "total_revenue": 0.0,
            
            # Scores (serão calculados quando houver histórico real)
            "purchase_probability": None,
            "attendance_probability": None,
            "churn_risk": None,
            
            # Notas
            "notes": parameters.get("notes", "")
        }
        
        # Calcular próximo aniversário
        if client_data["birth_date"]:
            client_data["days_until_birthday"] = self._days_until_birthday(client_data["birth_date"])
        
        return {
            "status": "created",
            "client": client_data,
            "message": f"✅ Cliente {client_name} cadastrado com sucesso!",
            "recommendations": self._generate_recommendations(client_data),
            "next_actions": [
                "📞 Agendar primeira reunião",
                "📧 Enviar email de boas-vindas",
                "🎂 Adicionar lembrete de aniversário",
                "📊 Iniciar tracking de interações"
            ]
        }
    
    def _schedule_appointment(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Agenda reunião/atendimento com cliente."""
        
        client_name = parameters.get("client_name")
        datetime_str = parameters.get("appointment_datetime")
        
        if not client_name or not datetime_str:
            return {
                "status": "error",
                "message": "client_name e appointment_datetime são obrigatórios"
            }
        
        # Parse datetime
        try:
            appointment_dt = datetime.fromisoformat(datetime_str.replace('T', ' '))
        except:
            try:
                appointment_dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
            except:
                return {
                    "status": "error",
                    "message": "Formato de data/hora inválido. Use: YYYY-MM-DD HH:MM"
                }
        
        days_until = (appointment_dt - datetime.now()).days
        hours_until = (appointment_dt - datetime.now()).total_seconds() / 3600
        
        # Calcular probabilidade de comparecimento
        attendance_score = self._calculate_attendance_score(parameters)
        
        appointment = {
            "client_name": client_name,
            "datetime": appointment_dt.isoformat(),
            "type": parameters.get("appointment_type", "atendimento"),
            "notes": parameters.get("appointment_notes", ""),
            "days_until": days_until,
            "hours_until": round(hours_until, 1),
            "attendance_probability": attendance_score,
            "status": "scheduled"
        }
        
        # Gerar lembretes
        reminders = []
        if days_until >= 1:
            reminders.append(f"📅 Lembrete 24h antes: {(appointment_dt - timedelta(days=1)).strftime('%d/%m às %H:%M')}")
        if hours_until >= 2:
            reminders.append(f"⏰ Lembrete 2h antes: {(appointment_dt - timedelta(hours=2)).strftime('%d/%m às %H:%M')}")
        
        # Notificação baseada em probabilidade
        notification_message = self._generate_attendance_message(attendance_score, client_name, appointment_dt)
        
        return {
            "status": "scheduled",
            "appointment": appointment,
            "notification": notification_message,
            "reminders": reminders,
            "channels": ["telegram", "sms", "email"],
            "recommendations": self._generate_appointment_recommendations(attendance_score)
        }
    
    def _analyze_client(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Analisa cliente e gera insights com IA."""
        
        client_name = parameters.get("client_name", "Cliente")
        
        # Calcular scores (retornam None se não há dados suficientes)
        purchase_score = self._calculate_purchase_score(parameters)
        attendance_score = self._calculate_attendance_score(parameters)
        churn_risk = self._calculate_churn_risk(parameters)
        engagement = self._calculate_engagement_score(parameters)
        
        # Classificação do cliente — só classifica se tem dados reais
        has_scores = purchase_score is not None
        if not has_scores:
            classification = "⬜ Novo (sem histórico suficiente)"
        elif purchase_score >= 80:
            classification = "🔥 Quente (Alta probabilidade)"
        elif purchase_score >= 60:
            classification = "🟡 Morno (Média probabilidade)"
        else:
            classification = "🔵 Frio (Baixa probabilidade)"
        
        # Análise de última interação
        last_interaction = parameters.get("last_interaction")
        days_since_last = self._days_since_last_interaction(last_interaction) if last_interaction else None
        
        analysis = {
            "client_name": client_name,
            "classification": classification,
            "scores": {
                "purchase_probability": purchase_score,
                "attendance_probability": attendance_score,
                "churn_risk": churn_risk,
                "engagement": engagement
            },
            "has_sufficient_data": has_scores,
            "insights": self._generate_insights(purchase_score, attendance_score, churn_risk, days_since_last) if has_scores else ["📊 Cliente novo — ainda não há dados suficientes para gerar insights. Continue registrando interações!"],
            "next_best_action": self._suggest_next_action(purchase_score, attendance_score, days_since_last) if has_scores else "Completar cadastro e registrar primeira interação",
            "urgency": "low" if not has_scores else ("high" if churn_risk and churn_risk > 70 else "medium" if churn_risk and churn_risk > 40 else "low")
        }
        
        return {
            "status": "analyzed",
            "analysis": analysis,
            "recommendations": self._generate_recommendations({
                "purchase_probability": purchase_score,
                "churn_risk": churn_risk
            }) if has_scores else ["Completar os dados do cliente", "Registrar compras e atendimentos para gerar análises reais"]
        }
    
    def _update_client(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza dados do cliente."""
        
        client_name = parameters.get("client_name")
        updates = {k: v for k, v in parameters.items() if k != "action" and k != "client_name"}
        
        return {
            "status": "updated",
            "client_name": client_name,
            "updated_fields": list(updates.keys()),
            "message": f"✅ Cliente {client_name} atualizado com sucesso!"
        }
    
    # ==================== SCORE CALCULATIONS ====================
    
    def _calculate_purchase_score(self, params: Dict[str, Any]) -> Optional[int]:
        """
        Calcula probabilidade de compra (0-100).
        Retorna None se não há dados suficientes para uma estimativa confiável.
        """
        # Precisa de pelo menos 1 compra ou interação real para calcular
        total_purchases = params.get("total_purchases", 0)
        total_appointments = params.get("total_appointments", 0)
        if total_purchases == 0 and total_appointments == 0:
            return None  # Sem histórico real — não inventar score
        
        score = 30  # Base conservadora para clientes com algum histórico
        
        # Segment
        segment = params.get("segment", "Standard")
        if segment == "Premium":
            score += 30
        elif segment == "Standard":
            score += 15
        
        # Source
        source = params.get("source", "")
        if "indica" in source.lower():
            score += 20
        elif "organic" in source.lower() or "google" in source.lower():
            score += 10
        
        # Opportunity stage
        stage = params.get("opportunity_stage", "")
        if "fechamento" in stage.lower():
            score += 30
        elif "negoci" in stage.lower():
            score += 20
        elif "prospec" in stage.lower():
            score += 10
        
        # Tags
        tags = params.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        if "vip" in tags:
            score += 15
        if "recorrente" in tags:
            score += 10
        
        return min(100, max(0, score))
    
    def _calculate_attendance_score(self, params: Dict[str, Any]) -> Optional[int]:
        """
        Calcula probabilidade de comparecimento (0-100).
        Retorna None se não há dados suficientes.
        """
        total_appointments = params.get("total_appointments", 0)
        if total_appointments == 0:
            return None  # Sem histórico real de comparecimento
        
        score = 60  # Base para quem já tem agendamentos
        
        # Histórico (simulado por tags)
        tags = params.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        if "pontual" in tags:
            score += 20
        if "faltou" in tags:
            score -= 30
        
        # Segmento
        if params.get("segment") == "Premium":
            score += 10
        
        return min(100, max(0, score))
    
    def _calculate_churn_risk(self, params: Dict[str, Any]) -> Optional[int]:
        """
        Calcula risco de perder o cliente (0-100, maior=pior).
        Retorna None se não há dados suficientes.
        """
        total_purchases = params.get("total_purchases", 0)
        total_appointments = params.get("total_appointments", 0)
        if total_purchases == 0 and total_appointments == 0:
            return None  # Cliente novo — sem dados para avaliar risco
        
        risk = 20  # Base para clientes com algum histórico
        
        last_interaction = params.get("last_interaction")
        if last_interaction:
            days_since = self._days_since_last_interaction(last_interaction)
            if days_since and days_since > 60:
                risk += 40
            elif days_since and days_since > 30:
                risk += 20
        
        return min(100, max(0, risk))
    
    def _calculate_engagement_score(self, params: Dict[str, Any]) -> Optional[int]:
        """Calcula score de engajamento (0-100). Retorna None se sem dados."""
        total_appointments = params.get("total_appointments", 0)
        total_purchases = params.get("total_purchases", 0)
        if total_appointments == 0 and total_purchases == 0:
            return None  # Sem dados reais de interação
        
        score = 30  # Base conservadora
        
        # Interações recentes
        if params.get("total_appointments", 0) > 5:
            score += 20
        elif params.get("total_appointments", 0) > 2:
            score += 10
        
        # Compras
        if params.get("total_purchases", 0) > 3:
            score += 20
        
        return min(100, max(0, score))
    
    # ==================== HELPER FUNCTIONS ====================
    
    def _days_until_birthday(self, birth_date_str: str) -> Optional[int]:
        """Calcula dias até próximo aniversário."""
        try:
            birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d")
            today = datetime.now()
            
            # Próximo aniversário
            next_birthday = birth_date.replace(year=today.year)
            if next_birthday < today:
                next_birthday = next_birthday.replace(year=today.year + 1)
            
            return (next_birthday - today).days
        except:
            return None
    
    def _days_since_last_interaction(self, last_interaction_str: str) -> Optional[int]:
        """Calcula dias desde última interação."""
        try:
            last_dt = datetime.fromisoformat(last_interaction_str)
            return (datetime.now() - last_dt).days
        except:
            return None
    
    def _generate_attendance_message(self, score: int, client_name: str, appointment_dt: datetime) -> str:
        """Gera mensagem de agendamento baseada em score."""
        if score >= 80:
            return f"✅ Agendamento confirmado para {client_name} em {appointment_dt.strftime('%d/%m às %H:%M')}. Alta probabilidade de comparecimento ({score}%)."
        elif score >= 60:
            return f"⚠️ Agendamento para {client_name} em {appointment_dt.strftime('%d/%m às %H:%M')}. Probabilidade média de comparecimento ({score}%). Recomendado: enviar lembrete 24h antes."
        else:
            return f"🔴 Agendamento para {client_name} em {appointment_dt.strftime('%d/%m às %H:%M')}. Baixa probabilidade de comparecimento ({score}%). CRÍTICO: confirmar por telefone 1 dia antes!"
    
    def _generate_insights(self, purchase_score: int, attendance_score: int, churn_risk: int, days_since_last: Optional[int]) -> List[str]:
        """Gera insights sobre o cliente."""
        insights = []
        
        if purchase_score >= 80:
            insights.append("🔥 Cliente com alta propensão a compra - priorize!")
        elif purchase_score < 40:
            insights.append("🔵 Cliente com baixa propensão - trabalhe relacionamento antes de venda")
        
        if churn_risk > 70:
            insights.append(f"⚠️ RISCO ALTO de perda do cliente ({churn_risk}% churn risk)")
        
        if days_since_last and days_since_last > 30:
            insights.append(f"📅 Sem interação há {days_since_last} dias - URGENTE reativar contato")
        
        if attendance_score < 60:
            insights.append("📞 Histórico de faltas - confirmar agendamentos por telefone")
        
        return insights
    
    def _suggest_next_action(self, purchase_score: int, attendance_score: int, days_since_last: Optional[int]) -> str:
        """Sugere próxima melhor ação."""
        if days_since_last and days_since_last > 60:
            return "📞 URGENTE: Ligar para reativar relacionamento"
        
        if purchase_score >= 80:
            return "💰 Enviar proposta comercial personalizada"
        elif purchase_score >= 60:
            return "📧 Nutrir lead com conteúdo de valor"
        else:
            return "🤝 Agendar reunião para entender necessidades"
    
    def _generate_recommendations(self, client_data: Dict[str, Any]) -> List[str]:
        """Gera recomendações baseadas nos dados."""
        recommendations = []
        
        purchase_prob = client_data.get("purchase_probability", 50)
        churn_risk = client_data.get("churn_risk", 30)
        
        if purchase_prob >= 80:
            recommendations.append("💎 Cliente Premium potencial - oferecer plano exclusivo")
        
        if churn_risk > 50:
            recommendations.append("🎁 Enviar benefício especial para retenção")
        
        if client_data.get("days_until_birthday", 999) <= 7:
            recommendations.append("🎂 Aniversário próximo - enviar mensagem personalizada")
        
        return recommendations
    
    def _generate_appointment_recommendations(self, attendance_score: int) -> List[str]:
        """Gera recomendações para agendamento."""
        recommendations = []
        
        if attendance_score < 60:
            recommendations.append("📞 Confirmar por telefone 1 dia antes")
            recommendations.append("⏰ Enviar 2 lembretes (24h e 2h antes)")
        elif attendance_score < 80:
            recommendations.append("📧 Enviar lembrete automático 24h antes")
        else:
            recommendations.append("✅ Cliente pontual - apenas 1 lembrete 24h antes")
        
        return recommendations


def run_clients_agent(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Helper para executar o agente de clientes."""
    agent = ClientsAgent()
    return agent.execute(parameters)
