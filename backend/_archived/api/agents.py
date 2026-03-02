
"""
API Router para Agentes de IA
=============================

Endpoints para executar os 6 agentes CODEX:
- Site Agent (automacao web)
- Deadlines Agent (prazos MEI)
- Attendance Agent (atendimento)
- Finance Agent (relatorios financeiros)
- NF Agent (notas fiscais)
- Collections Agent (cobrancas)
"""


from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

import logging
import uuid
from datetime import datetime
import sys

# Importações corrigidas e robustas
try:
    from .clients_sql import get_sales_for_agent
except ImportError:
    # get_obligations_for_agent removido
    get_sales_for_agent = None

# Inicialização robusta dos agentes
agents_loaded: bool = False


from typing import NoReturn, Any as _Any

class DummyAgent:
    def __getattr__(self, name: str) -> _Any:
        def dummy(*args: _Any, **kwargs: _Any) -> NoReturn:
            raise RuntimeError(f"Agente ou método '{name}' não disponível (import falhou)")
        return dummy

site_agent = DummyAgent()
clients_agent = DummyAgent()
agenda_agent = DummyAgent()
finance_agent = DummyAgent()
nf_agent = DummyAgent()
collections_agent = DummyAgent()
lead_qualificacao = DummyAgent()

# Tenta importar agentes e workflows de forma robusta, independente do contexto FastAPI
try:
    # Adiciona backend/ ao sys.path se não estiver
    import os
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from backend.agents import site_agent as _site_agent, clients_agent as _clients_agent, agenda_agent as _agenda_agent, finance_agent as _finance_agent, nf_agent as _nf_agent, collections_agent as _collections_agent  # type: ignore
    from backend.workflows import lead_qualificacao as _lead_qualificacao  # type: ignore
    site_agent = _site_agent  # type: ignore
    clients_agent = _clients_agent  # type: ignore
    agenda_agent = _agenda_agent  # type: ignore
    finance_agent = _finance_agent  # type: ignore
    nf_agent = _nf_agent  # type: ignore
    collections_agent = _collections_agent  # type: ignore
    lead_qualificacao = _lead_qualificacao  # type: ignore
    agents_loaded = True
    logging.info("Agentes carregados (import backend.*)")
except Exception as e:
    logging.error(f"Erro ao importar agentes/workflows: {e}")
    agents_loaded = False

router: APIRouter = APIRouter(prefix="/api/agents", tags=["agents"])
logger = logging.getLogger(__name__)

# Armazenamento temporario de tarefas (em producao, usar Redis/DB)
tasks_storage: Dict[str, Dict[str, Any]] = {}


# ==================== MODELS ====================

class SiteAutomationRequest(BaseModel):
    site: str = Field(..., description="Nome do site (ex: instagram)")
    objetivo: str = Field(..., description="Objetivo da automação")
    dry_run: bool = Field(default=False, description="Apenas gerar plano, não executar")


class LeadQualificationRequest(BaseModel):
    lead_data: Dict[str, Any] = Field(..., description="Dados do lead")
    contexto_nicho: Optional[str] = Field(None, description="Contexto do nicho de negócio")


class InvoiceGenerationRequest(BaseModel):
    sale_data: Dict[str, Any] = Field(..., description="Dados da venda")


class AgentExecutionRequest(BaseModel):
    agent_name: str = Field(..., description="Nome do agente a executar")
    parameters: Dict[str, Any] = Field(..., description="Parâmetros do agente")


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str  # pending, running, completed, failed
    agent: str
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ==================== HELPER FUNCTIONS ====================

def create_task(agent_name: str, parameters: Dict[str, Any]) -> str:
    """Criar nova tarefa no storage"""
    task_id = str(uuid.uuid4())[:8]
    tasks_storage[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "agent": agent_name,
        "parameters": parameters,
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "result": None,
        "error": None
    }
    return task_id


