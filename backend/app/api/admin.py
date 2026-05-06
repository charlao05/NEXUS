"""
NEXUS - Admin Dashboard API
=============================
Endpoints administrativos: métricas globais, usuários, MRR, saúde do sistema.
Acesso restrito a usuários com role=admin ou plano enterprise.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import func

from database.models import (  # type: ignore[import]
    SessionLocal, User, Subscription, Client, Transaction,
    Opportunity, Appointment, ChatMessage, ActivityLog,
)
from app.api.auth import get_current_user  # type: ignore[import]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# ============================================================================
# ADMIN GUARD
# ============================================================================

def _get_admin_emails() -> list[str]:
    """Lê ADMIN_EMAILS do env em runtime (para suportar testes)."""
    return [
        e.strip()
        for e in os.getenv("ADMIN_EMAILS", "admin@nexus.com").split(",")
        if e.strip()
    ]


async def require_admin(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Dependency que garante acesso admin.
    Acesso concedido SOMENTE por role ou email explícito — nunca por plano.
    (Padrão seguro: pagar pelo plano mais caro NÃO concede privilégios admin.)"""
    email = current_user.get("email", "")
    role = current_user.get("role", "user")

    if role in ("admin", "superadmin") or email in _get_admin_emails():
        return current_user

    raise HTTPException(status_code=403, detail="Acesso restrito a administradores")


# ============================================================================
# OVERVIEW — Métricas globais
# ============================================================================

@router.get("/overview")
async def admin_overview(admin: dict[str, Any] = Depends(require_admin)):
    """Métricas globais do sistema — visão admin."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        day_ago = now - timedelta(days=1)

        # Usuários
        total_users = db.query(User).count()
        active_users_24h = (
            db.query(User)
            .filter(User.last_login >= day_ago)
            .count()
        )
        active_users_7d = (
            db.query(User)
            .filter(User.last_login >= week_ago)
            .count()
        )
        new_users_month = (
            db.query(User)
            .filter(User.created_at >= month_start)
            .count()
        )

        # Distribuição por plano
        plan_dist = (
            db.query(User.plan, func.count(User.id).label("count"))
            .group_by(User.plan)
            .all()
        )
        plans = {row.plan or "free": row.count for row in plan_dist}

        # MRR (Monthly Recurring Revenue)
        active_subs = (
            db.query(Subscription)
            .filter(Subscription.status == "active")
            .all()
        )
        mrr = sum(float(s.amount or 0) for s in active_subs)
        total_subs = len(active_subs)

        # Churn (assinaturas canceladas último mês)
        cancelled_month = (
            db.query(Subscription)
            .filter(
                Subscription.status == "cancelled",
                Subscription.cancelled_at >= month_start,
            )
            .count()
        )

        # Clientes CRM
        total_clients = db.query(Client).count()

        # Volume de chat (últimos 7 dias)
        chat_volume = (
            db.query(ChatMessage)
            .filter(ChatMessage.created_at >= week_ago)
            .count()
        )

        # Receita total do mês (plataforma dos clientes)
        platform_revenue = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.type == "receita",
                Transaction.date >= month_start.date(),
            )
            .scalar()
        ) or 0

        return {
            "users": {
                "total": total_users,
                "active_24h": active_users_24h,
                "active_7d": active_users_7d,
                "new_this_month": new_users_month,
                "by_plan": plans,
            },
            "revenue": {
                "mrr": mrr,
                "active_subscriptions": total_subs,
                "cancelled_this_month": cancelled_month,
                "churn_rate": round(cancelled_month / max(total_subs, 1) * 100, 1),
            },
            "platform": {
                "total_clients": total_clients,
                "chat_messages_7d": chat_volume,
                "platform_revenue_month": float(platform_revenue),
            },
            "generated_at": now.isoformat(),
        }
    finally:
        db.close()


# ============================================================================
# LISTA DE USUÁRIOS
# ============================================================================

@router.get("/users")
async def list_users(
    page: int = 1,
    per_page: int = 20,
    search: str = "",
    plan: str = "",
    admin: dict[str, Any] = Depends(require_admin),
):
    """Lista todos os usuários com paginação e filtros."""
    db = SessionLocal()
    try:
        query = db.query(User)

        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                (User.email.ilike(search_filter))
                | (User.full_name.ilike(search_filter))
            )

        if plan:
            query = query.filter(User.plan == plan)

        total = query.count()
        users = (
            query.order_by(User.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return {
            "users": [u.to_dict() for u in users],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        }
    finally:
        db.close()


# ============================================================================
# DETALHES DE UM USUÁRIO
# ============================================================================

@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: int,
    admin: dict[str, Any] = Depends(require_admin),
):
    """Detalhes completos de um usuário específico."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        # Assinaturas
        subs = (
            db.query(Subscription)
            .filter(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
            .all()
        )

        # Atividade recente
        activities = (
            db.query(ActivityLog)
            .filter(ActivityLog.user_id == user_id)
            .order_by(ActivityLog.created_at.desc())
            .limit(20)
            .all()
        )

        # Volume de chat
        chat_count = (
            db.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id)
            .count()
        )

        return {
            "user": user.to_dict(),
            "subscriptions": [s.to_dict() for s in subs],
            "recent_activity": [a.to_dict() for a in activities],
            "chat_messages_total": chat_count,
        }
    finally:
        db.close()


