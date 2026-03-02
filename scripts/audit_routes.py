"""Auditoria completa de todas as rotas do NEXUS Backend"""
import requests
import json
import sys
import io

BASE = "http://localhost:8000"

# Login
try:
    r = requests.post(f"{BASE}/api/auth/login", json={"email":"charles.rsilva05@gmail.com","password":"Admin@123"}, timeout=10)
    login_data = r.json()
    tok = login_data.get("access_token","")
    refresh_tok = login_data.get("refresh_token","")
    if not tok:
        print("ERRO: Login falhou")
        sys.exit(1)
except Exception as e:
    print(f"ERRO: Backend não acessível: {e}")
    sys.exit(1)

h = {"Authorization": f"Bearer {tok}"}
results = []

def test(method, path, body=None, files=None, data=None, skip=False, skip_reason=""):
    if skip:
        results.append(("SKIP", 0, method, path, skip_reason))
        return
    url = f"{BASE}{path}"
    try:
        if method == "GET":
            r = requests.get(url, headers=h, timeout=15)
        elif method == "POST":
            if files:
                r = requests.post(url, headers=h, files=files, data=data or {}, timeout=15)
            else:
                r = requests.post(url, headers=h, json=body, timeout=15)
        elif method == "PUT":
            r = requests.put(url, headers=h, json=body, timeout=15)
        elif method == "DELETE":
            r = requests.delete(url, headers=h, timeout=15)
        else:
            return
        icon = "OK" if r.status_code < 400 else "FAIL"
        detail = ""
        if r.status_code >= 400:
            try:
                detail = str(r.json().get("detail",""))[:80]
            except:
                detail = r.text[:80]
        results.append((icon, r.status_code, method, path, detail))
    except Exception as e:
        results.append(("ERR", 0, method, path, str(e)[:80]))

# ==================== TESTES ====================

# CORE
test("GET", "/health")
test("GET", "/")

# AUTH (prefix: /api/auth)
test("GET", "/api/auth/me")
test("GET", "/api/auth/plans")
test("POST", "/api/auth/admin/switch-plan", {"plan":"free"})
test("GET", "/api/auth/export-my-data")
test("POST", "/api/auth/refresh", {"refresh_token": refresh_tok})
test("PUT", "/api/auth/preferences", {"communication_preference":"email"})
test("POST", "/api/auth/checkout", {"plan":"pro","email":"test@test.com"})
test("POST", "/api/auth/verify-payment", skip=True, skip_reason="Depende de sess\u00e3o Stripe real")
test("GET", "/api/auth/google")
test("GET", "/api/auth/google/start")
test("GET", "/api/auth/facebook/start")
test("POST", "/api/auth/forgot-password", {"email":"noreply@test.com"})
test("POST", "/api/auth/reset-password", skip=True, skip_reason="Depende de token de reset real")

# AGENTS (prefix: /api/agents)
test("GET", "/api/agents/list")
test("GET", "/api/agents/hub/status")
test("GET", "/api/agents/hub/messages")
test("GET", "/api/agents/hub/context")
test("POST", "/api/agents/hub/message", {"from_agent":"assistente","to_agent":"clientes","event_type":"cliente_criado","payload":{"nome":"Teste"},"priority":5})
test("GET", "/api/agents/agenda/config")
test("GET", "/api/agents/clientes/config")
test("GET", "/api/agents/contabilidade/config")
test("GET", "/api/agents/cobranca/config")
test("GET", "/api/agents/assistente/config")
test("GET", "/api/agents/agenda/status")
test("GET", "/api/agents/clientes/status")
test("GET", "/api/agents/contabilidade/status")
test("GET", "/api/agents/cobranca/status")
test("GET", "/api/agents/assistente/status")
test("POST", "/api/agents/assistente/execute", {"action":"chat","parameters":{"message":"oi"}})

# AGENT AUTOMATION (prefix: /api/agents/automation)
test("POST", "/api/agents/automation/start", {"goal":"acessar receita federal","agent_id":"assistente","message":"acessar receita federal"})

# AGENT MEDIA (prefix: /api/agents — file upload via multipart)
test("POST", "/api/agents/audio/transcribe", skip=True, skip_reason="Depende de API OpenAI Whisper (serviço externo, timeout)")
_dummy_txt = io.BytesIO(b"Teste de upload NEXUS")
test("POST", "/api/agents/upload", files={"files": ("test.txt", _dummy_txt, "text/plain")}, data={"agent": "assistente", "message": "analisar arquivo"})

# CRM (prefix: /api/crm)
test("GET", "/api/crm/dashboard")
test("GET", "/api/crm/clients")
test("GET", "/api/crm/clients/followup")
test("GET", "/api/crm/clients/birthdays")
test("GET", "/api/crm/pipeline")
test("GET", "/api/crm/appointments")
test("GET", "/api/crm/financial-summary")
test("GET", "/api/crm/invoices/overdue")
test("GET", "/api/crm/invoices/upcoming")

# CHAT HISTORY (prefix: /api/chat)
test("GET", "/api/chat/history/assistente")
test("GET", "/api/chat/history/agenda")
test("GET", "/api/chat/history/clientes")
test("POST", "/api/chat/save", {"agent_id":"assistente","role":"user","content":"Mensagem de teste auditoria"})

# ANALYTICS (prefix: /api/analytics)
test("GET", "/api/analytics/dashboard")

# NOTIFICATIONS (prefix: /api/notifications)
test("GET", "/api/notifications/unread")
test("POST", "/api/notifications/read", {})

# ADMIN (prefix: /api/admin)
test("GET", "/api/admin/overview")
test("GET", "/api/admin/users")
test("GET", "/api/admin/users/57")
test("GET", "/api/admin/mrr-chart")
test("GET", "/api/admin/health")

# ORCHESTRATOR (prefix: /api/orchestrator)
test("GET", "/api/orchestrator/health")

# ==================== RELATÓRIO ====================
import pathlib as _pathlib
_lines = []
def _p(s=""):
    _lines.append(s)
    print(s)

_p()
_p(f"{'STATUS':6} {'CODE':>4} {'METHOD':6} {'ENDPOINT':55} DETAIL")
_p("=" * 130)
ok = fail = skip = 0
for icon, code, method, path, detail in results:
    if icon == "OK":
        ok += 1
    elif icon == "SKIP":
        skip += 1
    else:
        fail += 1
    _p(f"[{icon:4}] {code:>4} {method:6} {path:55} {detail}")

_p(f"\n{'='*130}")
_p(f"TOTAL: {ok} OK  |  {fail} FAIL  |  {skip} SKIP  |  {ok+fail+skip} endpoints testados")
_p()

if fail > 0:
    _p("FALHAS DETALHADAS:")
    _p("-" * 80)
    for icon, code, method, path, detail in results:
        if icon != "OK":
            _p(f"  {code:>4} {method} {path}")
            _p(f"       -> {detail}")
            _p()

_out = _pathlib.Path(__file__).resolve().parent.parent / "logs" / "audit_gate3.txt"
_out.write_text("\n".join(_lines), encoding="utf-8")
print(f"\n>>> Relatório salvo em {_out}")
