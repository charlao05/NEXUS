"""
API do Agent Hub - Endpoints para Comunicação entre Agentes
============================================================

Endpoints:
- GET /api/agents/hub/status - Status do hub e agentes
- GET /api/agents/hub/messages - Mensagens recentes
- POST /api/agents/hub/message - Enviar mensagem
- POST /api/agents/hub/workflow - Executar workflow

- GET /api/agents/{agent}/config - Configuração de um agente
- PUT /api/agents/{agent}/config - Atualizar configuração
- POST /api/agents/{agent}/execute - Executar ação de um agente
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

# Importar dependência de autenticação
from app.api.auth import get_current_user  # type: ignore[import]

# Importar agentes existentes (paths relativos ao backend/)
from agents.agenda_agent import AgendaAgent
from agents.clients_agent import ClientsAgent
from agents.contabilidade_agent import ContabilidadeAgent
# Collections é módulo de funções, não classe - criar wrapper
from agents import collections_agent as collections_module

# Importar o hub
from agents.agent_hub import (
    AgentHub, AgentType, EventType, AgentMessage, get_hub, resolve_agent_type
)

logger = logging.getLogger(__name__)


# ============================================
# WRAPPERS PARA MÓDULOS SEM CLASSE
# ============================================

class CollectionsAgent:
    """Wrapper para o módulo collections_agent"""
    def __init__(self):
        self.name = "collections_agent"
        self.display_name = "🔔 Cobrança Automatizada"
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        action = parameters.get("action", "list_overdue")
        try:
            if action == "list_overdue":
                path = parameters.get("path", "data/collections.json")
                overdue = collections_module.find_overdue(path)
                return {"status": "ok", "overdue_count": len(overdue), "items": overdue}
            elif action == "generate_message":
                invoice = parameters.get("invoice", {})
                message = collections_module.generate_collection_message(invoice)
                return {"status": "ok", "message": message}
            else:
                return {"status": "error", "message": f"Ação desconhecida: {action}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class AssistenteAgent:
    """Agente Assistente Geral - Chat de IA"""
    def __init__(self):
        self.name = "assistente_agent"
        self.display_name = "🤖 Assistente Geral"
    
    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        action = parameters.get("action", "chat")
        try:
            if action == "chat":
                message = parameters.get("message", "")
                # Aqui seria integrado com LLM
                return {
                    "status": "ok",
                    "response": f"Recebi sua mensagem: {message}. Como posso ajudar?"
                }
            elif action == "suggest":
                context = parameters.get("context", {})
                return {
                    "status": "ok",
                    "suggestions": [
                        "Verificar compromissos do dia",
                        "Analisar financeiro do mês",
                        "Ver clientes pendentes de follow-up"
                    ]
                }
            else:
                return {"status": "error", "message": f"Ação desconhecida: {action}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

router = APIRouter(prefix="/api/agents", tags=["agents"])

# ============================================
# MODELOS PYDANTIC
# ============================================

class AgentConfig(BaseModel):
    enabled: bool = True
    auto_notify: bool = True
    notification_channels: List[str] = ["email"]
    settings: Dict[str, Any] = {}


class MessageRequest(BaseModel):
    from_agent: str
    to_agent: Optional[str] = None  # None = broadcast
    event_type: str
    payload: Dict[str, Any]
    priority: int = 5


class WorkflowRequest(BaseModel):
    workflow: str  # "novo_cliente", "cobranca", etc.
    data: Dict[str, Any]


class AgentAction(BaseModel):
    action: str
    parameters: Dict[str, Any] = {}


# ============================================
# CONFIGURAÇÕES DOS AGENTES (em memória por enquanto)
# ============================================

agent_configs: Dict[str, AgentConfig] = {
    "agenda": AgentConfig(
        enabled=True,
        auto_notify=True,
        notification_channels=["email", "whatsapp"],
        settings={
            "reminder_hours_before": 24,
            "daily_summary": True,
            "weekly_report": True
        }
    ),
    "clientes": AgentConfig(
        enabled=True,
        auto_notify=True,
        notification_channels=["email"],
        settings={
            "auto_follow_up_days": 7,
            "birthday_reminder": True,
            "lead_scoring": True
        }
    ),
    "contabilidade": AgentConfig(
        enabled=True,
        auto_notify=True,
        notification_channels=["email", "whatsapp"],
        settings={
            "alert_das_days_before": 5,
            "alert_dasn_days_before": 30,
            "alert_mei_limit_percent": 80,
            "monthly_report": True,
            "auto_backup": True,
            "nf_auto_send": True,
            "contract_templates": ["servico", "produto", "consultoria"],
            "tipo_atividade": "servicos",
        }
    ),
    "cobranca": AgentConfig(
        enabled=True,
        auto_notify=True,
        notification_channels=["whatsapp", "email"],
        settings={
            "auto_reminder_days": [3, 7, 15, 30],
            "friendly_tone": True,
            "escalation_enabled": False
        }
    ),
    "assistente": AgentConfig(
        enabled=True,
        auto_notify=True,
        notification_channels=["app"],
        settings={
            "proactive_suggestions": True,
            "learn_patterns": True,
            "voice_enabled": False
        }
    )
}

# ============================================
# INSTÂNCIAS DOS AGENTES
# ============================================

agents_instances: Dict[str, Any] = {}


# Mapa de aliases legados (financeiro + documentos → contabilidade)
_AGENT_ID_ALIAS: Dict[str, str] = {
    "financeiro": "contabilidade",
    "documentos": "contabilidade",
}


def _resolve_agent_id(agent_id: str) -> str:
    """Resolve IDs legados para o novo nome."""
    return _AGENT_ID_ALIAS.get(agent_id, agent_id)


def get_agent_instance(agent_name: str):
    """Retorna ou cria instância do agente"""
    agent_name = _resolve_agent_id(agent_name)
    if agent_name not in agents_instances:
        if agent_name == "agenda":
            agents_instances[agent_name] = AgendaAgent()
        elif agent_name == "clientes":
            agents_instances[agent_name] = ClientsAgent()
        elif agent_name == "contabilidade":
            agents_instances[agent_name] = ContabilidadeAgent()
        elif agent_name == "cobranca":
            agents_instances[agent_name] = CollectionsAgent()
        elif agent_name == "assistente":
            agents_instances[agent_name] = AssistenteAgent()
        else:
            return None
    return agents_instances.get(agent_name)


def init_agents():
    """Inicializa todos os agentes e registra no hub"""
    hub = get_hub()
    
    # Registrar agentes
    for agent_type in AgentType:
        instance = get_agent_instance(agent_type.value)
        if instance:
            hub.register_agent(agent_type, instance)
    
    # Configurar handlers de eventos
    _setup_event_handlers(hub)
    
    logger.info("✅ Todos os agentes inicializados e conectados ao Hub")


def _setup_event_handlers(hub: AgentHub):
    """Configura handlers de eventos entre agentes"""
    
    # Quando cliente é criado, agenda primeiro contato
    def on_cliente_criado(message: AgentMessage):
        cliente = message.payload
        logger.info(f"📆 Agendando primeiro contato para {cliente.get('nome')}")
        return {"acao": "primeiro_contato_agendado"}
    
    hub.subscribe(AgentType.AGENDA, EventType.CLIENTE_CRIADO, on_cliente_criado)
    
    # Quando pagamento atrasado, cobrança cria lembrete
    def on_pagamento_atrasado(message: AgentMessage):
        dados = message.payload
        logger.info(f"⚠️ Cobrança ativada: {dados.get('valor')} - {dados.get('dias_atraso')} dias")
        return {"acao": "cobranca_iniciada", "canal": "whatsapp"}
    
    hub.subscribe(AgentType.COBRANCA, EventType.PAGAMENTO_ATRASADO, on_pagamento_atrasado)
    
    # Contabilidade recebe notificação de NF emitida
    def on_nf_emitida(message: AgentMessage):
        nf = message.payload
        logger.info(f"📄 NF registrada na contabilidade: {nf.get('numero')}")
        return {"acao": "nf_registrada"}
    
    hub.subscribe(AgentType.CONTABILIDADE, EventType.NF_EMITIDA, on_nf_emitida)


# ============================================
# ENDPOINTS DO HUB
# ============================================

@router.get("/hub/status")
async def get_hub_status(user: dict = Depends(get_current_user)):
    """Retorna status completo do hub e todos os agentes"""
    hub = get_hub()
    return hub.get_status()


@router.get("/hub/messages")
async def get_hub_messages(limit: int = 50, user: dict = Depends(get_current_user)):
    """Retorna mensagens recentes do hub"""
    hub = get_hub()
    return {
        "messages": hub.get_recent_messages(limit),
        "total": len(hub.message_history)
    }


@router.post("/hub/message")
async def send_message(request: MessageRequest, user: dict = Depends(get_current_user)):
    """Envia uma mensagem entre agentes"""
    hub = get_hub()
    
    try:
        from_type = resolve_agent_type(request.from_agent)
        to_type = resolve_agent_type(request.to_agent) if request.to_agent else None
        event_type = EventType(request.event_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Tipo inválido: {e}")
    
    message = AgentMessage(
        from_agent=from_type,
        to_agent=to_type,
        event_type=event_type,
        payload=request.payload,
        priority=request.priority
    )
    
    result = await hub.publish(message)
    return result


@router.post("/hub/workflow")
async def execute_workflow(request: WorkflowRequest, user: dict = Depends(get_current_user)):
    """Executa um workflow orquestrado"""
    hub = get_hub()
    
    if request.workflow == "novo_cliente":
        return await hub.workflow_novo_cliente(request.data)
    elif request.workflow == "cobranca":
        return await hub.workflow_cobranca(
            request.data.get("cliente_id"),
            request.data.get("valor", 0)
        )
    else:
        raise HTTPException(status_code=400, detail=f"Workflow desconhecido: {request.workflow}")


# ============================================
# ENDPOINTS DE CONFIGURAÇÃO DOS AGENTES
# ============================================

@router.get("/list")
async def list_agents():
    """Lista todos os agentes disponíveis"""
    return {
        "agents": [
            {
                "id": "agenda",
                "name": "Agente de Agenda",
                "description": "Gerencia agendamentos, compromissos e lembretes automáticos",
                "icon": "📅",
                "status": "online",
                "enabled": agent_configs["agenda"].enabled
            },
            {
                "id": "clientes",
                "name": "Agente de Clientes",
                "description": "CRM completo com histórico, follow-up e segmentação",
                "icon": "👥",
                "status": "online",
                "enabled": agent_configs["clientes"].enabled
            },
            {
                "id": "contabilidade",
                "name": "Contabilidade MEI",
                "description": "DAS, NFs, DASN, IRPF, limites, calendário fiscal e todas as obrigações MEI",
                "icon": "📊",
                "status": "online",
                "enabled": agent_configs["contabilidade"].enabled
            },
            {
                "id": "cobranca",
                "name": "Agente de Cobrança",
                "description": "Lembretes de pagamento e gestão de inadimplência",
                "icon": "🔔",
                "status": "online",
                "enabled": agent_configs["cobranca"].enabled
            },
            {
                "id": "assistente",
                "name": "Assistente Geral",
                "description": "Chat de IA para dúvidas e automações personalizadas",
                "icon": "🤖",
                "status": "online",
                "enabled": agent_configs["assistente"].enabled
            }
        ]
    }


@router.get("/{agent_id}/config")
async def get_agent_config(agent_id: str):
    """Retorna configuração de um agente"""
    agent_id = _resolve_agent_id(agent_id)
    if agent_id not in agent_configs:
        raise HTTPException(status_code=404, detail=f"Agente não encontrado: {agent_id}")
    
    config = agent_configs[agent_id]
    return {
        "agent_id": agent_id,
        "config": config.model_dump()
    }


@router.put("/{agent_id}/config")
async def update_agent_config(agent_id: str, config: AgentConfig):
    """Atualiza configuração de um agente"""
    agent_id = _resolve_agent_id(agent_id)
    if agent_id not in agent_configs:
        raise HTTPException(status_code=404, detail=f"Agente não encontrado: {agent_id}")
    
    agent_configs[agent_id] = config
    
    return {
        "message": f"Configuração do agente {agent_id} atualizada",
        "config": config.model_dump()
    }


@router.post("/{agent_id}/execute")
async def execute_agent_action(
    agent_id: str,
    action: AgentAction,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Executa uma ação específica de um agente.
    Usa OpenAI GPT-4.1 para ações de chat e quick actions.
    Salva histórico no banco automaticamente.
    Fallback para execução local se LLM indisponível.
    """
    agent_id = _resolve_agent_id(agent_id)
    instance = get_agent_instance(agent_id)

    if not instance:
        raise HTTPException(status_code=404, detail=f"Agente não encontrado: {agent_id}")

    if not agent_configs.get(agent_id, AgentConfig()).enabled:
        raise HTTPException(status_code=400, detail=f"Agente {agent_id} está desabilitado")

    # ── Freemium: verificar acesso ao agente e limite diário ───────
    from app.services.limit_service import check_agent_access, check_agent_message_limit
    check_agent_access(current_user, agent_id)
    check_agent_message_limit(current_user)

    # ── user_id extraído do JWT (autenticado) ────────────────────
    _user_id: int | None = current_user.get("user_id")

    # ── Persistir chat no banco ──────────────────────────────────
    def _save_chat(user_msg: str, assistant_msg: str, uid: int | None = None) -> None:
        """Salva par de mensagens no histórico persistente"""
        try:
            from database.models import ChatMessage, SessionLocal as _SL  # type: ignore[import]
            db = _SL()
            try:
                _uid = uid or 0
                if user_msg:
                    db.add(ChatMessage(user_id=_uid, agent_id=agent_id, role="user", content=user_msg))
                if assistant_msg:
                    db.add(ChatMessage(user_id=_uid, agent_id=agent_id, role="assistant", content=assistant_msg))
                db.commit()
            finally:
                db.close()
        except Exception as ex:
            logger.debug(f"Chat não persistido: {ex}")

    # ── Detectar intenção de automação web ────────────────────────
    user_message = action.parameters.get("message", "")
    if user_message and action.action in ("smart_chat", "chat") and agent_id == "assistente":
        try:
            from app.api.agent_automation import _detect_automation_intent
            intent = _detect_automation_intent(user_message)
            if intent:
                # Redirecionar para o fluxo de automação
                from app.api.agent_automation import start_automation, AutomationStartRequest
                auto_req = AutomationStartRequest(
                    agent_id=agent_id,
                    goal=user_message,
                    message=user_message,
                    user_id=_user_id or 1,
                )
                auto_result = await start_automation(auto_req)
                _save_chat(user_message, auto_result.message, _user_id)
                return {
                    "status": "success",
                    "agent_id": agent_id,
                    "action": "automation_plan",
                    "message": auto_result.message,
                    "automation": {
                        "task_id": auto_result.task_id,
                        "requires_approval": True,
                        "plan_summary": auto_result.plan_summary,
                        "steps": auto_result.steps,
                        "risk_level": auto_result.risk_level,
                    },
                }
        except Exception as e:
            logger.warning(f"Automação detection falhou (prosseguindo com chat normal): {e}")

    # ── Inteligência via OpenAI GPT-4.1 ──────────────────────────
    try:
        from app.api.agent_chat import get_llm_response, ACTION_PROMPTS

        # Carregar histórico persistente para contexto
        chat_history: list[dict] = []
        try:
            from database.models import ChatMessage as _CM, SessionLocal as _SL2  # type: ignore[import]
            _db = _SL2()
            try:
                _query = _db.query(_CM).filter(_CM.agent_id == agent_id)
                # Filtrar histórico pelo user_id autenticado
                if _user_id:
                    _query = _query.filter(_CM.user_id == _user_id)
                recent = (
                    _query
                    .order_by(_CM.created_at.desc())
                    .limit(10)
                    .all()
                )
                chat_history = [{"role": m.role, "content": m.content} for m in reversed(recent)]
            finally:
                _db.close()
        except Exception:
            pass

        # Chat livre: usuário digitou uma mensagem
        if user_message and action.action in ("smart_chat", "chat"):
            llm_response = await get_llm_response(agent_id, user_message, history=chat_history, user_id=_user_id)
            if llm_response:
                _save_chat(user_message, llm_response, _user_id)
                hub = get_hub()
                hub.shared_context["estatisticas"]["eventos_processados"] += 1
                return {
                    "status": "success",
                    "agent_id": agent_id,
                    "action": action.action,
                    "message": llm_response
                }
            else:
                logger.warning(f"LLM retornou vazio para agent={agent_id} msg={user_message[:50]}")

        # Quick action (botão): converte ação em prompt natural
        if action.action in ACTION_PROMPTS:
            prompt = ACTION_PROMPTS[action.action]
            llm_response = await get_llm_response(agent_id, prompt, history=chat_history, user_id=_user_id)
            if llm_response:
                _save_chat(prompt, llm_response, _user_id)
                hub = get_hub()
                hub.shared_context["estatisticas"]["eventos_processados"] += 1
                return {
                    "status": "success",
                    "agent_id": agent_id,
                    "action": action.action,
                    "message": llm_response
                }
    except ImportError:
        logger.debug("agent_chat module não disponível, usando fallback local")
    except Exception as e:
        logger.warning(f"LLM indisponível ({e}), usando fallback local", exc_info=True)

    # ── Fallback: execução local do agente ───────────────────────
    params = {"action": action.action, **action.parameters}

    try:
        result = instance.execute(params)

        hub = get_hub()
        hub.shared_context["estatisticas"]["eventos_processados"] += 1

        # Extrair mensagem do resultado para manter contrato com frontend
        fallback_message = ""
        if isinstance(result, dict):
            fallback_message = result.get("message") or result.get("response") or result.get("resultado", "")
        elif isinstance(result, str):
            fallback_message = result

        return {
            "status": "success",
            "agent_id": agent_id,
            "action": action.action,
            "message": fallback_message or "Operação realizada, mas sem resposta detalhada.",
            "result": result
        }
    except Exception as e:
        logger.exception(f"Erro ao executar {agent_id}.{action.action}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/status")
