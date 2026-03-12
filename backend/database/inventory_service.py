"""
NEXUS - Inventory / Stock Service
===================================
Camada de serviço para gestão de estoque e produtos.
Multi-tenant: todas as queries filtram por user_id.

Funciona para os três perfis de MEI:
- Comércio: produtos para revenda (tênis, alimentos, roupas)
- Serviço: materiais utilizados (tinta, peças, insumos)
- Indústria: matéria-prima + produto acabado
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional
from sqlalchemy import func, or_, desc
import logging

from database.models import Product, StockMovement, get_session

logger = logging.getLogger(__name__)


class InventoryService:
    """Serviço de Inventário/Estoque com persistência real e multi-tenancy"""

    # ========================================================================
    # PRODUTOS — CRUD
    # ========================================================================

    @staticmethod
    def create_product(
        user_id: int,
        name: str,
        sku: str = None,
        category: str = None,
        unit: str = "un",
        cost_price: float = 0.0,
        sale_price: float = 0.0,
        min_stock: float = 0.0,
    ) -> dict:
        """Cria um produto no estoque do usuário."""
        session = get_session()
        try:
            # Deduplicação por SKU dentro do mesmo tenant
            if sku:
                existing = (
                    session.query(Product)
                    .filter(Product.user_id == user_id, Product.sku == sku)
                    .first()
                )
                if existing:
                    return {
                        "status": "duplicate",
                        "message": f"Produto com SKU '{sku}' já existe",
                        "product": existing.to_dict(),
                    }

            product = Product(
                user_id=user_id,
                name=name,
                sku=sku,
                category=category,
                unit=unit,
                cost_price=cost_price,
                sale_price=sale_price,
                min_stock=min_stock,
                current_stock=0.0,
            )
            session.add(product)
            session.commit()
            session.refresh(product)

            logger.info(f"✅ Produto criado: {name} (ID={product.id}, user={user_id})")
            return {"status": "created", "product": product.to_dict()}
        except Exception as e:
            session.rollback()
            logger.error(f"Erro ao criar produto: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            session.close()

    @staticmethod
    def get_products(
        user_id: int,
        category: str = None,
        low_stock_only: bool = False,
        search: str = None,
        is_active: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list:
        """Lista produtos do usuário com filtros."""
        session = get_session()
        try:
            q = session.query(Product).filter(Product.user_id == user_id)

            if is_active is not None:
                q = q.filter(Product.is_active == is_active)
            if category:
                q = q.filter(Product.category == category)
            if low_stock_only:
                q = q.filter(
                    Product.min_stock > 0,
                    Product.current_stock <= Product.min_stock,
                )
            if search:
                term = f"%{search}%"
                q = q.filter(
                    or_(
                        Product.name.ilike(term),
                        Product.sku.ilike(term),
                        Product.category.ilike(term),
                    )
                )

            total = q.count()
            products = q.order_by(Product.name).offset(offset).limit(limit).all()
            return {
                "total": total,
                "products": [p.to_dict() for p in products],
            }
        finally:
            session.close()

    @staticmethod
    def get_product_by_id(product_id: int, user_id: int) -> Optional[dict]:
        """Busca produto por ID (filtrado por user_id)."""
        session = get_session()
        try:
            product = (
                session.query(Product)
                .filter(Product.id == product_id, Product.user_id == user_id)
                .first()
            )
            if not product:
                return None
            data = product.to_dict()
            data["movements_count"] = len(product.movements)
            return data
        finally:
            session.close()

    @staticmethod
    def update_product(product_id: int, user_id: int, **fields) -> dict:
        """Atualiza campos de um produto."""
        session = get_session()
        try:
            product = (
                session.query(Product)
                .filter(Product.id == product_id, Product.user_id == user_id)
                .first()
            )
            if not product:
                return {"status": "not_found", "message": "Produto não encontrado"}

            allowed = {
                "name", "sku", "category", "unit", "cost_price",
                "sale_price", "min_stock", "is_active",
            }
            changed = []
            for key, value in fields.items():
                if key in allowed and value is not None:
                    setattr(product, key, value)
                    changed.append(key)

            if changed:
                product.updated_at = datetime.now(timezone.utc)
                session.commit()
                session.refresh(product)

            return {"status": "updated", "product": product.to_dict(), "changed": changed}
        except Exception as e:
            session.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            session.close()

    # ========================================================================
    # MOVIMENTAÇÕES DE ESTOQUE
    # ========================================================================

    @staticmethod
    def register_entry(
        user_id: int,
        product_id: int,
        quantity: float,
        unit_price: float = None,
        reason: str = "compra",
        notes: str = None,
        reference_id: str = None,
    ) -> dict:
        """Registra entrada de estoque (compra, produção, devolução, ajuste)."""
        if quantity <= 0:
            return {"status": "error", "message": "Quantidade deve ser maior que zero"}

        session = get_session()
        try:
            product = (
                session.query(Product)
                .filter(Product.id == product_id, Product.user_id == user_id)
                .first()
            )
            if not product:
                return {"status": "not_found", "message": "Produto não encontrado"}

            price = unit_price if unit_price is not None else product.cost_price
            total_value = round(quantity * price, 2)

            movement = StockMovement(
                user_id=user_id,
                product_id=product_id,
                type="entrada",
                quantity=quantity,
                unit_price=price,
                total_value=total_value,
                reason=reason,
                notes=notes,
                reference_id=reference_id,
            )
            session.add(movement)

            # Atualizar saldo do produto
            product.current_stock = round(product.current_stock + quantity, 4)
            # Atualizar preço de custo se informado
            if unit_price is not None:
                product.cost_price = unit_price
            product.updated_at = datetime.now(timezone.utc)

            session.commit()
            session.refresh(movement)

            logger.info(
                f"📦 Entrada: {quantity} {product.unit} de '{product.name}' "
                f"(estoque: {product.current_stock})"
            )
            return {
                "status": "created",
                "movement": movement.to_dict(),
                "new_stock": product.current_stock,
            }
        except Exception as e:
            session.rollback()
            logger.error(f"Erro ao registrar entrada: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            session.close()

    @staticmethod
    def register_exit(
        user_id: int,
        product_id: int,
        quantity: float,
        unit_price: float = None,
        reason: str = "venda",
        notes: str = None,
        reference_id: str = None,
    ) -> dict:
        """Registra saída de estoque (venda, uso, perda, ajuste)."""
        if quantity <= 0:
            return {"status": "error", "message": "Quantidade deve ser maior que zero"}

        session = get_session()
        try:
            product = (
                session.query(Product)
                .filter(Product.id == product_id, Product.user_id == user_id)
                .first()
            )
            if not product:
                return {"status": "not_found", "message": "Produto não encontrado"}

            # Verificar estoque suficiente
            if product.current_stock < quantity:
                return {
                    "status": "insufficient_stock",
                    "message": (
                        f"Estoque insuficiente para '{product.name}': "
                        f"disponível {product.current_stock} {product.unit}, "
                        f"solicitado {quantity} {product.unit}"
                    ),
                    "available": product.current_stock,
                }

            price = unit_price if unit_price is not None else product.sale_price
            total_value = round(quantity * price, 2)

            movement = StockMovement(
                user_id=user_id,
                product_id=product_id,
                type="saida",
                quantity=quantity,
                unit_price=price,
                total_value=total_value,
                reason=reason,
                notes=notes,
                reference_id=reference_id,
            )
            session.add(movement)

            # Atualizar saldo do produto
            product.current_stock = round(product.current_stock - quantity, 4)
            product.updated_at = datetime.now(timezone.utc)

            session.commit()
            session.refresh(movement)

            logger.info(
                f"📦 Saída: {quantity} {product.unit} de '{product.name}' "
                f"(estoque: {product.current_stock})"
            )
            return {
                "status": "created",
                "movement": movement.to_dict(),
                "new_stock": product.current_stock,
            }
        except Exception as e:
            session.rollback()
            logger.error(f"Erro ao registrar saída: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            session.close()

    @staticmethod
    def get_movements(
        user_id: int,
        product_id: int = None,
        type: str = None,
        start_date: date = None,
        end_date: date = None,
        limit: int = 50,
    ) -> list:
        """Lista movimentações com filtros."""
        session = get_session()
        try:
            q = session.query(StockMovement).filter(StockMovement.user_id == user_id)

            if product_id:
                q = q.filter(StockMovement.product_id == product_id)
            if type:
                q = q.filter(StockMovement.type == type)
            if start_date:
                q = q.filter(StockMovement.created_at >= datetime.combine(start_date, datetime.min.time()))
            if end_date:
                q = q.filter(StockMovement.created_at <= datetime.combine(end_date, datetime.max.time()))

            movements = q.order_by(desc(StockMovement.created_at)).limit(limit).all()
            return [m.to_dict() for m in movements]
        finally:
            session.close()

    # ========================================================================
    # RESUMOS E RELATÓRIOS
    # ========================================================================

    @staticmethod
    def get_stock_summary(user_id: int) -> dict:
        """Resumo geral do estoque do usuário."""
        session = get_session()
        try:
            products = (
                session.query(Product)
                .filter(Product.user_id == user_id, Product.is_active == True)
                .all()
            )

            total_products = len(products)
            total_stock_value = round(
                sum(p.current_stock * p.cost_price for p in products), 2
            )

            # Produtos abaixo do mínimo
            low_stock = [
                p.to_dict()
                for p in products
                if p.min_stock > 0 and p.current_stock <= p.min_stock
            ]

            # Top 5 por valor em estoque
            top_products = sorted(
                products,
                key=lambda p: p.current_stock * p.cost_price,
                reverse=True,
            )[:5]

            # Movimentações de hoje
            today = date.today()
            today_start = datetime.combine(today, datetime.min.time())
            today_end = datetime.combine(today, datetime.max.time())
            today_movements = (
                session.query(StockMovement)
                .filter(
                    StockMovement.user_id == user_id,
                    StockMovement.created_at >= today_start,
                    StockMovement.created_at <= today_end,
                )
                .all()
            )
            entradas_hoje = sum(1 for m in today_movements if m.type == "entrada")
            saidas_hoje = sum(1 for m in today_movements if m.type == "saida")

            # Movimentações da semana
            week_start = today - timedelta(days=today.weekday())  # segunda
            week_start_dt = datetime.combine(week_start, datetime.min.time())
            week_movements = (
                session.query(StockMovement)
                .filter(
                    StockMovement.user_id == user_id,
                    StockMovement.created_at >= week_start_dt,
                    StockMovement.created_at <= today_end,
                )
                .all()
            )
            entradas_semana = sum(1 for m in week_movements if m.type == "entrada")
            saidas_semana = sum(1 for m in week_movements if m.type == "saida")

            return {
                "total_products": total_products,
                "total_stock_value": total_stock_value,
                "low_stock_alerts": low_stock,
                "top_products": [p.to_dict() for p in top_products],
                "movements_today": {
                    "entradas": entradas_hoje,
                    "saidas": saidas_hoje,
                    "total": entradas_hoje + saidas_hoje,
                },
                "movements_this_week": {
                    "entradas": entradas_semana,
                    "saidas": saidas_semana,
                    "total": entradas_semana + saidas_semana,
                },
            }
        finally:
            session.close()

    @staticmethod
    def get_stock_report_by_period(
        user_id: int, start_date: date, end_date: date
    ) -> dict:
        """Relatório de movimentações por período, agrupado por produto."""
        session = get_session()
        try:
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())

            movements = (
                session.query(StockMovement)
                .filter(
                    StockMovement.user_id == user_id,
                    StockMovement.created_at >= start_dt,
                    StockMovement.created_at <= end_dt,
                )
                .all()
            )

            # Agrupar por produto
            by_product: dict = {}
            total_entradas = 0.0
            total_saidas = 0.0
            total_entradas_valor = 0.0
            total_saidas_valor = 0.0

            for m in movements:
                pid = m.product_id
                if pid not in by_product:
                    by_product[pid] = {
                        "product_id": pid,
                        "product_name": m.product.name if m.product else "?",
                        "entradas_qty": 0.0,
                        "saidas_qty": 0.0,
                        "entradas_valor": 0.0,
                        "saidas_valor": 0.0,
                    }
                if m.type == "entrada":
                    by_product[pid]["entradas_qty"] += m.quantity
                    by_product[pid]["entradas_valor"] += m.total_value
                    total_entradas += m.quantity
                    total_entradas_valor += m.total_value
                else:
                    by_product[pid]["saidas_qty"] += m.quantity
                    by_product[pid]["saidas_valor"] += m.total_value
                    total_saidas += m.quantity
                    total_saidas_valor += m.total_value

            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "movements_count": len(movements),
                "total_entradas": round(total_entradas, 2),
                "total_saidas": round(total_saidas, 2),
                "total_entradas_valor": round(total_entradas_valor, 2),
                "total_saidas_valor": round(total_saidas_valor, 2),
                "saldo_valor": round(total_entradas_valor - total_saidas_valor, 2),
                "by_product": list(by_product.values()),
            }
        finally:
            session.close()

    @staticmethod
    def get_low_stock_alerts(user_id: int) -> list:
        """Retorna produtos abaixo do estoque mínimo."""
        session = get_session()
        try:
            products = (
                session.query(Product)
                .filter(
                    Product.user_id == user_id,
                    Product.is_active == True,
                    Product.min_stock > 0,
                    Product.current_stock <= Product.min_stock,
                )
                .order_by(Product.current_stock)
                .all()
            )
            return [p.to_dict() for p in products]
        finally:
            session.close()
