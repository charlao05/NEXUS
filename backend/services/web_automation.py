"""
NEXUS - Assistente com Automação Web
======================================
Agente que planeja e executa tarefas web (abrir páginas, preencher formulários,
resolver pendências) COM APROVAÇÃO HUMANA obrigatória.

Fluxo inspirado em Comet/Atlas:
  1. Usuário solicita tarefa
  2. LLM gera plano detalhado de passos
  3. Plano é salvo como WebTask (status=pending)
  4. Usuário revisa e APROVA ou REJEITA
  5. Se aprovado, executa com Playwright + feedback em tempo real
  6. Resultado salvo para auditoria

Segurança: NUNCA executa sem aprovação. Credenciais ficam no .env, não no plano.
"""

from datetime import datetime
from typing import Optional
import json
import logging
import os

from database.models import WebTask, get_session

logger = logging.getLogger(__name__)


# ============================================================================
# PLANEJAMENTO — LLM gera o plano de automação
# ============================================================================

AUTOMATION_SYSTEM_PROMPT = """Você é o Assistente de Automação Web do NEXUS.
O usuário pediu para executar uma tarefa que envolve navegador/web.

Gere um PLANO DETALHADO de passos que o Playwright vai executar.
Use o formato JSON com a chave "steps", onde cada passo contém:
- "tipo": um de (open_url, click, type, wait_selector, wait_seconds, press_key)
- "descricao": descrição em português do que este passo faz
- "parametros": parâmetros do passo (url, selector, text, etc.)

REGRAS:
- NUNCA inclua senhas ou credenciais no plano. Use {{ENV:NOME_VARIAVEL}}.
- NUNCA faça ações destrutivas (deletar conta, apagar dados em massa).
- Sempre comece abrindo a URL com open_url.
- Inclua waits entre ações que dependem de carregamento.
- Descreva CLARAMENTE cada passo para o usuário revisar.

Exemplo de plano:
{
  "title": "Pagar DAS no Portal do Simples Nacional",
  "target_url": "http://www8.receita.fazenda.gov.br/simplesnacional",
  "estimated_time": "3 minutos",
  "risk_level": "baixo",
  "steps": [
    {"tipo": "open_url", "descricao": "Abrir portal do Simples Nacional", "parametros": {"url": "http://www8.receita.fazenda.gov.br/simplesnacional"}},
    {"tipo": "click", "descricao": "Clicar em PGMEI", "parametros": {"selector": "a[href*='pgmei']"}},
    {"tipo": "wait_seconds", "descricao": "Aguardar carregamento", "parametros": {"seconds": 3}},
    {"tipo": "type", "descricao": "Digitar CNPJ", "parametros": {"selector": "#cnpj", "text": "{{ENV:MEI_CNPJ}}"}}
  ]
}

DATA ATUAL: {date}
Responda APENAS com o JSON do plano, sem texto adicional."""


async def generate_automation_plan(user_message: str) -> dict:
    """Gera plano de automação via LLM"""
    try:
        from app.api.agent_chat import get_openai_client
        client = get_openai_client()
        if not client:
            return {"error": "OpenAI não disponível"}

        prompt = AUTOMATION_SYSTEM_PROMPT.format(
            date=datetime.now().strftime("%d/%m/%Y %H:%M")
        )

        response = client.chat_completion(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,  # Mais determinístico para planos
            max_tokens=1200,
        )

        # Tentar parsear JSON da resposta
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        plan = json.loads(text)
        return plan

    except json.JSONDecodeError:
        return {
            "title": "Plano não estruturado",
            "steps": [],
            "raw_response": response if 'response' in dir() else "Erro ao parsear",
        }
    except Exception as e:
        logger.error(f"Erro ao gerar plano: {e}")
        return {"error": str(e)}


# ============================================================================
# PERSISTÊNCIA — Salvar/buscar tarefas
# ============================================================================

