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
from typing import Any, Optional

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
# Estado das automações pendentes (Tier 2.4.7-bugfix)
# ---------------------------------------------------------------------------
# DB-first storage. Fallback dict in-memory APENAS em dev/local (env !=
# production) se DB indisponivel. Em prod, DB e fonte unica — falha = 500
# + Sentry capture, NUNCA cai silenciosamente pra memoria (que quebrava o
# bug original de multi-worker).
_automation_tasks: dict[str, dict[str, Any]] = {}  # dev-only fallback

# Rate limit para automações (por user_id)
_automation_rate: dict[int, list[float]] = {}  # user_id -> [timestamps]
_AUTOMATION_MAX_PER_HOUR = 10
_AUTOMATION_WINDOW_SECONDS = 3600


# ---------------------------------------------------------------------------
# Storage helpers (Tier 2.4.7-bugfix) — DB-first com compat dev-only
# ---------------------------------------------------------------------------

def _is_production() -> bool:
    """True se ENVIRONMENT=production (caso contrario eh dev/test/staging)."""
    import os
    return (os.getenv("ENVIRONMENT") or "").lower() == "production"


def _task_to_dict(t: Any) -> dict[str, Any]:
    """Serializa AutomationTask -> dict (formato compat com codigo legacy in-memory).

    plan_json / site_config_json / result_json sao desserializados pra dict/list.
    """
    import json as _json
    return {
        "task_id": t.task_id,
        "agent_id": t.agent_id,
        "user_id": t.user_id,
        "goal": t.goal or "",
        "message": t.message or "",
        "site_hint": t.site_hint or "",
        "plan": _json.loads(t.plan_json) if t.plan_json else {},
        "steps": (_json.loads(t.plan_json).get("steps", []) if t.plan_json else []),
        "site_config": _json.loads(t.site_config_json) if t.site_config_json else None,
        "status": t.status or "awaiting_approval",
        "result": _json.loads(t.result_json) if t.result_json else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _save_automation_task(task_data: dict[str, Any]) -> None:
    """Persiste task no DB. Em dev, fallback in-memory se DB falhar."""
    import json as _json
    try:
        from database.models import SessionLocal, AutomationTask
        db = SessionLocal()
        try:
            existing = db.query(AutomationTask).filter(
                AutomationTask.task_id == task_data["task_id"]
            ).first()
            if existing:
                # Update parcial: mantem task_id/user_id/created_at; atualiza estado
                existing.status = task_data.get("status", existing.status)
                if "plan" in task_data:
                    existing.plan_json = _json.dumps(task_data["plan"])
                if "site_config" in task_data:
                    existing.site_config_json = _json.dumps(task_data["site_config"]) if task_data.get("site_config") else None
                if "result" in task_data:
                    existing.result_json = _json.dumps(task_data["result"]) if task_data.get("result") else None
            else:
                new_task = AutomationTask(
                    task_id=task_data["task_id"],
                    user_id=task_data["user_id"],
                    agent_id=task_data.get("agent_id"),
                    goal=task_data["goal"],
                    message=task_data.get("message"),
                    site_hint=task_data.get("site_hint"),
                    plan_json=_json.dumps(task_data.get("plan", {})),
                    site_config_json=(_json.dumps(task_data["site_config"]) if task_data.get("site_config") else None),
                    status=task_data.get("status", "awaiting_approval"),
                    result_json=(_json.dumps(task_data["result"]) if task_data.get("result") else None),
                )
                db.add(new_task)
            db.commit()
            return
        finally:
            db.close()
    except Exception as e:
        # PROD: nunca cai pra memoria. Loga + Sentry + propaga (caller decide 500).
        if _is_production():
            logger.error(f"AutomationTask save FALHOU em producao: {e}", exc_info=True)
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(e)
            except Exception:
                pass
            raise
        # DEV: fallback in-memory + warning
        logger.warning(f"DB indisponivel em DEV, fallback in-memory: {e}")
        _automation_tasks[task_data["task_id"]] = dict(task_data)


def _get_automation_task(task_id: str) -> Optional[dict[str, Any]]:
    """Busca task no DB. Em dev, fallback in-memory se DB falhar."""
    try:
        from database.models import SessionLocal, AutomationTask
        db = SessionLocal()
        try:
            t = db.query(AutomationTask).filter(AutomationTask.task_id == task_id).first()
            if t is None:
                return None
            return _task_to_dict(t)
        finally:
            db.close()
    except Exception as e:
        if _is_production():
            logger.error(f"AutomationTask get FALHOU em producao: {e}", exc_info=True)
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(e)
            except Exception:
                pass
            raise
        logger.warning(f"DB indisponivel em DEV, fallback in-memory: {e}")
        return _automation_tasks.get(task_id)


def _update_automation_task_status(
    task_id: str,
    status: str,
    result: dict[str, Any] | None = None,
) -> None:
    """Atualiza apenas status + result (operacao mais comum nos endpoints)."""
    import json as _json
    try:
        from database.models import SessionLocal, AutomationTask
        db = SessionLocal()
        try:
            t = db.query(AutomationTask).filter(AutomationTask.task_id == task_id).first()
            if t is not None:
                t.status = status
                if result is not None:
                    t.result_json = _json.dumps(result)
                db.commit()
                return
        finally:
            db.close()
    except Exception as e:
        if _is_production():
            logger.error(f"AutomationTask update FALHOU em producao: {e}", exc_info=True)
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(e)
            except Exception:
                pass
            raise
        logger.warning(f"DB indisponivel em DEV, fallback in-memory: {e}")
        existing = _automation_tasks.get(task_id)
        if existing is not None:
            existing["status"] = status
            if result is not None:
                existing["result"] = result


def _check_automation_rate_limit(user_id: int) -> None:
    """Verifica rate limit de automações por usuário. Máx 10/hora."""
    import time
    now = time.time()
    window = now - _AUTOMATION_WINDOW_SECONDS
    timestamps = _automation_rate.get(user_id, [])
    timestamps = [t for t in timestamps if t > window]
    if len(timestamps) >= _AUTOMATION_MAX_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "AUTOMATION_RATE_LIMIT",
                "message": f"Limite de {_AUTOMATION_MAX_PER_HOUR} automações por hora atingido. Tente novamente em alguns minutos.",
            },
        )
    timestamps.append(now)
    _automation_rate[user_id] = timestamps


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
    preview_screenshot: str | None = None  # PNG base64 (apenas em waiting_for_user)


