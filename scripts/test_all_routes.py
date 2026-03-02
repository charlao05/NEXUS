"""Teste completo de todas as rotas do backend NEXUS."""
import requests
import json

BASE = "http://127.0.0.1:8000"
results = []

def test(method, path, expected=200, json_body=None, headers=None):
    url = BASE + path
    try:
        r = getattr(requests, method)(url, json=json_body, headers=headers or {}, timeout=10)
        status = "PASS" if r.status_code == expected else "FAIL"
        icon = "✅" if status == "PASS" else "❌"
        results.append((status, f"{icon} {method.upper():6s} {path:50s} -> {r.status_code} (esperado {expected})"))
        return r
    except Exception as e:
        results.append(("ERROR", f"💥 {method.upper():6s} {path:50s} -> ERRO: {e}"))
        return None

# ===== HEALTH & ROOT =====
test("get", "/health", 200)
test("get", "/", 200)
test("get", "/api/admin/health", 200)
test("get", "/api/llm/health", 200)
test("get", "/openapi.json", 200)

# ===== AUTH - PUBLIC =====
test("get", "/api/auth/plans", 200)
test("get", "/api/auth/me", 401)
test("post", "/api/auth/login", 401, json_body={"email": "fake@x.com", "password": "wrong"})

# ===== AUTH - LOGIN REAL =====
# Signup fresh user then login
requests.post(BASE + "/api/auth/signup", json={
    "email": "routetest@nexus.com",
    "password": "Teste1234",
    "full_name": "Route Tester"
}, timeout=10)
r = test("post", "/api/auth/login", 200, json_body={"email": "routetest@nexus.com", "password": "Teste1234"})
token = None
if r and r.status_code == 200:
    token = r.json().get("access_token")
    print(f"   Token obtido: {token[:30]}...")

auth = {"Authorization": f"Bearer {token}"} if token else {}

# ===== AUTH - ME =====
test("get", "/api/auth/me", 200 if token else 401, headers=auth)

# ===== CRM =====
test("get", "/api/crm/dashboard", 200 if token else 401, headers=auth)
test("get", "/api/crm/clients", 200 if token else 401, headers=auth)
test("get", "/api/crm/clients/birthdays", 200 if token else 401, headers=auth)
test("get", "/api/crm/clients/followup", 200 if token else 401, headers=auth)
test("get", "/api/crm/appointments", 200 if token else 401, headers=auth)
test("get", "/api/crm/pipeline", 200 if token else 401, headers=auth)
test("get", "/api/crm/financial-summary", 200 if token else 401, headers=auth)
test("get", "/api/crm/invoices/overdue", 200 if token else 401, headers=auth)
test("get", "/api/crm/invoices/upcoming", 200 if token else 401, headers=auth)

# ===== AGENTS =====
test("get", "/api/agents/list", 200 if token else 401, headers=auth)
test("get", "/api/agents/hub/status", 200 if token else 401, headers=auth)
test("get", "/api/agents/hub/context", 200 if token else 401, headers=auth)
test("get", "/api/agents/hub/messages", 200 if token else 401, headers=auth)

# Agent configs
for aid in ["clientes", "financeiro", "assistente"]:
    test("get", f"/api/agents/{aid}/config", 200 if token else 401, headers=auth)
    test("get", f"/api/agents/{aid}/status", 200 if token else 401, headers=auth)

# ===== CHAT/ANALYTICS =====
test("get", "/api/chat/history/clientes", 200 if token else 401, headers=auth)
test("get", "/api/analytics/dashboard", 200 if token else 401, headers=auth)
test("get", "/api/analytics/activity", 200 if token else 401, headers=auth)

# ===== NOTIFICATIONS =====
test("get", "/api/notifications/unread", 200 if token else 401, headers=auth)

# ===== ADMIN =====
test("get", "/api/admin/overview", 200 if token else 401, headers=auth)
test("get", "/api/admin/users", 200 if token else 401, headers=auth)
test("get", "/api/admin/mrr-chart", 200 if token else 401, headers=auth)

# ===== AUTOMATION =====
test("get", "/api/automation/tasks", 200 if token else 401, headers=auth)

# ===== STRIPE (checkout sem plano válido = 400/422, mas não 500) =====
r_stripe = requests.post(
    BASE + "/api/auth/checkout",
    json={"plan": "pro"},
    headers=auth,
    timeout=10,
)
stripe_ok = r_stripe.status_code != 500
icon = "✅" if stripe_ok else "❌"
results.append(("PASS" if stripe_ok else "FAIL", f"{icon} POST   /api/auth/checkout -> {r_stripe.status_code} (Stripe checkout, esperado != 500)"))
try:
    print(f"   Stripe checkout response: {r_stripe.json()}")
except:
    print(f"   Stripe checkout raw: {r_stripe.text[:200]}")

# ===== CORS =====
r2 = requests.options(
    BASE + "/health",
    headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    timeout=10,
)
cors_ok = r2.status_code in (200, 204)
icon = "✅" if cors_ok else "❌"
results.append(("PASS" if cors_ok else "FAIL", f"{icon} OPTIONS /health CORS -> {r2.status_code}"))
acao = r2.headers.get("access-control-allow-origin", "AUSENTE")
results.append(("INFO", f"   Access-Control-Allow-Origin: {acao}"))

# ===== SECURITY HEADERS =====
r3 = requests.get(BASE + "/health", timeout=10)
for h in ["X-Content-Type-Options", "X-Frame-Options", "X-XSS-Protection"]:
    val = r3.headers.get(h, "AUSENTE")
    hok = val != "AUSENTE"
    icon = "✅" if hok else "❌"
    results.append(("PASS" if hok else "FAIL", f"{icon} Header {h}: {val}"))

# ===== DATABASE CHECK via /api/crm/dashboard =====
r4 = requests.get(BASE + "/api/crm/dashboard", headers=auth, timeout=10)
if r4.status_code == 200:
    data = r4.json()
    results.append(("PASS", f"✅ DB conectado — {data.get('total_clients', '?')} clientes, {data.get('total_appointments', '?')} agendamentos"))
else:
    results.append(("FAIL", f"❌ DB — dashboard retornou {r4.status_code}"))

# ===== RELATÓRIO =====
print()
print("=" * 80)
print("RELATÓRIO COMPLETO — TODAS AS ROTAS DO NEXUS")
print("=" * 80)
for _, msg in results:
    print(msg)

total = len([r for r in results if r[0] in ("PASS", "FAIL", "ERROR")])
passed = len([r for r in results if r[0] == "PASS"])
failed = len([r for r in results if r[0] == "FAIL"])
errors = len([r for r in results if r[0] == "ERROR"])
print(f"\nTotal: {total} | ✅ Passou: {passed} | ❌ Falhou: {failed} | 💥 Erros: {errors}")
