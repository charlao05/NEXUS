"""
NEXUS API - Sistema Unificado de IA e Automação
================================================

Integração completa:
- Backend CODEX (agentes de IA + automação web)
- Frontend NEXUS (dashboard + UX)
- Stripe Payments + Google AdSense
- 6 Agentes de IA operacionais
"""

import sys
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Configurar logging estruturado em produção
if os.getenv("ENVIRONMENT") == "production":
    import json as _json

    class _JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_obj = {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            if record.exc_info and record.exc_info[1]:
                log_obj["exception"] = str(record.exc_info[1])
            return _json.dumps(log_obj, ensure_ascii=False)

    _handler = logging.StreamHandler()
    _handler.setFormatter(_JsonFormatter())
    logging.root.handlers = [_handler]
    logging.root.setLevel(logging.INFO)
else:
    logging.basicConfig(level=logging.INFO)

# Adicionar backend ao path para imports corretos
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(backend_dir.parent))

# Produção (Render rootDir=backend): o diretório-pai não tem 'backend/' como subpasta
# Criar alias de módulo para que 'from backend.xxx' resolva localmente
if not (backend_dir.parent / 'backend').exists():
    import types as _types
    _backend_mod = _types.ModuleType('backend')
    _backend_mod.__path__ = [str(backend_dir)]  # type: ignore[attr-defined]
    sys.modules['backend'] = _backend_mod

# Carregar variáveis de ambiente (.env) — ordem de prioridade (último vence):
#   1. .env (base)
#   2. .env.{ENVIRONMENT} (específico do ambiente: development, staging, production)
#   3. .env.local (override local, nunca commitado)
# Em testes (NEXUS_SKIP_DOTENV=1), pular load_dotenv para não sobrescrever env vars de teste.
if not os.getenv("NEXUS_SKIP_DOTENV"):
    # Detectar ambiente ANTES de carregar .env (pode vir do SO/container)
    _env_name = os.getenv("ENVIRONMENT", "development")

    dotenv_paths = [
        backend_dir / '.env',                           # backend/.env (base)
        backend_dir.parent / '.env',                    # NEXUS/.env (base)
        backend_dir / f'.env.{_env_name}',              # backend/.env.development (específico)
        backend_dir.parent / f'.env.{_env_name}',       # NEXUS/.env.development (específico)
        backend_dir / '.env.local',                     # backend/.env.local (override local)
        backend_dir.parent / '.env.local',              # NEXUS/.env.local (override principal)
    ]
    for dotenv_path in dotenv_paths:
        if dotenv_path.exists():
            load_dotenv(dotenv_path, override=True)
            logging.debug(f"📄 .env carregado: {dotenv_path.name}")
else:
    logging.info("⏭️ NEXUS_SKIP_DOTENV=1 — load_dotenv ignorado (modo teste)")

# Verificar se OPENAI_API_KEY está disponível
_oai_key = os.getenv("OPENAI_API_KEY", "")
_oai_model = os.getenv("OPENAI_MODEL", "gpt-4.1")
if _oai_key and not _oai_key.startswith("sk-proj-test"):
    logging.info(f"✅ OPENAI_API_KEY carregada (modelo: {_oai_model})")