# ============================================================================
# MRR CHART (últimos 6 meses)
# ============================================================================

@router.get("/mrr-chart")
async def mrr_chart(admin: dict[str, Any] = Depends(require_admin)):
    """MRR mês a mês (últimos 6 meses) para gráfico."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        data_points: list[dict[str, Any]] = []

        for i in range(5, -1, -1):
            # Primeiro dia de cada mês
            ref = now - timedelta(days=30 * i)
            month_start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if ref.month == 12:
                month_end = month_start.replace(year=ref.year + 1, month=1)
            else:
                month_end = month_start.replace(month=ref.month + 1)

            active_in_month = (
                db.query(func.coalesce(func.sum(Subscription.amount), 0))
                .filter(
                    Subscription.status.in_(["active", "cancelled"]),
                    Subscription.created_at < month_end,
                )
                .scalar()
            ) or 0

            # Contar novos usuários nesse mês
            new_users = (
                db.query(User)
                .filter(
                    User.created_at >= month_start,
                    User.created_at < month_end,
                )
                .count()
            )

            data_points.append({
                "month": month_start.strftime("%Y-%m"),
                "label": month_start.strftime("%b/%y"),
                "mrr": float(active_in_month),
                "new_users": new_users,
            })

        return {"chart": data_points}
    finally:
        db.close()


# ============================================================================
# SYSTEM HEALTH
# ============================================================================

@router.get("/health")
async def admin_health(admin: dict[str, Any] = Depends(require_admin)):
    """Health check detalhado — status do sistema."""
    db = SessionLocal()
    try:
        # DB check
        db_ok = False
        try:
            db.execute(func.count(User.id).select())  # type: ignore
            db_ok = True
        except Exception:
            try:
                db.query(User).limit(1).all()
                db_ok = True
            except Exception:
                pass

        # Tamanho do DB
        from pathlib import Path
        db_path = Path(os.getenv(
            "NEXUS_DB_PATH",
            str(Path(__file__).parent.parent.parent / "data" / "nexus.db"),
        ))
        db_size_mb = round(db_path.stat().st_size / 1_048_576, 2) if db_path.exists() else 0

        return {
            "status": "healthy" if db_ok else "degraded",
            "database": {
                "connected": db_ok,
                "size_mb": db_size_mb,
            },
            "environment": os.getenv("ENVIRONMENT", "development"),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        db.close()


# ============================================================================
# RELIABILITY — Browser Pool / Circuit Breaker / Sessoes
# Visibilidade e controle operacional da infraestrutura de automacao web.
# ============================================================================

@router.get("/reliability/pool")
async def admin_pool_stats(admin: dict[str, Any] = Depends(require_admin)):
    """Estado do BrowserPool em tempo real — sessoes ativas, capacidade.

    Util para diagnosticar saturacao ou sessoes orfas.
    """
    try:
        from browser.pool import BrowserPool
        pool = BrowserPool.get_instance()
        return {
            "ok": True,
            "pool": pool.stats(),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"admin_pool_stats erro: {e}")
        return {
            "ok": False,
            "error": str(e),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/reliability/circuit")
async def admin_circuit_stats(
    domain: str | None = None,
    admin: dict[str, Any] = Depends(require_admin),
):
    """Estado dos circuit breakers (todos ou um dominio especifico).

    Args:
        domain: Se fornecido, retorna apenas este dominio. Senao, todos
                em memoria local da instancia.
    """
    try:
        from browser.circuit_breaker import DomainCircuitBreaker
        breaker = DomainCircuitBreaker.get_instance()
        return {
            "ok": True,
            "circuits": breaker.stats(domain) if domain else breaker.stats(),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"admin_circuit_stats erro: {e}")
        return {"ok": False, "error": str(e)}


@router.post("/reliability/circuit/reset")
async def admin_circuit_reset(
    domain: str,
    admin: dict[str, Any] = Depends(require_admin),
):
    """Forca fechamento de um circuit breaker (uso administrativo).

    Util quando um circuito ficou travado em OPEN apos uma manutencao
    do site externo (gov.br, prefeitura) que ja foi resolvida.
    """
    if not domain or len(domain) < 3:
        raise HTTPException(status_code=400, detail="domain obrigatorio")

    try:
        from browser.circuit_breaker import DomainCircuitBreaker
        from utils.automation_logger import AutomationLogger, set_context

        breaker = DomainCircuitBreaker.get_instance()
        breaker.force_close(domain)

        # Audit: admin reset eh evento de seguranca relevante
        set_context(
            correlation_id=f"admin_reset_{int(datetime.now(timezone.utc).timestamp())}",
            user_id=admin.get("user_id", 0),
            agent_type="admin",
        )
        AutomationLogger.circuit_state_changed(
            domain=domain,
            from_state="open",
            to_state="closed",
            failures=0,
            reason=f"admin_force_close by {admin.get('email', 'unknown')}",
        )

        return {
            "ok": True,
            "domain": domain,
            "new_state": "closed",
            "reset_by": admin.get("email"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_circuit_reset erro: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/reliability/sessions/{user_id}")
async def admin_clear_user_sessions(
    user_id: int,
    domain: str | None = None,
    admin: dict[str, Any] = Depends(require_admin),
):
    """Remove cookies salvos de um usuario (todos os dominios ou um especifico).

    Util quando o usuario reclama de "ficou logado em algo errado" ou
    quando precisamos invalidar sessoes apos suspeita de compromisso.
    """
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="user_id invalido")

    try:
        from browser.session_store import SessionStore
        store = SessionStore.get_instance()
        removed = store.clear(user_id=user_id, domain=domain)

        logger.warning(
            f"[ADMIN] Sessoes limpas | target_user={user_id} domain={domain or 'ALL'} "
            f"removed={removed} by={admin.get('email')}"
        )
        return {
            "ok": True,
            "user_id": user_id,
            "domain": domain,
            "removed_keys": removed,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_clear_user_sessions erro: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# USAGE — LLM e Automation (Tier 1, in-memory)
# Janela movel de 48h maxima. Reinicio do processo zera dados.
# Tier 2 introduzira persistencia em tabelas dedicadas.
# ============================================================================
@router.get("/usage/llm")
async def admin_usage_llm(
    since_minutes: int = 60 * 24,
    admin: dict[str, Any] = Depends(require_admin),
):
    """Snapshot agregado de uso LLM. Default: ultimas 24h. Cap: 48h."""
    try:
        from utils.usage_tracker import UsageTracker
        # Cap defensivo: 48h é o teto de retenção
        capped = min(max(60, since_minutes), 48 * 60)
        return UsageTracker.snapshot_llm(since_minutes=capped)
    except Exception as e:
        logger.error(f"admin_usage_llm erro: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="usage_tracker indisponivel")


@router.get("/usage/automation")
async def admin_usage_automation(
    since_minutes: int = 60 * 24,
    admin: dict[str, Any] = Depends(require_admin),
):
    """Snapshot agregado de uso de automacao Playwright. Default: ultimas 24h. Cap: 48h."""
    try:
        from utils.usage_tracker import UsageTracker
        capped = min(max(60, since_minutes), 48 * 60)
        return UsageTracker.snapshot_automation(since_minutes=capped)
    except Exception as e:
        logger.error(f"admin_usage_automation erro: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="usage_tracker indisponivel")


# ============================================================================
# USAGE HISTORICAL — Tier 2 (DB-backed, sobrevive a restart e cold-start)
# Cap: ate 90 dias. Query agregada direto na tabela llm_usage_records.
# ============================================================================
@router.get("/usage/llm/historical")
async def admin_usage_llm_historical(
    since_hours: int = 24,
    user_id: int | None = None,
    admin: dict[str, Any] = Depends(require_admin),
):
    """Snapshot agregado historico de uso LLM (le do DB, sobrevive a restart).

    Args:
        since_hours: janela em horas (default 24h, max 90 dias = 2160h).
        user_id: se passado, filtra apenas este user.
    """
    try:
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import func
        from database.models import SessionLocal, LLMUsageRecord

        capped_hours = min(max(1, since_hours), 24 * 90)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=capped_hours)

        db = SessionLocal()
        try:
            q = db.query(LLMUsageRecord).filter(LLMUsageRecord.ts >= cutoff)
            if user_id is not None:
                q = q.filter(LLMUsageRecord.user_id == user_id)

            # Totais globais
            agg = db.query(
                func.count(LLMUsageRecord.id),
                func.coalesce(func.sum(LLMUsageRecord.prompt_tokens), 0),
                func.coalesce(func.sum(LLMUsageRecord.completion_tokens), 0),
                func.coalesce(func.sum(LLMUsageRecord.total_tokens), 0),
                func.coalesce(func.sum(LLMUsageRecord.cost_usd), 0.0),
                func.coalesce(func.avg(LLMUsageRecord.duration_ms), 0),
            ).filter(LLMUsageRecord.ts >= cutoff)
            if user_id is not None:
                agg = agg.filter(LLMUsageRecord.user_id == user_id)
            (calls, p_tok, c_tok, t_tok, cost, avg_dur) = agg.one()

            # By user
            by_user_rows = db.query(
                LLMUsageRecord.user_id,
                func.count(LLMUsageRecord.id),
                func.coalesce(func.sum(LLMUsageRecord.total_tokens), 0),
                func.coalesce(func.sum(LLMUsageRecord.cost_usd), 0.0),
            ).filter(LLMUsageRecord.ts >= cutoff)
            if user_id is not None:
                by_user_rows = by_user_rows.filter(LLMUsageRecord.user_id == user_id)
            by_user_rows = by_user_rows.group_by(LLMUsageRecord.user_id).all()

            # By model
            by_model_rows = db.query(
                LLMUsageRecord.model,
                func.count(LLMUsageRecord.id),
                func.coalesce(func.sum(LLMUsageRecord.total_tokens), 0),
                func.coalesce(func.sum(LLMUsageRecord.cost_usd), 0.0),
            ).filter(LLMUsageRecord.ts >= cutoff)
            if user_id is not None:
                by_model_rows = by_model_rows.filter(LLMUsageRecord.user_id == user_id)
            by_model_rows = by_model_rows.group_by(LLMUsageRecord.model).all()

            return {
                "window_hours": capped_hours,
                "filter_user_id": user_id,
                "events_count": int(calls),
                "totals": {
                    "calls": int(calls),
                    "prompt_tokens": int(p_tok),
                    "completion_tokens": int(c_tok),
                    "total_tokens": int(t_tok),
                    "cost_usd": round(float(cost), 6),
                    "avg_duration_ms": int(avg_dur or 0),
                },
                "by_user": {
                    int(uid): {
                        "calls": int(c),
                        "total_tokens": int(tk),
                        "cost_usd": round(float(co), 6),
                    }
                    for (uid, c, tk, co) in by_user_rows
                },
                "by_model": {
                    str(m or "unknown"): {
                        "calls": int(c),
                        "total_tokens": int(tk),
                        "cost_usd": round(float(co), 6),
                    }
                    for (m, c, tk, co) in by_model_rows
                },
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"admin_usage_llm_historical erro: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/usage/automation/historical")
async def admin_usage_automation_historical(
    since_hours: int = 24,
    user_id: int | None = None,
    admin: dict[str, Any] = Depends(require_admin),
):
    """Snapshot agregado historico de uso de automacao (DB-backed)."""
    try:
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import func, case
        from database.models import SessionLocal, AutomationUsageRecord

        capped_hours = min(max(1, since_hours), 24 * 90)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=capped_hours)

        db = SessionLocal()
        try:
            agg = db.query(
                func.count(AutomationUsageRecord.id),
                func.coalesce(func.sum(case((AutomationUsageRecord.success.is_(True), 1), else_=0)), 0),
                func.coalesce(func.sum(case((AutomationUsageRecord.success.is_(False), 1), else_=0)), 0),
                func.coalesce(func.avg(AutomationUsageRecord.duration_ms), 0),
            ).filter(AutomationUsageRecord.ts >= cutoff)
            if user_id is not None:
                agg = agg.filter(AutomationUsageRecord.user_id == user_id)
            (calls, succ, fail, avg_dur) = agg.one()

            calls_safe = int(calls) or 1

            by_tool_rows = db.query(
                AutomationUsageRecord.tool,
                func.count(AutomationUsageRecord.id),
                func.coalesce(func.sum(case((AutomationUsageRecord.success.is_(True), 1), else_=0)), 0),
            ).filter(AutomationUsageRecord.ts >= cutoff)
            if user_id is not None:
                by_tool_rows = by_tool_rows.filter(AutomationUsageRecord.user_id == user_id)
            by_tool_rows = by_tool_rows.group_by(AutomationUsageRecord.tool).all()

            return {
                "window_hours": capped_hours,
                "filter_user_id": user_id,
                "events_count": int(calls),
                "totals": {
                    "calls": int(calls),
                    "success": int(succ),
                    "failure": int(fail),
                    "success_rate": round(int(succ) / calls_safe, 3),
                    "avg_duration_ms": int(avg_dur or 0),
                },
                "by_tool": {
                    str(t or "unknown"): {
                        "calls": int(c),
                        "success": int(s),
                        "success_rate": round(int(s) / (int(c) or 1), 3),
                    }
                    for (t, c, s) in by_tool_rows
                },
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"admin_usage_automation_historical erro: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MARGIN — receita Stripe vs custo LLM, por tenant (Tier 2.3)
# ATENCAO: aproximacao gerencial. NAO usar para contabilidade fiscal.
# Rate USD->BRL via env USD_BRL_RATE (default 5.20). Custo Playwright/proxy
# = 0 nesta versao (TODO 2.3.2: prorate compute fixo + variaveis premium).
# ============================================================================

def _period_bounds_current_month():
    """Retorna (start, end_now) para o mes corrente em UTC."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, now


