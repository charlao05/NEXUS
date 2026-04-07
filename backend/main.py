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

# Carrega .env ANTES de qualquer import que leia os.getenv()
load_dotenv()

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

# ── Rate Limit Middleware (opcional) ─────────────────────────────────────────
try:
    from app.api.rate_limit import NexusRateLimitMiddleware
    app.add_middleware(NexusRateLimitMiddleware)
except Exception as exc:
    logger.warning(f"Rate limit middleware não carregado: {exc}")

# ── Routers ───────────────────────────────────────────────────────────────────
def _include(module_path: str, attr: str = "router") -> None:
    """Importa um módulo e registra seu router; loga aviso se falhar."""
    try:
        parts = module_path.split(".")
        mod = __import__(module_path, fromlist=[parts[-1]])
        router = getattr(mod, attr)
        app.include_router(router)
        logger.info(f"Router registrado: {module_path}")
    except Exception as exc:
        logger.warning(f"Router NÃO carregado ({module_path}): {exc}")


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


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("NEXUS API encerrando...")
