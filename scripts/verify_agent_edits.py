"""Verify agent_chat and agent_hub import correctly after edits."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

try:
    from app.api.agent_chat import get_llm_response, ACTION_PROMPTS, _get_direct_empty_response, _EMPTY_DATA_RESPONSES
    print(f"OK: agent_chat imported — {len(ACTION_PROMPTS)} actions, {sum(len(v) for v in _EMPTY_DATA_RESPONSES.values())} direct responses")
except Exception as e:
    print(f"FAIL: agent_chat — {e}")
    import traceback; traceback.print_exc()

try:
    # Test direct empty response for financeiro
    r = _get_direct_empty_response("contabilidade", "Como tá meu mês? Quanto entrou, quanto saiu e quanto sobrou.")
    print(f"OK: Direct empty response works — got {len(r)} chars")
except Exception as e:
    print(f"FAIL: direct response — {e}")

print("\nDone.")
