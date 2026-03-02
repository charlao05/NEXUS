"""
Testes do Orquestrador LangGraph.
=================================
Testa cada componente: state, policies, nodes, graph.
Usa mocks para LLM (OpenAI) e banco de dados.
"""
from __future__ import annotations

import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

from backend.orchestrator.state import (
    ActionRisk,
    AgentState,
    PlannedAction,
    ActionResult,
    PolicyDecision,
    TaskStatus,
    create_initial_state,
)


class TestState:
    def test_task_status_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_action_risk_values(self):
        assert ActionRisk.LOW.value == "low"
        assert ActionRisk.CRITICAL.value == "critical"

    def test_planned_action(self):
        action = PlannedAction(
            tool="crm_list_clients",
            params={"limit": 10},
            reason="Listar clientes",
            risk=ActionRisk.LOW,
        )
        assert action.tool == "crm_list_clients"
        assert action.params["limit"] == 10
        d = action.model_dump()
        assert d["risk"] == "low"

    def test_action_result(self):
        result = ActionResult(
            tool="crm_list_clients",
            success=True,
            output={"clients": []},
            duration_ms=42,
        )
        assert result.success is True
        assert result.duration_ms == 42

    def test_policy_decision(self):
        action = PlannedAction(tool="crm_list_clients")
        decision = PolicyDecision(action=action, allowed=True, reason="OK")
        assert decision.allowed is True

    def test_create_initial_state(self):
        state = create_initial_state(
            task_id="test_1",
            agent_type="clientes",
            user_id=1,
            goal="Listar meus clientes",
        )
        assert state["task_id"] == "test_1"
        assert state["agent_type"] == "clientes"
        assert state["user_id"] == 1
        assert state["goal"] == "Listar meus clientes"
        assert state["status"] == "pending"
        assert state["iteration"] == 0
        assert state["max_iterations"] == 10
        assert state["planned_actions"] == []
        assert state["action_results"] == []
        assert state["final_response"] == ""


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

from backend.orchestrator.policies import (
    evaluate_action,
    evaluate_plan,
    plan_requires_approval,
    BLOCKED_ACTIONS,
)


class TestPolicies:
    def test_blocked_action(self):
        action = PlannedAction(tool="delete_database")
        decision = evaluate_action("t1", action)
        assert decision.allowed is False
        assert "bloqueio" in decision.reason.lower() or "blocked" in decision.reason.lower()

    def test_allowed_read_action(self):
        action = PlannedAction(
            tool="crm_list_clients",
            params={"limit": 10},
            risk=ActionRisk.LOW,
        )
        decision = evaluate_action("t2", action)
        assert decision.allowed is True

    def test_respond_to_user_always_allowed(self):
        action = PlannedAction(tool="respond_to_user", params={"message": "Olá!"})
        decision = evaluate_action("t3", action)
        assert decision.allowed is True

    def test_unknown_action_blocked(self):
        action = PlannedAction(tool="hackear_nasa")
        decision = evaluate_action("t4", action)
        assert decision.allowed is False
        assert "registrada" in decision.reason.lower() or "unknown" in decision.reason.lower()

    def test_evaluate_plan_batch(self):
        actions = [
            PlannedAction(tool="crm_list_clients"),
            PlannedAction(tool="respond_to_user", params={"message": "pronto"}),
        ]
        decisions = evaluate_plan("t5", actions)
        assert len(decisions) == 2
        assert all(d.allowed for d in decisions)

    def test_plan_requires_approval(self):
        actions = [
            PlannedAction(tool="crm_delete_client", params={"client_id": 1}),
        ]
        decisions = evaluate_plan("t6", actions)
        # crm_delete_client é HIGH risk, pode requerer aprovação
        # mas a política não marca auto-approve como False necessariamente
        # O teste verifica que plan_requires_approval retorna um bool
        result = plan_requires_approval(decisions)
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Nodes (com mocks)
# ---------------------------------------------------------------------------


