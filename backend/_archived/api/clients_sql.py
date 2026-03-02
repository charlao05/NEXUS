"""
API de Clientes (mini-CRM) com persistência SQLite leve.
- Lista/cria/edita clientes
- Obrigações (prazos) e vendas vinculadas
- Sem autenticação por enquanto; para produção, proteger com JWT/Clerk.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/clients", tags=["clients"])

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "clients.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS obligations (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT,
            due_date TEXT,
            estimated_value REAL,
            priority TEXT,
            notes TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        );
        CREATE TABLE IF NOT EXISTS sales (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            cliente_nome TEXT,
            valor_total REAL,
            descricao_servicos TEXT,
            data_venda TEXT,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        );
        """
    )
    conn.commit()
    conn.close()


_init_db()


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


def _row_to_client(row: sqlite3.Row) -> Client:
    return Client(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        phone=row["phone"],
        notes=row["notes"],
        obligations=list_obligations(row["id"]),
        sales=list_sales(row["id"]),
    )


def list_clients_db() -> List[Client]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [_row_to_client(r) for r in rows]


def get_client_db(client_id: str) -> Optional[Client]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients WHERE id=?", (client_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_client(row)


def upsert_client_db(client: Client) -> Client:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO clients (id, name, email, phone, notes)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            email=excluded.email,
            phone=excluded.phone,
            notes=excluded.notes;
        """,
        (client.id, client.name, client.email, client.phone, client.notes),
    )
    conn.commit()
    conn.close()
    replace_obligations(client.id, client.obligations)
    replace_sales(client.id, client.sales)
    return client


def replace_obligations(client_id: str, obligations: List[Obligation]) -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM obligations WHERE client_id=?", (client_id,))
    cur.executemany(
        """
        INSERT INTO obligations (id, client_id, name, type, due_date, estimated_value, priority, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                o.id,
                client_id,
                o.name,
                o.type,
                o.due_date,
                o.estimated_value,
                o.priority,
                o.notes,
            )
            for o in obligations
        ],
    )
    conn.commit()
    conn.close()


def replace_sales(client_id: str, sales: List[Sale]) -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM sales WHERE client_id=?", (client_id,))
    cur.executemany(
        """
        INSERT INTO sales (id, client_id, cliente_nome, valor_total, descricao_servicos, data_venda)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                s.id,
                client_id,
                s.cliente_nome,
                s.valor_total,
                s.descricao_servicos,
                s.data_venda,
            )
            for s in sales
        ],
    )
    conn.commit()
    conn.close()


def list_obligations(client_id: str) -> List[Obligation]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM obligations WHERE client_id=?", (client_id,))
    rows = cur.fetchall()
    conn.close()
    return [Obligation(**dict(r)) for r in rows]


def list_sales(client_id: str) -> List[Sale]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sales WHERE client_id=?", (client_id,))
    rows = cur.fetchall()
    conn.close()
    return [Sale(**dict(r)) for r in rows]


# Seed demo client if empty
if not list_clients_db():
    demo = Client(
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
    )
    upsert_client_db(demo)


class CreateClientRequest(BaseModel):
    id: Optional[str] = None
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    obligations: List[Obligation] = Field(default_factory=list)
    sales: List[Sale] = Field(default_factory=list)


@router.get("/")
async def list_clients() -> Dict[str, Any]:
    return {"status": "ok", "clients": [c.dict() for c in list_clients_db()]}


@router.post("/")
async def create_client(req: CreateClientRequest) -> Dict[str, Any]:
    client_id = req.id or str(uuid4())[:8]
    client = Client(
        id=client_id,
        name=req.name,
        email=req.email,
        phone=req.phone,
        notes=req.notes,
        obligations=req.obligations,
        sales=req.sales,
    )
    upsert_client_db(client)
    logger.info("Cliente criado: %s", client_id)
    return {"status": "ok", "client": client.dict()}


@router.get("/{client_id}")
async def get_client(client_id: str) -> Dict[str, Any]:
    client = get_client_db(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return {"status": "ok", "client": client.dict()}


@router.put("/{client_id}")
async def update_client(client_id: str, req: CreateClientRequest) -> Dict[str, Any]:
    if not get_client_db(client_id):
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
    upsert_client_db(client)
    logger.info("Cliente atualizado: %s", client_id)
    return {"status": "ok", "client": client.dict()}


@router.get("/{client_id}/obligations")
async def get_client_obligations(client_id: str) -> Dict[str, Any]:
    client = get_client_db(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return {"status": "ok", "obligations": [o.dict() for o in client.obligations]}


@router.get("/{client_id}/sales")
async def get_client_sales(client_id: str) -> Dict[str, Any]:
    client = get_client_db(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return {"status": "ok", "sales": [s.dict() for s in client.sales]}


# Helpers para outros módulos

def get_obligations_for_agent(client_id: str) -> List[Dict[str, Any]]:
    client = get_client_db(client_id)
    return [o.dict() for o in client.obligations] if client else []


def get_sales_for_agent(client_id: str) -> List[Dict[str, Any]]:
    client = get_client_db(client_id)
    return [s.dict() for s in client.sales] if client else []
