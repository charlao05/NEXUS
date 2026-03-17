"""
NEXUS — Configuração Centralizada
====================================
Ponto único de leitura de variáveis de ambiente para todo o backend.

Uso:
    from app.core.settings import settings

    settings.OPENAI_API_KEY   # str
    settings.is_production     # bool

Motivação (baseada em boas práticas python-dotenv):
- Centraliza todos os os.getenv() em UM lugar
- Fornece defaults explícitos e documentados
- Módulos/agentes importam 'settings' em vez de chamar os.getenv() diretamente
- Facilita testes (basta trocar settings.XXX no fixture)
- NÃO chama load_dotenv() — isso é feito UMA VEZ em backend/main.py

IMPORTANTE: Este módulo é ADITIVO. Os módulos existentes que usam os.getenv()
continuam funcionando normalmente. A migração para 'settings' é gradual.
"""

from __future__ import annotations

import os
from typing import Optional


class _Settings:
    """Configuração tipada lida de variáveis de ambiente (já carregadas por main.py)."""

    # ── Core ──────────────────────────────────────────────
    @property
    def ENVIRONMENT(self) -> str:
        return os.getenv("ENVIRONMENT", "development")

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def CORS_ORIGINS(self) -> str:
        return os.getenv("CORS_ORIGINS", "")

    @property
    def FRONTEND_URL(self) -> str:
        return os.getenv("FRONTEND_URL", "")

    @property
    def BACKEND_BASE_URL(self) -> str:
        return os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")

    # ── JWT ───────────────────────────────────────────────
    @property
    def JWT_SECRET(self) -> Optional[str]:
        return os.getenv("JWT_SECRET")

    @property
    def JWT_ALGORITHM(self) -> str:
        return os.getenv("JWT_ALGORITHM", "HS256")

    # ── Database ──────────────────────────────────────────
    @property
    def DATABASE_URL(self) -> str:
        return os.getenv("DATABASE_URL", "")

    # ── OpenAI / LLM ─────────────────────────────────────
    @property
    def OPENAI_API_KEY(self) -> str:
        return os.getenv("OPENAI_API_KEY", "")

    @property
    def OPENAI_MODEL(self) -> str:
        return os.getenv("OPENAI_MODEL", "gpt-4.1")

    # ── Stripe ────────────────────────────────────────────
    @property
    def STRIPE_SECRET_KEY(self) -> Optional[str]:
        return os.getenv("STRIPE_SECRET_KEY")

    @property
    def STRIPE_PUBLISHABLE_KEY(self) -> Optional[str]:
        return os.getenv("STRIPE_PUBLISHABLE_KEY")

    @property
    def STRIPE_WEBHOOK_SECRET(self) -> Optional[str]:
        return os.getenv("STRIPE_WEBHOOK_SECRET")

    # ── Google OAuth ──────────────────────────────────────
    @property
    def GOOGLE_CLIENT_ID(self) -> Optional[str]:
        return os.getenv("GOOGLE_CLIENT_ID")

    @property
    def GOOGLE_CLIENT_SECRET(self) -> Optional[str]:
        return os.getenv("GOOGLE_CLIENT_SECRET")

    @property
    def GOOGLE_REDIRECT_URI(self) -> str:
        return os.getenv(
            "GOOGLE_REDIRECT_URI",
            f"{self.BACKEND_BASE_URL}/api/auth/google/callback",
        )

    # ── Facebook OAuth ────────────────────────────────────
    @property
    def FACEBOOK_CLIENT_ID(self) -> Optional[str]:
        return os.getenv("FACEBOOK_CLIENT_ID")

    @property
    def FACEBOOK_CLIENT_SECRET(self) -> Optional[str]:
        return os.getenv("FACEBOOK_CLIENT_SECRET")

    # ── Redis ─────────────────────────────────────────────
    @property
    def REDIS_URL(self) -> str:
        return os.getenv("REDIS_URL", "")

    # ── Email (Resend) ────────────────────────────────────
    @property
    def RESEND_API_KEY(self) -> str:
        return os.getenv("RESEND_API_KEY", "")

    @property
    def EMAIL_FROM(self) -> str:
        return os.getenv("EMAIL_FROM", "NEXUS <onboarding@resend.dev>")

    # ── Sentry ────────────────────────────────────────────
    @property
    def SENTRY_DSN(self) -> str:
        return os.getenv("SENTRY_DSN", "")

    # ── Browser / Playwright ──────────────────────────────
    @property
    def DEFAULT_BROWSER(self) -> str:
        return os.getenv("DEFAULT_BROWSER", "chromium")

    # ── Integrações Gov ───────────────────────────────────
    @property
    def CND_PROVIDER(self) -> str:
        return os.getenv("CND_PROVIDER", "mock")

    @property
    def NFSE_AGGREGATOR_PROVIDER(self) -> str:
        return os.getenv("NFSE_AGGREGATOR_PROVIDER", "focus_nfe")

    def __repr__(self) -> str:
        """Representação segura — nunca expõe valores de secrets."""
        return (
            f"<Settings env={self.ENVIRONMENT} "
            f"openai={'✓' if self.OPENAI_API_KEY else '✗'} "
            f"stripe={'✓' if self.STRIPE_SECRET_KEY else '✗'} "
            f"redis={'✓' if self.REDIS_URL else '✗'} "
            f"sentry={'✓' if self.SENTRY_DSN else '✗'}>"
        )


# Singleton — importar em qualquer módulo com: from app.core.settings import settings
settings = _Settings()