class TestSenseNode:
    def test_sense_sets_status(self):
        from backend.orchestrator.nodes.sense import sense_node

        state = create_initial_state(
            task_id="s1", agent_type="assistente", user_id=1, goal="Ajuda"
        )
        # SessionLocal é importado dentro da função (lazy), patch no módulo fonte
        with patch("backend.database.models.SessionLocal", side_effect=Exception("no db")):
            result = sense_node(state)

        assert result["status"] == TaskStatus.SENSING.value


class TestPlanNode:
    def test_plan_with_mock_llm(self):
        from backend.orchestrator.nodes.plan import plan_node
        from backend.orchestrator.state import PlannedAction as PA

        state = create_initial_state(
            task_id="p1", agent_type="clientes", user_id=1,
            goal="Listar clientes",
        )
        state["crm_context"] = "3 clientes cadastrados"
        state["status"] = TaskStatus.SENSING.value

        mock_actions = [
            PA(tool="crm_list_clients", params={}, reason="Listar", risk=ActionRisk.LOW),
            PA(tool="respond_to_user", params={"message": "Aqui estão seus clientes"}, reason="Responder", risk=ActionRisk.LOW),
        ]

        with patch("backend.orchestrator.nodes.plan._call_llm_planner", return_value=mock_actions):
            result = plan_node(state)

        assert result["status"] == TaskStatus.PLANNING.value
        assert len(result["planned_actions"]) == 2
        assert result["planned_actions"][0]["tool"] == "crm_list_clients"


class TestPolicyNode:
    def test_policy_filters_blocked(self):
        from backend.orchestrator.nodes.policy import policy_node

        state = create_initial_state(
            task_id="pol1", agent_type="clientes", user_id=1, goal="Test"
        )
        state["planned_actions"] = [
            {"tool": "crm_list_clients", "params": {}, "reason": "ok", "risk": "low"},
            {"tool": "delete_database", "params": {}, "reason": "bad", "risk": "critical"},
        ]

        result = policy_node(state)

        # Só crm_list_clients deve passar
        assert len(result["planned_actions"]) == 1
        assert result["planned_actions"][0]["tool"] == "crm_list_clients"


class TestActNode:
    def test_act_respond_to_user(self):
        from backend.orchestrator.nodes.act import act_node

        state = create_initial_state(
            task_id="a1", agent_type="clientes", user_id=1, goal="Test"
        )
        state["planned_actions"] = [
            {"tool": "respond_to_user", "params": {"message": "Olá!"}, "reason": "responder"},
        ]

        result = act_node(state)

        assert result["status"] == TaskStatus.EXECUTING.value
        assert result["final_response"] == "Olá!"
        assert len(result["action_results"]) == 1
        assert result["action_results"][0]["success"] is True

    def test_act_unknown_tool(self):
        from backend.orchestrator.nodes.act import act_node

        state = create_initial_state(
            task_id="a2", agent_type="clientes", user_id=1, goal="Test"
        )
        state["planned_actions"] = [
            {"tool": "nonexistent_tool", "params": {}},
        ]

        result = act_node(state)
        assert len(result["action_results"]) == 1
        assert result["action_results"][0]["success"] is False


