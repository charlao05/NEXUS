"""
Mapeamento centralizado de aliases de agentes.
Usado por limit_service, agent_hub e agent_chat.
"""

AGENT_ID_ALIASES: dict[str, str] = {
    "financeiro": "contabilidade",
    "documentos": "contabilidade",
}


def resolve_agent_id(agent_id: str) -> str:
    """Resolve um alias de agente para o ID canônico."""
    return AGENT_ID_ALIASES.get(agent_id, agent_id)