else:
    logging.warning("⚠️ OPENAI_API_KEY não configurada ou é placeholder")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Lifespan handler — inicializa e encerra recursos."""
    # Validar variáveis obrigatórias em produção
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production":
        missing = []
        for var in ["JWT_SECRET", "DATABASE_URL"]:
            if not os.getenv(var):
                missing.append(var)
        if missing:
            logging.critical(f"❌ Variáveis obrigatórias ausentes em PRODUCTION: {', '.join(missing)}")
            sys.exit(1)
        # Alertar sobre opcionais importantes
        for var in ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"]:
            if not os.getenv(var):
                logging.warning(f"⚠️ {var} não configurada — funcionalidade de pagamentos desabilitada")

    # Inicializar Sentry (monitoramento)
    try:
        from app.api.monitoring import init_sentry  # type: ignore[import]
        init_sentry()
    except ImportError:
        pass
    # Startup
    if init_agents is not None:
        try:
            init_agents()
            logging.info("✅ Agent Hub e agentes inicializados")
        except Exception as e:
            logging.warning(f"Falha ao inicializar agentes: {e}")
    # Inicializar banco de dados
    try:
        from database.models import init_db  # type: ignore[import]
        init_db()
        logging.info("✅ Banco de dados inicializado")
    except Exception as e:
        logging.warning(f"Banco de dados não inicializado: {e}")
            # Seed admin user se ADMIN_SEED_EMAIL configurado
    _seed_email = os.getenv("ADMIN_EMAILS", "")
    if _seed_email:
        try:
            from database.models import SessionLocal, User  # type: ignore[import]
            _db = SessionLocal()
            try:
                for _em in _seed_email.split(","):
                    _em = _em.strip()
                    if not _em:
                        continue
                    _u = _db.query(User).filter(User.email == _em).first()
                    if _u and (_u.role != "admin" or _u.plan != "completo"):
                        _u.role = "admin"
                        _u.plan = "completo"
                        if _u.full_name and _u.full_name == _u.full_name.lower():
                            _u.full_name = _u.full_name.title()
                        _db.commit()
                        logging.info(f"Admin seed: {_em} promovido para admin/completo")
            finally:
                _db.close()
        except Exception as _e:
            logging.warning(f"Admin seed falhou: {_e}")
    yield
    # Shutdown (cleanup se necessário)
    logging.info("🛑 NEXUS API encerrando")


# Variável global para init_agents (será preenchida pelo import abaixo)
init_agents = None

app = FastAPI(
    title="NEXUS API",
    version="1.0.0",
    description="Sistema de automação empresarial com agentes de IA — CRM, Agenda, Contabilidade, Cobrança e Assistente.",
    contact={"name": "NEXUS Suporte", "email": "suporte@nexus.app"},
    license_info={"name": "Proprietário"},
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENVIRONMENT") != "production" else None,
    openapi_url="/openapi.json" if os.getenv("ENVIRONMENT") != "production" else None,
    lifespan=lifespan,
)

# CORS configurado — dinâmico por ambiente
_cors_origins_env = os.getenv("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()] if _cors_origins_env else []

_is_production = os.getenv("ENVIRONMENT") == "production"

# Adicionar origens de desenvolvimento APENAS fora de produção
if not _is_production:
    _cors_origins += [
        "http://127.0.0.1:5173", "http://localhost:5173",
        "http://127.0.0.1:5175", "http://localhost:5175",
    ]

# Adicionar FRONTEND_URL se existir (usado em produção)
_frontend_url = os.getenv("FRONTEND_URL", "")
if _frontend_url and _frontend_url not in _cors_origins:
    _cors_origins.append(_frontend_url)

logging.info(f"🌐 CORS origins configurados: {_cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"] if _is_production else ["*"],
    allow_headers=["Authorization", "Content-Type", "Accept"] if _is_production else ["*"],
)


# ── Security headers middleware ──
from starlette.middleware.base import BaseHTTPMiddleware  # type: ignore[import]
from starlette.responses import Response as StarletteResponse  # type: ignore[import]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Security headers padrão enterprise (OpenAI/Anthropic/Google-grade)."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response: StarletteResponse = await call_next(request)

        # ── Headers universais (dev + prod) ──
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"  # desativado em favor de CSP (OWASP recomenda)
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(self), microphone=(self), geolocation=(), "
            "payment=(self), usb=(), magnetometer=(), gyroscope=(), accelerometer=()"
        )
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        # ── Cache-Control para endpoints de API (nunca cachear dados sensíveis) ──
        path = request.url.path
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"

        # ── Headers adicionais em produção ──
        if os.getenv("ENVIRONMENT") == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
            _frontend = os.getenv("FRONTEND_URL", "https://nexus.app").rstrip("/")
            csp = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                f"connect-src 'self' https://api.stripe.com {_frontend}; "
                "frame-src https://js.stripe.com https://hooks.stripe.com; "
                "frame-ancestors 'none'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self' https://accounts.google.com https://www.facebook.com https://checkout.stripe.com"
            )
            response.headers["Content-Security-Policy"] = csp

        return response


app.add_middleware(SecurityHeadersMiddleware)

# ── Rate limiting middleware ──
try:
    from app.api.rate_limit import RateLimitMiddleware  # type: ignore[import]
    app.add_middleware(RateLimitMiddleware)
    logging.info("✅ Rate limiting middleware ativo")
except ImportError as e:
    logging.warning(f"Rate limiting não carregado: {e}")

@app.get("/health")
async def health():
    """Health check com status de serviços."""
    health_info: dict[str, Any] = {"status": "ok", "service": "NEXUS Backend"}

    # Database check
    try:
        from database.models import SessionLocal  # type: ignore[import]
        from sqlalchemy import text as sa_text  # type: ignore[import]
        db = SessionLocal()
        db.execute(sa_text("SELECT 1"))
        db.close()
        health_info["database"] = "connected"
    except Exception as e:
        logger.error(f"Health check DB error: {e}")
        health_info["database"] = "error"
        health_info["status"] = "degraded"

    # Redis check
    try:
        from app.api.redis_client import get_redis, redis_available  # type: ignore[import]
        health_info["redis"] = "connected" if redis_available() else "unavailable"
    except ImportError:
        health_info["redis"] = "not_configured"

    # Sentry check
    sentry_dsn = os.getenv("SENTRY_DSN", "")
    health_info["sentry"] = "active" if sentry_dsn else "not_configured"

    return health_info

@app.get("/")
async def root():
    return {"message": "NEXUS API está rodando"}


# Importar rotas de autenticação
try:
    from app.api.auth import router as auth_router  # type: ignore[import]
    app.include_router(auth_router)  # type: ignore[arg-type]
    logging.info("✅ Rotas de autenticação carregadas")
except ImportError as e:
    logging.warning(f"Não foi possível importar auth routes: {e}")

# Importar rotas LLM — REMOVIDO: legado, substituído por agent_chat.get_llm_response
# Endpoints /api/llm/* não possuem consumidores no frontend
# from routes import llm_routes
# app.include_router(llm_routes.router)

# Importar rotas do Agent Hub (comunicação entre agentes)
try:
    from app.api.agent_hub import router as agent_hub_router, init_agents as _init_agents_fn  # type: ignore[import]
    app.include_router(agent_hub_router)  # type: ignore[arg-type]
    init_agents = _init_agents_fn  # type: ignore[assignment]
except ImportError as e:
    logging.warning(f"Não foi possível importar agent_hub routes: {e}")

# Importar rotas de mídia dos agentes (áudio/Whisper + upload/Vision)
try:
    from app.api.agent_media import router as agent_media_router  # type: ignore[import]
    app.include_router(agent_media_router)  # type: ignore[arg-type]
    logging.info("✅ Rotas de mídia dos agentes (áudio + upload) carregadas")
except ImportError as e:
    logging.warning(f"Não foi possível importar agent_media routes: {e}")

# Importar rotas CRM (automação web legada removida — substituída por /api/agents/automation)
try:
    from app.api.crm_routes import router as crm_router  # type: ignore[import]
    app.include_router(crm_router)  # type: ignore[arg-type]
    logging.info("✅ Rotas CRM carregadas")
except ImportError as e:
    logging.warning(f"Não foi possível importar crm_routes: {e}")

# Importar rotas de Chat History e Analytics
try:
    from app.api.chat_history import router as chat_router, analytics_router  # type: ignore[import]
    app.include_router(chat_router)  # type: ignore[arg-type]
    app.include_router(analytics_router)  # type: ignore[arg-type]
    logging.info("✅ Rotas de Chat History e Analytics carregadas")
except ImportError as e:
    logging.warning(f"Não foi possível importar chat_history routes: {e}")

# Importar rotas de Notificações (SSE)
try:
    from app.api.notifications import router as notifications_router  # type: ignore[import]
    app.include_router(notifications_router)  # type: ignore[arg-type]
    logging.info("✅ Rotas de Notificações SSE carregadas")
except ImportError as e:
    logging.warning(f"Não foi possível importar notifications routes: {e}")

# Importar rotas Admin Dashboard
try:
    from app.api.admin import router as admin_router  # type: ignore[import]
    app.include_router(admin_router)  # type: ignore[arg-type]
    logging.info("✅ Rotas Admin Dashboard carregadas")
except ImportError as e:
    logging.warning(f"Não foi possível importar admin routes: {e}")

# Importar rotas do Orquestrador LangGraph
try:
    from app.api.orchestrator import router as orchestrator_router  # type: ignore[import]
    app.include_router(orchestrator_router)  # type: ignore[arg-type]
    logging.info("✅ Rotas do Orquestrador LangGraph carregadas")
except ImportError as e:
    logging.warning(f"Não foi possível importar orchestrator routes: {e}")

# Importar rotas de Automação (ponte chat → orchestrator)
try:
    from app.api.agent_automation import router as agent_automation_router  # type: ignore[import]
    app.include_router(agent_automation_router)  # type: ignore[arg-type]
    logging.info("✅ Rotas de Automação de Agentes carregadas")
except ImportError as e:
    logging.warning(f"Não foi possível importar agent automation routes: {e}")

# Importar rotas de Integrações Governamentais (CNPJ, CND, NFSe, Transparência)
try:
    from app.api.gov_integrations import router as gov_router  # type: ignore[import]
    app.include_router(gov_router)  # type: ignore[arg-type]
    logging.info("✅ Rotas de Integrações Governamentais carregadas")
except ImportError as e:
    logging.warning(f"Não foi possível importar gov_integrations routes: {e}")

# Importar rotas de Inventário / Estoque
try:
    from app.api.inventory_routes import router as inventory_router  # type: ignore[import]
    app.include_router(inventory_router)  # type: ignore[arg-type]
    logging.info("✅ Rotas de Inventário/Estoque carregadas")
except ImportError as e:
    logging.warning(f"Não foi possível importar inventory routes: {e}")

# Pré-carregar módulo de inteligência dos agentes (OpenAI GPT-4.1)
try:
    from app.api.agent_chat import get_llm_response  # type: ignore[import]  # noqa: F401
    logging.info("✅ Módulo de inteligência GPT-4.1 carregado")
except ImportError as e:
    logging.warning(f"Módulo agent_chat indisponível: {e}")


# Importar rotas de Billing (Stripe Payments)
try:
    from app.api.billing import router as billing_router  # type: ignore[import]
    app.include_router(billing_router)  # type: ignore[arg-type]
    logging.info("✅ Rotas de Billing (Stripe) carregadas")
except ImportError as e:
    logging.warning(f"Não foi possível importar billing routes: {e}")

# ==================== ERROR HANDLERS ====================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Tratador global de exceções"""
    logging.error(f"Erro não tratado: {str(exc)}")
    # Reportar ao Sentry se ativo
    try:
        from app.api.monitoring import capture_exception  # type: ignore[import]
        capture_exception(exc, url=str(request.url), method=request.method)
    except ImportError:
        pass
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


# ============================================================================
# EXECUÇÃO PRINCIPAL
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*80)
    print("🚀 INICIANDO NEXUS API - BACKEND")
    print("="*80)
    print(f"📁 Path: {backend_dir}")
    print(f"🔗 URL: http://127.0.0.1:8000")
    print(f"📚 Docs: http://127.0.0.1:8000/docs")
    print("="*80 + "\n")

    try:
        uvicorn.run(
            "main:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n\n⛔ Servidor interrompido pelo usuário.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ ERRO AO INICIAR SERVIDOR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