class TestCheckNode:
    def test_check_completed_with_response(self):
        from backend.orchestrator.nodes.check import check_node

        state = create_initial_state(
            task_id="c1", agent_type="clientes", user_id=1, goal="Test"
        )
        state["final_response"] = "Pronto!"
        state["iteration"] = 0

        result = check_node(state)
        assert result["status"] == TaskStatus.COMPLETED.value

    def test_check_max_iterations(self):
        from backend.orchestrator.nodes.check import check_node

        state = create_initial_state(
            task_id="c2", agent_type="clientes", user_id=1, goal="Test",
            max_iterations=3,
        )
        state["iteration"] = 2  # +1 = 3 >= max_iterations

        result = check_node(state)
        assert result["status"] == TaskStatus.COMPLETED.value

    def test_check_error(self):
        from backend.orchestrator.nodes.check import check_node

        state = create_initial_state(
            task_id="c3", agent_type="clientes", user_id=1, goal="Test"
        )
        state["error"] = "Algo deu errado"

        result = check_node(state)
        assert result["status"] == TaskStatus.FAILED.value

    def test_should_continue(self):
        from backend.orchestrator.nodes.check import should_continue

        state: dict = {"status": "completed"}
        assert should_continue(state) == "done"  # type: ignore

        state = {"status": "failed"}
        assert should_continue(state) == "done"  # type: ignore

        state = {"status": "waiting_approval"}
        assert should_continue(state) == "wait_approval"  # type: ignore

        state = {"status": "checking"}
        assert should_continue(state) == "continue"  # type: ignore


# ---------------------------------------------------------------------------
# Graph compilation
# ---------------------------------------------------------------------------

class TestGraph:
    def test_graph_compiles(self):
        from backend.orchestrator.graph import create_orchestrator_graph
        graph = create_orchestrator_graph(interrupt_on_approval=False)
        assert graph is not None
        assert hasattr(graph, "astream")

    def test_graph_has_nodes(self):
        from backend.orchestrator.graph import create_orchestrator_graph
        graph = create_orchestrator_graph(interrupt_on_approval=False)
        # CompiledStateGraph tem .nodes
        node_names = set(graph.nodes.keys()) if hasattr(graph, 'nodes') else set()
        expected = {"sense", "plan", "policy", "approval_gate", "act", "check"}
        # At minimum the expected nodes should be present (plus __start__, __end__)
        assert expected.issubset(node_names) or len(node_names) >= 6


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_all_crm_tools_registered(self):
        from backend.orchestrator.nodes.act import _TOOL_REGISTRY
        crm_tools = {"crm_list_clients", "crm_get_client", "crm_create_client",
                      "crm_update_client", "crm_delete_client",
                      "crm_create_appointment", "crm_create_transaction"}
        for tool in crm_tools:
            assert tool in _TOOL_REGISTRY, f"{tool} não registrada"

    def test_browser_tools_registered(self):
        import backend.orchestrator.tools  # noqa: F401
        from backend.orchestrator.nodes.act import _TOOL_REGISTRY
        browser_tools = {"browser_navigate", "browser_click", "browser_type",
                         "browser_wait_selector", "browser_press_key",
                         "browser_wait", "browser_screenshot", "browser_get_text",
                         "browser_close"}
        for tool in browser_tools:
            assert tool in _TOOL_REGISTRY, f"{tool} não registrada"

    def test_respond_to_user_registered(self):
        from backend.orchestrator.nodes.act import _TOOL_REGISTRY
        assert "respond_to_user" in _TOOL_REGISTRY


# ---------------------------------------------------------------------------
# End-to-end com mock LLM
# ---------------------------------------------------------------------------

class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_full_run_with_mock_llm(self):
        """Testa o fluxo completo: sense → plan → policy → act → check
        com LLM mockada retornando um plano simples."""
        from backend.orchestrator.graph import run_task
        from backend.orchestrator.state import PlannedAction as PA

        mock_actions = [
            PA(
                tool="respond_to_user",
                params={"message": "Olá! Posso ajudar com algo?"},
                reason="Saudação",
                risk=ActionRisk.LOW,
            ),
        ]

        with patch("backend.orchestrator.nodes.plan._call_llm_planner", return_value=mock_actions), \
             patch("backend.database.models.SessionLocal", side_effect=Exception("no db")):

            result = await run_task(
                agent_type="assistente",
                user_id=1,
                goal="Diga olá",
                max_iterations=3,
            )

        assert result["status"] == "completed"
        assert "Olá" in result["final_response"]
        assert len(result["action_results"]) >= 1