class AutomationContinueRequest(BaseModel):
    """Requisição para continuar automação após input do usuário."""
    task_id: str


# ---------------------------------------------------------------------------
# Detecção de necessidade de input do usuário
# ---------------------------------------------------------------------------

_WAITING_KEYWORDS = [
    "credenciais", "login", "senha", "autenticação", "autenticar",
    "entrar com", "fazer login", "insira", "digite seus",
    "preencha seus", "usuário e senha", "faça login",
    "dados de acesso", "identificação", "seus dados", "efetuar login",
    "realizar login", "acesse com", "entre com", "tela de login",
    "formulário de login", "página de login",
    # HIL — human-in-the-loop
    "agora é a parte que só você pode fazer",
    "agora é com você",
    "anti-robô", "anti-robo", "captcha",
]


def _capture_preview_screenshot(user_id: int) -> str | None:
    """Captura screenshot da pagina ativa do usuario em base64 (PNG completo).

    Usado para mostrar ao usuario qual tela ele precisa preencher quando a
    automacao fica em waiting_for_user. Diferente de browser_screenshot
    (que trunca pra 100 chars no result do tool), aqui retornamos o b64
    inteiro pra renderizar como <img> no chat.

    Returns:
        String base64 (sem prefixo data:image), ou None se falhou.
    """
    try:
        import base64
        from browser.pool import BrowserPool

        pool = BrowserPool.get_instance()
        if not pool.has_session(user_id):
            return None
        page = pool.get_page(user_id)
        png_bytes = page.screenshot(type="png", full_page=False)
        return base64.b64encode(png_bytes).decode("utf-8")
    except Exception as e:
        logger.warning(f"Falha ao capturar preview screenshot para user {user_id}: {e}")
        return None


def _detect_waiting_for_user(result: dict[str, Any]) -> bool:
    """Detecta se o resultado da automação indica que precisa de input do usuário."""
    # 1. Orquestrador já sinalizou via status
    if result.get("status") == "waiting_for_user":
        return True

    final_resp = (result.get("final_response") or "").lower()
    # 2. Resposta menciona credenciais / login
    if any(kw in final_resp for kw in _WAITING_KEYWORDS):
        return True

    # 3. Resultado de percepção detectou login page ou wait_for_user_login
    for r in result.get("action_results", []):
        # Detecção via tool wait_for_user_login
        if r.get("tool") == "wait_for_user_login":
            return True
        output = r.get("output")
        if isinstance(output, dict):
            # Flag explícita de waiting_for_user
            if output.get("waiting_for_user"):
                return True
            ps = output.get("page_state", {})
            if isinstance(ps, dict) and ps.get("page_type") == "login":
                return True
    return False


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
        "receita federal": "receita_federal_cpf",
        "consultar cpf": "receita_federal_cpf",
        "consultar cnpj": "receita_federal_cnpj",
        "cpf": "receita_federal_cpf",
        "cnpj": "receita_federal_cnpj",
        "situação cadastral": "receita_federal_cpf",
        "consulta cadastral": "receita_federal_cpf",
        "e-cac": "ecac",
        "ecac": "ecac",
        "simples nacional": "simples_nacional",
        "das ": "pgmei_das",
        "dasn": "simples_nacional",
        "pgmei": "pgmei_das",
        "gerar das": "pgmei_das",
        "pagar das": "pgmei_das",
        "emitir das": "pgmei_das",
        "parcelar": "simples_nacional",
        "regularizar": "simples_nacional",
        "prefeitura": "prefeitura_nfse",
        "nota fiscal": "prefeitura_nfse",
        "nfs-e": "prefeitura_nfse",
        "nfse": "prefeitura_nfse",
        "emitir nf": "prefeitura_nfse",
        "nota fiscal eletrônica": "prefeitura_nfse",
        "instagram": "generico",
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

        _model = "gpt-4o-mini"
        import time as _t
        _track_t0 = _t.time()
        response = client.chat.completions.create(
            model=_model,
            messages=[
                {"role": "system", "content": classification_prompt},
                {"role": "user", "content": message},
            ],
            temperature=0.0,
            max_tokens=5,
        )
        try:
            from helpers.openai_tracking import track_openai_response
            track_openai_response(response, _model, _track_t0, agent_type_override="automation_classifier")
        except Exception:
            pass

        answer = (response.choices[0].message.content or "").strip().upper().replace(".", "")
        return answer in ("SIM", "YES", "S")

    except Exception as e:
        logger.debug(f"LLM classification error: {e}")
        return False


