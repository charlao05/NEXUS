"""
Agent Hub - Sistema Central de Comunicação entre Agentes
=========================================================

Orquestra a comunicação entre todos os agentes do NEXUS:
- Agenda, Clientes, Financeiro, Cobrança, Documentos, Assistente

Funcionalidades:
- Broadcast de eventos entre agentes
- Compartilhamento de dados contextuais
- Orquestração de workflows multi-agente
- Histórico de interações
- Cache de contexto compartilhado
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Tipos de agentes disponíveis"""
    AGENDA = "agenda"
    CLIENTES = "clientes"
    CONTABILIDADE = "contabilidade"
    COBRANCA = "cobranca"
    ASSISTENTE = "assistente"


# Mapeamento legado → novo (financeiro e documentos foram unificados em contabilidade)
_AGENT_ALIAS = {
    "financeiro": "contabilidade",
    "documentos": "contabilidade",
}


def resolve_agent_type(value: str) -> AgentType:
    """Resolve AgentType com suporte a nomes legados."""
    value = _AGENT_ALIAS.get(value, value)
    return AgentType(value)


class EventType(Enum):
    """Tipos de eventos que podem ser trocados entre agentes"""
    # Eventos de Cliente
    CLIENTE_CRIADO = "cliente_criado"
    CLIENTE_ATUALIZADO = "cliente_atualizado"
    CLIENTE_AGENDADO = "cliente_agendado"
    
    # Eventos de Agenda
    COMPROMISSO_CRIADO = "compromisso_criado"
    COMPROMISSO_PROXIMO = "compromisso_proximo"
    LEMBRETE_ENVIADO = "lembrete_enviado"
    
    # Eventos de Contabilidade (antigos Financeiros + Documentos)
    PAGAMENTO_RECEBIDO = "pagamento_recebido"
    PAGAMENTO_ATRASADO = "pagamento_atrasado"
    LIMITE_MEI_ALERTA = "limite_mei_alerta"
    DAS_VENCENDO = "das_vencendo"
    DASN_VENCENDO = "dasn_vencendo"
    NF_EMITIDA = "nf_emitida"
    CONTRATO_GERADO = "contrato_gerado"
    RELATORIO_PRONTO = "relatorio_pronto"
    DESENQUADRAMENTO_RISCO = "desenquadramento_risco"
    
    # Eventos de Cobrança
    COBRANCA_ENVIADA = "cobranca_enviada"
    INADIMPLENCIA_DETECTADA = "inadimplencia_detectada"
    
    # Eventos Gerais
    ACAO_SOLICITADA = "acao_solicitada"
    RESPOSTA_USUARIO = "resposta_usuario"


class AgentMessage:
    """Mensagem trocada entre agentes"""
    
    def __init__(
        self,
        from_agent: AgentType,
        to_agent: Optional[AgentType],  # None = broadcast para todos
        event_type: EventType,
        payload: Dict[str, Any],
        priority: int = 5,  # 1 = urgente, 10 = baixa
        correlation_id: Optional[str] = None
    ):
        self.id = f"msg_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.timestamp = datetime.now()
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.event_type = event_type
        self.payload = payload
        self.priority = priority
        self.correlation_id = correlation_id or self.id
        self.processed = False
        self.responses: List[Dict] = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "from_agent": self.from_agent.value,
            "to_agent": self.to_agent.value if self.to_agent else "broadcast",
            "event_type": self.event_type.value,
            "payload": self.payload,
            "priority": self.priority,
            "correlation_id": self.correlation_id,
            "processed": self.processed,
            "responses": self.responses
        }


