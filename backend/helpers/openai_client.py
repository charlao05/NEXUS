"""
Cliente OpenAI para NEXUS
==========================
Substitui Google Cloud Vertex AI para reduzir custos em 90%.

Autor: Charles Rodrigues da Silva (via Perplexity Comet)
Data: 01/02/2026
Versão: 2.0.0

Custos estimados (GPT-4o mini):
- Input: $0.15 / 1M tokens
- Output: $0.60 / 1M tokens
- Uso típico NEXUS: R$ 10-50/mês
"""

from typing import Optional, Any, List

# Nota: AppConfig removido - não utilizado diretamente neste módulo


def get_openai_client(config: Optional[Any] = None) -> "OpenAIClient":
    """
    Retorna instância singleton do OpenAIClient.
    Se config (AppConfig) for fornecido, usa os parâmetros dele.
    """
    if config is not None and hasattr(config, 'openai'):
        openai_cfg = config.openai
        return OpenAIClient(
            api_key=str(openai_cfg.api_key),
            model=str(openai_cfg.model),
            timeout=float(getattr(openai_cfg, 'timeout', 30)),
            max_retries=int(getattr(openai_cfg, 'max_retries', 3))
        )
    # Retorna singleton se não houver config
    return _get_singleton_client()


import os
import logging
from openai.types.chat import ChatCompletionMessageParam
import time
from openai import OpenAI, OpenAIError

# Configurar logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Handler para console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