def _resolve_margin_status(margin_pct: float | None) -> str:
    """healthy >= 70%, warning 0-70%, loss < 0%, n/a se margin_pct=null."""
    if margin_pct is None:
        return "n/a"
    if margin_pct < 0:
        return "loss"
    if margin_pct < 70.0:
        return "warning"
    return "healthy"


def _safe_margin_pct(mrr: float, cost: float) -> float | None:
    """Convencao:
      mrr > 0 -> (mrr - cost) / mrr * 100
      mrr == 0 AND cost > 0 -> -100.0
      mrr == 0 AND cost == 0 -> None (nao enviesa agregacoes)
    """
    if mrr > 0:
        return round(((mrr - cost) / mrr) * 100.0, 2)
    if cost > 0:
        return -100.0
    return None


def _resolve_user_revenue(db, user_id: int) -> tuple[float, str]:
    """Retorna (mrr_brl, subscription_status). Usa subscription mais recente.

    subscription_status semantica:
      "active" / "trialing" / "past_due" / "cancelled" — direto do Stripe
      "free" — sem registro de subscription (nunca pagou)
    """
    from database.models import Subscription
    sub = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.updated_at.desc(), Subscription.id.desc())
        .first()
    )
    if sub is None:
        return 0.0, "free"
    # Se cancelada ha mais de 30 dias, considera free pra fins de margem
    sub_status = sub.status or "unknown"
    if sub_status == "cancelled":
        return 0.0, "cancelled"
    return float(sub.amount or 0.0), sub_status