async def get_agent_status(agent_id: str):
    """Retorna status detalhado de um agente"""
    agent_id = _resolve_agent_id(agent_id)
    hub = get_hub()
    
    try:
        agent_type = resolve_agent_type(agent_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Agente não encontrado: {agent_id}")
    
    status = hub.agent_status.get(agent_type, {
        "online": agent_id in agents_instances,
        "registered_at": None,
        "last_activity": None,
        "messages_sent": 0,
        "messages_received": 0
    })
    
    return {
        "agent_id": agent_id,
        "status": status,
        "config": agent_configs.get(agent_id, AgentConfig()).model_dump()
    }


# ============================================
# ENDPOINTS DE DADOS COMPARTILHADOS
# ============================================

@router.get("/hub/context")
async def get_shared_context(user: dict = Depends(get_current_user)):
    """Retorna o contexto compartilhado entre agentes"""
    hub = get_hub()
    return {
        "context": {
            "clientes_count": len(hub.shared_context.get("clientes", {})),
            "compromissos_hoje": hub.shared_context.get("compromissos_hoje", []),
            "alertas_ativos": hub.shared_context.get("alertas_ativos", []),
            "ultimo_sync": hub.shared_context.get("ultimo_sync"),
            "estatisticas": hub.shared_context.get("estatisticas", {})
        }
    }


@router.post("/hub/sync")
async def sync_agents(user: dict = Depends(get_current_user)):
    """Sincroniza dados entre todos os agentes"""
    hub = get_hub()
    hub.shared_context["ultimo_sync"] = datetime.now().isoformat()
    
    # Inicializar agentes se necessário
    init_agents()
    
    return {
        "message": "Sincronização concluída",
        "timestamp": hub.shared_context["ultimo_sync"],
        "agents_online": len([s for s in hub.agent_status.values() if s.get("online")])
    }
