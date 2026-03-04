"""
Agent Automation Bridge — Conecta o chat dos agentes ao Orquestrador LangGraph.
=================================================================================

Quando o Assistente detecta intenção de automação web no chat,
este módulo faz a ponte: gera um plano via LLM, apresenta ao usuário
para aprovação, e então executa via Playwright (orchestrator).

Endpoints:
    POST /api/agents/automation/start   — Inicia automação (gera plano, pede aprovação)
    POST /api/agents/automation/approve — Aprova e executa o plano
    POST /api/agents/automation/reject  — Rejeita o plano
    GET  /api/agents/automation/status  — Status de uma automação em andamento
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents/automation", tags=["Agent Automation"])

# Importar autenticação
try:
    from app.api.auth import get_current_user  # type: ignore[import]
except ImportError:
    async def get_current_user():  # type: ignore[misc]
        return {"user_id": 1, "email": "dev@local", "plan": "free", "role": "user"}

# ---------------------------------------------------------------------------
# Estado em memória das automações pendentes
# ---------------------------------------------------------------------------
_automation_tasks: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AutomationStartRequest(BaseModel):
    """Requisição para iniciar uma automação via chat."""
    agent_id: str = Field(default="assistente", description="Agente que solicitou")
    goal: str = Field(description="O que o usuário quer automatizar")
    message: str = Field(default="", description="Mensagem original do usuário")
    user_id: int | None = Field(default=None, description="User ID (set internally)")


class AutomationApproveRequest(BaseModel):
    """Aprovação/rejeição de plano."""
    task_id: str
    approved: bool = True
    reason: str = ""


class AutomationStartResponse(BaseModel):
    """Resposta com plano para aprovação."""
    task_id: str
    status: str  # "awaiting_approval", "error"
    plan_summary: str  # Plano formatado para o usuário
    steps: list[dict[str, Any]]  # Passos detalhados
    risk_level: str  # low, medium, high, critical
    message: str  # Mensagem amigável para o chat


class AutomationResultResponse(BaseModel):
    """Resultado da execução."""
    task_id: str
    status: str
    message: str
    action_results: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_automation_intent(message: str) -> dict[str, Any] | None:
    """Detecta se a mensagem do usuário contém intenção de automação.
    Usa LLM para classificação inteligente com fallback para keywords.
    Retorna dict com goal e site_hint se detectado, ou None.
    """
    msg = message.lower().strip()

    # ── Fase 1: Keywords rápidas (zero-cost, sem LLM) ────────────
    automation_keywords = [
        "automatizar", "automação", "abrir site", "acessar site",
        "preencher formulário", "consultar cpf", "consultar cnpj",
        "emitir nota", "emitir nf", "portal", "receita federal",
        "prefeitura", "gov.br", "simples nacional", "dasn",
        "automatize", "execut", "rodar automação", "fazer por mim",
        "pode fazer isso", "pode realizar", "realizar a consulta",
        "n8n", "selenium", "playwright", "navegador",
        # Expressões naturais adicionais
        "acessar o site", "entrar no site", "abrir o portal",
        "gerar boleto", "gerar das", "pagar das", "emitir das",
        "verificar situação", "consulta cadastral", "situação cadastral",
        "consultar situação", "fazer a consulta", "fazer consulta",
        "pode consultar", "quero consultar", "preciso consultar",
        "pode acessar", "pode verificar", "pode emitir",
        "me ajuda a acessar", "me ajude a acessar",
        "quero acessar", "quero emitir", "quero gerar",
        "pesquisar no site", "buscar no site", "buscar cpf",
        "nota fiscal eletrônica", "nfs-e", "nfse",
        "certificado digital", "e-cac", "ecac",
        "pgmei", "regularizar", "parcelar",
    ]

    keyword_match = any(kw in msg for kw in automation_keywords)

    # ── Fase 2: Se keyword não bateu, tentar classificação LLM ───
    if not keyword_match:
        try:
            llm_detected = _llm_classify_automation(message)
            if not llm_detected:
                return None
        except Exception as e:
            logger.debug(f"LLM classification fallback: {e}")
            return None

    # ── Fase 3: Identificar site/serviço ─────────────────────────
    site_hints = {
        "receita federal": "receita_federal",
        "consultar cpf": "receita_federal",
        "consultar cnpj": "receita_federal",
        "cpf": "receita_federal",
        "cnpj": "receita_federal",
        "situação cadastral": "receita_federal",
        "consulta cadastral": "receita_federal",
        "e-cac": "receita_federal",
        "ecac": "receita_federal",
        "simples nacional": "simples_nacional",
        "das ": "simples_nacional",
        "dasn": "simples_nacional",
        "pgmei": "simples_nacional",
        "gerar das": "simples_nacional",
        "pagar das": "simples_nacional",
        "emitir das": "simples_nacional",
        "parcelar": "simples_nacional",
        "regularizar": "simples_nacional",
        "prefeitura": "prefeitura",
        "nota fiscal": "prefeitura_nf",
        "nfs-e": "prefeitura_nf",
        "nfse": "prefeitura_nf",
        "emitir nf": "prefeitura_nf",
        "nota fiscal eletrônica": "prefeitura_nf",
        "instagram": "instagram",
        "gov.br": "gov_br",
    }

    site_hint = "generico"
    for keyword, site in site_hints.items():
        if keyword in msg:
            site_hint = site
            break

    return {"goal": message, "site_hint": site_hint}


def _llm_classify_automation(message: str) -> bool:
    """Usa o LLM para classificar se a mensagem é um pedido de automação web.
    Retorna True se for automação, False caso contrário.
    Chamada rápida com max_tokens baixo.
    """
    try:
        from app.api.agent_chat import get_openai_client

        client = get_openai_client()
        if not client:
            return False

        classification_prompt = """Você é um classificador binário. Analise a mensagem do usuário e responda APENAS "SIM" ou "NAO".

