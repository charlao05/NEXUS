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
