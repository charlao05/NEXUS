"""
openai_tracking — Helper para registrar usage de chamadas OpenAI feitas
diretamente via SDK (sem passar por OpenAIClient.chat_completion wrapper).

Uso:
    import time
    from helpers.openai_tracking import track_openai_response

    _t0 = time.time()
    response = client.chat.completions.create(model="gpt-4o-mini", ...)
    track_openai_response(response, "gpt-4o-mini", _t0)

Existe porque o codebase tem ~10 sites usando o SDK OpenAI direto em vez
do wrapper centralizado. Em vez de refatorar todos pra usar OpenAIClient
(escopo grande), este helper permite instrumentar cada callsite com 2 linhas.

NUNCA propaga exceção. Falhas são suprimidas (instrumentação não pode
quebrar caminho feliz).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Tabela de preços (mantida em sincronia com OpenAIClient.estimate_cost).
# USD por 1M tokens, janeiro 2026.
_PRICES_PER_1M = {
    "gpt-4o-mini":   {"input": 0.15, "output": 0.60},
    "gpt-4o":        {"input": 2.50, "output": 10.00},
    "gpt-4-turbo":   {"input": 10.00, "output": 30.00},
    "gpt-4":         {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}


def _calc_cost_usd(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calcula custo USD inline. Modelos desconhecidos usam tabela do gpt-4o-mini."""
    p = _PRICES_PER_1M.get(model, _PRICES_PER_1M["gpt-4o-mini"])
    return (input_tokens / 1_000_000) * p["input"] + (output_tokens / 1_000_000) * p["output"]


def track_openai_response(
    response: Any,
    model: str,
    started_at: float,
    *,
    user_id_override: Optional[int] = None,
    agent_type_override: Optional[str] = None,
) -> None:
    """Registra usage de uma response OpenAI no UsageTracker.

    Args:
        response: objeto retornado por client.chat.completions.create(...).
                  Deve ter .usage com prompt_tokens/completion_tokens.
        model: nome do modelo usado (ex: "gpt-4o-mini").
        started_at: time.time() capturado ANTES da chamada .create().
        user_id_override: se passado, ignora contextvar e usa este user_id.
                          Útil em endpoints que recebem user_id via dependency.
        agent_type_override: idem para agent_type.
    """
    try:
        # Imports tardios evitam custo se nunca chamado
        from utils.usage_tracker import UsageTracker
        from utils.automation_logger import (
            _correlation_id as _ctx_corr,
            _user_id as _ctx_user,
            _agent_type as _ctx_agent,
        )

        # Extrair tokens de forma defensiva
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0

        # Custo via tabela inline (auto-contida; sem depender de OpenAIClient instanciado)
        try:
            cost_usd = _calc_cost_usd(prompt_tokens, completion_tokens, model)
        except Exception:
            cost_usd = 0.0

        duration_ms = max(0, int((time.time() - started_at) * 1000))

        # Resolver user_id: override > contextvar > 0
        if user_id_override is not None:
            uid = int(user_id_override)
        else:
            uid = int(_ctx_user.get() or 0)

        agent = agent_type_override or _ctx_agent.get()

        UsageTracker.record_llm(
            user_id=uid,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=duration_ms,
            cost_usd=cost_usd,
            correlation_id=_ctx_corr.get(),
            agent_type=agent,
        )
    except Exception:
        # Suprimir totalmente — instrumentação não pode quebrar caminho feliz
        logger.debug("track_openai_response suprimido", exc_info=True)
