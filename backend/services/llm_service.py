"""Serviço LLM para NEXUS - Camada de abstração sobre OpenAI"""
import json
import logging
from typing import List, Dict, Any, Optional
from openai.types.chat import ChatCompletionMessageParam

# Import com fallback para execução direta ou como pacote
try:
    from ..helpers.openai_client import get_openai_client
except ImportError:
    from helpers.openai_client import get_openai_client  # type: ignore

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.client = get_openai_client()  # type: ignore
    
    # Métodos da classe abaixo
    def processar_agendamento(self, texto_usuario: str, contexto: Optional[str] = None) -> Dict[str, Any]:
        """Extrai informações de agendamento do texto"""
        system_prompt = (
            "Você é um assistente de agendamentos do NEXUS.\n"
            "Extraia do texto:\n"
            "- data: YYYY-MM-DD\n"
            "- hora: HH:MM\n"
            "- duracao: minutos (padrão: 60)\n"
            "- titulo: string\n"
            "- participantes: lista de nomes/emails\n"
            "- local: string ou null\n\n"
            "Retorne APENAS JSON válido."
        )
        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt}
        ]
        if contexto:
            messages.append({"role": "system", "content": f"Contexto: {contexto}"})
        messages.append({"role": "user", "content": texto_usuario})
        try:
            response: str = self.client.chat_completion(messages, temperature=0.3, max_tokens=500)  # type: ignore
            return json.loads(response)  # type: ignore
        except Exception as e:
            logger.error(f"❌ Erro processar agendamento: {e}")
            return {"erro": str(e), "texto_original": texto_usuario}
    
    def gerar_resposta_chat(self, mensagem: str, historico: Optional[List[ChatCompletionMessageParam]] = None) -> str:
        """Gera resposta de chat natural"""
        messages: List[ChatCompletionMessageParam] = list(historico) if historico else []
        messages.append({"role": "user", "content": mensagem})
        return self.client.chat_completion(messages, temperature=0.7)  # type: ignore
    
    # Métodos da classe abaixo
    def analisar_sentimento(self, texto: str) -> Dict[str, Any]:
        """Analisa sentimento: positivo/neutro/negativo"""
        prompt = (
            f"Analise o sentimento e retorne JSON:\n"
            f"{{'sentimento': 'positivo|neutro|negativo', 'confianca': 0.0-1.0}}\n\n"
            f"Texto: {texto}"
        )
        try:
            messages: List[ChatCompletionMessageParam] = [{"role": "user", "content": prompt}]
            response: str = self.client.chat_completion(messages, temperature=0.1)  # type: ignore
            return json.loads(response)  # type: ignore
        except Exception:
            return {"sentimento": "neutro", "confianca": 0.0}

# Singleton
_service = None
def get_llm_service() -> LLMService:
    global _service
    if _service is None:
        _service = LLMService()
    return _service
