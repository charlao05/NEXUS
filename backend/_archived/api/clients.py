"""
API simples de Clientes (mini-CRM em memória)
- Permite listar/criar clientes
- Permite acessar obrigações e vendas associadas
- Sem persistência (reinicia a cada boot). Para produção, substituir por DB/Redis.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/clients", tags=["clients"])


class Obligation(BaseModel):
    id: str
    name: str
    type: Optional[str] = None
    due_date: Optional[str] = None
    estimated_value: Optional[float] = None
    priority: Optional[str] = None
    notes: Optional[str] = None


class Sale(BaseModel):
    id: str
    cliente_nome: Optional[str] = None
    valor_total: Optional[float] = None
    descricao_servicos: Optional[str] = None
    data_venda: Optional[str] = None


class Client(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    obligations: List[Obligation] = Field(default_factory=list)
    sales: List[Sale] = Field(default_factory=list)


# Armazenamento em memória (reset a cada boot)
CLIENTS: Dict[str, Client] = {}

# Clientes de amostra para facilitar uso imediato
SAMPLE_CLIENTS = [
    Client(
        id="cliente123",
        name="Cliente Demo 123",
        email="cliente123@email.com",
        obligations=[
            Obligation(
                id="DAS-001",
                name="DAS - Janeiro",
                type="DAS",
                due_date="2026-01-20",
                estimated_value=80.50,
                priority="high",
            )
        ],
        sales=[
            Sale(
                id="SALE-001",
                cliente_nome="Cliente Demo 123",
                valor_total=250.0,
                descricao_servicos="Serviço de manutenção",
                data_venda="2025-12-28",
            )
        ],
    ),
    Client(
        id="cliente456",
        name="Cliente Demo 456",
        email="cliente456@email.com",
        obligations=[],
        sales=[],
    ),
]

for c in SAMPLE_CLIENTS:
    CLIENTS[c.id] = c


@router.get("/")
async def list_clients() -> Dict[str, Any]:
    return {"status": "ok", "clients": [c.dict() for c in CLIENTS.values()]}


class CreateClientRequest(BaseModel):
    id: Optional[str] = None
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    obligations: List[Obligation] = Field(default_factory=list)
    sales: List[Sale] = Field(default_factory=list)


@router.post("/")
async def create_client(req: CreateClientRequest) -> Dict[str, Any]:
    client_id = req.id or str(uuid4())[:8]
    if client_id in CLIENTS:
        raise HTTPException(status_code=400, detail="Cliente já existe")
    client = Client(
        id=client_id,
        name=req.name,
        email=req.email,
        phone=req.phone,
        notes=req.notes,
        obligations=req.obligations,
        sales=req.sales,
    )
    CLIENTS[client_id] = client
    logger.info("Cliente criado: %s", client_id)
    return {"status": "ok", "client": client.dict()}


@router.get("/{client_id}")
async def get_client(client_id: str) -> Dict[str, Any]:
    client = CLIENTS.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return {"status": "ok", "client": client.dict()}


@router.put("/{client_id}")
async def update_client(client_id: str, req: CreateClientRequest) -> Dict[str, Any]:
    if client_id not in CLIENTS:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    client = Client(
        id=client_id,
        name=req.name,
        email=req.email,
        phone=req.phone,
        notes=req.notes,
        obligations=req.obligations,
        sales=req.sales,
    )
    CLIENTS[client_id] = client
    logger.info("Cliente atualizado: %s", client_id)
    return {"status": "ok", "client": client.dict()}


@router.get("/{client_id}/obligations")
async def get_client_obligations(client_id: str) -> Dict[str, Any]:
    client = CLIENTS.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return {"status": "ok", "obligations": [o.dict() for o in client.obligations]}


@router.get("/{client_id}/sales")
async def get_client_sales(client_id: str) -> Dict[str, Any]:
    client = CLIENTS.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return {"status": "ok", "sales": [s.dict() for s in client.sales]}
