import os
import sys
from pathlib import Path

# ── ISOLAMENTO: banco em memória para todos os testes ──
# Sobrescreve DATABASE_URL ANTES de qualquer import do app.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENVIRONMENT"] = "test"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"  # DB 1 separado

# Impedir que main.py load_dotenv(override=True) sobrescreva DATABASE_URL
os.environ["NEXUS_SKIP_DOTENV"] = "1"

"""
NEXUS — Configuração global de testes (backend)
=================================================
Garante que ENVIRONMENT=test está setado antes de qualquer teste,
desabilitando rate limiting e outros comportamentos de produção.
Usa banco SQLite em memória (StaticPool) — NÃO polui o banco real.

IMPORTANTE: database.models é importado aqui para garantir que o engine
seja criado com :memory: ANTES que qualquer teste importe app.api.*
transitivamente (ex: app.api.notifications importa models).
"""

# Garantir que backend está no PYTHONPATH
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Forçar import de models para criar engine :memory: com StaticPool
# ANTES que qualquer teste importe app.api.* transitivamente
from database.models import init_db  # noqa: E402
init_db()
