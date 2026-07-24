"""
NEXUS — FastAPI Application Entry Point
=========================================
Carrega variáveis de ambiente, configura middlewares, registra todos os
routers e expõe o objeto `app` para o Gunicorn/Uvicorn.

Startup:
  gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
  uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from pathlib import Path

# Carrega .env ANTES de qualquer import que leia os.getenv()
# Primeiro tenta backend/.env, depois root/.env (para pegar STRIPE, GOOGLE, etc.)
_backend_env = Path(__file__).parent / ".env"
_root_env = Path(__file__).parent.parent / ".env"
load_dotenv(_backend_env)
load_dotenv(_root_env)  # não sobrescreve vars já definidas (override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Sentry (opcional) ─────────────────────────────────────────────────────────
try:
    from app.api.monitoring import init_sentry
    init_sentry()
except Exception:
    pass

# ── FastAPI App ───────────────────────────────────────────────────────────────
_env = os.getenv("ENVIRONMENT", "development")
_is_prod = _env == "production"

app = FastAPI(
    title="NEXUS API",
    description="Plataforma SaaS de diagnóstico empresarial com IA",
    version="1.0.0",
    docs_url=None if _is_prod else "/docs",
    redoc_url=None,
    openapi_url=None if _is_prod else "/openapi.json",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
_raw_origins = os.getenv(
    "CORS_ORIGINS",
    "https://app.nexxusapp.com.br,https://nexxusapp.com.br",
)
_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# Em desenvolvimento, permite localhost
if not _is_prod:
    _origins += [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Security Headers Middleware ───────────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as _Request
from starlette.responses import Response as _Response


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: _Request, call_next):  # type: ignore[override]
        response: _Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if _is_prod:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(_SecurityHeadersMiddleware)

# ── Rate Limit Middleware (opcional) ─────────────────────────────────────────
try:
    from app.api.rate_limit import NexusRateLimitMiddleware
    app.add_middleware(NexusRateLimitMiddleware)
except Exception as exc:
    logger.warning(f"Rate limit middleware não carregado: {exc}")

# ── Routers ───────────────────────────────────────────────────────────────────
def _include(module_path: str, attr: str = "router") -> None:
    """Importa um módulo e registra seu router; loga ERROR com stack se falhar.

    CRÍTICO: falhas silenciosas aqui causam 404 nas rotas (ex: agent_hub.py em 2026-04-15).
    Loga em nível ERROR com exc_info pra aparecer nos logs do Render.
    """
    try:
        parts = module_path.split(".")
        mod = __import__(module_path, fromlist=[parts[-1]])
        router = getattr(mod, attr)
        app.include_router(router)
        logger.info(f"[ROUTER-OK] {module_path}")
    except Exception as exc:
        logger.error(
            f"[ROUTER-FAIL] {module_path} → {type(exc).__name__}: {exc} "
            f"(rotas deste módulo retornarão 404 até o import ser consertado)",
            exc_info=True,
        )


# Core — auth e billing primeiro (dependências de outros routers)
_include("app.api.auth")
_include("app.api.billing")

# Agentes
_include("app.api.agent_hub")
_include("app.api.agent_automation")
_include("app.api.agent_media")

# Chat e orquestração
_include("app.api.chat_history")
_include("app.api.orchestrator")

# Dados de negócio
_include("app.api.crm_routes")
_include("app.api.inventory_routes")

# Plataforma
_include("app.api.admin")
_include("app.api.notifications")
_include("app.api.gov_integrations")

# Integrações externas (opcionais — podem falhar se dependências não instaladas)
_include("app.api.telegram")
_include("routes.llm_routes")


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health_check():
    """Endpoint de saúde para o Render e load balancers."""
    info: dict = {"status": "ok", "service": "NEXUS Backend"}

    # Database
    try:
        from database.models import SessionLocal
        from sqlalchemy import text as _text
        _db = SessionLocal()
        _db.execute(_text("SELECT 1"))
        _db.close()
        info["database"] = "connected"
    except Exception as _e:
        logger.error(f"Health check DB error: {_e}")
        info["database"] = "error"
        info["status"] = "degraded"

    # Redis
    try:
        from app.api.redis_client import redis_available
        info["redis"] = "connected" if redis_available() else "unavailable"
    except Exception:
        info["redis"] = "not_configured"

    # Sentry
    info["sentry"] = "active" if os.getenv("SENTRY_DSN") else "not_configured"

    return info


# ── Startup / Shutdown Events ─────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    logger.info(f"NEXUS API iniciando — ambiente: {_env}")
    logger.info(f"CORS origins: {_origins}")
    # Garante o schema no RUNTIME (idempotente). DATABASE_URL está sempre
    # disponível aqui — diferente do build, onde o Postgres do Render pode
    # não estar acessível. create_all só cria tabelas ausentes.
    try:
        from database.models import Base, engine
        Base.metadata.create_all(engine)
        logger.info("Schema do banco verificado/criado no startup (create_all).")
    except Exception as e:
        logger.error(f"Falha ao verificar/criar schema no startup: {e}",
                     exc_info=True)

    # Migração idempotente de COLUNAS novas.
    # create_all() cria TABELAS ausentes, mas NÃO adiciona coluna em tabela que
    # já existe — e este deploy NÃO executa alembic (render.yaml não chama
    # `alembic upgrade`; o schema de produção veio todo do create_all). Precisa
    # rodar ANTES de qualquer query em User: o SELECT do SQLAlchemy já inclui a
    # coluna nova e falharia se ela não existisse no banco.
    try:
        from database.models import engine as _eng
        from sqlalchemy import inspect as _inspect, text as _text
        _colunas_novas = [
            # (tabela, coluna, DDL) — compatível com Postgres e SQLite
            ("users", "profile_type", "VARCHAR(20) DEFAULT 'mei'"),
        ]
        _insp = _inspect(_eng)
        _tabelas = set(_insp.get_table_names())
        for _tab, _col, _ddl in _colunas_novas:
            if _tab not in _tabelas:
                continue  # create_all já criou com a coluna
            if _col in {c["name"] for c in _insp.get_columns(_tab)}:
                continue  # já migrado
            with _eng.begin() as _conn:
                _conn.execute(_text(f"ALTER TABLE {_tab} ADD COLUMN {_col} {_ddl}"))
            logger.info(f"Migração: coluna {_tab}.{_col} adicionada.")
    except Exception as e:
        logger.error(f"Falha na migração de colunas no startup: {e}", exc_info=True)

    # Owner bootstrap (idempotente): garante que qualquer conta cujo email
    # esteja em ADMIN_EMAILS seja admin + plano completo. Cobre o caso de a
    # conta já existir antes de a env ser definida. Sem ADMIN_EMAILS, no-op.
    try:
        _admins = [
            e.strip().lower()
            for e in os.getenv("ADMIN_EMAILS", "").split(",")
            if e.strip()
        ]
        if _admins:
            from database.models import SessionLocal, User
            from sqlalchemy import func as _func
            _db = SessionLocal()
            try:
                _promoted = 0
                rows = (
                    _db.query(User)
                    .filter(_func.lower(User.email).in_(_admins))
                    .all()
                )
                for _u in rows:
                    changed = False
                    if _u.plan != "completo":
                        _u.plan = "completo"
                        changed = True
                    if _u.role != "admin":
                        _u.role = "admin"
                        changed = True
                    if changed:
                        _promoted += 1
                if _promoted:
                    _db.commit()
                    logger.info(
                        f"Owner bootstrap: {_promoted} conta(s) promovida(s) "
                        f"a admin+completo."
                    )
            finally:
                _db.close()
    except Exception as e:
        logger.error(f"Owner bootstrap falhou (não-fatal): {e}", exc_info=True)


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("NEXUS API encerrando...")
