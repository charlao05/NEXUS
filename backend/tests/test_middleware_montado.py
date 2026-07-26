# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
Testes de MONTAGEM de middleware — o app tem mesmo o que pensa que tem?
=======================================================================

POR QUE ESTE ARQUIVO EXISTE
---------------------------
O rate limit NUNCA esteve ativo, nem em producao. main.py importava
"NexusRateLimitMiddleware", nome que nunca existiu — a classe sempre se chamou
RateLimitMiddleware. Um `except Exception` engolia o ImportError e logava um
WARNING, entao o app subia "saudavel" com /api/auth/login e
/api/auth/forgot-password SEM limite algum.

Isso sobreviveu a uma suite verde porque tests/test_fase8.py:81-104 verifica
apenas as CONSTANTES da classe (EXEMPT_PREFIXES, AUTH_RATE_LIMITED,
AUTH_LIMITS), importando-a diretamente. Um teste que importa a classe prova que
a classe existe — nao que alguem a montou no app.

E a mesma licao do teste de integracao do /margin: verificar o componente nao e
verificar o sistema. Aqui o alvo e a MONTAGEM, nao o comportamento.

    cd backend && pytest tests/test_middleware_montado.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def app():
    backend = Path(__file__).parent.parent
    sys.path.insert(0, str(backend))
    os.environ.setdefault("JWT_SECRET", "test-secret-middleware")
    os.environ.setdefault(
        "NEXUS_DB_PATH", str(backend / "data" / "test_middleware.db"))
    from main import app as _app
    return _app


def _nomes(app) -> list[str]:
    return [m.cls.__name__ for m in app.user_middleware]


def test_rate_limit_esta_montado(app):
    """REGRESSAO: o middleware de rate limit precisa estar NO APP.

    Se este teste falhar, /api/auth/login e /api/auth/forgot-password estao sem
    protecao contra brute force e email bombing — mesmo que a classe exista e
    mesmo que os testes de constantes passem.
    """
    nomes = _nomes(app)
    assert any("RateLimit" in n for n in nomes), (
        f"RateLimitMiddleware NAO esta montado. Middlewares presentes: {nomes}. "
        "Login e recuperacao de senha estao sem rate limit."
    )


def test_security_headers_esta_montado(app):
    """O outro middleware de seguranca — mesma classe de risco."""
    nomes = _nomes(app)
    assert any("SecurityHeaders" in n for n in nomes), (
        f"SecurityHeaders nao montado. Presentes: {nomes}")


def test_cors_esta_montado(app):
    nomes = _nomes(app)
    assert any("CORS" in n for n in nomes), f"CORS nao montado. Presentes: {nomes}"


def test_rotas_de_auth_sensiveis_estao_na_lista_do_rate_limit(app):
    """Montado nao basta: as rotas certas precisam estar cobertas.

    Um middleware montado que nao lista /api/auth/login deixaria o brute force
    livre do mesmo jeito.
    """
    from app.api.rate_limit import RateLimitMiddleware

    protegidas = RateLimitMiddleware.AUTH_RATE_LIMITED
    for rota in ("/api/auth/login", "/api/auth/signup",
                 "/api/auth/forgot-password", "/api/auth/reset-password"):
        assert rota in protegidas, f"{rota} fora do rate limit agressivo"


def test_import_do_middleware_nao_e_silencioso():
    """O nome importado por main.py precisa existir de verdade.

    Guarda contra a reintroducao do padrao original: importar um nome errado
    dentro de try/except e seguir em frente com um warning.
    """
    import app.api.rate_limit as rl

    assert hasattr(rl, "RateLimitMiddleware"), (
        "RateLimitMiddleware sumiu de app/api/rate_limit.py — main.py vai quebrar")
    assert not hasattr(rl, "NexusRateLimitMiddleware"), (
        "Alguem criou o alias NexusRateLimitMiddleware. Prefira corrigir o "
        "import em main.py a manter dois nomes para a mesma classe.")
