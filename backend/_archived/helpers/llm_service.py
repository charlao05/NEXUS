"""
Serviço LLM - NEXUS
===================
Refatorado para OpenAI API
Autor: Charles Rodrigues
Data: 25/01/2026
Versão: 2.0.0
"""

import json
import logging
from typing import Dict, List, Optional, Any
from functools import lru_cache

try:
    from .openai_client import get_openai_client, OpenAIClient
except ImportError:
    from openai_client import get_openai_client, OpenAIClient  # type: ignore


logger = logging.getLogger(__name__)


class LLMService:
    """
    Serviço centralizado para operações LLM
    Abstrai a complexidade do OpenAI client
    """
    
    def __init__(self, client: Optional[OpenAIClient] = None):
        """Inicializa serviço com cliente OpenAI"""
        self.client = client or get_openai_client()
    
    def gerar_resposta_chat(self, prompt: str) -> str:
        """Gera resposta de chat usando o modelo LLM."""
        messages = [
            {"role": "user", "content": prompt}
        ]
        return self.client.chat_completion(messages)

    def processar_agendamento(self, texto: str) -> dict:
        """Processa texto para extrair dados de agendamento (stub demo)."""
        # Exemplo simplificado: retorna texto como campo
        return {"texto": texto, "data": "2026-01-26", "hora": "14:00", "pessoa": "Maria"}

    def analisar_sentimento(self, texto: str) -> str:
        """Analisa sentimento do texto (stub demo)."""
        # Exemplo simplificado: retorna sempre positivo
        return "Positivo"

@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    """
    Retorna instância singleton do serviço LLM
    """
    return LLMService()
