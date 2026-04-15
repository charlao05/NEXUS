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


# ── Debug: OpenAI runtime state ──────────────────────────────────────────────
# Protegido por token fixo pra evitar exposição pública. Remover após diagnóstico.
@app.get("/debug/openai", tags=["debug"])
async def debug_openai(token: str = ""):
    """Dump não-mascarado do estado da OPENAI_API_KEY vista pelo processo + teste direto.

    Uso: GET /debug/openai?token=nx_debug_2026_april
    """
    if token != "nx_debug_2026_april":
        return {"error": "unauthorized"}

    key = os.getenv("OPENAI_API_KEY", "")
    result: dict = {
        "env_OPENAI_API_KEY_length": len(key),
        "env_OPENAI_API_KEY_prefix": key[:20] if key else None,
        "env_OPENAI_API_KEY_suffix": key[-10:] if key else None,
        "env_OPENAI_API_KEY_has_whitespace": any(c in key for c in [" ", "\n", "\t", "\r"]),
        "env_OPENAI_API_KEY_has_quotes": key.startswith('"') or key.startswith("'") or key.endswith('"') or key.endswith("'"),
        "env_OPENAI_MODEL": os.getenv("OPENAI_MODEL", "<not_set>"),
        "env_OPENAI_ORG_ID": os.getenv("OPENAI_ORG_ID", "<not_set>"),
        "env_OPENAI_ORGANIZATION": os.getenv("OPENAI_ORGANIZATION", "<not_set>"),
    }

    # Teste real da chave
    try:
        from openai import OpenAI
        c = OpenAI(api_key=key)
        r = c.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        result["openai_test"] = "OK"
        result["openai_response"] = r.choices[0].message.content
        result["openai_model_used"] = r.model
    except Exception as e:
        result["openai_test"] = "FAIL"
        result["openai_error_type"] = type(e).__name__
        result["openai_error_message"] = str(e)[:500]

    return result


# ── Startup / Shutdown Events ─────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    logger.info(f"NEXUS API iniciando — ambiente: {_env}")
    logger.info(f"CORS origins: {_origins}")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("NEXUS API encerrando...")
