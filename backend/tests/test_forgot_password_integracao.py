# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
Recuperacao de senha — o teste que faltava
===========================================

POR QUE ESTE ARQUIVO EXISTE
---------------------------
tests/test_fase6.py cobre reset de senha e passa 10/10, mas NAO exercita a
etapa que estava quebrada:

  - test_full_password_reset_flow (:420-466) INJETA o token direto no banco com
    SessionLocal e so entao chama /api/auth/reset-password. Pula
    forgot-password E o envio de e-mail por completo.
  - test_forgot_password_with_real_user (:408-418) so verifica status_code==200
    — e a rota retornava 200 SEMPRE, ate quando o commit falhava. O teste
    passava sem provar nada.

Resultado: o endpoint respondia {"status":"sent"} sem enviar nada, e a suite
ficava verde.

O QUE ESTE ARQUIVO PROVA
------------------------
1. Servico de e-mail indisponivel -> 503, NAO 200 "sent" (o defeito principal).
2. As duas formas distintas de indisponibilidade sao detectadas: chave ausente
   E pacote 'resend' ausente (esta segunda passava despercebida mesmo com a
   chave correta configurada).
3. Com o servico no ar, o token e realmente PERSISTIDO no banco e a funcao de
   envio e chamada com o e-mail e o token corretos.
4. Anti-enumeracao continua valendo: e-mail cadastrado e nao cadastrado
   produzem resposta identica.

    cd backend && pytest tests/test_forgot_password_integracao.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

EMAIL_TESTE = "forgot-integracao@nexus.com"
SENHA = "Teste1234!"


@pytest.fixture(scope="module")
def app():
    backend = Path(__file__).parent.parent
    sys.path.insert(0, str(backend))
    os.environ.setdefault("JWT_SECRET", "test-secret-forgot")
    os.environ.setdefault(
        "NEXUS_DB_PATH", str(backend / "data" / "test_forgot.db"))
    from main import app as _app
    from database.models import init_db
    init_db()
    return _app


@pytest.fixture(scope="module")
def client(app):
    c = TestClient(app)
    c.post("/api/auth/signup", json={
        "email": EMAIL_TESTE, "password": SENHA, "full_name": "Forgot Teste"})
    return c


@pytest.fixture
def servico_no_ar(monkeypatch):
    """Simula o Resend operacional, sem enviar nada de verdade."""
    import app.api.email_service as es

    monkeypatch.setenv("RESEND_API_KEY", "re_fake_para_teste")
    monkeypatch.setattr(es, "email_service_disponivel", lambda: (True, "ok"))

    enviados: list[tuple[str, str]] = []

    def _fake_send(email, token):
        enviados.append((email, token))
        return {"status": "sent", "id": "fake"}

    monkeypatch.setattr(es, "send_password_reset_email", _fake_send)
    return enviados


# ==========================================================================
# 1. O DEFEITO PRINCIPAL — falso sucesso
# ==========================================================================
def test_sem_chave_responde_503_e_nao_sucesso(client, monkeypatch):
    """Sem RESEND_API_KEY a rota deve RECUSAR, nao dizer 'enviamos'."""
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    import app.api.email_service as es
    monkeypatch.setattr(es, "RESEND_API_KEY", "")

    resp = client.post("/api/auth/forgot-password", json={"email": EMAIL_TESTE})

    assert resp.status_code == 503, (
        f"REGRESSAO DO FALSO SUCESSO: esperado 503, veio {resp.status_code} "
        f"com corpo {resp.text}")
    assert resp.json()["detail"]["error"] == "EMAIL_SERVICE_UNAVAILABLE"
    print("\n  sem chave -> 503 EMAIL_SERVICE_UNAVAILABLE  OK")


def test_pacote_resend_ausente_tambem_e_detectado(monkeypatch):
    """A segunda forma de falha silenciosa: chave certa, pacote faltando.

    _get_resend() devolvia None nos dois casos, entao 'chave configurada' nunca
    foi garantia de que o e-mail sairia.
    """
    import builtins
    import app.api.email_service as es

    monkeypatch.setenv("RESEND_API_KEY", "re_fake_para_teste")

    real_import = builtins.__import__

    def _sem_resend(name, *a, **kw):
        if name == "resend":
            raise ImportError("simulado: pacote ausente")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _sem_resend)

    ok, motivo = es.email_service_disponivel()
    assert ok is False, "pacote ausente deveria tornar o servico indisponivel"
    assert "resend" in motivo
    print(f"\n  pacote ausente -> indisponivel ('{motivo}')  OK")


def test_com_chave_o_servico_fica_disponivel(monkeypatch):
    import app.api.email_service as es
    monkeypatch.setenv("RESEND_API_KEY", "re_fake_para_teste")
    try:
        import resend  # noqa: F401
    except ImportError:
        pytest.skip("pacote 'resend' nao instalado neste ambiente")
    ok, motivo = es.email_service_disponivel()
    assert ok is True, motivo


# ==========================================================================
# 2. O CAMINHO FELIZ — token persistido e envio chamado
# ==========================================================================
def test_token_e_persistido_e_envio_chamado(client, servico_no_ar):
    """Prova a etapa que test_fase6 pulava ao injetar o token direto no banco."""
    from database.models import SessionLocal, User

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == EMAIL_TESTE).first()
        assert u is not None
        u.password_reset_token = None
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/auth/forgot-password", json={"email": EMAIL_TESTE})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "sent"

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == EMAIL_TESTE).first()
        token_no_banco = u.password_reset_token
        assert token_no_banco, "token NAO foi persistido em users.password_reset_token"
        assert u.password_reset_expires is not None, "expiracao nao gravada"
    finally:
        db.close()

    assert len(servico_no_ar) == 1, (
        f"send_password_reset_email chamado {len(servico_no_ar)}x, esperado 1")
    email_usado, token_usado = servico_no_ar[0]
    assert email_usado == EMAIL_TESTE
    assert token_usado == token_no_banco, (
        "o token enviado por e-mail difere do gravado no banco — o link nao funcionaria")
    print(f"\n  token persistido e enviado (mesmo valor)  OK")


# ==========================================================================
# 3. ANTI-ENUMERACAO — nao pode vazar quem tem conta
# ==========================================================================
def test_email_inexistente_responde_igual(client, servico_no_ar):
    """Com o servico no ar, cadastrado e nao cadastrado sao indistinguiveis."""
    r_existe = client.post("/api/auth/forgot-password", json={"email": EMAIL_TESTE})
    r_nao_existe = client.post(
        "/api/auth/forgot-password", json={"email": "ninguem-aqui@nexus.com"})

    assert r_existe.status_code == r_nao_existe.status_code == 200
    assert r_existe.json() == r_nao_existe.json(), (
        "respostas diferentes vazam quais e-mails tem conta")
    print("\n  cadastrado e nao cadastrado -> resposta identica  OK")


def test_503_nao_depende_do_email_pedido(client, monkeypatch):
    """O 503 e sobre o SERVICO, nao sobre a conta — logo nao vaza nada."""
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    import app.api.email_service as es
    monkeypatch.setattr(es, "RESEND_API_KEY", "")

    r1 = client.post("/api/auth/forgot-password", json={"email": EMAIL_TESTE})
    r2 = client.post(
        "/api/auth/forgot-password", json={"email": "ninguem-aqui@nexus.com"})

    assert r1.status_code == r2.status_code == 503
    assert r1.json() == r2.json(), "o 503 nao pode distinguir conta existente"
    print("\n  503 identico para conta existente e inexistente  OK")
