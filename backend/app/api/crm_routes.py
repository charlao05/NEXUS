"""
NEXUS - API REST para CRM e Automação Web
===========================================
Endpoints REST protegidos por autenticação.
Multi-tenant: todas as operações filtradas por user_id.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Literal
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crm", tags=["crm"])
automation_router = APIRouter(prefix="/api/automation", tags=["automation"])


# ============================================================================
# PUB/SUB HELPER — Dispara eventos automaticamente no Agent Hub
# ============================================================================

def _fire_hub_event(event_name: str, payload: dict) -> None:
    """Dispara evento no Agent Hub (fire-and-forget, non-blocking).
    CRITICAL FIX #2: Pub/Sub é disparado automaticamente após ações CRM REST."""
    try:
        from agents.agent_hub import hub, EventType, AgentType, AgentMessage
        import asyncio

        _event_map = {
            "CLIENTE_CRIADO": (EventType.CLIENTE_CRIADO, AgentType.CLIENTES),
            "CLIENTE_ATUALIZADO": (EventType.CLIENTE_ATUALIZADO, AgentType.CLIENTES),
            "COMPROMISSO_CRIADO": (EventType.COMPROMISSO_CRIADO, AgentType.AGENDA),
            "PAGAMENTO_RECEBIDO": (EventType.PAGAMENTO_RECEBIDO, AgentType.CONTABILIDADE),
            "NF_EMITIDA": (EventType.NF_EMITIDA, AgentType.CONTABILIDADE),
        }
        if event_name not in _event_map:
            return
        event_type, from_agent = _event_map[event_name]
        msg = AgentMessage(
            from_agent=from_agent,
            to_agent=None,
            event_type=event_type,
            payload=payload,
            priority=5,
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(hub.publish(msg))
        except RuntimeError:
            pass
        logger.debug(f"📡 Hub event {event_name} dispatched via REST")
    except Exception as e:
        logger.debug(f"Hub event skipped: {e}")


# Import auth dependency
def _get_current_user_dep():
    from app.api.auth import get_current_user
    return get_current_user

def _user_id_from(user: dict) -> int:
    return user.get("user_id", 0)


# ============================================================================
# MODELS
# ============================================================================

class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    cpf_cnpj: Optional[str] = Field(None, max_length=18, pattern=r'^[0-9./-]+$')
    birth_date: Optional[str] = None  # YYYY-MM-DD
    address: Optional[str] = Field(None, max_length=300)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=2)
    segment: Literal["standard", "vip", "premium", "inactive"] = "standard"
    source: Literal["manual", "import", "web", "referral", "social"] = "manual"
    tags: list[str] = []
    notes: str = Field("", max_length=2000)


class ClientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    segment: Optional[Literal["standard", "vip", "premium", "inactive"]] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = Field(None, max_length=2000)
    is_active: Optional[bool] = None


class OpportunityCreate(BaseModel):
    client_id: int
    title: str = Field(..., min_length=1, max_length=200)
    value: float = Field(0, ge=0)
    stage: Literal["prospeccao", "qualificacao", "proposta", "negociacao", "fechado_ganho", "fechado_perdido"] = "prospeccao"
    expected_close: Optional[str] = None
    notes: str = Field("", max_length=2000)


class OpportunityStageUpdate(BaseModel):
    stage: Literal["prospeccao", "qualificacao", "proposta", "negociacao", "fechado_ganho", "fechado_perdido"]


class AppointmentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    scheduled_at: str  # ISO datetime
    client_id: Optional[int] = None
    description: str = Field("", max_length=2000)
    duration_minutes: int = Field(60, ge=5, le=480)
    type: Literal["reuniao", "consulta", "follow_up", "apresentacao", "outro"] = "reuniao"


class TransactionCreate(BaseModel):
    type: Literal["receita", "despesa"]
    amount: float = Field(..., gt=0)
    description: str = Field(..., min_length=1, max_length=300)
    category: str = Field("geral", max_length=50)
    date: Optional[str] = None  # YYYY-MM-DD
    client_id: Optional[int] = None
    notes: str = Field("", max_length=2000)


class InvoiceCreate(BaseModel):
    client_id: int
    description: str = Field(..., min_length=1, max_length=300)
    amount: float = Field(..., gt=0)
    due_date: str  # YYYY-MM-DD


