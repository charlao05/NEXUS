"""
Módulo LLM central do NEXUS
============================
Ponto único de acesso à OpenAI API.

Consolida e substitui:
  - helpers/openai_client.py  → OpenAIClient + get_openai_client()
  - services/llm_service.py   → processar_agendamento, analisar_sentimento
  - utils/llm_client.py       → gerar_plano_acao, gerar_texto_simples
  - app/api/agent_media._get_openai_raw → get_raw_openai()

Uso:
    from app.core.llm import get_openai_client, get_raw_openai
    from app.core.llm import gerar_plano_acao, gerar_texto_simples
"""

import json
import logging
import os
import time
from functools import lru_cache
from typing import Any, Dict, Generator, List, Optional

from openai import OpenAI, OpenAIError
from openai.types.chat import ChatCompletionMessageParam

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cliente estruturado (OpenAIClient)
# ---------------------------------------------------------------------------

class OpenAIClient:
    """
    Cliente unificado para OpenAI API.

    Fornece:
    - chat_completion()        — completion síncrona
    - chat_completion_stream() — streaming
    - embeddings()             — vetores semânticos
    - estimate_cost()          — custo estimado

    Preços (Abril 2026):
        gpt-4o-mini:  Input $0.15 / Output $0.60 (por 1M tokens)
        gpt-4o:       Input $2.50 / Output $10.00
        gpt-4.1:      Input $2.00 / Output $8.00
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")

        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY não encontrada. Configure no arquivo .env:\n"
                "OPENAI_API_KEY=sk-proj-..."
            )
        if self.api_key.startswith("sk-proj-test"):
            raise ValueError(
                "OPENAI_API_KEY é um placeholder. Substitua por uma chave real."
            )

        self.default_model = (
            model or os.getenv("OPENAI_MODEL") or "gpt-4.1"
        )
        self.client = OpenAI(
            api_key=self.api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        logger.info(f"OpenAI Client inicializado (modelo: {self.default_model})")

    # ------------------------------------------------------------------
    def chat_completion(
        self,
        messages: List[ChatCompletionMessageParam],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        **kwargs: Any,
    ) -> str:
        """Gera resposta de chat (síncrona). Retorna o texto da resposta."""
        try:
            start = time.time()
            response = self.client.chat.completions.create(  # type: ignore
                model=model or self.default_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                **kwargs,
            )
            elapsed = time.time() - start
            content: str = response.choices[0].message.content  # type: ignore
            usage: Any = response.usage
            cost = self.estimate_cost(
                input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                model=model or self.default_model,
            )
            logger.info(
                f"OpenAI response in {elapsed:.2f}s | "
                f"tokens={getattr(usage, 'total_tokens', 0) if usage else 0} | "
                f"cost=${cost:.6f}"
            )
            return content  # type: ignore
        except OpenAIError:
            raise
        except Exception as exc:
            logger.error(f"Erro inesperado no chat_completion: {exc}")
            raise

    # ------------------------------------------------------------------
    def chat_completion_stream(
        self,
        messages: List[ChatCompletionMessageParam],
        model: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """Gera resposta com streaming. Yields chunks de texto."""
        try:
            stream = self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                temperature=temperature,
                stream=True,
                **kwargs,
            )
            full = ""
            for chunk in stream:
                delta = (
                    getattr(chunk.choices[0].delta, "content", None)
                    if getattr(chunk.choices[0], "delta", None)
                    else None
                )
                if delta:
                    full += delta
                    yield delta
            logger.info(f"Streaming concluído ({len(full)} chars)")
        except OpenAIError:
            raise
        except Exception as exc:
            logger.error(f"Erro no streaming: {exc}")
            raise

    # ------------------------------------------------------------------
    def embeddings(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small",
    ) -> List[List[float]]:
        """Gera embeddings para uma lista de textos."""
        try:
            response = self.client.embeddings.create(model=model, input=texts)
            return [item.embedding for item in response.data]
        except OpenAIError:
            raise
        except Exception as exc:
            logger.error(f"Erro nos embeddings: {exc}")
            raise

    # ------------------------------------------------------------------
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: Optional[str] = None,
    ) -> float:
        """Estimativa de custo em USD."""
        prices: Dict[str, Dict[str, float]] = {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o":      {"input": 2.50, "output": 10.00},
            "gpt-4.1":     {"input": 2.00, "output": 8.00},
            "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        }
        m = model or self.default_model
        p = prices.get(m, prices["gpt-4o-mini"])
        return (
            (input_tokens / 1_000_000) * p["input"]
            + (output_tokens / 1_000_000) * p["output"]
        )

    def _test_connection(self) -> bool:
        try:
            self.client.models.list()
            return True
        except OpenAIError:
            return False


# ---------------------------------------------------------------------------
# Singleton gerenciado
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _singleton_client() -> OpenAIClient:
    return OpenAIClient()


def get_openai_client(config: Optional[Any] = None) -> OpenAIClient:
    """
    Retorna a instância singleton de OpenAIClient.
    Se config (AppConfig) for fornecido, usa os parâmetros dele.
    """
    if config is not None and hasattr(config, "openai"):
        cfg = config.openai
        return OpenAIClient(
            api_key=str(cfg.api_key),
            model=str(cfg.model),
            timeout=float(getattr(cfg, "timeout", 30)),
            max_retries=int(getattr(cfg, "max_retries", 3)),
        )
    return _singleton_client()


def get_raw_openai() -> Optional[OpenAI]:
    """
    Retorna o cliente OpenAI bruto (sem wrapper) para chamadas especiais
    como Whisper (transcrição) e GPT-4 Vision.

    Retorna None se OPENAI_API_KEY não estiver configurada, permitindo
    fallback gracioso nos endpoints de mídia.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("sk-proj-test"):
        return None
    try:
        return OpenAI(api_key=api_key)
    except Exception as exc:
        logger.warning(f"get_raw_openai falhou: {exc}")
        return None


