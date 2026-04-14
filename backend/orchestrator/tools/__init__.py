"""Tools do orquestrador LangGraph.

Importar este pacote registra automaticamente todas as tools
no _TOOL_REGISTRY do act_node via decorator @register_tool.
"""
# Browser tools (importar para registrar via @register_tool)
import orchestrator.tools.browser  # noqa: F401