class OpenAIClient:
    """
    Cliente unificado para OpenAI API
    
    Fornece métodos simples para:
    - Chat completions (texto)
    - Streaming (respostas em tempo real)
    - Embeddings (vetores para busca semântica)
    - Estimativa de custos
    
    Exemplo básico:
        >>> client = OpenAIClient()
        >>> response = client.chat_completion([
        ...     {"role": "user", "content": "Olá!"}
        ... ])
        >>> print(response)
        "Olá! Como posso ajudar?"
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3
    ):
        """
        Inicializa cliente OpenAI
        
            api_key: Chave API OpenAI (se None, usa OPENAI_API_KEY do .env)
            model: Modelo padrão (se None, usa OPENAI_MODEL do .env ou gpt-4o-mini)
            timeout: Timeout em segundos para requisições (default: 30s)
            max_retries: Número máximo de tentativas em caso de erro (default: 3)
        
        Raises:
            ValueError: Se OPENAI_API_KEY não estiver configurada
        """
        # Obter API key
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        # Validar API key
        if not self.api_key:
            raise ValueError(
                "⚠️ OPENAI_API_KEY não encontrada!\n\n"
                "Configure no arquivo backend/.env:\n"
                "OPENAI_API_KEY=sk-proj-...\n\n"
                "Obtenha sua chave em: https://platform.openai.com/api-keys"
            )
        
        if self.api_key == "sk-proj-test-development-mode":
            raise ValueError(
                "⚠️ OPENAI_API_KEY é um placeholder!\n\n"
                "Substitua no backend/.env por uma chave real:\n"
                "1. Acesse https://platform.openai.com/api-keys\n"
                "3. Cole no .env: OPENAI_API_KEY=sk-proj-ABC123..."
            )
        
        # Configurar modelo padrão — HARDCODED gpt-4o-mini (ignora env var pra evitar deploy quebrado)
        self.default_model = model or "gpt-4o-mini"
        
        # Criar cliente OpenAI
        self.client = OpenAI(
            api_key=self.api_key,
            timeout=timeout,
            max_retries=max_retries
        )
        # Log de inicialização
        logger.info(f"✅ OpenAI Client inicializado (modelo: {self.default_model}, timeout: {timeout}s)")
    
    def _test_connection(self) -> bool:
        """
        Testa conexão com OpenAI API
        Returns:
            True se conexão OK, False caso contrário
        """
        try:
            # Tenta listar modelos disponíveis (requisição leve)
            _ = self.client.models.list()  # Removido: variável não utilizada
            logger.info("✅ Conexão OpenAI OK")
            return True
        except OpenAIError as e:
            logger.warning(f"⚠️ Erro ao testar conexão OpenAI: {str(e)}")
            return False
    
    from typing import Any
    def chat_completion(
        self,
        messages: List[ChatCompletionMessageParam],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        **kwargs: Any
    ) -> str:
        """
        Gera resposta de chat completion (síncrono)
        
        Args:
            messages: Lista de mensagens no formato OpenAI:
                [
                    {"role": "system", "content": "Você é um assistente..."},
                    {"role": "user", "content": "Olá!"},
                    {"role": "assistant", "content": "Olá! Como posso ajudar?"},
                    {"role": "user", "content": "Me conte uma piada"}
                ]
            model: Modelo a usar (default: self.default_model)
            temperature: Criatividade (0.0-2.0, default: 0.7)
                - 0.0-0.3: Respostas determinísticas, precisas
                - 0.4-0.7: Balanceado (recomendado)
                - 0.8-2.0: Criativo, variado
            max_tokens: Máximo de tokens na resposta (None = sem limite)
            top_p: Nucleus sampling (0.0-1.0, default: 1.0)
            frequency_penalty: Penalidade por repetição (0.0-2.0, default: 0.0)
            presence_penalty: Penalidade por novos tópicos (0.0-2.0, default: 0.0)
            **kwargs: Outros parâmetros da OpenAI API
        
        Returns:
            str: Resposta gerada pelo modelo
        
        Raises:
            OpenAIError: Se houver erro na API
        
        Example:
            >>> client = OpenAIClient()
            >>> response = client.chat_completion([
            ...     {"role": "system", "content": "Você é um assistente de agendamento"},
            ...     {"role": "user", "content": "Agende reunião amanhã 10h"}
            ... ])
            >>> print(response)
        """
        try:
            # Log da requisição
            logger.debug(
                f"📤 Enviando requisição OpenAI "
                f"(modelo: {model or self.default_model}, "
                f"{len(messages)} mensagens)"
            )
            
            # Timestamp inicial
            start_time = time.time()
            
            # Fazer requisição
            response = self.client.chat.completions.create(  # type: ignore
                model=model or self.default_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                **kwargs
            )
            
            # Timestamp final
            elapsed_time = time.time() - start_time
            
            # Extrair resposta
            content: str = response.choices[0].message.content  # type: ignore
            
            # Log de custos e performance
            usage: Any = response.usage  # type: ignore
            estimated_cost = self.estimate_cost(
                input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,  # type: ignore
                output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,  # type: ignore
                model=model or self.default_model
            )
            
            logger.info(
                f"📥 Resposta recebida em {elapsed_time:.2f}s | "
                f"Tokens: {getattr(usage, 'total_tokens', 0) if usage else 0} "  # type: ignore
                f"({getattr(usage, 'prompt_tokens', 0) if usage else 0} in, {getattr(usage, 'completion_tokens', 0) if usage else 0} out) | "  # type: ignore
                f"Custo estimado: ${estimated_cost:.6f}"
            )

            # ── Usage tracking (Tier 1 — sink in-memory) ──
            # Desvia os números que já calculamos acima pro UsageTracker, pra
            # consulta agregada via /api/admin/usage/llm. NUNCA propaga exceção.
            try:
                from utils.usage_tracker import UsageTracker
                from utils.automation_logger import (
                    _correlation_id as _ctx_corr,
                    _user_id as _ctx_user,
                    _agent_type as _ctx_agent,
                )
                UsageTracker.record_llm(
                    user_id=(_ctx_user.get() or 0),
                    model=model or self.default_model,
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,  # type: ignore
                    completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,  # type: ignore
                    duration_ms=int(elapsed_time * 1000),
                    cost_usd=float(estimated_cost),
                    correlation_id=_ctx_corr.get(),
                    agent_type=_ctx_agent.get(),
                )
            except Exception:
                logger.debug("UsageTracker.record_llm suprimido", exc_info=True)

            return content  # type: ignore
            
        except OpenAIError as e:
            logger.error(f"❌ Erro OpenAI: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Erro inesperado: {str(e)}")
            raise
    
    from typing import Any, Generator
    def chat_completion_stream(
        self,
        messages: List[ChatCompletionMessageParam],
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> Generator[str, None, None]:
        """
        Gera resposta de chat com streaming (respostas em tempo real)
        
        Útil para:
        - Interfaces de chat (mostrar resposta sendo escrita)
        - Respostas longas (feedback imediato)
        - Reduzir percepção de latência
        
        Args:
            messages: Lista de mensagens
            model: Modelo a usar
            temperature: Criatividade
            **kwargs: Outros parâmetros
        
        Yields:
            str: Chunks da resposta conforme são gerados
        
        Example:
            >>> client = OpenAIClient()
            >>> for chunk in client.chat_completion_stream(messages):
            ...     print(chunk, end="", flush=True)  # Imprime em tempo real
        """
        try:
            logger.debug("📤 Iniciando streaming OpenAI...")
            
            # Criar stream
            stream = self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                temperature=temperature,
                stream=True,
                **kwargs
            )
            full_response: str = ""
            for chunk in stream:
                delta_content: Optional[str] = getattr(chunk.choices[0].delta, "content", None) if getattr(chunk.choices[0], "delta", None) else None
                if delta_content:
                    full_response += delta_content
                    yield delta_content
            logger.info(f"📥 Streaming concluído ({len(full_response)} caracteres)")
                    
        except OpenAIError as e:
            logger.error(f"❌ Erro OpenAI streaming: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Erro inesperado no streaming: {str(e)}")
            raise
    
    def embeddings(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small"
    ) -> List[List[float]]:
        """
        Gera embeddings para textos (vetores para busca semântica)
        
        Útil para:
        - Busca semântica em documentos
        - Similaridade entre textos
        - Clustering de textos
        - Recomendações
        
        Args:
            texts: Lista de textos para embeddings
            model: Modelo de embedding (opções):
                - "text-embedding-3-small": 1536 dims, $0.02/1M tokens (recomendado)
                - "text-embedding-3-large": 3072 dims, $0.13/1M tokens
                - "text-embedding-ada-002": 1536 dims, $0.10/1M tokens (legado)
        
        Returns:
            Lista de vetores (cada vetor é uma lista de floats)
        
        Example:
            >>> client = OpenAIClient()
            >>> embeddings = client.embeddings([
            ...     "Reunião às 10h",
            ...     "Meeting at 10am"
            ... ])
            >>> # Calcular similaridade
            >>> from numpy import dot
            >>> from numpy.linalg import norm
            >>> similarity = dot(embeddings, embeddings) / (
            ...     norm(embeddings) * norm(embeddings)
            ... )
            >>> print(f"Similaridade: {similarity:.2f}")  # ~0.85 (similar)
        """
        try:
            logger.debug(
                f"📤 Gerando embeddings para {len(texts)} textos "
                f"(modelo: {model})"
            )
            
            response = self.client.embeddings.create(
                model=model,
                input=texts
            )
            
            embeddings = [item.embedding for item in response.data]
            
            logger.info(
                f"📥 {len(embeddings)} embeddings gerados "
                f"({len(embeddings)} dimensões)"
            )
            
            return embeddings
            
        except OpenAIError as e:
            logger.error(f"❌ Erro ao gerar embeddings: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"❌ Erro inesperado nos embeddings: {str(e)}")
            raise
    
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: Optional[str] = None
    ) -> float:
        """
        Estima custo da requisição em USD
        
        Preços (Janeiro 2026):
            gpt-4o-mini:
                Input: $0.15 / 1M tokens
                Output: $0.60 / 1M tokens
            gpt-4o:
                Input: $2.50 / 1M tokens
                Output: $10.00 / 1M tokens
            gpt-4-turbo:
                Input: $10.00 / 1M tokens
                Output: $30.00 / 1M tokens
        Args:
            input_tokens: Número de tokens de entrada
            output_tokens: Número de tokens de saída
            model: Modelo usado (se None, usa self.default_model)
        Returns:
            float: custo estimado
        """
        prices = {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        }
        m = model or self.default_model
        p = prices.get(m, prices["gpt-4o-mini"])
        return (input_tokens / 1_000_000) * p["input"] + (output_tokens / 1_000_000) * p["output"]


# Função de fábrica auxiliar para singleton (nível de módulo)
from functools import lru_cache as _lru_cache

@_lru_cache(maxsize=1)
def _get_singleton_client() -> OpenAIClient:
    """Retorna instância singleton do OpenAIClient"""
    return OpenAIClient()