# ---------------------------------------------------------------------------
# Funções utilitárias (anteriormente em utils/llm_client.py)
# ---------------------------------------------------------------------------

def _extrair_json(texto: str) -> str:
    """Extrai o primeiro bloco JSON de um texto qualquer."""
    inicio = texto.find("{")
    fim = texto.rfind("}")
    if inicio == -1 or fim == -1 or fim <= inicio:
        raise ValueError("Nenhum JSON encontrado na resposta do modelo.")
    return texto[inicio: fim + 1]


def gerar_plano_acao(
    site: str, objetivo: str, contexto_site: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Gera um plano de ação em JSON para automatizar um site via Playwright.

    Retorno:
    {
      "steps": [
        {"tipo": "open_url|click|type|wait_selector|press_key|wait_seconds",
         "parametros": {...}}
      ]
    }
    """
    client = get_openai_client()
    contexto_serial = json.dumps(contexto_site, ensure_ascii=False, indent=2)

    system_msg = (
        "Você é um agente de automação web. Gere planos em JSON usando Playwright.\n\n"
        "TIPOS SUPORTADOS: open_url, wait_selector, click, type, press_key, wait_seconds\n\n"
        "REGRAS:\n"
        "1. Responda APENAS com JSON válido.\n"
        '2. Formato: {"steps": [{"tipo": "...", "parametros": {...}}]}\n'
        "3. Inclua só os parâmetros relevantes para cada tipo.\n"
        "4. Não invente credenciais; use placeholders.\n"
        "5. Use seletores CSS válidos.\n"
    )
    user_msg = (
        f"Site: {site}\nObjetivo: {objetivo}\n\n"
        f"Contexto do site:\n{contexto_serial}\n\n"
        "Responda SOMENTE com JSON válido."
    )

    messages: List[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]
    raw = client.chat_completion(messages, temperature=0)
    json_str = _extrair_json(raw)
    try:
        plan = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError("JSON retornado pelo modelo é inválido.") from exc
    if not isinstance(plan, dict) or "steps" not in plan:
        raise ValueError("JSON não contém campo 'steps'.")
    logger.info("Plano de ação gerado: %d passos.", len(plan["steps"]))
    return plan


def gerar_texto_simples(
    prompt: str, max_tokens: int = 200, temperature: float = 0.2
) -> str:
    """Gera texto curto a partir de um prompt."""
    client = get_openai_client()
    messages: List[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": "Você é um assistente útil que responde em português de forma curta e direta.",
        },
        {"role": "user", "content": prompt},
    ]
    return client.chat_completion(messages, max_tokens=max_tokens, temperature=temperature)


# ---------------------------------------------------------------------------
# Funções utilitárias (anteriormente em services/llm_service.py)
# ---------------------------------------------------------------------------

def processar_agendamento(
    texto_usuario: str, contexto: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extrai informações de agendamento do texto.
    Retorna dict com: data, hora, duracao, titulo, participantes, local.
    """
    client = get_openai_client()
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
    msgs: List[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt},
    ]
    if contexto:
        msgs.append({"role": "system", "content": f"Contexto: {contexto}"})
    msgs.append({"role": "user", "content": texto_usuario})
    try:
        response = client.chat_completion(msgs, temperature=0.3, max_tokens=500)
        return json.loads(response)  # type: ignore
    except Exception as exc:
        logger.error(f"Erro processar_agendamento: {exc}")
        return {"erro": str(exc), "texto_original": texto_usuario}


def analisar_sentimento(texto: str) -> Dict[str, Any]:
    """Analisa sentimento: positivo / neutro / negativo."""
    client = get_openai_client()
    prompt = (
        f"Analise o sentimento e retorne JSON:\n"
        f"{{'sentimento': 'positivo|neutro|negativo', 'confianca': 0.0-1.0}}\n\n"
        f"Texto: {texto}"
    )
    try:
        msgs: List[ChatCompletionMessageParam] = [{"role": "user", "content": prompt}]
        response = client.chat_completion(msgs, temperature=0.1)
        return json.loads(response)  # type: ignore
    except Exception:
        return {"sentimento": "neutro", "confianca": 0.0}