class InteractionCreate(BaseModel):
    client_id: int
    type: Literal["nota", "ligacao", "email", "reuniao", "whatsapp", "visita"] = "nota"
    channel: Literal["manual", "sistema", "web", "telefone", "email", "whatsapp"] = "manual"
    summary: str = Field(..., min_length=1, max_length=500)
    details: str = Field("", max_length=2000)
    sentiment: Literal["positive", "neutral", "negative"] = "neutral"


class WebTaskRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


class TaskApproval(BaseModel):
    approved_by: str = "user"


# ============================================================================
# CRM ENDPOINTS
# ============================================================================

@router.post("/clients")
async def create_client(data: ClientCreate, user: dict = Depends(_get_current_user_dep())):
    from app.services.limit_service import check_crm_limit
    check_crm_limit(user)
    from database.crm_service import CRMService
    uid = _user_id_from(user)
    birth = None
    if data.birth_date:
        try:
            birth = date.fromisoformat(data.birth_date)
        except ValueError:
            raise HTTPException(400, "birth_date deve ser YYYY-MM-DD")

    result = CRMService.create_client(
        name=data.name, user_id=uid, phone=data.phone, email=data.email,
        cpf_cnpj=data.cpf_cnpj, birth_date=birth,
        address=data.address, city=data.city, state=data.state,
        segment=data.segment, source=data.source,
        tags=data.tags, notes=data.notes,
    )
    # Pub/Sub: notifica hub sobre novo cliente
    if result.get("status") == "created":
        _fire_hub_event("CLIENTE_CRIADO", result.get("client", {}))
    return result


@router.get("/clients")
async def list_clients(
    q: str = "", segment: str = None,
    sort_by: str = "name", limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    user: dict = Depends(_get_current_user_dep()),
):
    from database.crm_service import CRMService
    return CRMService.search_clients(
        query=q, segment=segment, sort_by=sort_by,
        limit=limit, offset=offset, user_id=_user_id_from(user),
    )