async def _generate_automation_plan(goal: str, site_hint: str) -> dict[str, Any]:
    """Usa o LLM para gerar um plano de automação estruturado.
    
    Integra templates MEI para enriquecer o contexto do planner.
    """
    try:
        from app.api.agent_chat import get_openai_client

        client = get_openai_client()
        if not client:
            return _fallback_plan(goal, site_hint)

        # Carregar template específico
        template_context = ""
        try:
            from orchestrator.templates import get_template, format_template_for_llm
            template = get_template(site_hint)
            template_context = format_template_for_llm(template, goal)
        except Exception as e:
            logger.debug(f"Templates não disponíveis: {e}")

        system_prompt = f"""Você é o planejador de automação do NEXUS.
O usuário quer automatizar uma tarefa web. Gere um plano de ações SEGURO.

REGRAS:
1. Responda APENAS com JSON válido
2. Cada passo deve ter: step (número), action (tipo), description (pt-BR), params
3. NUNCA inclua senhas, tokens ou dados sensíveis
4. Actions disponíveis: navigate, click, type, wait, screenshot, read_text,
   scroll, hover, select_option, check_checkbox, submit_form, upload_file,
   go_back, go_forward, get_page_state, extract_table, find_by_text,
   evaluate_js, get_attribute
5. Inclua "risk_level": low|medium|high baseado nas ações
6. SEMPRE inclua get_page_state após navigate para "enxergar" a página
7. Se o site requer login, inclua passo para PARAR e avisar o usuário

Site/serviço detectado: {site_hint}

{template_context}

Formato:
{{
    "plan_summary": "Resumo do plano em português simples",
    "risk_level": "low|medium|high",
    "steps": [
        {{"step": 1, "action": "navigate", "description": "Abrir site X", "params": {{"url": "..."}}}}
    ]
}}
"""

        _model = "gpt-4o-mini"
        import time as _t
        _track_t0 = _t.time()
        response = client.chat.completions.create(
            model=_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Objetivo: {goal}"},
            ],
            temperature=0.2,
            max_tokens=600,
        )
        try:
            from helpers.openai_tracking import track_openai_response
            track_openai_response(response, _model, _track_t0, agent_type_override="automation_planner")
        except Exception:
            pass

        # Parse JSON da resposta
        import json
        # Limpar possíveis marcas de código
        clean = (response.choices[0].message.content or "").strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1]
            if clean.endswith("```"):
                clean = clean[:-3]
        plan = json.loads(clean)

        # ── Pós-processamento: forçar URL do template no primeiro navigate ──
        # O LLM pode inventar URLs. A URL real vem do template e é canon.
        try:
            from orchestrator.templates import get_template as _gt
            tpl = _gt(site_hint)
            canonical_url = tpl.get("site_config", {}).get("url", "")
            if canonical_url:
                for step in plan.get("steps", []):
                    if step.get("action") == "navigate":
                        old_url = step.get("params", {}).get("url", "")
                        if old_url != canonical_url:
                            logger.info(
                                f"URL corrigida no plano: {old_url[:80]} -> {canonical_url[:80]}"
                            )
                            step["params"]["url"] = canonical_url
                        break  # corrigir apenas o primeiro navigate
        except Exception:
            pass

        return plan

    except Exception as e:
        logger.warning(f"Erro ao gerar plano via LLM: {e}")
        return _fallback_plan(goal, site_hint)


