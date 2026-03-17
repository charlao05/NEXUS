"""
NEXUS - Notificações em Tempo Real (SSE)
=========================================
Server-Sent Events para notificações push ao frontend.
Suporta: alertas de sistema, lembretes de agendamento, status de agentes, trial warnings.
Backend: Redis (quando disponível) ou in-memory (fallback).
"""

import asyncio
import json
import time
import logging
from typing import Any, Optional
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.auth import get_current_user  # type: ignore[import]
from database.models import (  # type: ignore[import]
    SessionLocal, Appointment, Invoice, User, Subscription,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ============================================================================
# IN-MEMORY NOTIFICATION QUEUE
# ============================================================================

class NotificationQueue:
    """Fila de notificações por usuário (in-memory)."""

    def __init__(self):
        self._queues: dict[int, asyncio.Queue] = defaultdict(lambda: asyncio.Queue(maxsize=100))
        self._unread: dict[int, list[dict[str, Any]]] = defaultdict(list)

    def get_queue(self, user_id: int) -> asyncio.Queue:
        return self._queues[user_id]

    async def push(self, user_id: int, notification: dict[str, Any]) -> None:
        """Envia notificação para o usuário."""
        notification.setdefault("id", f"n-{int(time.time() * 1000)}")
        notification.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        notification.setdefault("read", False)

        # Guardar no buffer de não-lidas (máx 50)
        self._unread[user_id].append(notification)
        if len(self._unread[user_id]) > 50:
            self._unread[user_id] = self._unread[user_id][-50:]

        # Tentar enviar para conexão SSE ativa
        q = self._queues.get(user_id)
        if q:
            try:
                q.put_nowait(notification)
            except asyncio.QueueFull:
                pass

    def get_unread(self, user_id: int) -> list[dict[str, Any]]:
        """Retorna notificações não lidas."""
        return list(self._unread.get(user_id, []))

    def mark_read(self, user_id: int, notification_id: Optional[str] = None) -> int:
        """Marca notificações como lidas. Se id=None, marca todas."""
        count = 0
        if notification_id:
            for n in self._unread.get(user_id, []):
                if n["id"] == notification_id and not n["read"]:
                    n["read"] = True
                    count += 1
        else:
            for n in self._unread.get(user_id, []):
                if not n["read"]:
                    n["read"] = True
                    count += 1
        return count

    def clear(self, user_id: int) -> None:
        self._unread[user_id] = []

    def cleanup_user(self, user_id: int) -> None:
        """Remove queue quando usuário desconecta."""
        self._queues.pop(user_id, None)


# ============================================================================
# REDIS-BACKED NOTIFICATION QUEUE
# ============================================================================

class RedisNotificationQueue:
    """Fila de notificações com Redis — persiste entre reinícios, funciona multi-worker."""

    UNREAD_KEY = "notif:unread:{user_id}"
    CHANNEL_KEY = "notif:channel:{user_id}"
    MAX_UNREAD = 50

    def __init__(self, redis_client):
        self._redis = redis_client
        # SSE queues permanecem in-memory (por processo)
        self._queues: dict[int, asyncio.Queue] = defaultdict(lambda: asyncio.Queue(maxsize=100))

    def get_queue(self, user_id: int) -> asyncio.Queue:
        return self._queues[user_id]

    async def push(self, user_id: int, notification: dict[str, Any]) -> None:
        notification.setdefault("id", f"n-{int(time.time() * 1000)}")
        notification.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        notification.setdefault("read", False)

        key = self.UNREAD_KEY.format(user_id=user_id)
        self._redis.lpush(key, json.dumps(notification, ensure_ascii=False))
        self._redis.ltrim(key, 0, self.MAX_UNREAD - 1)
        self._redis.expire(key, 86400 * 7)  # 7 dias TTL

        # Publicar via Pub/Sub para SSE listeners em outros workers
        self._redis.publish(
            self.CHANNEL_KEY.format(user_id=user_id),
            json.dumps(notification, ensure_ascii=False),
        )

        # SSE local
        q = self._queues.get(user_id)
        if q:
            try:
                q.put_nowait(notification)
            except asyncio.QueueFull:
                pass

    def get_unread(self, user_id: int) -> list[dict[str, Any]]:
        key = self.UNREAD_KEY.format(user_id=user_id)
        raw = self._redis.lrange(key, 0, self.MAX_UNREAD)
        return [json.loads(r) for r in raw]

    def mark_read(self, user_id: int, notification_id: Optional[str] = None) -> int:
        key = self.UNREAD_KEY.format(user_id=user_id)
        items = self._redis.lrange(key, 0, -1)
        count = 0
        pipe = self._redis.pipeline()
        pipe.delete(key)
        for raw in items:
            n = json.loads(raw)
            if notification_id:
                if n["id"] == notification_id and not n.get("read"):
                    n["read"] = True
                    count += 1
            else:
                if not n.get("read"):
                    n["read"] = True
                    count += 1
            pipe.rpush(key, json.dumps(n, ensure_ascii=False))
        pipe.expire(key, 86400 * 7)
        pipe.execute()
        return count

    def clear(self, user_id: int) -> None:
        self._redis.delete(self.UNREAD_KEY.format(user_id=user_id))

    def cleanup_user(self, user_id: int) -> None:
        self._queues.pop(user_id, None)


# ============================================================================
# INSTÂNCIA AUTO-SELECT
# ============================================================================

def _create_queue():
    """Cria a fila de notificações — Redis se disponível, senão in-memory."""
    try:
        from app.api.redis_client import get_redis  # type: ignore[import]
        r = get_redis()
        if r:
            logger.info("✅ Notificações usando Redis")
            return RedisNotificationQueue(r)
    except Exception as e:
        logger.debug(f"Redis não disponível para notificações: {e}")
    return NotificationQueue()


_notifications = _create_queue()


# Função pública para enviar notificações de qualquer parte do código
async def send_notification(
    user_id: int,
    type: str,
    title: str,
    message: str,
    data: Optional[dict[str, Any]] = None,
    severity: str = "info",  # info, warning, success, error
) -> None:
    """API pública para enviar notificações de qualquer módulo."""
    await _notifications.push(user_id, {
        "type": type,
        "title": title,
        "message": message,
        "severity": severity,
        "data": data or {},
    })


# ============================================================================
# SSE STREAM ENDPOINT
# ============================================================================

@router.get("/stream")
async def notification_stream(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    SSE endpoint — mantém conexão aberta e envia notificações em tempo real.
    O frontend conecta via EventSource.
    """
    user_id = current_user["user_id"]

    async def event_generator():
        queue = _notifications.get_queue(user_id)
        try:
            # Enviar heartbeat inicial
            yield f"event: connected\ndata: {json.dumps({'user_id': user_id}, ensure_ascii=False)}\n\n"

            # Enviar notificações não lidas pendentes
            unread = _notifications.get_unread(user_id)
            for n in unread:
                if not n.get("read"):
                    yield f"event: notification\ndata: {json.dumps(n, ensure_ascii=False)}\n\n"

            # Gerar notificações proativas (agendamentos próximos, trial, etc.)
            proactive = _generate_proactive_notifications(user_id)
            for n in proactive:
                await _notifications.push(user_id, n)
                yield f"event: notification\ndata: {json.dumps(n, ensure_ascii=False)}\n\n"

            # Loop principal — aguarda novas notificações
            while True:
                if await request.is_disconnected():
                    break

                try:
                    notification = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"event: notification\ndata: {json.dumps(notification, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat para manter conexão viva
                    yield f"event: heartbeat\ndata: {json.dumps({'ts': int(time.time())})}\n\n"

        except asyncio.CancelledError:
            pass
        finally:
            _notifications.cleanup_user(user_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx
        },
    )


# ============================================================================
# REST ENDPOINTS para notificações
# ============================================================================

@router.get("/unread")
async def get_unread_notifications(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retorna notificações não lidas."""
    user_id = current_user["user_id"]
    unread = [n for n in _notifications.get_unread(user_id) if not n.get("read")]
    return {"notifications": unread, "count": len(unread)}


@router.post("/read")
async def mark_notifications_read(
    notification_id: Optional[str] = None,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Marca notificações como lidas."""
    count = _notifications.mark_read(current_user["user_id"], notification_id)
    return {"marked": count}


@router.delete("/clear")
async def clear_notifications(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Limpa todas as notificações."""
    _notifications.clear(current_user["user_id"])
    return {"cleared": True}


# ============================================================================
# PROACTIVE NOTIFICATION GENERATOR
# ============================================================================

def _generate_proactive_notifications(user_id: int) -> list[dict[str, Any]]:
    """Gera notificações proativas baseadas no estado do banco."""
    notifications: list[dict[str, Any]] = []
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        today = now.date()

        # 1) Agendamentos nas próximas 2 horas
        two_hours = now + timedelta(hours=2)
        upcoming = (
            db.query(Appointment)
            .filter(
                Appointment.scheduled_at >= now,
                Appointment.scheduled_at <= two_hours,
                Appointment.status == "scheduled",
            )
            .all()
        )
        for apt in upcoming:
            minutes_until = int((apt.scheduled_at - now).total_seconds() / 60)
            notifications.append({
                "type": "appointment_reminder",
                "title": "Agendamento próximo",
                "message": f"'{apt.title}' em {minutes_until} minutos",
                "severity": "warning" if minutes_until < 30 else "info",
                "data": {"appointment_id": apt.id, "minutes_until": minutes_until},
            })

        # 2) Faturas vencidas (atrasadas) — cobrança urgente
        overdue_invoices = (
            db.query(Invoice)
            .filter(
                Invoice.status == "pending",
                Invoice.due_date < today,
            )
            .all()
        )
        if overdue_invoices:
            total_overdue = sum(inv.amount for inv in overdue_invoices)
            for inv in overdue_invoices[:5]:  # max 5 notificações individuais
                days_late = (today - inv.due_date).days
                # Buscar nome do cliente
                from database.models import Client
                client = db.query(Client).filter(Client.id == inv.client_id).first()
                client_name = client.name if client else "Cliente"
                notifications.append({
                    "type": "invoice_overdue",
                    "title": "🔴 Pagamento atrasado",
                    "message": f"{client_name} — R$ {inv.amount:,.2f} venceu há {days_late} dia(s)",
                    "severity": "error",
                    "data": {
                        "invoice_id": inv.id,
                        "client_id": inv.client_id,
                        "client_name": client_name,
                        "amount": inv.amount,
                        "days_overdue": days_late,
                        "due_date": inv.due_date.isoformat(),
                    },
                })
            if len(overdue_invoices) > 5:
                notifications.append({
                    "type": "invoice_overdue_summary",
                    "title": "🔴 Mais pagamentos atrasados",
                    "message": f"Total: {len(overdue_invoices)} fatura(s) vencida(s) — R$ {total_overdue:,.2f}",
                    "severity": "error",
                    "data": {"count": len(overdue_invoices), "total": total_overdue},
                })

        # 3) Faturas vencendo HOJE — lembrete de último dia
        due_today = (
            db.query(Invoice)
            .filter(
                Invoice.status == "pending",
                Invoice.due_date == today,
            )
            .all()
        )
        for inv in due_today:
            from database.models import Client
            client = db.query(Client).filter(Client.id == inv.client_id).first()
            client_name = client.name if client else "Cliente"
            notifications.append({
                "type": "invoice_due_today",
                "title": "🟡 Vence hoje!",
                "message": f"{client_name} — R$ {inv.amount:,.2f} vence HOJE",
                "severity": "warning",
                "data": {
                    "invoice_id": inv.id,
                    "client_id": inv.client_id,
                    "client_name": client_name,
                    "amount": inv.amount,
                    "due_date": today.isoformat(),
                },
            })

        # 4) Faturas vencendo nos próximos 3 dias — antecipação
        three_days = today + timedelta(days=3)
        upcoming_invoices = (
            db.query(Invoice)
            .filter(
                Invoice.status == "pending",
                Invoice.due_date > today,
                Invoice.due_date <= three_days,
            )
            .all()
        )
        for inv in upcoming_invoices:
            from database.models import Client
            client = db.query(Client).filter(Client.id == inv.client_id).first()
            client_name = client.name if client else "Cliente"
            days_until = (inv.due_date - today).days
            notifications.append({
                "type": "invoice_due_soon",
                "title": "📅 Pagamento próximo",
                "message": f"{client_name} — R$ {inv.amount:,.2f} vence em {days_until} dia(s)",
                "severity": "info",
                "data": {
                    "invoice_id": inv.id,
                    "client_id": inv.client_id,
                    "client_name": client_name,
                    "amount": inv.amount,
                    "days_until_due": days_until,
                    "due_date": inv.due_date.isoformat(),
                },
            })

        # 5) Lembrete do DAS MEI — vence dia 20 de cada mês
        day_of_month = today.day
        if day_of_month <= 20:
            days_to_das = 20 - day_of_month
            if days_to_das <= 5 and days_to_das > 0:
                notifications.append({
                    "type": "das_reminder",
                    "title": "📋 DAS MEI",
                    "message": f"Boleto mensal do MEI vence em {days_to_das} dia(s) (dia 20)",
                    "severity": "warning" if days_to_das <= 2 else "info",
                    "data": {"days_until": days_to_das, "due_day": 20},
                })
            elif days_to_das == 0:
                notifications.append({
                    "type": "das_reminder",
                    "title": "🔴 DAS MEI vence HOJE",
                    "message": "Boleto mensal do MEI vence HOJE (dia 20). Pague para evitar multa!",
                    "severity": "error",
                    "data": {"days_until": 0, "due_day": 20},
                })

        # 6) Lembrete de upgrade para usuários Free
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.plan == "free":
            notifications.append({
                "type": "free_plan_reminder",
                "title": "Plano Gratuito",
                "message": "Você está no plano gratuito. Faça upgrade para desbloquear todos os agentes e limites.",
                "severity": "info",
                "data": {"upgrade_url": "/pricing"},
            })

    except Exception as e:
        logger.warning(f"Erro ao gerar notificações proativas: {e}")
    finally:
        db.close()

    return notifications
