# pyright: reportMissingImports=false
"""
Testes — Módulo de Inventário / Estoque
=========================================
Testa: Product CRUD, StockMovement (entrada/saída), insuficiência,
       summary, relatórios por período, alertas, busca.
"""

import pytest
from datetime import date, timedelta
from starlette.testclient import TestClient


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def app():
    """Importa app isolada para testes de inventário."""
    import sys
    from pathlib import Path
    backend = Path(__file__).parent.parent
    sys.path.insert(0, str(backend))
    import os
    os.environ.setdefault("JWT_SECRET", "test-secret-inventory")
    os.environ.setdefault("NEXUS_DB_PATH", str(backend / "data" / "test_inventory.db"))
    os.environ["ADMIN_EMAILS"] = "inventoryadmin@nexus.com"

    from main import app as _app
    from database.models import init_db
    init_db()
    return _app


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_token(client):
    """Cria usuário e retorna token."""
    client.post("/api/auth/signup", json={
        "email": "inventoryuser@nexus.com",
        "password": "Teste1234!",
        "full_name": "Inventory User",
    })
    resp = client.post("/api/auth/login", json={
        "email": "inventoryuser@nexus.com",
        "password": "Teste1234!",
    })
    return resp.json()["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# PRODUTO — CRUD
# ============================================================================

class TestProductCRUD:
    """Testar criação, leitura, atualização e listagem de produtos."""

    def test_create_product_minimal(self, client, auth_token):
        """Cria produto apenas com nome."""
        resp = client.post(
            "/api/inventory/products",
            json={"name": "Caneta Azul"},
            headers=_headers(auth_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "created"
        assert data["product"]["name"] == "Caneta Azul"
        assert data["product"]["current_stock"] == 0

    def test_create_product_full(self, client, auth_token):
        """Cria produto com todos os campos."""
        resp = client.post(
            "/api/inventory/products",
            json={
                "name": "Tênis Nike Air",
                "sku": "NIKE-AIR-001",
                "category": "Calçados",
                "unit": "par",
                "cost_price": 150.00,
                "sale_price": 299.90,
                "min_stock": 5,
            },
            headers=_headers(auth_token),
        )
        assert resp.status_code == 201
        p = resp.json()["product"]
        assert p["sku"] == "NIKE-AIR-001"
        assert p["cost_price"] == 150.00
        assert p["sale_price"] == 299.90
        assert p["min_stock"] == 5

    def test_create_product_duplicate_sku(self, client, auth_token):
        """SKU duplicado retorna 409."""
        resp = client.post(
            "/api/inventory/products",
            json={"name": "Outro Tênis", "sku": "NIKE-AIR-001"},
            headers=_headers(auth_token),
        )
        assert resp.status_code == 409

    def test_list_products(self, client, auth_token):
        """Lista todos os produtos."""
        resp = client.get("/api/inventory/products", headers=_headers(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        assert len(data["products"]) >= 2

    def test_get_product_by_id(self, client, auth_token):
        """Busca produto por ID."""
        # Criar para ter ID conhecido
        resp = client.post(
            "/api/inventory/products",
            json={"name": "Produto Para Get", "sku": "GET-001"},
            headers=_headers(auth_token),
        )
        pid = resp.json()["product"]["id"]

        resp = client.get(f"/api/inventory/products/{pid}", headers=_headers(auth_token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Produto Para Get"

    def test_get_product_not_found(self, client, auth_token):
        """Produto inexistente retorna 404."""
        resp = client.get("/api/inventory/products/99999", headers=_headers(auth_token))
        assert resp.status_code == 404

    def test_update_product(self, client, auth_token):
        """Atualizar campos de um produto."""
        # Pegar o primeiro produto
        products = client.get("/api/inventory/products", headers=_headers(auth_token)).json()["products"]
        pid = products[0]["id"]

        resp = client.put(
            f"/api/inventory/products/{pid}",
            json={"sale_price": 349.90, "min_stock": 10},
            headers=_headers(auth_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"
        assert "sale_price" in resp.json()["changed"]

    def test_search_products(self, client, auth_token):
        """Busca por texto (nome ou SKU)."""
        resp = client.get(
            "/api/inventory/products?search=Nike",
            headers=_headers(auth_token),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


# ============================================================================
# MOVIMENTAÇÕES
# ============================================================================

class TestStockMovements:
    """Testar entradas e saídas de estoque."""

    @pytest.fixture(autouse=True)
    def _setup_product(self, client, auth_token):
        """Cria produto base para as movimentações."""
        resp = client.post(
            "/api/inventory/products",
            json={
                "name": "Produto Mov",
                "sku": "MOV-001",
                "cost_price": 10.0,
                "sale_price": 25.0,
                "min_stock": 2,
            },
            headers=_headers(auth_token),
        )
        data = resp.json()
        # Pode já existir de run anterior (sku duplicate → 409)
        if resp.status_code == 409:
            products = client.get(
                "/api/inventory/products?search=MOV-001",
                headers=_headers(auth_token),
            ).json()["products"]
            self.product_id = products[0]["id"]
        else:
            self.product_id = data["product"]["id"]

    def test_register_entry(self, client, auth_token):
        """Entrada de estoque incrementa saldo."""
        resp = client.post(
            "/api/inventory/movements/entry",
            json={
                "product_id": self.product_id,
                "quantity": 20,
                "unit_price": 10.0,
                "reason": "compra",
            },
            headers=_headers(auth_token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "created"
        assert data["new_stock"] >= 20

    def test_register_exit(self, client, auth_token):
        """Saída de estoque decrementa saldo."""
        # Garantir estoque
        client.post(
            "/api/inventory/movements/entry",
            json={"product_id": self.product_id, "quantity": 10},
            headers=_headers(auth_token),
        )
        resp = client.post(
            "/api/inventory/movements/exit",
            json={
                "product_id": self.product_id,
                "quantity": 3,
                "reason": "venda",
            },
            headers=_headers(auth_token),
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "created"

    def test_exit_insufficient_stock(self, client, auth_token):
        """Saída maior que estoque retorna 422."""
        resp = client.post(
            "/api/inventory/movements/exit",
            json={
                "product_id": self.product_id,
                "quantity": 999999,
                "reason": "venda",
            },
            headers=_headers(auth_token),
        )
        assert resp.status_code == 422

    def test_entry_with_zero_quantity(self, client, auth_token):
        """Quantidade zero é rejeitada (validation)."""
        resp = client.post(
            "/api/inventory/movements/entry",
            json={"product_id": self.product_id, "quantity": 0},
            headers=_headers(auth_token),
        )
        assert resp.status_code == 422  # Pydantic gt=0

    def test_list_movements(self, client, auth_token):
        """Listar movimentações."""
        resp = client.get("/api/inventory/movements", headers=_headers(auth_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_movements_filtered(self, client, auth_token):
        """Filtrar movimentações por tipo."""
        resp = client.get(
            "/api/inventory/movements?type=entrada",
            headers=_headers(auth_token),
        )
        assert resp.status_code == 200
        for m in resp.json():
            assert m["type"] == "entrada"


# ============================================================================
# RESUMOS E RELATÓRIOS
# ============================================================================

class TestStockReports:
    """Testar summary, relatórios por período e alertas."""

    def test_stock_summary(self, client, auth_token):
        """Resumo geral do estoque."""
        resp = client.get("/api/inventory/summary", headers=_headers(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "total_products" in data
        assert "total_stock_value" in data
        assert "low_stock_alerts" in data
        assert "movements_today" in data
        assert "movements_this_week" in data

    def test_stock_report_by_period(self, client, auth_token):
        """Relatório por período."""
        today = date.today().isoformat()
        start = (date.today() - timedelta(days=30)).isoformat()
        resp = client.get(
            f"/api/inventory/report?start_date={start}&end_date={today}",
            headers=_headers(auth_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "period" in data
        assert "movements_count" in data
        assert "by_product" in data

    def test_stock_report_invalid_dates(self, client, auth_token):
        """start > end retorna 400."""
        resp = client.get(
            "/api/inventory/report?start_date=2025-12-31&end_date=2025-01-01",
            headers=_headers(auth_token),
        )
        assert resp.status_code == 400

    def test_low_stock_alerts(self, client, auth_token):
        """Alertas de estoque baixo."""
        resp = client.get("/api/inventory/alerts", headers=_headers(auth_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ============================================================================
# SEGURANÇA — Multi-tenancy
# ============================================================================

class TestMultiTenancy:
    """Verificar que dados de um usuário não vazam para outro."""

    def test_isolation_between_users(self, client):
        """Usuário B não vê produtos do Usuário A."""
        # Criar Usuário B
        client.post("/api/auth/signup", json={
            "email": "inventoryuserB@nexus.com",
            "password": "Teste1234!",
            "full_name": "Inventory User B",
        })
        resp = client.post("/api/auth/login", json={
            "email": "inventoryuserB@nexus.com",
            "password": "Teste1234!",
        })
        token_b = resp.json()["access_token"]

        # Listar produtos do user B — deve ser vazio
        resp = client.get("/api/inventory/products", headers=_headers(token_b))
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_unauthenticated_access(self, client):
        """Sem token retorna 401."""
        resp = client.get("/api/inventory/products")
        assert resp.status_code in (401, 403)