def update_task(task_id: str, status: str, result: Any = None, error: Optional[str] = None):
    """Atualizar status da tarefa"""
    if task_id in tasks_storage:
        tasks_storage[task_id]["status"] = status
        if status in ["completed", "failed"]:
            tasks_storage[task_id]["completed_at"] = datetime.now().isoformat()
        if result is not None:
            tasks_storage[task_id]["result"] = result
        if error is not None:
            tasks_storage[task_id]["error"] = error


async def execute_agent_background(task_id: str, agent_name: str, parameters: Dict[str, Any]):
    """Executar agente em background"""
    try:
        update_task(task_id, "running")
        
        if agent_name == "site_agent":
            site = parameters.get("site")
            objetivo = parameters.get("objetivo")
            dry_run = parameters.get("dry_run", False)
            
            # Validar parâmetros obrigatórios
            if not site or not objetivo:
                raise ValueError("site e objetivo são obrigatórios para site_agent")
            
            plano = site_agent.planejar(str(site), str(objetivo))  # type: ignore
            if not dry_run:
                site_agent.executar_plano(str(site), plano)  # type: ignore
            
            result = {"plano": plano, "dry_run": dry_run}  # type: ignore
        
        elif agent_name == "agenda_agent":
            # Agenda Completa: todos os compromissos do usuário
            # Suporta modo fiscal (obligations_json) ou compromisso único (due_date)
            result = agenda_agent.run_agenda_agent(parameters)  # type: ignore

        elif agent_name == "lead_qualification":
            lead_data = parameters.get("lead_data")
            contexto = parameters.get("contexto_nicho", "")

            if not lead_data or not isinstance(lead_data, dict):
                raise ValueError("lead_data deve ser um dicionário")

            result = lead_qualificacao.qualificar_lead(lead_data, str(contexto))  # type: ignore


        elif agent_name == "nf_agent":
            sale_data = parameters.get("sale_data")
            if not sale_data and parameters.get("client_id") and get_sales_for_agent:
                sales = get_sales_for_agent(str(parameters.get("client_id")))
                sale_data = sales[0] if sales else None

            if not sale_data or not isinstance(sale_data, dict):
                raise ValueError("sale_data deve ser um dicionário ou disponível para o cliente informado")

            result = nf_agent.prepare_invoice_steps(sale_data)  # type: ignore

        elif agent_name == "clients_agent":
            # CRM Completo: cadastro, agendamento, análise
            result = clients_agent.run_clients_agent(parameters)  # type: ignore

        else:
            raise ValueError(f"Agente desconhecido: {agent_name}")

        update_task(task_id, "completed", result=result)

    except Exception as e:
        logger.exception(f"Erro ao executar agente {agent_name}: {e}")
        update_task(task_id, "failed", error=str(e))


# ==================== ENDPOINTS ====================

@router.get("/")
async def list_agents() -> Dict[str, Any]:
    """Listar todos os agentes disponíveis"""
    if not agents_loaded:
        return {
            "status": "error",
            "message": "Agentes não carregados. Verifique a instalação.",
            "agents": []
        }
    
    return {
        "status": "ok",
        "agents": [
            {"name": "site_agent", "description": "Automacao web com Playwright", "endpoint": "/api/agents/site-automation"},
            {"name": "lead_qualification", "description": "Qualificacao de leads com IA", "endpoint": "/api/agents/lead-qualification"},
            {"name": "agenda_agent", "description": "Agenda Completa - Todos os compromissos (fiscal, pagamentos, NFs, fornecedores, prazos)", "endpoint": "/api/agents/execute"},
            {"name": "attendance_agent", "description": "Agendamento Passivo - Clientes agendando com voce", "endpoint": "/api/agents/site"},
            {"name": "clients_agent", "description": "Clientes (CRM Completo) - Cadastro, agendamento, analise e probabilidades", "endpoint": "/api/agents/clients"},
            {"name": "finance_agent", "description": "Relatorios financeiros", "endpoint": "/api/agents/finance"},
            {"name": "nf_agent", "description": "Emissao de NFS-e", "endpoint": "/api/agents/invoice"},
            {"name": "collections_agent", "description": "Cobrancas automaticas", "endpoint": "/api/agents/collections"}
        ]
    }


