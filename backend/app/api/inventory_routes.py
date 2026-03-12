"""
NEXUS - API REST para Inventário / Estoque
============================================
Endpoints REST protegidos por autenticação.
Multi-tenant: todas as operações filtradas por user_id.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


# ============================================================================
# AUTH HELPER
# ============================================================================

def _get_current_user_dep():
    from app.api.auth import get_current_user
    return get_current_user


def _user_id_from(user: dict) -> int:
    return user.get("user_id", 0)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sku: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    unit: str = Field("un", max_length=20)
    cost_price: float = Field(0.0, ge=0)
    sale_price: float = Field(0.0, ge=0)
    min_stock: float = Field(0.0, ge=0)


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    sku: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=100)
    unit: Optional[str] = Field(None, max_length=20)
    cost_price: Optional[float] = Field(None, ge=0)
    sale_price: Optional[float] = Field(None, ge=0)
    min_stock: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None


class MovementCreate(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)
    unit_price: Optional[float] = Field(None, ge=0)
    reason: str = Field("compra", max_length=100)
    notes: Optional[str] = Field(None, max_length=500)
    reference_id: Optional[str] = Field(None, max_length=100)


# ============================================================================
# PRODUTOS
# ============================================================================

@router.post("/products", status_code=201)
async def create_product(
    body: ProductCreate,
    current_user: dict = Depends(_get_current_user_dep()),
):
    """Criar um novo produto no estoque."""
    from database.inventory_service import InventoryService

    uid = _user_id_from(current_user)
    result = InventoryService.create_product(
        user_id=uid,
        name=body.name,
        sku=body.sku,
        category=body.category,
        unit=body.unit,
        cost_price=body.cost_price,
        sale_price=body.sale_price,
        min_stock=body.min_stock,
    )
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    if result["status"] == "duplicate":
        raise HTTPException(status_code=409, detail=result["message"])
    return result


@router.get("/products")
async def list_products(
    category: Optional[str] = None,
    low_stock: bool = False,
    search: Optional[str] = None,
    is_active: bool = True,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(_get_current_user_dep()),
):
    """Listar produtos com filtros."""
    from database.inventory_service import InventoryService

    uid = _user_id_from(current_user)
    return InventoryService.get_products(
        user_id=uid,
        category=category,
        low_stock_only=low_stock,
        search=search,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )


@router.get("/products/{product_id}")
async def get_product(
    product_id: int,
    current_user: dict = Depends(_get_current_user_dep()),
):
    """Buscar produto por ID."""
    from database.inventory_service import InventoryService

    uid = _user_id_from(current_user)
    result = InventoryService.get_product_by_id(product_id, uid)
    if not result:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return result


@router.put("/products/{product_id}")
async def update_product(
    product_id: int,
    body: ProductUpdate,
    current_user: dict = Depends(_get_current_user_dep()),
):
    """Atualizar produto."""
    from database.inventory_service import InventoryService

    uid = _user_id_from(current_user)
    fields = body.model_dump(exclude_none=True)
    result = InventoryService.update_product(product_id, uid, **fields)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail=result["message"])
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


# ============================================================================
# MOVIMENTAÇÕES
# ============================================================================

@router.post("/movements/entry", status_code=201)
async def register_entry(
    body: MovementCreate,
    current_user: dict = Depends(_get_current_user_dep()),
):
    """Registrar entrada de estoque (compra, produção, devolução)."""
    from database.inventory_service import InventoryService

    uid = _user_id_from(current_user)
    result = InventoryService.register_entry(
        user_id=uid,
        product_id=body.product_id,
        quantity=body.quantity,
        unit_price=body.unit_price,
        reason=body.reason,
        notes=body.notes,
        reference_id=body.reference_id,
    )
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail=result["message"])
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@router.post("/movements/exit", status_code=201)
async def register_exit(
    body: MovementCreate,
    current_user: dict = Depends(_get_current_user_dep()),
):
    """Registrar saída de estoque (venda, uso, perda)."""
    from database.inventory_service import InventoryService

    uid = _user_id_from(current_user)
    result = InventoryService.register_exit(
        user_id=uid,
        product_id=body.product_id,
        quantity=body.quantity,
        unit_price=body.unit_price,
        reason=body.reason,
        notes=body.notes,
        reference_id=body.reference_id,
    )
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail=result["message"])
    if result["status"] == "insufficient_stock":
        raise HTTPException(status_code=422, detail=result["message"])
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@router.get("/movements")
async def list_movements(
    product_id: Optional[int] = None,
    type: Optional[Literal["entrada", "saida"]] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(_get_current_user_dep()),
):
    """Listar movimentações com filtros."""
    from database.inventory_service import InventoryService

    uid = _user_id_from(current_user)
    return InventoryService.get_movements(
        user_id=uid,
        product_id=product_id,
        type=type,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


# ============================================================================
# RESUMOS E RELATÓRIOS
# ============================================================================

@router.get("/summary")
async def stock_summary(
    current_user: dict = Depends(_get_current_user_dep()),
):
    """Resumo geral do estoque: valor total, alertas, movimentações."""
    from database.inventory_service import InventoryService

    uid = _user_id_from(current_user)
    return InventoryService.get_stock_summary(uid)


@router.get("/report")
async def stock_report(
    start_date: date = Query(...),
    end_date: date = Query(...),
    current_user: dict = Depends(_get_current_user_dep()),
):
    """Relatório de movimentações por período, agrupado por produto."""
    from database.inventory_service import InventoryService

    uid = _user_id_from(current_user)
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date deve ser <= end_date")
    return InventoryService.get_stock_report_by_period(uid, start_date, end_date)


@router.get("/alerts")
async def low_stock_alerts(
    current_user: dict = Depends(_get_current_user_dep()),
):
    """Produtos abaixo do estoque mínimo."""
    from database.inventory_service import InventoryService

    uid = _user_id_from(current_user)
    return InventoryService.get_low_stock_alerts(uid)