@router.get("/margin")
async def admin_margin(
    user_id: int,
    period: str = "current_month",
    admin: dict[str, Any] = Depends(require_admin),
):
    """Margem bruta do mes corrente para um user_id.

    period: 'current_month' (unico suportado nesta versao).
    Retorna receita Stripe (MRR teorico) - custo LLM (USD convertido p/ BRL).
    """
    if period != "current_month":
        raise HTTPException(status_code=400, detail="period suportado: current_month")

    try:
        from sqlalchemy import func
        from database.models import SessionLocal, User, LLMUsageRecord

        usd_brl = float(os.getenv("USD_BRL_RATE", "5.20") or "5.20")
        start, end = _period_bounds_current_month()

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user is None:
                raise HTTPException(status_code=404, detail=f"user_id {user_id} nao encontrado")

            mrr_brl, sub_status = _resolve_user_revenue(db, user_id)

            agg = db.query(
                func.count(LLMUsageRecord.id),
                func.coalesce(func.sum(LLMUsageRecord.cost_usd), 0.0),
                func.coalesce(func.sum(LLMUsageRecord.total_tokens), 0),
                func.coalesce(func.avg(LLMUsageRecord.duration_ms), 0),
            ).filter(
                LLMUsageRecord.user_id == user_id,
                LLMUsageRecord.ts >= start,
                LLMUsageRecord.ts <= end,
            ).one()
            (calls, llm_usd, total_tokens, avg_dur) = agg

            llm_brl = float(llm_usd) * usd_brl
            automation_cost_brl = 0.0  # TODO 2.3.2

            costs_total = llm_brl + automation_cost_brl
            margin_brl = mrr_brl - costs_total
            margin_pct = _safe_margin_pct(mrr_brl, costs_total)
            status = _resolve_margin_status(margin_pct)

            return {
                "disclaimer": "Aproximacao gerencial. Nao usar para contabilidade fiscal.",
                "user_id": user_id,
                "email": user.email,
                "plan": user.plan,
                "subscription_status": sub_status,
                "period": {
                    "type": period,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                },
                "usd_brl_rate": usd_brl,
                "revenue": {
                    "mrr_brl": round(mrr_brl, 2),
                    "stripe_invoice_paid_brl": None,  # TODO 2.3.1
                },
                "costs": {
                    "llm_usd": round(float(llm_usd), 6),
                    "llm_brl": round(llm_brl, 4),
                    "llm_calls": int(calls),
                    "llm_total_tokens": int(total_tokens),
                    "llm_avg_duration_ms": int(avg_dur or 0),
                    "automation_cost_brl": automation_cost_brl,
                    "total_brl": round(costs_total, 4),
                },
                "margin": {
                    "gross_brl": round(margin_brl, 2),
                    "margin_pct": margin_pct,
                    "status": status,
                },
            }
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_margin erro: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/margin/all")
async def admin_margin_all(
    period: str = "current_month",
    sort: str = "margin_asc",
    limit: int = 100,
    status_filter: str | None = None,
    admin: dict[str, Any] = Depends(require_admin),
):
    """Lista ranked de margem por tenant. Default: piores margens primeiro.

    Args:
        period: 'current_month' (unico suportado).
        sort: 'margin_asc' | 'margin_desc' | 'cost_desc' | 'revenue_desc'.
        limit: 1..500 (cap defensivo).
        status_filter: 'healthy' | 'warning' | 'loss' | 'n/a' (None = todos).

    Inclui APENAS users que tiveram LLM usage no periodo (nao varre toda User).
    """
    if period != "current_month":
        raise HTTPException(status_code=400, detail="period suportado: current_month")

    try:
        from sqlalchemy import func
        from database.models import SessionLocal, User, LLMUsageRecord

        usd_brl = float(os.getenv("USD_BRL_RATE", "5.20") or "5.20")
        start, end = _period_bounds_current_month()
        capped_limit = min(max(1, limit), 500)

        db = SessionLocal()
        try:
            # 1. Usuarios com tracafego LLM no periodo
            traffic_rows = db.query(
                LLMUsageRecord.user_id,
                func.count(LLMUsageRecord.id),
                func.coalesce(func.sum(LLMUsageRecord.cost_usd), 0.0),
                func.coalesce(func.sum(LLMUsageRecord.total_tokens), 0),
            ).filter(
                LLMUsageRecord.ts >= start,
                LLMUsageRecord.ts <= end,
            ).group_by(LLMUsageRecord.user_id).all()

            items: list[dict[str, Any]] = []
            user_ids = [int(r[0]) for r in traffic_rows if r[0] is not None]
            users_by_id: dict[int, User] = {
                u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()
            } if user_ids else {}

            for (uid, calls, llm_usd, total_tokens) in traffic_rows:
                uid = int(uid or 0)
                user = users_by_id.get(uid)
                mrr_brl, sub_status = _resolve_user_revenue(db, uid) if uid > 0 else (0.0, "anonymous")
                llm_brl = float(llm_usd) * usd_brl
                costs_total = llm_brl  # automation cost = 0 nesta versao
                margin_brl = mrr_brl - costs_total
                margin_pct = _safe_margin_pct(mrr_brl, costs_total)
                status = _resolve_margin_status(margin_pct)

                if status_filter and status != status_filter:
                    continue

                items.append({
                    "user_id": uid,
                    "email": user.email if user else None,
                    "plan": user.plan if user else "unknown",
                    "subscription_status": sub_status,
                    "mrr_brl": round(mrr_brl, 2),
                    "llm_brl": round(llm_brl, 4),
                    "llm_calls": int(calls),
                    "llm_total_tokens": int(total_tokens),
                    "automation_cost_brl": 0.0,
                    "margin_brl": round(margin_brl, 2),
                    "margin_pct": margin_pct,
                    "status": status,
                })

            # Sorting
            if sort == "margin_asc":
                items.sort(key=lambda x: (
                    x["margin_pct"] if x["margin_pct"] is not None else 999.0
                ))
            elif sort == "margin_desc":
                items.sort(key=lambda x: (
                    -(x["margin_pct"]) if x["margin_pct"] is not None else 999.0
                ))
            elif sort == "cost_desc":
                items.sort(key=lambda x: -x["llm_brl"])
            elif sort == "revenue_desc":
                items.sort(key=lambda x: -x["mrr_brl"])
            else:
                raise HTTPException(status_code=400, detail=f"sort invalido: {sort}")

            total_users_with_traffic = len(items)
            return {
                "disclaimer": "Aproximacao gerencial. Nao usar para contabilidade fiscal.",
                "period": {
                    "type": period,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                },
                "usd_brl_rate": usd_brl,
                "sort": sort,
                "status_filter": status_filter,
                "total_users_with_traffic": total_users_with_traffic,
                "shown": min(capped_limit, total_users_with_traffic),
                "items": items[:capped_limit],
            }
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_margin_all erro: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
