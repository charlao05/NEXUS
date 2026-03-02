"""
Node PLAN — LLM Planner.
Recebe contexto e objetivo, retorna lista de ações estruturadas.
O LLM é tratado como planner NÃO confiável — saída passa pela política.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

from backend.orchestrator.state import (
    ActionRisk,
    AgentState,
    PlannedAction,
    TaskStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts por tipo de agente
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = """Você é o planejador de ações do NEXUS.
Seu trabalho é analisar o pedido do usuário e propor uma lista de ações concretas.

REGRAS OBRIGATÓRIAS:
1. Responda APENAS com JSON válido, sem texto extra.
2. Cada ação deve ter: tool, params, reason, risk
3. Níveis de risco: low, medium, high, critical
4. NUNCA inclua senhas, tokens ou dados sensíveis nos parâmetros
5. Prefira ações simples e atômicas (uma ação = uma operação)
6. Máximo de {max_steps} ações por plano

TOOLS DISPONÍVEIS:
{available_tools}

CONTEXTO DO USUÁRIO:
{crm_context}

Formato de resposta:
{{"actions": [{{"tool": "nome", "params": {{}}, "reason": "porquê", "risk": "low"}}]}}
"""

# Tools disponíveis por tipo de agente
AGENT_TOOLS: dict[str, str] = {
    "clientes": """
- crm_list_clients: Lista clientes. params: {limit?, status?}
- crm_get_client: Detalhes de um cliente. params: {client_id}
- crm_create_client: Cria cliente. params: {name, email?, phone?, segment?}
- crm_update_client: Atualiza cliente. params: {client_id, fields: {}}
- crm_delete_client: Remove cliente. params: {client_id} (REQUER APROVAÇÃO)
- crm_create_appointment: Agenda compromisso. params: {client_id?, title, date, time}
- respond_to_user: Responde ao usuário. params: {message}
""",
    "financeiro": """
- crm_list_clients: Lista clientes (para contexto).
- crm_create_transaction: Registra receita/despesa. params: {type: income|expense, amount, description, client_id?}
- create_invoice: Emite nota fiscal. params: {client_id, amount, description} (REQUER APROVAÇÃO)
- respond_to_user: Responde ao usuário. params: {message}
""",
    "contabilidade": """
- crm_create_transaction: Registra receita/despesa. params: {type, amount, description}
- create_invoice: Emite NF. params: {client_id, amount, description} (REQUER APROVAÇÃO)
- respond_to_user: Responde com informações fiscais. params: {message}
""",
    "cobranca": """
- crm_list_clients: Lista clientes com cobranças pendentes.
- send_email: Envia email de cobrança. params: {to, subject, body} (REQUER APROVAÇÃO)
- send_whatsapp: Envia WhatsApp de cobrança. params: {to, message} (REQUER APROVAÇÃO)
- respond_to_user: Responde ao usuário. params: {message}
""",
    "agenda": """
- crm_create_appointment: Agenda compromisso. params: {title, date, time, client_id?}
- crm_list_clients: Lista clientes (para associar).
- respond_to_user: Responde ao usuário. params: {message}
""",
    "assistente": """
- crm_list_clients: Lista clientes.
- crm_create_client: Cria cliente. params: {name, email?, phone?}
- crm_create_appointment: Agenda compromisso. params: {title, date, time}
- crm_create_transaction: Registra receita/despesa. params: {type, amount, description}
- respond_to_user: Responde ao usuário. params: {message}
""",
    "browser": """
- browser_navigate: Abre URL. params: {url}
- browser_click: Clica em elemento. params: {selector}
- browser_type: Digita em campo. params: {selector, text}
- browser_wait: Espera elemento. params: {selector, timeout?}
- browser_screenshot: Captura tela. params: {}
- browser_press_key: Pressiona tecla. params: {key}
- respond_to_user: Responde ao usuário. params: {message}
""",
}


def plan_node(state: AgentState) -> dict[str, Any]:
    """Chama o LLM para gerar um plano de ações."""
    agent_type = state.get("agent_type", "assistente")
    goal = state.get("goal", "")
    crm_context = state.get("crm_context", "")
    max_steps = state.get("max_steps", 20)
    iteration = state.get("iteration", 0)
    
    logger.info(f"🧠 PLAN: gerando plano para goal='{goal[:80]}...' (iteração {iteration})")
    
    updates: dict[str, Any] = {
        "status": TaskStatus.PLANNING.value,
        "updated_at": datetime.now().isoformat(),
    }
    
    try:
        # Montar contexto de iterações anteriores
        prev_results = state.get("action_results", [])
        iteration_context = ""
        if prev_results:
            results_summary = []
            for r in prev_results[-5:]:  # Últimos 5 resultados
                status = "✅" if r.get("success") else "❌"
                results_summary.append(f"{status} {r.get('tool', '?')}: {str(r.get('output', ''))[:100]}")
            iteration_context = f"\n\nResultados anteriores:\n" + "\n".join(results_summary)
        
        # Montar system prompt
        available_tools = AGENT_TOOLS.get(agent_type, AGENT_TOOLS["assistente"])
        system = PLANNER_SYSTEM_PROMPT.format(
            max_steps=max_steps,
            available_tools=available_tools,
            crm_context=crm_context + iteration_context,
        )
        
        # Chamar LLM
        actions = _call_llm_planner(system, goal, state.get("messages", []))
        
        updates["planned_actions"] = [a.model_dump() for a in actions]
        updates["current_step"] = 0
        
        logger.info(f"📋 Plano gerado com {len(actions)} ações")
        
    except Exception as e:
        logger.error(f"Erro no planner: {e}")
        # Fallback: responder ao usuário diretamente
        updates["planned_actions"] = [
            PlannedAction(
                tool="respond_to_user",
                params={"message": f"Desculpe, tive um problema ao planejar: {e}"},
                reason="Fallback por erro no planner",
                risk=ActionRisk.LOW,
            ).model_dump()
        ]
        updates["current_step"] = 0
        
    return updates


def _call_llm_planner(
    system_prompt: str,
    user_goal: str,
    history: list,
) -> list[PlannedAction]:
    """Chama OpenAI para gerar plano de ações."""
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("sk-proj-test"):
        logger.warning("⚠️ OPENAI_API_KEY não configurada, usando fallback")
        return [
            PlannedAction(
                tool="respond_to_user",
                params={"message": "Preciso da chave OpenAI configurada para planejar ações."},
                reason="API key ausente",
                risk=ActionRisk.LOW,
            )
        ]
    
    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1")
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_goal},
    ]
    
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    
    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)
    
    actions_raw = data.get("actions", [])
    actions: list[PlannedAction] = []
    
    for a in actions_raw:
        try:
            risk_str = a.get("risk", "low")
            risk = ActionRisk(risk_str) if risk_str in ActionRisk.__members__.values() else ActionRisk.LOW
            actions.append(PlannedAction(
                tool=a.get("tool", "respond_to_user"),
                params=a.get("params", {}),
                reason=a.get("reason", ""),
                risk=risk,
            ))
        except Exception as parse_err:
            logger.warning(f"Ação inválida ignorada: {a} — {parse_err}")
    
    # Garantir que há pelo menos uma ação
    if not actions:
        actions.append(PlannedAction(
            tool="respond_to_user",
            params={"message": "Não consegui gerar um plano de ações. Pode reformular o pedido?"},
            reason="Plano vazio do LLM",
            risk=ActionRisk.LOW,
        ))
    
    return actions
