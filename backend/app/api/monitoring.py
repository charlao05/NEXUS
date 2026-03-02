"""
NEXUS - Sentry Monitoring
===========================
Integração com Sentry para monitoramento de erros e performance.
Ativa apenas com SENTRY_DSN configurado.
"""

import os
import logging

logger = logging.getLogger(__name__)


def init_sentry() -> bool:
    """
    Inicializa o Sentry SDK. Retorna True se ativado.
    Requer env var SENTRY_DSN.
    """
    dsn = os.getenv("SENTRY_DSN", "")
    if not dsn:
        logger.info("SENTRY_DSN não configurado — monitoramento Sentry desativado")
        return False

    try:
        import sentry_sdk  # type: ignore[import-unresolved]
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore[import-unresolved]
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration  # type: ignore[import-unresolved]

        environment = os.getenv("ENVIRONMENT", "development")
        release = os.getenv("SENTRY_RELEASE", "nexus@0.4.0")

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            traces_sample_rate=0.2 if environment == "production" else 1.0,
            profiles_sample_rate=0.1 if environment == "production" else 0.5,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            # Não enviar dados sensíveis
            send_default_pii=False,
            # Filtrar transações de health check
            traces_sampler=_traces_sampler,
        )
        logger.info(f"✅ Sentry inicializado ({environment}, release={release})")
        return True

    except ImportError:
        logger.warning("sentry-sdk não instalado — pip install sentry-sdk[fastapi]")
        return False
    except Exception as e:
        logger.error(f"Falha ao inicializar Sentry: {e}")
        return False


def _traces_sampler(sampling_context: dict) -> float:
    """Sampler customizado — ignora health checks e docs."""
    transaction_context = sampling_context.get("transaction_context", {})
    name = transaction_context.get("name", "")

    # Não rastrear health checks
    if name in ("/health", "/", "/openapi.json") or name.startswith("/docs"):
        return 0.0

    # Admin e auth — taxa mais alta
    if "/admin/" in name or "/auth/" in name:
        return 1.0

    # Default
    env = os.getenv("ENVIRONMENT", "development")
    return 0.2 if env == "production" else 1.0


def capture_exception(exc: Exception, **extra) -> None:
    """Wrapper para capturar exceção no Sentry (se ativo)."""
    try:
        import sentry_sdk  # type: ignore[import-unresolved]
        scope = sentry_sdk.get_current_scope()
        for key, value in extra.items():
            scope.set_extra(key, value)
        sentry_sdk.capture_exception(exc)
    except (ImportError, Exception):
        pass


def set_user_context(user_id: int, email: str, plan: str = "free") -> None:
    """Define contexto de usuário no Sentry."""
    try:
        import sentry_sdk  # type: ignore[import-unresolved]
        sentry_sdk.set_user({
            "id": str(user_id),
            "email": email,
            "subscription": plan,
        })
    except ImportError:
        pass
