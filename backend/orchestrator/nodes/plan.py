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

from orchestrator.state import (
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
7. Para tarefas de browser: use browser_get_page_state após navegação
   para "enxergar" os elementos da página antes de interagir

REGRA CRÍTICA — HUMAN-IN-THE-LOOP:
Se a página atual contiver campos de CPF, CNPJ, senha, anti-robô ou CAPTCHA,
ou se estiver num domínio sensível (Receita Federal, gov.br, bancos, prefeituras):
- **NÃO planeje ações de browser_type ou browser_click em campos de login/senha/CPF/captcha.**
- Em vez disso, crie UM ÚNICO passo com tool="wait_for_user_login" e params contendo
  "message_to_user" com instruções claras em português simples para o usuário preencher
  esses dados manualmente. Exemplo:
  {{"tool": "wait_for_user_login", "params": {{"message_to_user": "Agora é com você: digite seu CPF e data de nascimento e clique em Consultar."}}, "reason": "Campos sensíveis detectados", "risk": "low"}}
- Após o wait_for_user_login, NÃO adicione mais ações — o orquestrador vai pausar e
  retomar depois que o usuário completar sua parte.

TOOLS DISPONÍVEIS:
{available_tools}

CONTEXTO DO USUÁRIO:
{crm_context}

OBSERVAÇÃO DA PÁGINA ATUAL:
{page_observation}

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
NAVEGAÇÃO:
- browser_navigate: Abre URL. params: {url}
- browser_go_back: Volta à página anterior. params: {}
- browser_go_forward: Avança para próxima página. params: {}
- browser_scroll: Rola a página. params: {direction: up|down, amount?: 500}

INTERAÇÃO:
- browser_click: Clica em elemento. params: {selector}
- browser_type: Digita em campo. params: {selector, text, secret?: false}
- browser_press_key: Pressiona tecla. params: {key} (Enter, Tab, Escape, etc.)
- browser_hover: Passa mouse sobre elemento. params: {selector}

FORMULÁRIOS:
- browser_select_option: Seleciona opção em dropdown. params: {selector, value}
- browser_check_checkbox: Marca/desmarca checkbox. params: {selector, checked?: true}
- browser_submit_form: Submete formulário. params: {selector?: "form"}
- browser_upload_file: Faz upload de arquivo. params: {selector, file_path}

LEITURA/EXTRAÇÃO:
- browser_get_text: Lê texto de elemento. params: {selector}
- browser_get_attribute: Lê atributo de elemento. params: {selector, attribute}
- browser_extract_table: Extrai tabela HTML. params: {selector?: "table"}
- browser_find_by_text: Encontra elemento por texto. params: {text, tag?: "*"}
- browser_get_page_state: Captura estado da página (elementos interativos). params: {}

AVANÇADO:
- browser_screenshot: Captura tela. params: {path?}
- browser_evaluate_js: Executa JavaScript (apenas leitura). params: {expression}
- browser_handle_dialog: Configura resposta para diálogos. params: {accept?, prompt_text?}
- browser_drag_drop: Arrasta elemento. params: {source, target}

UTILIDADE:
- browser_wait_selector: Espera elemento aparecer. params: {selector, timeout_ms?}
- browser_wait: Espera N segundos. params: {seconds}
- browser_close: Fecha o navegador. params: {}
- respond_to_user: Responde ao usuário. params: {message}

DICAS PARA PLANEJAR AUTOMAÇÃO:
1. SEMPRE comece com browser_navigate para abrir a URL
2. Após navegar, use browser_get_page_state para "enxergar" a página
3. Use os selectors retornados pela percepção para clicar/digitar
4. Se encontrar formulário, preencha campo por campo
5. Se encontrar tela de login (page_type=login), use respond_to_user para avisar
6. Use browser_screenshot para capturar evidências
7. NUNCA inclua senhas ou dados de cartão nos parâmetros

REGRA CRÍTICA: Você DEVE executar browser_navigate + browser_get_page_state
ANTES de usar respond_to_user. O browser é REAL — não invente que "a página
foi aberta" sem ter executado browser_navigate primeiro.
Só use respond_to_user depois de TER NAVEGADO e observado a página real.
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
    
    # --- Human-in-the-loop: se sense detectou tela sensível, gerar wait_for_user_login ---
    if state.get("awaiting_user_input"):
        resume_hint = state.get("resume_hint", "")
        reason = state.get("awaiting_user_reason", "Campos sensíveis detectados")
        
        message_to_user = resume_hint or (
            "Agora é a parte que só você pode fazer.\n"
            "Digite seus dados na tela do site e clique no botão de envio.\n"
            "Quando a próxima tela aparecer, volte aqui e clique em 'Continuar Automação'.\n"
            "O robô não vê nem guarda seu CPF ou senha."
        )
        
        wait_action = PlannedAction(
            tool="wait_for_user_login",
            params={"message_to_user": message_to_user},
            reason=reason,
            risk=ActionRisk.LOW,
        )
        updates["planned_actions"] = [wait_action.model_dump()]
        updates["current_step"] = 0
        
        logger.info(f"⏸️ PLAN: Gerado wait_for_user_login — {reason}")
        return updates
    
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
        
        # Informar ao planner quais ações foram bloqueadas pela política
        blocked_info = state.get("blocked_actions_info", "")
        if blocked_info:
            iteration_context += (
                f"\n\n⚠️ AÇÕES BLOQUEADAS PELA POLÍTICA DE SEGURANÇA (NÃO repita estas ações):\n"
                f"{blocked_info}\n"
                f"Use wait_for_user_login para campos sensíveis como CPF, senha e captcha."
            )
        
        # Montar system prompt
        available_tools = AGENT_TOOLS.get(agent_type, AGENT_TOOLS["assistente"])
        page_observation = state.get("page_observation", "Nenhuma página aberta.")
        
        # Injetar URL canônica do template para evitar que o LLM invente URLs
        site_config = state.get("site_config") or {}
        canonical_url = site_config.get("url", "")
        url_instruction = ""
        if canonical_url and agent_type == "browser":
            url_instruction = (
                f"\n\nURL CANÔNICA OBRIGATÓRIA: {canonical_url}\n"
                f"Quando usar browser_navigate, use EXATAMENTE esta URL. "
                f"NÃO invente ou modifique a URL."
            )
        
        system = PLANNER_SYSTEM_PROMPT.format(
            max_steps=max_steps,
            available_tools=available_tools,
            crm_context=crm_context + iteration_context + url_instruction,
            page_observation=page_observation,
        )
        
        # Chamar LLM
        actions = _call_llm_planner(system, goal, state.get("messages", []))
        
        # ── Validação pós-LLM para browser agent ────────────────
        # Se é browser agent na iteração 0 e o LLM só gerou respond_to_user
        # (sem nenhuma ação real de browser), forçar navegação antes.
        if agent_type == "browser" and iteration == 0:
            has_browser_action = any(
                a.tool.startswith("browser_") for a in actions
            )
            if not has_browser_action:
                # O LLM tentou atalhar com respond_to_user sem abrir o browser.
                # Forçar: navigate + get_page_state + respond_to_user
                site_config = state.get("site_config") or {}
                url = site_config.get("url", "")
                if url:
                    logger.warning(
                        f"⚠️ plan_node: LLM não gerou browser actions — "
                        f"forçando navigate para {url}"
                    )
                    forced_actions = [
                        PlannedAction(
                            tool="browser_navigate",
                            params={"url": url},
                            reason="Navegação forçada — LLM não planejou ações de browser",
                            risk=ActionRisk.LOW,
                        ),
                        PlannedAction(
                            tool="browser_get_page_state",
                            params={},
                            reason="Capturar estado da página após navegação",
                            risk=ActionRisk.LOW,
                        ),
                        PlannedAction(
                            tool="browser_screenshot",
                            params={},
                            reason="Screenshot para evidência",
                            risk=ActionRisk.LOW,
                        ),
                    ]
                    # Manter o respond_to_user original como última ação
                    actions = forced_actions + actions
        
        # ── Pós-processamento: forçar URL canônica do template ──────
        # Impede que o LLM invente URLs para browser_navigate
        if agent_type == "browser" and canonical_url:
            for a in actions:
                if a.tool == "browser_navigate":
                    planned_url = a.params.get("url", "")
                    if planned_url and planned_url != canonical_url:
                        # Só corrigir se a URL planejada é do mesmo domínio (evitar substituir URLs totalmente diferentes)
                        from urllib.parse import urlparse
                        planned_host = urlparse(planned_url).hostname or ""
                        canon_host = urlparse(canonical_url).hostname or ""
                        if planned_host == canon_host or not planned_url.startswith("http"):
                            logger.warning(
                                f"⚠️ URL corrigida pelo pós-processador: "
                                f"{planned_url[:60]} → {canonical_url[:60]}"
                            )
                            a.params["url"] = canonical_url
        
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
    model = "gpt-4o-mini"
    
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
