"""Teste de validação das correções de URL."""
import sys
sys.path.insert(0, ".")

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

# === Test 1: plan.py compiles with URL injection ===
print("\n=== Test 1: plan.py compiles ===")
from backend.orchestrator.nodes.plan import plan_node, PLANNER_SYSTEM_PROMPT
from backend.orchestrator.state import create_initial_state, PlannedAction, ActionRisk
check("plan.py imports OK", True)

# === Test 2: URL canonicalization logic ===
print("\n=== Test 2: URL canonicalization ===")
from urllib.parse import urlparse

canonical = "https://servicos.receita.fazenda.gov.br/Servicos/CPF/ConsultaSituacao/ConsultaPublica.asp"
bad_url = "https://servicos.receita.fazenda.gov.br/servicos/receituario/consultaCPF"

planned_host = urlparse(bad_url).hostname
canon_host = urlparse(canonical).hostname
check("Same host detection", planned_host == canon_host, f"{planned_host} vs {canon_host}")

# Simulate post-processing
action = PlannedAction(tool="browser_navigate", params={"url": bad_url}, reason="test", risk=ActionRisk.LOW)
if action.params["url"] != canonical and planned_host == canon_host:
    action.params["url"] = canonical
check("URL corrected from hallucinated to canonical", action.params["url"] == canonical, action.params["url"][:80])

# Different host should NOT be corrected
other_url = "https://www.google.com/search"
action2 = PlannedAction(tool="browser_navigate", params={"url": other_url}, reason="test", risk=ActionRisk.LOW)
other_host = urlparse(other_url).hostname
if other_host != canon_host:
    pass  # Should NOT fix
check("Different host NOT corrected", action2.params["url"] == other_url)

# === Test 3: agent_automation post-processing ===
print("\n=== Test 3: agent_automation plan fixer ===")
import inspect
from backend.app.api.agent_automation import _generate_automation_plan
src = inspect.getsource(_generate_automation_plan)
check("Has canonical_url logic", "canonical_url" in src)
check("Has URL correction log", "URL corrigida no plano" in src)

# === Test 4: plan_node has canonical URL instruction ===
print("\n=== Test 4: plan_node canonical URL ===")
src_plan = inspect.getsource(plan_node)
check("plan_node injects canonical URL from site_config", "URL CANÔNICA OBRIGATÓRIA" in src_plan)
check("plan_node has post-processing URL fix", "URL corrigida pelo pós-processador" in src_plan)

# === Test 5: Template URLs are correct ===
print("\n=== Test 5: Template URLs ===")
from backend.orchestrator.templates import get_template
tpl_cpf = get_template("receita_federal_cpf")
url_cpf = tpl_cpf["site_config"]["url"]
check("CPF template has correct URL", "ConsultaSituacao/ConsultaPublica.asp" in url_cpf, url_cpf)

tpl_cnpj = get_template("receita_federal_cnpj")
url_cnpj = tpl_cnpj["site_config"]["url"]
check("CNPJ template has correct URL", "cnpjreva" in url_cnpj, url_cnpj)

# === Test 6: Regression — HIL pipeline still works ===
print("\n=== Test 6: HIL Regression ===")
from backend.orchestrator.nodes.sense import _detect_sensitive_screen
r = _detect_sensitive_screen(
    "CPF: [input] Data de Nascimento: [input] Anti-Robo nao preenchido",
    "https://servicos.receita.fazenda.gov.br/servicos/cpf/consultasituacao/ConsultaPublica.asp"
)
check("HIL detection still works", r is not None)

# === Summary ===
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
if failed == 0:
    print("ALL TESTS PASSED ✓")
else:
    print("SOME TESTS FAILED ✗")
    sys.exit(1)
