"""
NEXUS — Testes do Chat Context Service (Lacuna #18)
=====================================================
Testa load/save de contexto de chat com mock de Redis e SQLite.
"""

import json
from unittest.mock import MagicMock, patch, call

import pytest


# ── FIXTURES ────────────────────────────────────────────────────


class FakeRedisPipeline:
    """Mock de pipeline Redis para testes."""

    def __init__(self, store: dict):
        self._store = store
        self._ops: list = []

    def rpush(self, key, value):
        self._ops.append(("rpush", key, value))
        return self

    def ltrim(self, key, start, stop):
        self._ops.append(("ltrim", key, start, stop))
        return self

    def expire(self, key, ttl):
        self._ops.append(("expire", key, ttl))
        return self

    def delete(self, key):
        self._ops.append(("delete", key))
        return self

    def execute(self):
        for op in self._ops:
            if op[0] == "rpush":
                _, key, value = op
                self._store.setdefault(key, []).append(value)
            elif op[0] == "ltrim":
                _, key, start, stop = op
                if key in self._store:
                    lst = self._store[key]
                    if stop == -1:
                        self._store[key] = lst[start:]
                    else:
                        self._store[key] = lst[start : stop + 1]
            elif op[0] == "delete":
                _, key = op
                self._store.pop(key, None)
        self._ops.clear()
        return []


class FakeRedis:
    """Mock completo de redis.Redis para testes do chat_context."""

    def __init__(self):
        self._store: dict[str, list] = {}

    def lrange(self, key, start, end):
        lst = self._store.get(key, [])
        return lst[start : end + 1] if lst else []

    def exists(self, key) -> bool:
        return key in self._store

    def pipeline(self):
        return FakeRedisPipeline(self._store)

    def delete(self, key):
        self._store.pop(key, None)


@pytest.fixture
def fake_redis():
    return FakeRedis()


# ── TESTS ───────────────────────────────────────────────────────


class TestChatContextRedisKey:
    """Testa o formato da chave Redis."""

    def test_key_format(self):
        from app.services.chat_context import _redis_key

        assert _redis_key(42, "agenda") == "chat_history:42:agenda"
        assert _redis_key(1, "financeiro") == "chat_history:1:financeiro"


class TestSaveMessage:
    """Testa save_message (dual-write Redis + SQLite)."""

    @patch("app.services.chat_context._save_to_sqlite")
    @patch("app.services.chat_context._get_redis")
    def test_save_message_with_redis(self, mock_get_redis, mock_sqlite, fake_redis):
        """Mensagem deve ser salva no Redis E no SQLite."""
        mock_get_redis.return_value = fake_redis
        mock_sqlite.return_value = None

        from app.services.chat_context import save_message

        save_message(user_id=1, agent_id="agenda", role="user", content="Olá")

        # Redis deve ter 1 mensagem
        key = "chat_history:1:agenda"
        assert key in fake_redis._store
        assert len(fake_redis._store[key]) == 1
        msg = json.loads(fake_redis._store[key][0])
        assert msg["role"] == "user"
        assert msg["content"] == "Olá"
        assert "timestamp" in msg

        # SQLite deve ter sido chamado
        mock_sqlite.assert_called_once_with(1, "agenda", "user", "Olá")

    @patch("app.services.chat_context._save_to_sqlite")
    @patch("app.services.chat_context._get_redis")
    def test_save_message_without_redis(self, mock_get_redis, mock_sqlite):
        """Sem Redis, deve salvar apenas no SQLite sem erros."""
        mock_get_redis.return_value = None
        mock_sqlite.return_value = None

        from app.services.chat_context import save_message

        save_message(user_id=1, agent_id="agenda", role="assistant", content="Resposta")

        mock_sqlite.assert_called_once_with(1, "agenda", "assistant", "Resposta")


class TestSaveTurn:
    """Testa save_turn (salva par user+assistant)."""

    @patch("app.services.chat_context._save_to_sqlite")
    @patch("app.services.chat_context._get_redis")
    def test_save_turn_both_messages(self, mock_get_redis, mock_sqlite, fake_redis):
        """save_turn deve salvar 2 mensagens (user + assistant)."""
        mock_get_redis.return_value = fake_redis
        mock_sqlite.return_value = None

        from app.services.chat_context import save_turn

        save_turn(user_id=5, agent_id="financeiro", user_message="Qual meu lucro?", assistant_message="Lucro: R$1.200")

        key = "chat_history:5:financeiro"
        assert len(fake_redis._store[key]) == 2
        msgs = [json.loads(m) for m in fake_redis._store[key]]
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert mock_sqlite.call_count == 2


