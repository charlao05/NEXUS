"""
helpers/openai_client.py — Wrapper de compatibilidade.
Toda a lógica foi consolidada em app/core/llm.py.
"""
# Re-exporta para não quebrar imports existentes
from app.core.llm import OpenAIClient, get_openai_client  # noqa: F401

__all__ = ["OpenAIClient", "get_openai_client"]