def create_web_task(title: str, description: str, target_url: str, plan: dict) -> dict:
    """Salva tarefa de automação aguardando aprovação"""
    session = get_session()
    try:
        task = WebTask(
            title=title,
            description=description,
            target_url=target_url,
            plan_json=plan,
            status="pending",
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        logger.info(f"📋 WebTask #{task.id} criada: {title}")
        return task.to_dict()
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


def get_pending_tasks() -> list:
    """Lista tarefas aguardando aprovação"""
    session = get_session()
    try:
        tasks = session.query(WebTask).filter(
            WebTask.status == "pending"
        ).order_by(WebTask.created_at.desc()).all()
        return [t.to_dict() for t in tasks]
    finally:
        session.close()


def get_task(task_id: int) -> Optional[dict]:
    """Busca tarefa por ID"""
    session = get_session()
    try:
        task = session.query(WebTask).filter(WebTask.id == task_id).first()
        return task.to_dict() if task else None
    finally:
        session.close()


def approve_task(task_id: int, approved_by: str = "user") -> dict:
    """Aprova tarefa para execução"""
    session = get_session()
    try:
        task = session.query(WebTask).filter(WebTask.id == task_id).first()
        if not task:
            return {"status": "not_found"}
        if task.status != "pending":
            return {"status": "invalid", "message": f"Tarefa está em status: {task.status}"}
        task.status = "approved"
        task.approved_by = approved_by
        task.approved_at = datetime.utcnow()
        session.commit()
        logger.info(f"✅ WebTask #{task_id} APROVADA por {approved_by}")
        return {"status": "approved", "task": task.to_dict()}
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


def reject_task(task_id: int) -> dict:
    """Rejeita tarefa"""
    session = get_session()
    try:
        task = session.query(WebTask).filter(WebTask.id == task_id).first()
        if not task:
            return {"status": "not_found"}
        task.status = "cancelled"
        session.commit()
        return {"status": "cancelled"}
    finally:
        session.close()


# ============================================================================
# EXECUÇÃO — Playwright com feedback
# ============================================================================

def execute_approved_task(task_id: int) -> dict:
    """Executa tarefa APROVADA no navegador.
    NUNCA executa tarefa pendente ou não aprovada.
    """
    session = get_session()
    try:
        task = session.query(WebTask).filter(WebTask.id == task_id).first()
        if not task:
            return {"status": "not_found"}
        if task.status != "approved":
            return {"status": "not_approved", "message": "Tarefa precisa ser aprovada antes de executar"}

        task.status = "running"
        session.commit()

        plan = task.plan_json or {}
        steps = plan.get("steps", [])

        if not steps:
            task.status = "failed"
            task.error = "Plano sem passos"
            session.commit()
            return {"status": "failed", "error": "Plano sem passos"}

        # Resolver variáveis de ambiente nos parâmetros
        steps = _resolve_env_vars(steps)

        # Executar com Playwright
        results = []
        try:
            from browser import playwright_client, actions

            p, browser, page = playwright_client.iniciar_navegador()

            for idx, step in enumerate(steps, 1):
                tipo = step.get("tipo", "")
                desc = step.get("descricao", f"Passo {idx}")
                params = step.get("parametros", {})

                logger.info(f"🔄 Passo {idx}/{len(steps)}: {desc}")

                try:
                    if tipo in ("open_url", "abrir_url"):
                        actions.abrir_url(page, params.get("url", ""))
                    elif tipo in ("click", "clicar"):
                        actions.clicar(page, params.get("selector", ""))
                    elif tipo in ("type", "digitar"):
                        actions.digitar(
                            page, params.get("selector", ""),
                            params.get("text", ""),
                            secret=params.get("secret", False)
                        )
                    elif tipo in ("wait_selector", "esperar_selector"):
                        actions.esperar_selector(
                            page, params.get("selector", ""),
                            timeout_ms=params.get("timeout_ms", 10000)
                        )
                    elif tipo in ("wait_seconds", "aguardar_segundos"):
                        actions.wait_seconds(page, params.get("seconds", 2))
                    elif tipo in ("press_key", "pressionar_tecla"):
                        actions.press_key(page, params.get("key", "Enter"))
                    else:
                        logger.warning(f"Tipo desconhecido: {tipo}")

                    results.append({"step": idx, "description": desc, "status": "ok"})
                except Exception as step_err:
                    results.append({"step": idx, "description": desc, "status": "error", "error": str(step_err)})
                    logger.error(f"❌ Erro no passo {idx}: {step_err}")
                    # Continua com os próximos passos (tolerância a falhas)

            playwright_client.fechar_navegador(p, browser)

            task.status = "completed"
            task.result = json.dumps(results, ensure_ascii=False)
            task.completed_at = datetime.utcnow()
            session.commit()

            logger.info(f"✅ WebTask #{task_id} concluída: {len(results)} passos")
            return {"status": "completed", "results": results}

        except Exception as exec_err:
            task.status = "failed"
            task.error = str(exec_err)
            task.result = json.dumps(results, ensure_ascii=False) if results else ""
            session.commit()
            logger.error(f"❌ WebTask #{task_id} falhou: {exec_err}")
            return {"status": "failed", "error": str(exec_err), "partial_results": results}

    finally:
        session.close()


def _resolve_env_vars(steps: list) -> list:
    """Substitui {{ENV:NOME}} por valores reais do .env"""
    import re
    env_pattern = re.compile(r"\{\{ENV:([A-Z_]+)\}\}")

    resolved = []
    for step in steps:
        step_str = json.dumps(step, ensure_ascii=False)
        for match in env_pattern.finditer(step_str):
            var_name = match.group(1)
            var_value = os.getenv(var_name, "")
            step_str = step_str.replace(match.group(0), var_value)
        resolved.append(json.loads(step_str))
    return resolved


# ============================================================================
# HISTÓRICO
# ============================================================================

def get_task_history(limit: int = 20) -> list:
    """Histórico de tarefas executadas"""
    session = get_session()
    try:
        tasks = session.query(WebTask).order_by(
            WebTask.created_at.desc()
        ).limit(limit).all()
        return [t.to_dict() for t in tasks]
    finally:
        session.close()
