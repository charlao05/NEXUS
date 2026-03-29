"""Test quick action response with empty data — should NOT hallucinate."""
import requests

# Login first
login_r = requests.post(
    "http://127.0.0.1:8000/api/auth/login",
    json={"email": "appnexxus.app@gmail.com", "password": "Admin@123"},
    timeout=10,
)
token = login_r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
hallucination_markers = ["Jose Santos", "Maria Silva", "joao", "cliente x"]

tests = [
    ("contabilidade", "monthly_summary", "Resumo do mês"),
    ("contabilidade", "list_overdue", "Quem tá devendo"),
    ("clientes", "list_clients", "Meus clientes"),
    ("agenda", "list_today", "Agenda de hoje"),
]

for agent, action, label in tests:
    r = requests.post(
        f"http://127.0.0.1:8000/api/agents/{agent}/execute",
        json={"action": action, "parameters": {}},
        headers=headers,
        timeout=30,
    )
    msg = r.json().get("message", "NO MESSAGE")[:150]
    found = [m for m in hallucination_markers if m.lower() in msg.lower()]
    status = "ALUCINOU" if found else "OK"
    print(f"[{status}] {label} ({r.status_code}): {msg[:80]}...")
