"""
services/llm_service.py — Wrapper de compatibilidade.
Toda a lógica foi consolidada em app/core/llm.py.
"""
from typing import Any, Dict, List, Optional

from openai.types.chat import ChatCompletionMessageParam

# Re-importa do módulo central
from app.core.llm import (  # noqa: F401
    get_openai_client,
    processar_agendamento,
    analisar_sentimento,
)


class LLMService:
    """Mantida para compatibilidade. Use app.core.llm diretamente em código novo."""

    def __init__(self) -> None:
        self.client = get_openai_client()

    def processar_agendamento(
        self, texto_usuario: str, contexto: Optional[str] = None
    ) -> Dict[str, Any]:
        return processar_agendamento(texto_usuario, contexto)

    def gerar_resposta_chat(
        self,
        mensagem: str,
        historico: Optional[List[ChatCompletionMessageParam]] = None,
    ) -> str:
        msgs: List[ChatCompletionMessageParam] = list(historico) if historico else []
        msgs.append({"role": "user", "content": mensagem})
        return self.client.chat_completion(msgs, temperature=0.7)

    def analisar_sentimento(self, texto: str) -> Dict[str, Any]:
        return analisar_sentimento(texto)


_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _service
    if _service is None:
        _service = LLMService()
    return _service