def _fallback_plan(goal: str, site_hint: str) -> dict[str, Any]:
    """Plano de fallback quando o LLM não está disponível.
    
    Usa templates MEI para gerar planos estruturados sem LLM.
    """
    try:
        from orchestrator.templates import get_template
        template = get_template(site_hint)

        url = template["site_config"].get("url", "")
        steps = []
        step_num = 1

        # Passo 1: Navegar
        if url:
            steps.append({
                "step": step_num, "action": "navigate",
                "description": f"Abrir {template['site_config']['name']}",
                "params": {"url": url},
            })
            step_num += 1

        # Passo 2: Aguardar
        steps.append({
            "step": step_num, "action": "wait",
            "description": "Aguardar carregamento da página",
            "params": {"seconds": 2},
        })
        step_num += 1

        # Passo 3: Percepção (estilo Comet — capturar estado)
        steps.append({
            "step": step_num, "action": "get_page_state",
            "description": "Capturar estado da página (elementos interativos)",
            "params": {},
        })
        step_num += 1

        # Passo 4: Screenshot
        steps.append({
            "step": step_num, "action": "screenshot",
            "description": "Capturar tela para verificação",
            "params": {},
        })
        step_num += 1

        # Passo 5: Ler texto
        steps.append({
            "step": step_num, "action": "read_text",
            "description": "Ler conteúdo da página para orientar próximos passos",
            "params": {"selector": "body"},
        })

        return {
            "plan_summary": template["goal"],
            "risk_level": template.get("risk_level", "medium"),
            "steps": steps,
        }

    except Exception:
        # Ultra-fallback se templates falharem
        return {
            "plan_summary": f"Automação: {goal[:100]}",
            "risk_level": "medium",
            "steps": [
                {"step": 1, "action": "navigate", "description": "Abrir o site solicitado", "params": {"url": ""}},
                {"step": 2, "action": "get_page_state", "description": "Capturar estado da página", "params": {}},
                {"step": 3, "action": "screenshot", "description": "Capturar tela para verificação", "params": {}},
            ],
        }


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
    """Executa o plano de automação via orchestrator LangGraph.
    
    Tenta o orchestrator completo (sense→plan→policy→act→check).
    Se falhar, usa execução direta dos passos via Playwright.
    """
    try:
        # Forçar import das browser tools para registro no act_node
        import orchestrator.tools.browser  # noqa: F401
        from orchestrator.graph import run_task

        result = await run_task(
            agent_type="browser",
            user_id=task.get("user_id", 1),
            goal=task.get("goal", ""),
            original_message=task.get("message", ""),
            max_iterations=12,
            max_steps=len(task.get("steps", [])) + 5,
            site_config=task.get("site_config"),
        )

        # Verificar se o orchestrator realmente executou algo
        action_results = result.get("action_results", [])
        browser_actions = [r for r in action_results if r.get("tool", "").startswith("browser_")]
        
        if not browser_actions and result.get("status") not in ("failed", "waiting_for_user"):
            logger.warning("Orchestrador completou sem ações de browser — tentando execução direta")
            return await _execute_direct(task)

        # Detectar circuit breaker aberto: se qualquer ação foi bloqueada
        # pelo circuit breaker, comunicar ao usuário com retry estimado.
        circuit_step = next(
            (
                r for r in action_results
                if isinstance(r, dict) and (
                    r.get("circuit_open")
                    or (isinstance(r.get("output"), dict) and r.get("output", {}).get("circuit_open"))
                )
            ),
            None,
        )
        if circuit_step:
            output = circuit_step.get("output") if isinstance(circuit_step.get("output"), dict) else circuit_step
            retry_in = int(output.get("retry_in_seconds") or 0)
            domain = output.get("domain") or "esse site"
            retry_min = max(1, retry_in // 60)
            result["status"] = "circuit_open"
            result["final_response"] = (
                f"⚡ **{domain} está com instabilidade no momento.**\n\n"
                f"Para proteger sua conta, pausei tentativas por aproximadamente "
                f"{retry_min} min. Tente novamente depois — a automação volta automaticamente."
            )
            return result

        # Detectar se precisa de input do usuário (login/credenciais)
        if _detect_waiting_for_user(result):
            result["status"] = "waiting_for_user"
            resp = result.get("final_response", "")
            # Se a resposta já veio com linguagem clara do wait_for_user_login, usar como está
            # Caso contrário, adicionar instrução padrão
            if "Continuar Automação" not in resp:
                result["final_response"] = (
                    resp.rstrip()
                    + "\n\n🔒 **Agora é a parte que só você pode fazer.**"
                    + "\n\n1. Olhe para a tela do site que abrimos."
                    + "\n2. Digite seus dados (CPF, data de nascimento, senha — o que for pedido)."
                    + "\n3. Clique no botão do site (ex: 'Consultar', 'Entrar')."
                    + "\n4. Quando a próxima tela aparecer, volte aqui e clique no botão abaixo."
                    + "\n\n💡 *O robô não vê nem guarda seu CPF ou senha. Isso é só entre você e o site.*"
                    + "\n\n🔄 Clique em **Continuar Automação** quando estiver pronto."
                )
            # Preview screenshot pra mostrar ao usuario qual tela preencher
            if not result.get("preview_screenshot"):
                try:
                    import asyncio as _asyncio
                    result["preview_screenshot"] = await _asyncio.to_thread(
                        _capture_preview_screenshot, task.get("user_id", 0)
                    )
                except Exception:
                    result["preview_screenshot"] = None

        return result

    except Exception as e:
        logger.error(f"Erro na execução da automação: {e}", exc_info=True)

        # Fallback: execução direta via browser tools
        return await _execute_direct(task)


async def _execute_direct(task: dict[str, Any]) -> dict[str, Any]:
    """Fallback: executa passos diretamente via Playwright (sem orchestrator).

    Roda sync Playwright via asyncio.to_thread para não bloquear o event loop.
    """
    import asyncio
    import time as _time

    # Audit: lifecycle events para a fallback path (orchestrator path ja audita
    # via run_task → TaskContext). Aqui garantimos correlation_id+events.
    _task_id_for_audit = task.get("task_id") or f"auto_{uuid.uuid4().hex[:12]}"
    _user_id_for_audit = task.get("user_id", 0)
    _t_start = _time.time()
    _audit_ctx = None
    try:
        from utils.automation_logger import AutomationLogger, TaskContext
        _audit_ctx = TaskContext(
            task_id=_task_id_for_audit,
            user_id=_user_id_for_audit,
            agent_type="browser",
        )
        _audit_ctx.__enter__()
        AutomationLogger.task_started(
            goal=task.get("goal", ""),
            max_iterations=1,
            thread_id=_task_id_for_audit,
            mode="direct_fallback",
        )
    except Exception:
        AutomationLogger = None  # type: ignore[assignment]

    # Sentry user context
    try:
        from app.api.monitoring import set_user_context
        set_user_context(user_id=_user_id_for_audit, extra={"task_id": _task_id_for_audit, "mode": "direct_fallback"})
    except Exception:
        pass

    def _run_steps_sync() -> tuple[list[dict[str, Any]], bool, bool]:
        """Execução síncrona dos passos Playwright.
        
        Returns:
            (results, all_ok, needs_user_input)
        """
        results: list[dict[str, Any]] = []
        needs_user_input = False
        try:
            from orchestrator.tools.browser import (
                browser_navigate, browser_click, browser_type,
                browser_wait, browser_screenshot, browser_get_text,
                browser_scroll, browser_hover, browser_select_option,
                browser_check_checkbox, browser_submit_form, browser_go_back,
                browser_go_forward, browser_get_attribute, browser_extract_table,
                browser_find_by_text, browser_evaluate_js, browser_get_page_state,
                shutdown_browser,
            )

            # State mínimo para as browser tools
            minimal_state = {
                "user_id": task.get("user_id", 1),
                "goal": task.get("goal", ""),
                "agent_type": "browser",
            }

            # Mapa de ações para funções
            action_map = {
                "navigate": browser_navigate,
                "click": browser_click,
                "type": browser_type,
                "wait": lambda params, state: browser_wait({"seconds": params.get("seconds", 2)}, state),
                "screenshot": browser_screenshot,
                "read_text": browser_get_text,
                "scroll": browser_scroll,
                "hover": browser_hover,
                "select_option": browser_select_option,
                "check_checkbox": browser_check_checkbox,
                "submit_form": browser_submit_form,
                "go_back": browser_go_back,
                "go_forward": browser_go_forward,
                "get_attribute": browser_get_attribute,
                "extract_table": browser_extract_table,
                "find_by_text": browser_find_by_text,
                "evaluate_js": browser_evaluate_js,
                "get_page_state": browser_get_page_state,
            }

            for step in task.get("steps", []):
                action = step.get("action", "")
                params = step.get("params", {})

                try:
                    handler = action_map.get(action)
                    if handler:
                        r = handler(params, minimal_state)
                    else:
                        r = {"success": False, "error": f"Ação desconhecida: {action}"}

                    results.append({"step": step.get("step"), "action": action, **r})

                    # Circuit breaker: domain bloqueado por falhas repetidas →
                    # parar imediatamente com retry_in_seconds para o usuario.
                    if isinstance(r, dict) and r.get("circuit_open"):
                        break

                    if not r.get("success", False):
                        break

                except Exception as e:
                    results.append({"step": step.get("step"), "action": action, "success": False, "error": str(e)})
                    break

            # Pós-execução: verificar se a página precisa de input do usuário
            try:
                ps_result = browser_get_page_state({}, minimal_state)
                if ps_result.get("success"):
                    ps = ps_result.get("page_state", {})
                    if isinstance(ps, dict) and ps.get("page_type") in ("login", "form"):
                        needs_user_input = True
            except Exception:
                pass

            # Só fechar browser se NÃO precisar de input do usuário.
            # Passar user_id para liberar somente a sessao desse usuario
            # (sem user_id, shutdown_browser fecharia o pool inteiro).
            if not needs_user_input:
                try:
                    shutdown_browser(user_id=task.get("user_id", 0), close=True)
                except Exception:
                    pass

            all_ok = all(r.get("success", False) for r in results)
            return results, all_ok, needs_user_input

        except ImportError as e:
            logger.error(f"Playwright não disponível: {e}")
            return [{"step": 0, "action": "import", "success": False, "error": str(e)}], False, False
        except Exception as e:
            logger.error(f"Erro na execução direta: {e}", exc_info=True)
            return [{"step": 0, "action": "error", "success": False, "error": str(e)}], False, False

    # Executar em thread separada para não bloquear o event loop async
    try:
        results, all_ok, needs_user_input = await asyncio.to_thread(_run_steps_sync)
    except Exception as e:
        logger.error(f"Erro ao executar em thread: {e}")
        results = [{"step": 0, "action": "thread", "success": False, "error": str(e)}]
        all_ok = False
        needs_user_input = False

    # Circuit breaker — detectar e formatar mensagem amigavel
    circuit_open_step = next(
        (r for r in results if isinstance(r, dict) and r.get("circuit_open")),
        None,
    )

    if circuit_open_step:
        retry_in = int(circuit_open_step.get("retry_in_seconds") or 0)
        domain = circuit_open_step.get("domain") or "esse site"
        retry_min = max(1, retry_in // 60)
        status = "circuit_open"
        message = (
            f"⚡ **{domain} está com instabilidade no momento.**\n\n"
            f"Para proteger sua conta, pausei tentativas por aproximadamente "
            f"{retry_min} min. Tente novamente depois — a automação volta automaticamente."
        )
    elif needs_user_input:
        status = "waiting_for_user"
        message = (
            _format_results_for_chat(results)
            + "\n\n🔒 **Agora é a parte que só você pode fazer.**"
            + "\n\n1. Olhe para a tela do site que abrimos."
            + "\n2. Digite seus dados (CPF, data de nascimento, senha — o que for pedido)."
            + "\n3. Clique no botão do site (ex: 'Consultar', 'Entrar')."
            + "\n4. Quando a próxima tela aparecer, volte aqui e clique no botão abaixo."
            + "\n\n💡 *O robô não vê nem guarda seu CPF ou senha. Isso é só entre você e o site.*"
            + "\n\n🔄 Clique em **Continuar Automação** quando estiver pronto."
        )
    else:
        status = "completed" if all_ok else "partial"
        message = _format_results_for_chat(results)

    # Audit: task_completed (com awaiting flag se for o caso)
    duration_ms = int((_time.time() - _t_start) * 1000)
    if AutomationLogger is not None:
        try:
            AutomationLogger.task_completed(
                status=status,
                actions_count=len(results),
                duration_ms=duration_ms,
                awaiting_user_input=needs_user_input,
                circuit_open=bool(circuit_open_step),
            )
        except Exception:
            pass
    if _audit_ctx is not None:
        try:
            _audit_ctx.__exit__(None, None, None)
        except Exception:
            pass

    # Preview screenshot apenas em waiting_for_user (browser ainda aberto)
    preview_b64: str | None = None
    if status == "waiting_for_user":
        try:
            preview_b64 = await asyncio.to_thread(
                _capture_preview_screenshot, task.get("user_id", 0)
            )
        except Exception:
            preview_b64 = None

    return {
        "task_id": task.get("task_id", "unknown"),
        "status": status,
        "final_response": message,
        "action_results": results,
        "preview_screenshot": preview_b64,
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
    # Rate limit: máximo 10 automações/hora por usuário
    _check_automation_rate_limit(user_id)

    task_id = f"auto_{uuid.uuid4().hex[:12]}"

    # Detectar site/serviço
    intent = _detect_automation_intent(request.goal or request.message)
    site_hint = intent["site_hint"] if intent else "generico"

    # Gerar plano via LLM
    plan = await _generate_automation_plan(request.goal, site_hint)

    # Formatar para o chat
    chat_message = _format_plan_for_chat(plan)

    # Carregar site_config do template (se disponível)
    site_config = None
    try:
        from orchestrator.templates import get_template
        template = get_template(site_hint)
        site_config = template.get("site_config")
    except Exception:
        pass

    # Persistir estado no DB (Tier 2.4.7-bugfix: compartilhado entre workers)
    _save_automation_task({
        "task_id": task_id,
        "agent_id": request.agent_id,
        "user_id": user_id,
        "goal": request.goal,
        "message": request.message,
        "site_hint": site_hint,
        "plan": plan,
        "site_config": site_config,
        "status": "awaiting_approval",
    })

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
    task = _get_automation_task(request.task_id)
    # Verificar que o usuário é o dono da task
    if task and task.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Você não tem permissão para esta automação")
    if not task:
        raise HTTPException(status_code=404, detail=f"Automação {request.task_id} não encontrada")

    if task["status"] != "awaiting_approval":
        raise HTTPException(status_code=400, detail=f"Automação já processada: {task['status']}")

    if not request.approved:
        _update_automation_task_status(request.task_id, "rejected")
        return AutomationResultResponse(
            task_id=request.task_id,
            status="rejected",
            message="🚫 Automação cancelada conforme solicitado.",
        )

    # Executar!
    _update_automation_task_status(request.task_id, "executing")
    logger.info(f"🚀 Executando automação {request.task_id}: {task['goal'][:80]}")

    result = await _execute_automation(task)

    final_status = result.get("status", "completed")
    _update_automation_task_status(request.task_id, final_status, result=result)

    return AutomationResultResponse(
        task_id=request.task_id,
        status=result.get("status", "completed"),
        message=result.get("final_response", "Automação concluída."),
        action_results=result.get("action_results", []),
        preview_screenshot=result.get("preview_screenshot"),
    )


@router.get("/status/{task_id}")
async def automation_status(
    task_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Retorna status de uma automação. Requer autenticação."""
    task = _get_automation_task(task_id)
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


# ---------------------------------------------------------------------------
# Continuação: retomar automação após input do usuário (login, etc.)
# ---------------------------------------------------------------------------

@router.post("/continue", response_model=AutomationResultResponse)
async def continue_automation(
    request: AutomationContinueRequest,
    current_user: dict = Depends(get_current_user),
) -> AutomationResultResponse:
    """Retoma automação após o usuário inserir dados no browser (login, etc.).

    O browser permanece aberto desde a execução anterior. Este endpoint
    re-sente a página atual, re-planeja e executa os próximos passos.
    """
    task = _get_automation_task(request.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Automação não encontrada")
    if task.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para esta automação")
    if task["status"] != "waiting_for_user":
        raise HTTPException(
            status_code=400,
            detail=f"Automação não está aguardando continuação (status: {task['status']})",
        )

    _update_automation_task_status(request.task_id, "executing")
    logger.info(f"🔄 Continuando automação {request.task_id} após input do usuário")

    result = await _continue_automation(task)

    final_status = result.get("status", "completed")
    _update_automation_task_status(request.task_id, final_status, result=result)

    return AutomationResultResponse(
        task_id=request.task_id,
        status=result.get("status", "completed"),
        message=result.get("final_response", "Automação concluída."),
        action_results=result.get("action_results", []),
        preview_screenshot=result.get("preview_screenshot"),
    )


async def _continue_automation(task: dict[str, Any]) -> dict[str, Any]:
    """Continua automação: re-sensa a página e executa próximos passos.

    O browser já está aberto (não foi fechado na execução anterior).
    Tenta via orchestrator primeiro, depois fallback direto.
    
    O orchestrator vai:
    1. sense_node: capturar novo DOM (pós-login) e limpar flags de awaiting_user_input
    2. plan_node: planejar ações normais (sem wait_for_user_login, já que a tela mudou)
    3. act_node: executar ações (extrair dados, baixar PDF, etc.)
    """
    try:
        import orchestrator.tools.browser  # noqa: F401
        from orchestrator.graph import run_task

        # O goal é adaptado para indicar que o usuário já fez login
        continuation_goal = (
            f"Continuar a tarefa: {task.get('goal', '')}. "
            "O usuário já preencheu seus dados (CPF, senha, captcha, etc.) no navegador. "
            "A página agora deve estar diferente (pós-login/pós-consulta). "
            "Capture o estado atual da página e prossiga com o objetivo original: "
            "extrair informações, baixar comprovantes, copiar dados, etc."
        )

        result = await run_task(
            agent_type="browser",
            user_id=task.get("user_id", 1),
            goal=continuation_goal,
            original_message=task.get("message", ""),
            max_iterations=12,
            max_steps=15,
            site_config=task.get("site_config"),
        )

        # Verificar novamente se ainda precisa de input
        if _detect_waiting_for_user(result):
            result["status"] = "waiting_for_user"
            resp = result.get("final_response", "")
            if "Continuar Automação" not in resp:
                result["final_response"] = (
                    resp.rstrip()
                    + "\n\n🔄 Ainda é necessário completar ações no navegador. "
                    "Clique em **Continuar Automação** quando estiver pronto."
                )
            if not result.get("preview_screenshot"):
                try:
                    import asyncio as _asyncio
                    result["preview_screenshot"] = await _asyncio.to_thread(
                        _capture_preview_screenshot, task.get("user_id", 0)
                    )
                except Exception:
                    result["preview_screenshot"] = None
        else:
            # Automação concluída — fechar somente esta sessao
            try:
                from orchestrator.tools.browser import shutdown_browser
                shutdown_browser(user_id=task.get("user_id", 0), close=True)
            except Exception:
                pass
            
            # Adicionar mensagem de retomada bem-sucedida
            resp = result.get("final_response", "")
            if resp and "Continuar Automação" not in resp:
                result["final_response"] = (
                    "✅ **Beleza, já estou vendo a tela depois do seu login.**\n\n"
                    + resp
                )

        return result

    except Exception as e:
        logger.error(f"Erro ao continuar automação: {e}", exc_info=True)
        return await _continue_direct(task)


async def _continue_direct(task: dict[str, Any]) -> dict[str, Any]:
    """Fallback de continuação: captura estado atual + screenshot + responde."""
    import asyncio
    import time as _time

    _task_id_for_audit = task.get("task_id") or f"auto_{uuid.uuid4().hex[:12]}"
    _user_id_for_audit = task.get("user_id", 0)
    _t_start = _time.time()
    _audit_ctx = None
    try:
        from utils.automation_logger import AutomationLogger, TaskContext
        _audit_ctx = TaskContext(
            task_id=_task_id_for_audit,
            user_id=_user_id_for_audit,
            agent_type="browser",
        )
        _audit_ctx.__enter__()
        AutomationLogger.task_started(
            goal=f"continue: {task.get('goal', '')}",
            max_iterations=1,
            thread_id=_task_id_for_audit,
            mode="continue_direct",
        )
    except Exception:
        AutomationLogger = None  # type: ignore[assignment]

    try:
        from app.api.monitoring import set_user_context
        set_user_context(user_id=_user_id_for_audit, extra={"task_id": _task_id_for_audit, "mode": "continue_direct"})
    except Exception:
        pass

    def _sense_current_page() -> dict[str, Any]:
        from orchestrator.tools.browser import (
            browser_get_page_state,
            browser_screenshot,
            browser_get_text,
            shutdown_browser,
        )

        minimal_state = {
            "user_id": task.get("user_id", 1),
            "goal": task.get("goal", ""),
            "agent_type": "browser",
        }

        results: list[dict[str, Any]] = []
        page_text = ""
        page_state: dict[str, Any] = {}

        # 1. Capturar estado da página
        try:
            ps = browser_get_page_state({}, minimal_state)
            results.append({"step": 1, "action": "get_page_state", **ps})
            if ps.get("success"):
                page_state = ps.get("page_state", {})
        except Exception as ex:
            results.append({"step": 1, "action": "get_page_state", "success": False, "error": str(ex)})

        # 2. Screenshot
        try:
            ss = browser_screenshot({}, minimal_state)
            results.append({"step": 2, "action": "screenshot", **ss})
        except Exception as ex:
            results.append({"step": 2, "action": "screenshot", "success": False, "error": str(ex)})

        # 3. Ler texto
        try:
            txt = browser_get_text({"selector": "body"}, minimal_state)
            results.append({"step": 3, "action": "read_text", **txt})
            if txt.get("success"):
                page_text = txt.get("text", "")[:2000]
        except Exception as ex:
            results.append({"step": 3, "action": "read_text", "success": False, "error": str(ex)})

        # Fechar somente a sessao deste usuario (nao o pool inteiro)
        try:
            shutdown_browser(user_id=task.get("user_id", 0), close=True)
        except Exception:
            pass

        return {
            "results": results,
            "page_text": page_text,
            "page_state": page_state,
        }

    try:
        sense_data = await asyncio.to_thread(_sense_current_page)
    except Exception as e:
        logger.error(f"Erro ao sensar página para continuação: {e}")
        if AutomationLogger is not None:
            try:
                AutomationLogger.task_failed(
                    error=str(e),
                    status="failed",
                    duration_ms=int((_time.time() - _t_start) * 1000),
                )
            except Exception:
                pass
        if _audit_ctx is not None:
            try:
                _audit_ctx.__exit__(None, None, None)
            except Exception:
                pass
        return {
            "task_id": task.get("task_id", "unknown"),
            "status": "failed",
            "final_response": (
                "❌ Não consegui acessar o navegador. "
                "O browser pode ter sido fechado. Tente iniciar uma nova automação."
            ),
            "action_results": [],
        }

    # Usar LLM para interpretar a página capturada
    page_text = sense_data.get("page_text", "")
    page_state = sense_data.get("page_state", {})
    page_title = page_state.get("title", "")
    page_type = page_state.get("page_type", "")
    page_url = page_state.get("url", "")

    try:
        from app.api.agent_chat import get_openai_client

        client = get_openai_client()
        if client:
            _model = "gpt-4o-mini"
            import time as _t
            _track_t0 = _t.time()
            resp = client.chat.completions.create(
                model=_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Você é o assistente do NEXUS. O usuário pediu uma automação web. "
                            "Ele inseriu credenciais no navegador e você capturou a página atual. "
                            "Resuma o que a página mostra, se o login foi bem-sucedido, e oriente "
                            "o usuário sobre próximos passos. Seja conciso e amigável."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Objetivo original: {task.get('goal', '')}\n\n"
                            f"URL atual: {page_url}\n"
                            f"Título: {page_title}\n"
                            f"Tipo: {page_type}\n\n"
                            f"Texto da página (resumido):\n{page_text[:1500]}"
                        ),
                    },
                ],
                temperature=0.3,
                max_tokens=400,
            )
            try:
                from helpers.openai_tracking import track_openai_response
                track_openai_response(resp, _model, _track_t0,
                                      user_id_override=task.get("user_id", 0),
                                      agent_type_override="automation_continue")
            except Exception:
                pass
            message = resp.choices[0].message.content or ""
        else:
            message = (
                f"📄 Página capturada: **{page_title or 'Sem título'}**\n"
                f"🔗 URL: {page_url}\n\n"
                f"Texto: {page_text[:500]}"
            )
    except Exception:
        message = (
            f"📄 Página capturada: **{page_title or 'Sem título'}**\n"
            f"🔗 URL: {page_url}\n\n"
            f"Texto: {page_text[:500]}"
        )

    results = sense_data.get("results", [])
    if AutomationLogger is not None:
        try:
            AutomationLogger.task_completed(
                status="completed",
                actions_count=len(results),
                duration_ms=int((_time.time() - _t_start) * 1000),
                awaiting_user_input=False,
                mode="continue_direct",
            )
        except Exception:
            pass
    if _audit_ctx is not None:
        try:
            _audit_ctx.__exit__(None, None, None)
        except Exception:
            pass

    return {
        "task_id": task.get("task_id", "unknown"),
        "status": "completed",
        "final_response": message,
        "action_results": results,
    }