Responda "SIM" se o usuário está pedindo para:
- Acessar, abrir ou navegar em um site ou portal
- Consultar algo em um site do governo (CPF, CNPJ, DAS, nota fiscal)
- Preencher formulário online
- Emitir documento eletrônico (nota fiscal, boleto, DAS)
- Fazer qualquer tarefa que envolva controlar um navegador web
- Realizar ação automatizada em um site ou sistema online

Responda "NAO" se o usuário está:
- Fazendo uma pergunta informacional (ex: "o que é CPF?", "quando vence o DAS?")
- Pedindo dica, explicação ou orientação teórica
- Conversando normalmente sem querer ação prática em site
- Pedindo para calcular, listar ou resumir algo do sistema interno

Mensagem:"""

        response = client.chat_completion(
            messages=[
                {"role": "system", "content": classification_prompt},
                {"role": "user", "content": message},
            ],
            temperature=0.0,
            max_tokens=5,
        )

        answer = response.strip().upper().replace(".", "")
        return answer in ("SIM", "YES", "S")

    except Exception as e:
        logger.debug(f"LLM classification error: {e}")
        return False


async def _generate_automation_plan(goal: str, site_hint: str) -> dict[str, Any]:
    """Usa o LLM para gerar um plano de automação estruturado."""
    try:
        from app.api.agent_chat import get_openai_client

        client = get_openai_client()
        if not client:
            return _fallback_plan(goal, site_hint)

        system_prompt = f"""Você é o planejador de automação do NEXUS.
O usuário quer automatizar uma tarefa web. Gere um plano de ações SEGURO.

REGRAS:
1. Responda APENAS com JSON válido
2. Cada passo deve ter: step (número), action (tipo), description (pt-BR), params
3. NUNCA inclua senhas, tokens ou dados sensíveis
4. Ações disponíveis: navigate, click, type, wait, screenshot, read_text
5. Inclua "risk_level": low|medium|high baseado nas ações

Site/serviço detectado: {site_hint}

