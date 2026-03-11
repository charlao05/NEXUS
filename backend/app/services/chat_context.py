"""
NEXUS — Chat Context Service (Redis + SQLite)
===============================================
Persistência de contexto de chat entre mensagens usando Redis como cache
rápido com fallback automático para SQLite.

Lacuna #18: O agente perdia contexto entre mensagens porque o histórico
dependia apenas de queries SQLite. Agora:
  - Redis armazena últimas 20 mensagens por user/agent com TTL 24h
  - Leitura: Redis (rápido) → fallback SQLite
  - Escrita: Redis + SQLite (dual-write)

Chave Redis: chat_history:{user_id}:{agent_id}
TTL: 24 horas
Máximo: 20 mensagens por contexto
"""

import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── CONFIGURAÇÃO ──────────────────────────────────────────────
CHAT_HISTORY_TTL = 86400  # 24 horas em segundos
CHAT_HISTORY_MAX_MESSAGES = 20


def _redis_key(user_id: int, agent_id: str) -> str:
    """Gera chave Redis para histórico de chat."""
    return f"chat_history:{user_id}:{agent_id}"


def _get_redis():
    """Obtém cliente Redis (pode ser None se indisponível)."""
    try:
        from app.api.redis_client import get_redis
        return get_redis()
    except Exception:
        return None


# ============================================================================
# LEITURA — Carregar histórico de chat
# ============================================================================

def load_chat_history(
    user_id: int,
    agent_id: str,
    limit: int = CHAT_HISTORY_MAX_MESSAGES,
) -> list[dict]:
    """Carrega histórico de chat: tenta Redis primeiro, fallback SQLite.

    Retorna lista de dicts: [{"role": "user"|"assistant", "content": "...", "timestamp": "..."}]
    Ordenada cronologicamente (mais antiga primeiro).
    """
    # ── Tenta Redis (rápido) ─────────────────────────────
    history = _load_from_redis(user_id, agent_id, limit)
    if history is not None:
        logger.debug(f"📦 Chat history from Redis: {len(history)} msgs (user={user_id}, agent={agent_id})")
        return history

    # ── Fallback: SQLite ─────────────────────────────────
    history = _load_from_sqlite(user_id, agent_id, limit)
    logger.debug(f"🗄️ Chat history from SQLite: {len(history)} msgs (user={user_id}, agent={agent_id})")

    # Popula Redis para próximas leituras serem rápidas
    if history:
        _save_batch_to_redis(user_id, agent_id, history)

    return history


def _load_from_redis(user_id: int, agent_id: str, limit: int) -> Optional[list[dict]]:
    """Carrega histórico do Redis. Retorna None se Redis indisponível."""
    r = _get_redis()
    if r is None:
        return None

    try:
        key = _redis_key(user_id, agent_id)
        raw_list = r.lrange(key, 0, limit - 1)
        if not raw_list:
            # Chave existe mas está vazia? Ou nunca existiu?
            # Retorna [] se a chave existe, None se não existe
            if r.exists(key):
                return []
            return None  # Chave não existe → fallback para SQLite

        messages = []
        for raw in raw_list:
            try:
                msg = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode("utf-8"))
                messages.append(msg)
            except (json.JSONDecodeError, AttributeError):
                continue

        return messages
    except Exception as e:
        logger.debug(f"Redis load failed: {e}")
        return None


def _load_from_sqlite(user_id: int, agent_id: str, limit: int) -> list[dict]:
    """Carrega histórico do SQLite (fonte de verdade)."""
    try:
        from database.models import ChatMessage, SessionLocal

        db = SessionLocal()
        try:
            query = (
                db.query(ChatMessage)
                .filter(ChatMessage.user_id == user_id, ChatMessage.agent_id == agent_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
                .all()
            )
            # Reverter para ordem cronológica
            return [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.created_at.isoformat() if m.created_at else "",
                }
                for m in reversed(query)
            ]
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"SQLite chat load failed: {e}")
        return []


# ============================================================================
# ESCRITA — Salvar mensagem no contexto
# ============================================================================

def save_message(
    user_id: int,
    agent_id: str,
    role: str,
    content: str,
) -> None:
    """Salva uma mensagem no contexto (dual-write: Redis + SQLite).

    Args:
        user_id: ID do usuário autenticado
        agent_id: ID do agente (agenda, clientes, contabilidade, cobranca, assistente)
        role: 'user' ou 'assistant'
        content: conteúdo da mensagem
    """
    timestamp = datetime.now().isoformat()

    # ── Redis (cache rápido) ─────────────────────────────
    _append_to_redis(user_id, agent_id, role, content, timestamp)

    # ── SQLite (persistência permanente) ─────────────────
    _save_to_sqlite(user_id, agent_id, role, content)


def save_turn(
    user_id: int,
    agent_id: str,
    user_message: str,
    assistant_message: str,
) -> None:
    """Salva um turno completo (pergunta + resposta) no contexto.
    Atalho para salvar as duas mensagens de uma vez.
    """
    if user_message:
        save_message(user_id, agent_id, "user", user_message)
    if assistant_message:
        save_message(user_id, agent_id, "assistant", assistant_message)


def _append_to_redis(
    user_id: int, agent_id: str, role: str, content: str, timestamp: str
) -> None:
    """Adiciona mensagem ao Redis (RPUSH + LTRIM + EXPIRE)."""
    r = _get_redis()
    if r is None:
        return

    try:
        key = _redis_key(user_id, agent_id)
        msg_json = json.dumps(
            {"role": role, "content": content, "timestamp": timestamp},
            ensure_ascii=False,
        )
        pipe = r.pipeline()
        pipe.rpush(key, msg_json)
        # Manter apenas as últimas N mensagens
        pipe.ltrim(key, -CHAT_HISTORY_MAX_MESSAGES, -1)
        pipe.expire(key, CHAT_HISTORY_TTL)
        pipe.execute()
    except Exception as e:
        logger.debug(f"Redis append failed: {e}")


def _save_batch_to_redis(
    user_id: int, agent_id: str, messages: list[dict]
) -> None:
    """Salva batch de mensagens no Redis (para warm-up do cache)."""
    r = _get_redis()
    if r is None:
        return

    try:
        key = _redis_key(user_id, agent_id)
        pipe = r.pipeline()
        pipe.delete(key)  # Limpa antes de repopular
        for msg in messages[-CHAT_HISTORY_MAX_MESSAGES:]:
            msg_json = json.dumps(msg, ensure_ascii=False)
            pipe.rpush(key, msg_json)
        pipe.expire(key, CHAT_HISTORY_TTL)
        pipe.execute()
    except Exception as e:
        logger.debug(f"Redis batch save failed: {e}")


def _save_to_sqlite(
    user_id: int, agent_id: str, role: str, content: str
) -> None:
    """Salva mensagem no SQLite (fonte de verdade permanente)."""
    try:
        from database.models import ChatMessage, SessionLocal

        db = SessionLocal()
        try:
            db.add(ChatMessage(
                user_id=user_id,
                agent_id=agent_id,
                role=role,
                content=content,
            ))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"SQLite chat save failed: {e}")


# ============================================================================
# UTILIDADES
# ============================================================================

def clear_context(user_id: int, agent_id: str) -> None:
    """Limpa contexto de chat do Redis (SQLite permanece inalterado)."""
    r = _get_redis()
    if r is None:
        return
    try:
        r.delete(_redis_key(user_id, agent_id))
    except Exception:
        pass
