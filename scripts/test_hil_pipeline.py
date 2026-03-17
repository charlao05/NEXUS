"""Test completo do pipeline Human-in-the-Loop."""
import sys
sys.path.insert(0, ".")

from backend.orchestrator.state import create_initial_state, TaskStatus, PlannedAction, ActionRisk
from backend.orchestrator.nodes.sense import _detect_sensitive_screen
from backend.orchestrator.nodes.plan import plan_node
from backend.orchestrator.nodes.act import _wait_for_user_login
from backend.orchestrator.policies import evaluate_action, ACTION_POLICIES

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} — {detail}")
        failed += 1

# ── Test 1: Sensitive Screen Detection ──────────────────────
print("\n=== Test 1: Sensitive Screen Detection ===")
obs = (
    "URL: https://servicos.receita.fazenda.gov.br/cpf/ConsultaPublica.asp\n"
    "CPF: [input] Data de Nascimento: [input] Anti-Robo nao foi preenchido"
)
url = "https://servicos.receita.fazenda.gov.br/servicos/cpf/consultasituacao/ConsultaPublica.asp"
r = _detect_sensitive_screen(obs, url)
check("Detects Receita Federal CPF page", r is not None)
if r:
    check("Reason mentions sensitive", "sensív" in r["reason"].lower() or "login" in r["reason"].lower() or "cpf" in r["reason"].lower(), r["reason"][:80])
    check("Hint is non-empty", len(r["hint"]) > 10, r["hint"][:60])

# Non-sensitive page should NOT trigger
r2 = _detect_sensitive_screen("Some random page with buttons and links", "https://example.com")
check("Does NOT detect non-sensitive page", r2 is None, f"Got: {r2}")

# ── Test 2: Plan Node Short-Circuit ────────────────────────
print("\n=== Test 2: Plan Node Short-Circuit (awaiting_user_input) ===")
state = create_initial_state(task_id="t1", agent_type="browser", user_id=1, goal="Consultar CPF")
state["awaiting_user_input"] = True
state["resume_hint"] = "Digite seu CPF e data de nascimento"
state["awaiting_user_reason"] = "Campos sensíveis detectados"
result = plan_node(state)
actions = result.get("planned_actions", [])
check("Returns exactly 1 action", len(actions) == 1, f"Got {len(actions)}")
if actions:
    check("Tool is wait_for_user_login", actions[0].get("tool") == "wait_for_user_login")

# ── Test 3: wait_for_user_login Tool ───────────────────────
print("\n=== Test 3: wait_for_user_login Tool ===")
output = _wait_for_user_login({"message_to_user": "Test message"}, 1)
check("Returns waiting_for_user=True", output.get("waiting_for_user") is True)
check("Returns response string", isinstance(output.get("response"), str) and len(output["response"]) > 0)

# ── Test 4: Policy allows wait_for_user_login ──────────────
print("\n=== Test 4: Policy allows wait_for_user_login ===")
action = PlannedAction(tool="wait_for_user_login", params={}, reason="test", risk=ActionRisk.LOW)
decision = evaluate_action("t1", action)
check("wait_for_user_login is allowed", decision.allowed)

# ── Test 5: Policy blocks browser_type on CPF field ────────
print("\n=== Test 5: Policy blocks browser_type on sensitive fields ===")
# Test with selector containing CPF
action_cpf = PlannedAction(
    tool="browser_type",
    params={"selector": "#cpf", "text": "12345678900"},
    reason="test",
    risk=ActionRisk.LOW,
)
dec_cpf = evaluate_action("t2", action_cpf)
check("Blocks browser_type on #cpf selector", not dec_cpf.allowed, f"allowed={dec_cpf.allowed}, reason={dec_cpf.reason[:80]}")

# Test with selector containing senha
action_pwd = PlannedAction(
    tool="browser_type",
    params={"selector": "input[name='senha']", "text": "pass"},
    reason="test",
    risk=ActionRisk.LOW,
)
dec_pwd = evaluate_action("t3", action_pwd)
check("Blocks browser_type on senha field", not dec_pwd.allowed, f"allowed={dec_pwd.allowed}")

# Test with non-sensitive field — should be allowed
action_ok = PlannedAction(
    tool="browser_type",
    params={"selector": "#search", "text": "hello"},
    reason="test",
    risk=ActionRisk.LOW,
)
dec_ok = evaluate_action("t4", action_ok)
check("Allows browser_type on #search (non-sensitive)", dec_ok.allowed, f"allowed={dec_ok.allowed}, reason={dec_ok.reason[:80]}")

# ── Test 6: State fields initialization ────────────────────
print("\n=== Test 6: State fields initialization ===")
s = create_initial_state(task_id="t5", agent_type="browser", user_id=1, goal="test")
check("awaiting_user_input defaults to False", s["awaiting_user_input"] is False)
check("awaiting_user_reason defaults to empty", s["awaiting_user_reason"] == "")
check("resume_hint defaults to empty", s["resume_hint"] == "")
check("sensitive_screen_snapshot defaults to empty", s["sensitive_screen_snapshot"] == "")

# ── Summary ────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
if failed == 0:
    print("ALL TESTS PASSED ✓")
else:
    print(f"SOME TESTS FAILED ✗")
    sys.exit(1)
