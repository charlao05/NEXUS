"""Teste de validação das correções do limite de tentativas."""
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

# === Test 1: State has blocked_actions_info ===
print("\n=== Test 1: State fields ===")
from backend.orchestrator.state import create_initial_state, AgentState
s = create_initial_state(task_id="t1", agent_type="browser", user_id=1, goal="test")
check("blocked_actions_info exists and defaults to ''", s.get("blocked_actions_info") == "")
check("awaiting_user_input still works", s.get("awaiting_user_input") is False)

# === Test 2: check_node — mixed results handling ===
print("\n=== Test 2: check_node — mixed results ===")
from backend.orchestrator.nodes.check import check_node
from backend.orchestrator.state import TaskStatus

# Simulate state with mixed results after 3 iterations
state_mixed = create_initial_state(task_id="t2", agent_type="browser", user_id=1, goal="test")
state_mixed["iteration"] = 2  # will become 3 inside check_node
state_mixed["action_results"] = [
    {"tool": "browser_navigate", "success": True, "output": {"message": "Navigated to receita.gov.br"}},
    {"tool": "browser_click", "success": False, "error": "Element not found"},
    {"tool": "browser_screenshot", "success": True, "output": {"message": "Screenshot taken"}},
]
state_mixed["planned_actions"] = [
    {"tool": "browser_navigate"}, {"tool": "browser_click"}, {"tool": "browser_screenshot"}
]
result_mixed = check_node(state_mixed)
check(
    "Mixed results after 3 iterations → COMPLETED (not looping)",
    result_mixed.get("status") == TaskStatus.COMPLETED.value,
    f"Got status: {result_mixed.get('status')}"
)
check(
    "Mixed results response includes successful actions",
    "Navigated" in result_mixed.get("final_response", "") or "Screenshot" in result_mixed.get("final_response", ""),
    f"Got: {result_mixed.get('final_response', '')[:100]}"
)

# Mixed results after 1 iteration → should continue
state_early = create_initial_state(task_id="t3", agent_type="browser", user_id=1, goal="test")
state_early["iteration"] = 0  # will become 1
state_early["action_results"] = [
    {"tool": "browser_navigate", "success": True, "output": {"message": "ok"}},
    {"tool": "browser_click", "success": False, "error": "fail"},
]
state_early["planned_actions"] = [{"tool": "browser_navigate"}, {"tool": "browser_click"}]
result_early = check_node(state_early)
check(
    "Mixed results after 1 iteration → NOT completed (continues loop)",
    result_early.get("status") != TaskStatus.COMPLETED.value and result_early.get("status") != TaskStatus.FAILED.value,
    f"Got status: {result_early.get('status')}"
)

# === Test 3: check_node — better limit message ===
print("\n=== Test 3: check_node — limit message ===")
state_limit = create_initial_state(task_id="t4", agent_type="browser", user_id=1, goal="test", max_iterations=5)
state_limit["iteration"] = 4  # will become 5 = max_iterations
state_limit["action_results"] = [
    {"tool": "browser_navigate", "success": True, "output": {"message": "Abriu receita.gov.br"}},
    {"tool": "browser_screenshot", "success": True, "output": {"message": "Screenshot salvo"}},
]
state_limit["planned_actions"] = [{"tool": "browser_navigate"}, {"tool": "browser_screenshot"}]
result_limit = check_node(state_limit)
check(
    "Limit message includes successful steps",
    "browser_navigate" in result_limit.get("final_response", "") or "Abriu" in result_limit.get("final_response", ""),
    f"Got: {result_limit.get('final_response', '')[:150]}"
)

# Limit with NO successful results
state_empty_limit = create_initial_state(task_id="t5", agent_type="browser", user_id=1, goal="test", max_iterations=3)
state_empty_limit["iteration"] = 2  # will become 3
state_empty_limit["action_results"] = []
state_empty_limit["planned_actions"] = []
result_empty = check_node(state_empty_limit)
check(
    "Limit with no results → different message",
    "sem conseguir completar" in result_empty.get("final_response", "").lower() or "reformular" in result_empty.get("final_response", "").lower(),
    f"Got: {result_empty.get('final_response', '')[:100]}"
)

# === Test 4: policy_node — blocked_actions_info ===
print("\n=== Test 4: policy_node — blocked_actions_info ===")
from backend.orchestrator.nodes.policy import policy_node
from backend.orchestrator.state import PlannedAction, ActionRisk

state_policy = create_initial_state(task_id="t6", agent_type="browser", user_id=1, goal="test")
state_policy["planned_actions"] = [
    PlannedAction(tool="browser_type", params={"selector": "#cpf", "text": "12345"}, reason="Type CPF", risk=ActionRisk.LOW).model_dump(),
    PlannedAction(tool="browser_navigate", params={"url": "https://servicos.receita.fazenda.gov.br/cpf"}, reason="Navigate", risk=ActionRisk.LOW).model_dump(),
]
policy_result = policy_node(state_policy)
blocked_info = policy_result.get("blocked_actions_info", "")
check(
    "blocked_actions_info populated when actions are blocked",
    "browser_type" in blocked_info,
    f"Got: {blocked_info[:120]}"
)
check(
    "Navigate is still allowed",
    any(a.get("tool") == "browser_navigate" for a in policy_result.get("planned_actions", [])),
    f"Got actions: {[a.get('tool') for a in policy_result.get('planned_actions', [])]}"
)

# No blocked actions
state_policy2 = create_initial_state(task_id="t7", agent_type="browser", user_id=1, goal="test")
state_policy2["planned_actions"] = [
    PlannedAction(tool="browser_navigate", params={"url": "https://www.gov.br"}, reason="Nav", risk=ActionRisk.LOW).model_dump(),
]
policy_result2 = policy_node(state_policy2)
check(
    "blocked_actions_info empty when no blocks",
    policy_result2.get("blocked_actions_info") == "",
    f"Got: '{policy_result2.get('blocked_actions_info')}'"
)

# === Test 5: plan_node — includes blocked info in context ===
print("\n=== Test 5: plan_node — blocked info feedback ===")
from backend.orchestrator.nodes.plan import PLANNER_SYSTEM_PROMPT
check("PLANNER_SYSTEM_PROMPT has wait_for_user_login", "wait_for_user_login" in PLANNER_SYSTEM_PROMPT)

# === Test 6: agent_automation — max_iterations ===
print("\n=== Test 6: agent_automation — max_iterations ===")
import inspect
from backend.app.api.agent_automation import _execute_automation, _continue_automation
src_exec = inspect.getsource(_execute_automation)
src_cont = inspect.getsource(_continue_automation)
check("_execute_automation uses max_iterations=12", "max_iterations=12" in src_exec, f"Found: {'max_iterations=5' if 'max_iterations=5' in src_exec else 'other'}")
check("_continue_automation uses max_iterations=12", "max_iterations=12" in src_cont, f"Found: {'max_iterations=5' if 'max_iterations=5' in src_cont else 'other'}")

# Check waiting_for_user bypass fix
check(
    "_execute_automation excludes waiting_for_user from direct fallback",
    "waiting_for_user" in src_exec and "not in" in src_exec,
    "Check the browser_actions fallback condition"
)

# === Summary ===
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
if failed == 0:
    print("ALL TESTS PASSED ✓")
else:
    print("SOME TESTS FAILED ✗")
    sys.exit(1)