class AgentHub:
    """
    Hub Central de Comunicação entre Agentes
    
    Padrão Pub/Sub com suporte a:
    - Mensagens diretas (agent-to-agent)
    - Broadcast (agent-to-all)
    - Workflows orquestrados
    - Cache de contexto compartilhado
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        
        # Registro de agentes
        self.agents: Dict[AgentType, Any] = {}
        
        # Handlers de eventos por agente
        self.event_handlers: Dict[AgentType, Dict[EventType, Callable]] = {}
        
        # Fila de mensagens
        self.message_queue: List[AgentMessage] = []
        
        # Histórico de mensagens (últimas 1000)
        self.message_history: List[AgentMessage] = []
        self.max_history = 1000
        
        # Contexto compartilhado entre agentes
        self.shared_context: Dict[str, Any] = {
            "clientes": {},  # Cache de clientes ativos
            "compromissos_hoje": [],  # Compromissos do dia
            "alertas_ativos": [],  # Alertas pendentes
            "ultimo_sync": None,
            "estatisticas": {
                "mensagens_hoje": 0,
                "eventos_processados": 0,
                "erros": 0
            }
        }
        
        # Status de conexão dos agentes
        self.agent_status: Dict[AgentType, Dict[str, Any]] = {}
        
        logger.info("🔗 Agent Hub inicializado")
    
    def register_agent(self, agent_type: AgentType, agent_instance: Any) -> None:
        """Registra um agente no hub"""
        self.agents[agent_type] = agent_instance
        self.event_handlers[agent_type] = {}
        self.agent_status[agent_type] = {
            "online": True,
            "registered_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "messages_sent": 0,
            "messages_received": 0
        }
        logger.info(f"✅ Agente {agent_type.value} registrado no Hub")
    
    def subscribe(
        self, 
        agent_type: AgentType, 
        event_type: EventType, 
        handler: Callable
    ) -> None:
        """Inscreve um agente para receber um tipo de evento"""
        if agent_type not in self.event_handlers:
            self.event_handlers[agent_type] = {}
        
        self.event_handlers[agent_type][event_type] = handler
        logger.debug(f"📡 {agent_type.value} inscrito para {event_type.value}")
    
    async def publish(self, message: AgentMessage) -> Dict[str, Any]:
        """
        Publica uma mensagem no hub
        
        Se to_agent for None, faz broadcast para todos os agentes inscritos.
        Se to_agent for especificado, envia apenas para aquele agente.
        """
        # Adiciona à fila e histórico
        self.message_queue.append(message)
        self.message_history.append(message)
        
        # Limita histórico
        if len(self.message_history) > self.max_history:
            self.message_history = self.message_history[-self.max_history:]
        
        # Atualiza estatísticas
        self.shared_context["estatisticas"]["mensagens_hoje"] += 1
        
        # Atualiza status do remetente
        if message.from_agent in self.agent_status:
            self.agent_status[message.from_agent]["last_activity"] = datetime.now().isoformat()
            self.agent_status[message.from_agent]["messages_sent"] += 1
        
        # Processa a mensagem
        responses = await self._process_message(message)
        
        message.processed = True
        message.responses = responses
        
        return {
            "status": "delivered",
            "message_id": message.id,
            "responses": responses
        }
    
    async def _process_message(self, message: AgentMessage) -> List[Dict]:
        """Processa uma mensagem e entrega aos destinatários"""
        responses = []
        
        if message.to_agent:
            # Mensagem direta
            if message.to_agent in self.event_handlers:
                handlers = self.event_handlers[message.to_agent]
                if message.event_type in handlers:
                    try:
                        response = await self._call_handler(
                            handlers[message.event_type],
                            message
                        )
                        responses.append({
                            "agent": message.to_agent.value,
                            "response": response
                        })
                        self._update_receiver_stats(message.to_agent)
                    except Exception as e:
                        logger.error(f"Erro ao processar mensagem: {e}")
                        self.shared_context["estatisticas"]["erros"] += 1
        else:
            # Broadcast
            for agent_type, handlers in self.event_handlers.items():
                if agent_type == message.from_agent:
                    continue  # Não envia para si mesmo
                    
                if message.event_type in handlers:
                    try:
                        response = await self._call_handler(
                            handlers[message.event_type],
                            message
                        )
                        responses.append({
                            "agent": agent_type.value,
                            "response": response
                        })
                        self._update_receiver_stats(agent_type)
                    except Exception as e:
                        logger.error(f"Erro no broadcast para {agent_type.value}: {e}")
        
        self.shared_context["estatisticas"]["eventos_processados"] += 1
        return responses
    
    async def _call_handler(self, handler: Callable, message: AgentMessage) -> Any:
        """Chama o handler de forma assíncrona ou síncrona"""
        if asyncio.iscoroutinefunction(handler):
            return await handler(message)
        else:
            return handler(message)
    
    def _update_receiver_stats(self, agent_type: AgentType) -> None:
        """Atualiza estatísticas do receptor"""
        if agent_type in self.agent_status:
            self.agent_status[agent_type]["last_activity"] = datetime.now().isoformat()
            self.agent_status[agent_type]["messages_received"] += 1
    
    # ============================================
    # MÉTODOS DE CONVENIÊNCIA PARA OS AGENTES
    # ============================================
    
    def notify_cliente_criado(self, cliente_data: Dict) -> None:
        """Notifica todos os agentes sobre um novo cliente"""
        message = AgentMessage(
            from_agent=AgentType.CLIENTES,
            to_agent=None,  # Broadcast
            event_type=EventType.CLIENTE_CRIADO,
            payload=cliente_data,
            priority=5
        )
        asyncio.create_task(self.publish(message))
        
        # Atualiza contexto compartilhado
        cliente_id = cliente_data.get("id") or cliente_data.get("cpf_cnpj")
        if cliente_id:
            self.shared_context["clientes"][cliente_id] = cliente_data
    
    def notify_pagamento_atrasado(self, cliente_id: str, valor: float, dias_atraso: int) -> None:
        """Notifica sobre pagamento atrasado - dispara workflow de cobrança"""
        message = AgentMessage(
            from_agent=AgentType.CONTABILIDADE,
            to_agent=AgentType.COBRANCA,
            event_type=EventType.PAGAMENTO_ATRASADO,
            payload={
                "cliente_id": cliente_id,
                "valor": valor,
                "dias_atraso": dias_atraso,
                "data_vencimento": (datetime.now().date()).isoformat()
            },
            priority=2  # Alta prioridade
        )
        asyncio.create_task(self.publish(message))
    
    def notify_compromisso_proximo(self, compromisso: Dict) -> None:
        """Notifica sobre compromisso próximo"""
        # Envia para Assistente criar lembrete
        message = AgentMessage(
            from_agent=AgentType.AGENDA,
            to_agent=AgentType.ASSISTENTE,
            event_type=EventType.COMPROMISSO_PROXIMO,
            payload=compromisso,
            priority=3
        )
        asyncio.create_task(self.publish(message))
    
    def request_nf_emissao(self, dados_nf: Dict) -> None:
        """Solicita emissão de NF ao agente de contabilidade"""
        message = AgentMessage(
            from_agent=AgentType.CONTABILIDADE,
            to_agent=AgentType.CONTABILIDADE,
            event_type=EventType.ACAO_SOLICITADA,
            payload={
                "acao": "emitir_nf",
                "dados": dados_nf
            },
            priority=4
        )
        asyncio.create_task(self.publish(message))
    
    def get_context(self, key: str) -> Any:
        """Obtém valor do contexto compartilhado"""
        return self.shared_context.get(key)
    
    def set_context(self, key: str, value: Any) -> None:
        """Define valor no contexto compartilhado"""
        self.shared_context[key] = value
    
    def get_cliente(self, cliente_id: str) -> Optional[Dict]:
        """Obtém cliente do cache compartilhado"""
        return self.shared_context["clientes"].get(cliente_id)
    
    # ============================================
    # WORKFLOWS ORQUESTRADOS
    # ============================================
    
    async def workflow_novo_cliente(self, cliente_data: Dict) -> Dict[str, Any]:
        """
        Workflow: Novo Cliente
        
        1. Clientes: Cadastra cliente
        2. Agenda: Cria compromisso de primeiro contato
        3. Financeiro: Inicializa ficha financeira
        4. Documentos: Prepara contrato
        """
        results = {
            "workflow": "novo_cliente",
            "cliente": cliente_data.get("nome"),
            "steps": []
        }
        
        # 1. Notifica criação
        self.notify_cliente_criado(cliente_data)
        results["steps"].append({"step": "cadastro", "status": "ok"})
        
        # 2. Agenda primeiro contato
        if AgentType.AGENDA in self.agents:
            agenda_result = self.agents[AgentType.AGENDA].execute({
                "action": "create_appointment",
                "client_name": cliente_data.get("nome"),
                "type": "primeiro_contato",
                "auto_schedule": True
            })
            results["steps"].append({"step": "agenda", "status": "ok", "data": agenda_result})
        
        # 3. Broadcast para outros agentes
        await self.publish(AgentMessage(
            from_agent=AgentType.CLIENTES,
            to_agent=None,
            event_type=EventType.CLIENTE_CRIADO,
            payload=cliente_data,
            priority=5
        ))
        
        return results
    
    async def workflow_cobranca(self, cliente_id: str, valor: float) -> Dict[str, Any]:
        """
        Workflow: Cobrança Automatizada
        
        1. Financeiro: Identifica inadimplência
        2. Clientes: Obtém dados de contato
        3. Cobrança: Gera e envia cobrança
        4. Agenda: Cria lembrete de follow-up
        """
        results = {
            "workflow": "cobranca",
            "cliente_id": cliente_id,
            "valor": valor,
            "steps": []
        }
        
        # Obter dados do cliente
        cliente = self.get_cliente(cliente_id)
        if cliente:
            results["steps"].append({
                "step": "dados_cliente",
                "status": "ok",
                "contato": cliente.get("telefone")
            })
        
        # Notificar cobrança
        self.notify_pagamento_atrasado(cliente_id, valor, 0)
        results["steps"].append({"step": "notificacao", "status": "enviada"})
        
        return results
    
    # ============================================
    # STATUS E MONITORAMENTO
    # ============================================
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status completo do hub"""
        return {
            "hub_status": "online",
            "timestamp": datetime.now().isoformat(),
            "agents": {
                agent.value: self.agent_status.get(agent, {"online": False})
                for agent in AgentType
            },
            "statistics": self.shared_context["estatisticas"],
            "queue_size": len(self.message_queue),
            "context_keys": list(self.shared_context.keys())
        }
    
    def get_recent_messages(self, limit: int = 50) -> List[Dict]:
        """Retorna mensagens recentes"""
        return [
            msg.to_dict() 
            for msg in self.message_history[-limit:]
        ]


# Instância global do hub
hub = AgentHub()


def get_hub() -> AgentHub:
    """Retorna instância do hub"""
    return hub