class TestLoadChatHistory:
    """Testa load_chat_history com Redis e fallback SQLite."""

    @patch("app.services.chat_context._get_redis")
    def test_load_from_redis(self, mock_get_redis, fake_redis):
        """Se Redis tem dados, deve retornar sem consultar SQLite."""
        # Pré-popular Redis
        key = "chat_history:10:agenda"
        fake_redis._store[key] = [
            json.dumps({"role": "user", "content": "msg1", "timestamp": "2025-01-01T00:00:00"}),
            json.dumps({"role": "assistant", "content": "resp1", "timestamp": "2025-01-01T00:00:01"}),
        ]
        mock_get_redis.return_value = fake_redis

        from app.services.chat_context import load_chat_history

        history = load_chat_history(user_id=10, agent_id="agenda")

        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "msg1"
        assert history[1]["role"] == "assistant"

    @patch("app.services.chat_context._save_batch_to_redis")
    @patch("app.services.chat_context._load_from_sqlite")
    @patch("app.services.chat_context._get_redis")
    def test_fallback_to_sqlite_when_no_redis(self, mock_get_redis, mock_sqlite, mock_batch):
        """Se Redis indisponível, deve usar SQLite e aquecer cache."""
        mock_get_redis.return_value = None  # Redis não disponível
        mock_sqlite.return_value = [
            {"role": "user", "content": "Olá", "timestamp": "2025-01-01T00:00:00"},
            {"role": "assistant", "content": "Oi!", "timestamp": "2025-01-01T00:00:01"},
        ]

        from app.services.chat_context import load_chat_history

        history = load_chat_history(user_id=20, agent_id="clientes")

        assert len(history) == 2
        mock_sqlite.assert_called_once_with(20, "clientes", 20)
        # Cache batch save deve ser chamado para aquecer Redis na próxima
        mock_batch.assert_called_once()

    @patch("app.services.chat_context._get_redis")
    def test_load_returns_empty_when_no_data(self, mock_get_redis):
        """Se nenhuma fonte tem dados, retorna lista vazia."""
        mock_get_redis.return_value = None

        from app.services.chat_context import load_chat_history

        with patch("app.services.chat_context._load_from_sqlite", return_value=[]):
            history = load_chat_history(user_id=99, agent_id="agenda")

        assert history == []


class TestRedisTrimming:
    """Testa que Redis respeita o limite de 20 mensagens."""

    @patch("app.services.chat_context._save_to_sqlite")
    @patch("app.services.chat_context._get_redis")
    def test_max_messages_trimmed(self, mock_get_redis, mock_sqlite, fake_redis):
        """Redis deve manter no máximo CHAT_HISTORY_MAX_MESSAGES."""
        mock_get_redis.return_value = fake_redis
        mock_sqlite.return_value = None

        from app.services.chat_context import save_message, CHAT_HISTORY_MAX_MESSAGES

        # Salvar 25 mensagens (excede limite de 20)
        for i in range(25):
            save_message(user_id=1, agent_id="agenda", role="user", content=f"msg-{i}")

        key = "chat_history:1:agenda"
        assert len(fake_redis._store[key]) <= CHAT_HISTORY_MAX_MESSAGES


class TestClearContext:
    """Testa clear_context."""

    @patch("app.services.chat_context._get_redis")
    def test_clear_removes_redis_key(self, mock_get_redis, fake_redis):
        """clear_context deve remover a chave do Redis."""
        key = "chat_history:1:agenda"
        fake_redis._store[key] = [json.dumps({"role": "user", "content": "test"})]
        mock_get_redis.return_value = fake_redis

        from app.services.chat_context import clear_context

        clear_context(user_id=1, agent_id="agenda")

        assert key not in fake_redis._store

    @patch("app.services.chat_context._get_redis")
    def test_clear_no_redis_no_error(self, mock_get_redis):
        """clear_context sem Redis não deve dar erro."""
        mock_get_redis.return_value = None

        from app.services.chat_context import clear_context

        # Não deve lançar exceção
        clear_context(user_id=1, agent_id="agenda")