@router.post("/site-automation")
async def site_automation(request: SiteAutomationRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Executar automação web via Site Agent"""
    if not agents_loaded:
        raise HTTPException(status_code=503, detail="Agentes não disponíveis")
    
    try:
        task_id = create_task("site_agent", {
            "site": request.site,
            "objetivo": request.objetivo,
            "dry_run": request.dry_run
        })
        
        # Executar em background
        background_tasks.add_task(
            execute_agent_background,
            task_id,
            "site_agent",
            {"site": request.site, "objetivo": request.objetivo, "dry_run": request.dry_run}
        )
        
        return {
            "status": "accepted",
            "task_id": task_id,
            "message": f"Automação de '{request.site}' iniciada",
            "check_status": f"/api/agents/status/{task_id}"
        }
        
    except Exception as e:
        logger.exception(f"Erro ao iniciar automação: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lead-qualification")
async def lead_qualification(request: LeadQualificationRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Qualificar lead com IA"""
    if not agents_loaded:
        raise HTTPException(status_code=503, detail="Agentes não disponíveis")
    
    try:
        task_id = create_task("lead_qualification", {
            "lead_data": request.lead_data,
            "contexto_nicho": request.contexto_nicho
        })
        
        background_tasks.add_task(
            execute_agent_background,
            task_id,
            "lead_qualification",
            {"lead_data": request.lead_data, "contexto_nicho": request.contexto_nicho}
        )
        
        return {
            "status": "accepted",
            "task_id": task_id,
            "message": "Qualificação de lead iniciada",
            "check_status": f"/api/agents/status/{task_id}"
        }
        
    except Exception as e:
        logger.exception(f"Erro ao qualificar lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invoice")
async def generate_invoice(request: InvoiceGenerationRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Gerar instruções para emissão de NFS-e"""
    if not agents_loaded:
        raise HTTPException(status_code=503, detail="Agentes não disponíveis")
    
    try:
        task_id = create_task("nf_agent", {"sale_data": request.sale_data})
        
        background_tasks.add_task(
            execute_agent_background,
            task_id,
            "nf_agent",
            {"sale_data": request.sale_data}
        )
        
        return {
            "status": "accepted",
            "task_id": task_id,
            "message": "Geração de NF iniciada",
            "check_status": f"/api/agents/status/{task_id}"
        }
        
    except Exception as e:
        logger.exception(f"Erro ao gerar NF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}")
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """Verificar status de uma tarefa"""
    if task_id not in tasks_storage:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    
    task = tasks_storage[task_id]
    return TaskStatusResponse(**task)


@router.get("/tasks")
async def list_tasks(limit: int = 10) -> Dict[str, Any]:
    """Listar tarefas recentes"""
    tasks = list(tasks_storage.values())
    tasks.sort(key=lambda x: x["created_at"], reverse=True)
    return {
        "total": len(tasks),
        "tasks": tasks[:limit]
    }


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str) -> Dict[str, Any]:
    """Deletar tarefa do storage"""
    if task_id in tasks_storage:
        del tasks_storage[task_id]
        return {"status": "ok", "message": f"Tarefa {task_id} removida"}
    raise HTTPException(status_code=404, detail="Tarefa não encontrada")


# ==================== GENERIC AGENT EXECUTOR ====================

@router.post("/execute")
async def execute_agent(request: AgentExecutionRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Executar qualquer agente de forma genérica"""
    if not agents_loaded:
        raise HTTPException(status_code=503, detail="Agentes não disponíveis")
    
    try:
        task_id = create_task(request.agent_name, request.parameters)
        
        background_tasks.add_task(
            execute_agent_background,
            task_id,
            request.agent_name,
            request.parameters
        )
        
        return {
            "status": "accepted",
            "task_id": task_id,
            "agent": request.agent_name,
            "message": f"Agente {request.agent_name} iniciado",
            "check_status": f"/api/agents/status/{task_id}"
        }
        
    except Exception as e:
        logger.exception(f"Erro ao executar agente: {e}")
        raise HTTPException(status_code=500, detail=str(e))

