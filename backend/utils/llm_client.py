"""
utils/llm_client.py — Wrapper de compatibilidade.
Toda a lógica foi consolidada em app/core/llm.py.
"""
# Re-exporta para não quebrar imports existentes
from app.core.llm import (  # noqa: F401
    gerar_plano_acao,
    gerar_texto_simples,
    _extrair_json,
)

__all__ = ["gerar_plano_acao", "gerar_texto_simples", "_extrair_json"]
