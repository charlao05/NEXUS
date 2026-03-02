"""Test quick action response with empty data — should NOT hallucinate."""
import requests

# Login first
login_r = requests.post(
    "http://127.0.0.1:8000/api/auth/login",
    json={"email": "charles.rsilva05@gmail.com", "password": "Admin@123"},
    timeout=10,
)
token = login_r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Test: "Resumo do mês" (financeiro → contabilidade)
print("=" * 60)
print("TEST 1: Resumo do mês (contabilidade)")
print("=" * 60)
r = requests.post(
    "http://127.0.0.1:8000/api/agents/contabilidade/execute",
    json={"action": "monthly_summary", "parameters": {}},
    headers=headers,
    timeout=30,
)
print(f"STATUS: {r.status_code}")
data = r.json()
msg = data.get("message", "NO MESSAGE")
print(f"RESPONSE:\n{msg}")

# Check for hallucination markers
hallucination_markers = ["Jose Santos", "Maria", "R$ 500", "R$ 1.000", "R$ 2.000", "cliente fulano"]
found = [m for m in hallucination_markers if m.lower() in msg.lower()]
if found:
    print(f"\n⚠️ POSSÍVEL ALUCINAÇÃO detectada: {found}")
else:
    print(f"\n✅ Sem alucinação detectada!")

# Test: "Quem tá devendo" (cobrança → contabilidade)
print("\n" + "=" * 60)
print("TEST 2: Quem tá devendo (cobranca)")
print("=" * 60)
r2 = requests.post(
    "http://127.0.0.1:8000/api/agents/contabilidade/execute",
    json={"action": "list_overdue", "parameters": {}},
    headers=headers,
    timeout=30,
)
print(f"STATUS: {r2.status_code}")
msg2 = r2.json().get("message", "NO MESSAGE")
print(f"RESPONSE:\n{msg2}")

found2 = [m for m in hallucination_markers if m.lower() in msg2.lower()]
if found2:
    print(f"\n⚠️ POSSÍVEL ALUCINAÇÃO detectada: {found2}")
else:
    print(f"\n✅ Sem alucinação detectada!")

# Test: "Meus clientes" (clientes)
print("\n" + "=" * 60)
print("TEST 3: Meus clientes")
print("=" * 60)
r3 = requests.post(
    "http://127.0.0.1:8000/api/agents/clientes/execute",
    json={"action": "list_clients", "parameters": {}},
    headers=headers,
    timeout=30,
)
print(f"STATUS: {r3.status_code}")
msg3 = r3.json().get("message", "NO MESSAGE")
print(f"RESPONSE:\n{msg3}")

found3 = [m for m in hallucination_markers if m.lower() in msg3.lower()]
if found3:
    print(f"\n⚠️ POSSÍVEL ALUCINAÇÃO detectada: {found3}")
else:
    print(f"\n✅ Sem alucinação detectada!")