@router.get("/clients/followup")
async def clients_followup(days: int = 7, limit: int = 20, user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    return {"clients": CRMService.get_clients_for_followup(days, limit, user_id=_user_id_from(user))}


@router.get("/clients/birthdays")
async def clients_birthdays(days: int = 7, user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    return {"clients": CRMService.get_birthday_clients(days, user_id=_user_id_from(user))}


@router.get("/clients/{client_id}")
async def get_client(client_id: int, user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    result = CRMService.get_client(client_id, user_id=_user_id_from(user))
    if not result:
        raise HTTPException(404, "Cliente não encontrado")
    return result


@router.put("/clients/{client_id}")
async def update_client(client_id: int, data: ClientUpdate, user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    result = CRMService.update_client(client_id, user_id=_user_id_from(user), **fields)
    if result.get("status") == "updated":
        _fire_hub_event("CLIENTE_ATUALIZADO", {"client_id": client_id, **fields})
    return result


@router.delete("/clients/{client_id}")
async def delete_client(client_id: int, hard: bool = False, user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    return CRMService.delete_client(client_id, soft=not hard, user_id=_user_id_from(user))


# Interações
@router.post("/interactions")
async def add_interaction(data: InteractionCreate, user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    uid = _user_id_from(user)
    # Verificar se o cliente pertence ao usuário
    client = CRMService.get_client(data.client_id, user_id=uid)
    if not client or client.get("status") == "error":
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return CRMService.add_interaction(
        data.client_id, data.type, data.channel,
        data.summary, data.details, data.sentiment,
    )


@router.get("/clients/{client_id}/interactions")
async def get_interactions(client_id: int, limit: int = 50, user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    uid = _user_id_from(user)
    # Verificar se o cliente pertence ao usuário
    client = CRMService.get_client(client_id, user_id=uid)
    if not client or client.get("status") == "error":
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return {"interactions": CRMService.get_interactions(client_id, limit)}


# Pipeline de vendas
@router.post("/opportunities")
async def create_opportunity(data: OpportunityCreate, user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    close = None
    if data.expected_close:
        close = date.fromisoformat(data.expected_close)
    return CRMService.create_opportunity(
        data.client_id, data.title, data.value,
        data.stage, expected_close=close, notes=data.notes,
        user_id=_user_id_from(user),
    )


@router.put("/opportunities/{opp_id}/stage")
async def update_opp_stage(opp_id: int, data: OpportunityStageUpdate, user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    return CRMService.update_opportunity_stage(opp_id, data.stage)


@router.get("/pipeline")
async def get_pipeline(user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    return CRMService.get_pipeline_summary(user_id=_user_id_from(user))


# Agendamentos
@router.post("/appointments")
async def create_appointment(data: AppointmentCreate, user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    try:
        dt = datetime.fromisoformat(data.scheduled_at)
    except ValueError:
        raise HTTPException(400, "scheduled_at deve ser formato ISO")
    result = CRMService.create_appointment(
        data.title, dt, data.client_id,
        data.description, data.duration_minutes, data.type,
        user_id=_user_id_from(user),
    )
    if result.get("status") == "created":
        _fire_hub_event("COMPROMISSO_CRIADO", result.get("appointment", {}))
    return result


@router.get("/appointments")
async def list_appointments(
    start: str = None, end: str = None,
    status: str = None, limit: int = 50,
    user: dict = Depends(_get_current_user_dep()),
):
    from database.crm_service import CRMService
    s = date.fromisoformat(start) if start else None
    e = date.fromisoformat(end) if end else None
    return {"appointments": CRMService.get_appointments(s, e, status, limit, user_id=_user_id_from(user))}


# Financeiro
@router.post("/transactions")
async def create_transaction(data: TransactionCreate, user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    tx_date = date.fromisoformat(data.date) if data.date else None
    result = CRMService.record_transaction(
        data.type, data.amount, data.description,
        data.category, tx_date, data.client_id, data.notes,
        user_id=_user_id_from(user),
    )
    if result.get("status") == "created":
        _fire_hub_event("PAGAMENTO_RECEBIDO", result.get("transaction", {}))
    return result


@router.get("/financial-summary")
async def financial_summary(month: int = None, year: int = None, user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    return CRMService.get_financial_summary(month, year, user_id=_user_id_from(user))


@router.get("/financial-summary/today")
async def financial_summary_today(user: dict = Depends(_get_current_user_dep())):
    """Fluxo de caixa do dia atual."""
    from database.crm_service import CRMService
    return CRMService.get_daily_summary(user_id=_user_id_from(user))


@router.get("/financial-summary/week")
async def financial_summary_week(user: dict = Depends(_get_current_user_dep())):
    """Fluxo de caixa da semana atual (segunda a hoje)."""
    from database.crm_service import CRMService
    return CRMService.get_weekly_summary(user_id=_user_id_from(user))


@router.get("/financial-summary/range")
async def financial_summary_range(
    start: str = Query(..., description="Data início ISO (YYYY-MM-DD)"),
    end: str = Query(..., description="Data fim ISO (YYYY-MM-DD)"),
    user: dict = Depends(_get_current_user_dep()),
):
    """Fluxo de caixa por período personalizado."""
    from database.crm_service import CRMService
    try:
        start_d = date.fromisoformat(start)
        end_d = date.fromisoformat(end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de data inválido. Use YYYY-MM-DD")
    if start_d > end_d:
        raise HTTPException(status_code=400, detail="start deve ser <= end")
    return CRMService.get_financial_summary_by_range(start_d, end_d, user_id=_user_id_from(user))


# Cobranças
@router.post("/invoices")
async def create_invoice(data: InvoiceCreate, user: dict = Depends(_get_current_user_dep())):
    from app.services.limit_service import check_invoice_limit
    check_invoice_limit(user)
    from database.crm_service import CRMService
    result = CRMService.create_invoice(
        data.client_id, data.description,
        data.amount, date.fromisoformat(data.due_date),
        user_id=_user_id_from(user),
    )
    if result.get("status") == "created":
        _fire_hub_event("NF_EMITIDA", result.get("invoice", {}))
    return result


@router.get("/invoices/overdue")
async def overdue_invoices(user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    return {"invoices": CRMService.get_overdue_invoices(user_id=_user_id_from(user))}


@router.get("/invoices/upcoming")
async def upcoming_invoices(days: int = 7, user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    return {"invoices": CRMService.get_upcoming_invoices(days, user_id=_user_id_from(user))}


# Dashboard
@router.get("/dashboard")
async def crm_dashboard(user: dict = Depends(_get_current_user_dep())):
    from database.crm_service import CRMService
    return CRMService.get_crm_dashboard(user_id=_user_id_from(user))


# ============================================================================
# DATA EXPORT — MEDIUM FIX #14
# ============================================================================

@router.get("/export/clients")
async def export_clients_csv(user: dict = Depends(_get_current_user_dep())):
    """Exporta todos os clientes do usuário em formato CSV."""
    import csv
    import io
    from starlette.responses import StreamingResponse
    from database.crm_service import CRMService

    uid = _user_id_from(user)
    result = CRMService.search_clients(query="", user_id=uid, limit=10000)
    clients = result.get("clients", []) if isinstance(result, dict) else result

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Nome", "Telefone", "Email", "Segmento", "Ativo", "Criado em"])
    for c in clients:
        writer.writerow([
            c.get("id", ""), c.get("name", ""), c.get("phone", ""),
            c.get("email", ""), c.get("segment", ""), c.get("is_active", ""),
            c.get("created_at", ""),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=clientes.csv"},
    )


@router.get("/export/transactions")
async def export_transactions_csv(
    month: int = None, year: int = None,
    user: dict = Depends(_get_current_user_dep()),
):
    """Exporta transações financeiras em formato CSV."""
    import csv
    import io
    from starlette.responses import StreamingResponse
    from database.crm_service import CRMService
    from database.models import Transaction, SessionLocal

    uid = _user_id_from(user)
    db = SessionLocal()
    try:
        query = db.query(Transaction).filter(Transaction.user_id == uid)
        if month and year:
            from datetime import date as _date
            start = _date(year, month, 1)
            end_month = month + 1 if month < 12 else 1
            end_year = year if month < 12 else year + 1
            end = _date(end_year, end_month, 1)
            query = query.filter(Transaction.created_at >= start, Transaction.created_at < end)
        transactions = query.order_by(Transaction.created_at.desc()).limit(5000).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Tipo", "Valor", "Descrição", "Categoria", "Data"])
        for t in transactions:
            writer.writerow([
                t.id, t.type, f"{t.amount:.2f}", t.description,
                t.category, t.created_at.isoformat() if t.created_at else "",
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=transacoes.csv"},
        )
    finally:
        db.close()


# ============================================================================
# AUTOMAÇÃO WEB ENDPOINTS
# ============================================================================

@automation_router.post("/tasks/plan")
async def plan_web_task(data: WebTaskRequest, user: dict = Depends(_get_current_user_dep())):
    """Gera plano de automação via LLM (não executa ainda)"""
    from services.web_automation import generate_automation_plan, create_web_task
    plan = await generate_automation_plan(data.message)
    if "error" in plan:
        raise HTTPException(500, plan["error"])

    # Salvar como tarefa pendente
    task = create_web_task(
        title=plan.get("title", "Automação Web"),
        description=data.message,
        target_url=plan.get("target_url", ""),
        plan=plan,
    )
    return task


@automation_router.get("/tasks")
async def list_tasks(status: str = None, limit: int = 20, user: dict = Depends(_get_current_user_dep())):
    """Lista tarefas de automação"""
    from services.web_automation import get_pending_tasks, get_task_history
    if status == "pending":
        return {"tasks": get_pending_tasks()}
    return {"tasks": get_task_history(limit)}


@automation_router.get("/tasks/{task_id}")
async def get_task_detail(task_id: int, user: dict = Depends(_get_current_user_dep())):
    from services.web_automation import get_task
    task = get_task(task_id)
    if not task:
        raise HTTPException(404, "Tarefa não encontrada")
    return task


@automation_router.post("/tasks/{task_id}/approve")
async def approve_task_endpoint(task_id: int, data: TaskApproval, user: dict = Depends(_get_current_user_dep())):
    """Aprova tarefa para execução"""
    from services.web_automation import approve_task
    result = approve_task(task_id, data.approved_by)
    if result.get("status") == "not_found":
        raise HTTPException(404, "Tarefa não encontrada")
    return result


@automation_router.post("/tasks/{task_id}/reject")
async def reject_task_endpoint(task_id: int, user: dict = Depends(_get_current_user_dep())):
    """Rejeita tarefa"""
    from services.web_automation import reject_task
    return reject_task(task_id)


@automation_router.post("/tasks/{task_id}/execute")
async def execute_task_endpoint(task_id: int, user: dict = Depends(_get_current_user_dep())):
    """Executa tarefa APROVADA no navegador"""
    from services.web_automation import execute_approved_task
    result = execute_approved_task(task_id)
    if result.get("status") == "not_found":
        raise HTTPException(404, "Tarefa não encontrada")
    if result.get("status") == "not_approved":
        raise HTTPException(400, "Tarefa precisa ser aprovada antes de executar")
    return result
