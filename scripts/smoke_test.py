"""Smoke Test E2E — Validação completa dos fluxos críticos do NEXUS"""
import requests
import sys

BASE = "http://localhost:8000"
S = requests.Session()
results = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append((status, label, detail))
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {label}{suffix}")


# 1. Health
r = S.get(f"{BASE}/health", timeout=5)
check("Health endpoint", r.status_code == 200, f"db={r.json().get('database')}")

# 2. Login
r = S.post(f"{BASE}/api/auth/login", json={
    "email": "charles.rsilva05@gmail.com",
    "password": "Admin@123"
}, timeout=10)
login_data = r.json()
check("Login", r.status_code == 200 and "access_token" in login_data, f"plan={login_data.get('plan')}")
tok = login_data.get("access_token", "")
h = {"Authorization": f"Bearer {tok}"}

# 3. /me
r = S.get(f"{BASE}/api/auth/me", headers=h, timeout=5)
me = r.json()
check("/me retorna dados corretos", r.status_code == 200 and me.get("email") == "charles.rsilva05@gmail.com",
      f"plan={me.get('plan')}")

# 4. Switch plan free -> pro -> enterprise -> free
for plan in ["pro", "enterprise", "free"]:
    r = S.post(f"{BASE}/api/auth/admin/switch-plan", headers=h, json={"plan": plan}, timeout=5)
    resp = r.json()
    # Atualizar token se novo foi retornado
    new_tok = resp.get("access_token")
    if new_tok:
        tok = new_tok
        h = {"Authorization": f"Bearer {tok}"}
    check(f"Switch para {plan}", r.status_code == 200 and resp.get("plan") == plan)

# 5. CRM dashboard (precisa auth)
r = S.get(f"{BASE}/api/crm/dashboard", headers=h, timeout=5)
check("CRM dashboard", r.status_code == 200)

# 6. Agents list
r = S.get(f"{BASE}/api/agents/list", headers=h, timeout=5)
agents = r.json().get("agents", [])
check("Agents list", r.status_code == 200 and len(agents) == 5, f"{len(agents)} agentes")

# 7. Hub status (agora requer auth)
r_noauth = S.get(f"{BASE}/api/agents/hub/status", timeout=5)
r_auth = S.get(f"{BASE}/api/agents/hub/status", headers=h, timeout=5)
check("Hub requer auth (sem=401, com=200)",
      r_noauth.status_code == 401 and r_auth.status_code == 200,
      f"sem={r_noauth.status_code} com={r_auth.status_code}")

# 8. Agent execute (chat com GPT-4.1)
r = S.post(f"{BASE}/api/agents/assistente/execute", headers=h,
           json={"action": "chat", "parameters": {"message": "Qual é a capital do Brasil?"}},
           timeout=30)
msg = r.json().get("message", "")
check("Agent execute (chat GPT-4.1)", r.status_code == 200 and len(msg) > 5, msg[:80])

# 9. Notifications
r = S.get(f"{BASE}/api/notifications/unread", headers=h, timeout=5)
check("Notifications unread", r.status_code == 200)

# 10. Admin overview
r = S.get(f"{BASE}/api/admin/overview", headers=h, timeout=5)
check("Admin overview", r.status_code == 200 and "users" in r.json())

# 11. Analytics dashboard
r = S.get(f"{BASE}/api/analytics/dashboard", headers=h, timeout=5)
check("Analytics dashboard", r.status_code == 200)

# 12. Orchestrator health
r = S.get(f"{BASE}/api/orchestrator/health", headers=h, timeout=5)
check("Orchestrator health", r.status_code == 200)

# 13. Chat history save + retrieve
r = S.post(f"{BASE}/api/chat/save", headers=h, json={
    "agent_id": "assistente", "role": "user", "content": "smoke test"
}, timeout=5)
check("Chat save", r.status_code == 200)

r = S.get(f"{BASE}/api/chat/history/assistente", headers=h, timeout=5)
check("Chat history", r.status_code == 200)

# 14. Agent configs (todos os 5)
for agent in ["agenda", "clientes", "contabilidade", "cobranca", "assistente"]:
    r = S.get(f"{BASE}/api/agents/{agent}/config", headers=h, timeout=5)
    check(f"Config {agent}", r.status_code == 200)

# 15. Rotas removidas retornam 404/405
removed = [
    ("GET", "/api/automation/tasks"),
    ("POST", "/api/automation/tasks/plan"),
    ("GET", "/api/llm/health"),
    ("POST", "/api/llm/chat"),
]
for method, path in removed:
    if method == "GET":
        r = S.get(f"{BASE}{path}", headers=h, timeout=5)
    else:
        r = S.post(f"{BASE}{path}", headers=h, json={}, timeout=5)
    check(f"Removida: {method} {path}", r.status_code in (404, 405), f"got {r.status_code}")

# 16. Checkout Stripe
r = S.post(f"{BASE}/api/auth/checkout", headers=h, json={
    "plan": "pro", "email": "charles.rsilva05@gmail.com"
}, timeout=10)
check("Stripe checkout", r.status_code == 200 and "checkout_url" in r.json())

# ===== RESUMO =====
print(f"\n{'=' * 70}")
passed = sum(1 for s, _, _ in results if s == "PASS")
failed = sum(1 for s, _, _ in results if s == "FAIL")
print(f"SMOKE TEST COMPLETO: {passed} PASS / {failed} FAIL / {len(results)} total")

if failed > 0:
    print(f"\nFALHAS:")
    for s, label, detail in results:
        if s == "FAIL":
            print(f"  [FAIL] {label} — {detail}")
    sys.exit(1)
else:
    print("Todos os testes passaram.")
    sys.exit(0)