Formato:
{{
    "plan_summary": "Resumo do plano em português simples",
    "risk_level": "low|medium|high",
    "steps": [
        {{"step": 1, "action": "navigate", "description": "Abrir site X", "params": {{"url": "..."}}}}
    ]
}}
"""

        response = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Objetivo: {goal}"},
            ],
            temperature=0.2,
            max_tokens=600,
        )

        # Parse JSON da resposta
        import json
        # Limpar possíveis marcas de código
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1]
            if clean.endswith("```"):
                clean = clean[:-3]
        plan = json.loads(clean)
        return plan

    except Exception as e:
        logger.warning(f"Erro ao gerar plano via LLM: {e}")
        return _fallback_plan(goal, site_hint)


def _fallback_plan(goal: str, site_hint: str) -> dict[str, Any]:
    """Plano de fallback quando o LLM não está disponível."""
    plans: dict[str, dict[str, Any]] = {
        "receita_federal": {
            "plan_summary": "Consulta de situação cadastral do CPF na Receita Federal",
            "risk_level": "low",
            "steps": [
                {"step": 1, "action": "navigate", "description": "Abrir site da Receita Federal — Consulta CPF", "params": {"url": "https://servicos.receita.fazenda.gov.br/Servicos/CPF/ConsultaSituacao/ConsultaPublica.asp"}},
                {"step": 2, "action": "wait", "description": "Aguardar carregamento da página", "params": {"seconds": 2}},
                {"step": 3, "action": "screenshot", "description": "Capturar tela para verificação", "params": {}},
                {"step": 4, "action": "read_text", "description": "Ler conteúdo da página para orientar próximos passos", "params": {"selector": "body"}},
            ],
        },
        "simples_nacional": {
            "plan_summary": "Acesso ao Portal do Simples Nacional para consulta",
            "risk_level": "medium",
            "steps": [
                {"step": 1, "action": "navigate", "description": "Abrir Portal do Simples Nacional", "params": {"url": "https://www8.receita.fazenda.gov.br/SimplesNacional/"}},
                {"step": 2, "action": "wait", "description": "Aguardar carregamento", "params": {"seconds": 2}},
                {"step": 3, "action": "screenshot", "description": "Capturar tela para verificação", "params": {}},
            ],
        },
    }

    default_plan = {
        "plan_summary": f"Automação: {goal[:100]}",
        "risk_level": "medium",
        "steps": [
            {"step": 1, "action": "navigate", "description": "Abrir o site solicitado", "params": {"url": ""}},
            {"step": 2, "action": "screenshot", "description": "Capturar tela para verificação", "params": {}},
        ],
    }

    return plans.get(site_hint, default_plan)


def _format_plan_for_chat(plan: dict[str, Any]) -> str:
    """Formata o plano como mensagem amigável para o chat."""
    risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
    risk = plan.get("risk_level", "medium")

    lines = [
        f"🤖 **Plano de Automação**",
        f"",
        f"📋 {plan.get('plan_summary', 'Automação solicitada')}",
        f"",
        f"**Passos que vou executar:**",
    ]

    for step in plan.get("steps", []):
        num = step.get("step", "?")
        desc = step.get("description", "")
        lines.append(f"{num}. {desc}")

    lines.extend([
        f"",
        f"Risco: {risk_emoji.get(risk, '⚪')} **{risk.upper()}**",
        f"",
        f"⚠️ **Nenhuma senha ou dado sensível será incluído.**",
        f"Vou abrir o navegador e executar as ações acima.",
        f"",
        f"Posso prosseguir?",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Execução real via Orchestrator
# ---------------------------------------------------------------------------

async def _execute_automation(task: dict[str, Any]) -> dict[str, Any]:
    """Executa o plano de automação via orchestrator LangGraph."""
    try:
        from backend.orchestrator.graph import run_task

        result = await run_task(
            agent_type="browser",
            user_id=task.get("user_id", 1),
            goal=task.get("goal", ""),
            original_message=task.get("message", ""),
            max_iterations=5,
            max_steps=len(task.get("steps", [])) + 5,
            site_config=task.get("site_config"),
        )

        return result

    except Exception as e:
        logger.error(f"Erro na execução da automação: {e}", exc_info=True)

        # Fallback: execução direta via browser tools
        return await _execute_direct(task)


async def _execute_direct(task: dict[str, Any]) -> dict[str, Any]:
    """Fallback: executa passos diretamente via Playwright (sem orchestrator)."""
    results: list[dict[str, Any]] = []
    try:
        from backend.orchestrator.tools.browser import (
            browser_navigate, browser_click, browser_type,
            browser_wait, browser_screenshot, browser_get_text,
            shutdown_browser,
        )

        dummy_state = {}  # type: ignore[arg-type]

        for step in task.get("steps", []):
            action = step.get("action", "")
            params = step.get("params", {})

            try:
                if action == "navigate":
                    r = browser_navigate(params, dummy_state)
                elif action == "click":
                    r = browser_click(params, dummy_state)
                elif action == "type":
                    r = browser_type(params, dummy_state)
                elif action == "wait":
                    r = browser_wait({"seconds": params.get("seconds", 2)}, dummy_state)
                elif action == "screenshot":
                    r = browser_screenshot(params, dummy_state)
                elif action == "read_text":
                    r = browser_get_text(params, dummy_state)
                else:
                    r = {"success": False, "error": f"Ação desconhecida: {action}"}

                results.append({"step": step.get("step"), "action": action, **r})

                if not r.get("success", False):
                    break

            except Exception as e:
                results.append({"step": step.get("step"), "action": action, "success": False, "error": str(e)})
                break

        # Fechar browser ao final
        try:
            shutdown_browser()
        except Exception:
            pass

        all_ok = all(r.get("success", False) for r in results)
        return {
            "task_id": task.get("task_id", "unknown"),
            "status": "completed" if all_ok else "partial",
            "final_response": _format_results_for_chat(results),
            "action_results": results,
        }

    except ImportError as e:
        logger.error(f"Playwright não disponível: {e}")
        return {
            "task_id": task.get("task_id", "unknown"),
            "status": "failed",
            "final_response": "⚠️ O Playwright não está instalado. Execute: `npx playwright install chromium`",
            "action_results": [],
        }
    except Exception as e:
        logger.error(f"Erro na execução direta: {e}", exc_info=True)
        return {
            "task_id": task.get("task_id", "unknown"),
            "status": "failed",
            "final_response": f"⚠️ Erro durante a automação: {str(e)}",
            "action_results": [],
        }


def _format_results_for_chat(results: list[dict[str, Any]]) -> str:
    """Formata resultados da automação para o chat."""
    if not results:
        return "⚠️ Nenhum passo foi executado."

    lines = ["🤖 **Resultado da Automação**\n"]
    for r in results:
        step = r.get("step", "?")
        action = r.get("action", "?")
        ok = r.get("success", False)
        emoji = "✅" if ok else "❌"
        msg = r.get("message", r.get("error", ""))

        lines.append(f"{emoji} Passo {step} ({action}): {msg}")

    all_ok = all(r.get("success", False) for r in results)
    if all_ok:
        lines.append("\n🎉 **Automação concluída com sucesso!**")
    else:
        lines.append("\n⚠️ Alguns passos falharam. Verifique os detalhes acima.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=AutomationStartResponse)
async def start_automation(
    request: AutomationStartRequest,
    current_user: dict = Depends(get_current_user),
) -> AutomationStartResponse:
    """Inicia automação: gera plano e retorna para aprovação do usuário. Requer autenticação."""
    user_id = current_user["user_id"]
    return await _start_automation_core(request, user_id)


async def _start_automation_core(
    request: AutomationStartRequest,
    user_id: int,
) -> AutomationStartResponse:
    """Core logic para iniciar automação — chamável tanto pelo endpoint quanto por agent_hub."""
    task_id = f"auto_{uuid.uuid4().hex[:12]}"

    # Detectar site/serviço
    intent = _detect_automation_intent(request.goal or request.message)
    site_hint = intent["site_hint"] if intent else "generico"

    # Gerar plano via LLM
    plan = await _generate_automation_plan(request.goal, site_hint)

    # Formatar para o chat
    chat_message = _format_plan_for_chat(plan)

    # Salvar estado
    _automation_tasks[task_id] = {
        "task_id": task_id,
        "agent_id": request.agent_id,
        "user_id": user_id,
        "goal": request.goal,
        "message": request.message,
        "site_hint": site_hint,
        "plan": plan,
        "steps": plan.get("steps", []),
        "status": "awaiting_approval",
        "created_at": datetime.now().isoformat(),
    }

    return AutomationStartResponse(
        task_id=task_id,
        status="awaiting_approval",
        plan_summary=plan.get("plan_summary", ""),
        steps=plan.get("steps", []),
        risk_level=plan.get("risk_level", "medium"),
        message=chat_message,
    )


@router.post("/approve", response_model=AutomationResultResponse)
async def approve_automation(
    request: AutomationApproveRequest,
    current_user: dict = Depends(get_current_user),
) -> AutomationResultResponse:
    """Aprova e executa a automação, ou rejeita. Requer autenticação."""
    task = _automation_tasks.get(request.task_id)
    # Verificar que o usuário é o dono da task
    if task and task.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Você não tem permissão para esta automação")
    if not task:
        raise HTTPException(status_code=404, detail=f"Automação {request.task_id} não encontrada")

    if task["status"] != "awaiting_approval":
        raise HTTPException(status_code=400, detail=f"Automação já processada: {task['status']}")

    if not request.approved:
        task["status"] = "rejected"
        return AutomationResultResponse(
            task_id=request.task_id,
            status="rejected",
            message="🚫 Automação cancelada conforme solicitado.",
        )

    # Executar!
    task["status"] = "executing"
    logger.info(f"🚀 Executando automação {request.task_id}: {task['goal'][:80]}")

    result = await _execute_automation(task)

    task["status"] = result.get("status", "completed")
    task["result"] = result

    return AutomationResultResponse(
        task_id=request.task_id,
        status=result.get("status", "completed"),
        message=result.get("final_response", "Automação concluída."),
        action_results=result.get("action_results", []),
    )


@router.get("/status/{task_id}")
async def automation_status(
    task_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Retorna status de uma automação. Requer autenticação."""
    task = _automation_tasks.get(task_id)
    # Verificar que o usuário é o dono da task
    if task and task.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Você não tem permissão para esta automação")
    if not task:
        raise HTTPException(status_code=404, detail=f"Automação {task_id} não encontrada")

    return {
        "task_id": task_id,
        "status": task["status"],
        "goal": task.get("goal", ""),
        "created_at": task.get("created_at"),
        "plan_summary": task.get("plan", {}).get("plan_summary", ""),
    }
