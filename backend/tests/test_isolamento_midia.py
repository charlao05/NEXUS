# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
Isolamento entre tenants em audio e imagem — O BALDE COMUM
===========================================================

O DEFEITO (encontrado e corrigido em 01/08/2026 — E-041)

`agent_media.py` fechava um ciclo de vazamento:

  GRAVAVA   :206-207 (audio) e :379-380 (upload) salvavam
            ChatMessage(user_id=0, ...) — o literal zero, nao o usuario
  LIA       :186 e :358 buscavam as 10 ultimas mensagens daquele agente
            SEM filtro de user_id e injetavam como `conversation_history`
            DENTRO DO PROMPT DO LLM

Nao era vazamento acidental entre tenants. Era um BALDE COMUM: todo mundo
escrevia no mesmo balde e todo mundo lia o balde inteiro.

O QUE ACONTECIA NA PRATICA

Marina manda um audio -> o conteudo vai para o balde.
Joao sobe uma imagem -> o codigo le o balde -> a conversa da Marina entra no
prompt do LLM do Joao -> a resposta pode refleti-la de volta para ele.

Vazava CONTEUDO LIVRE DE CONVERSA: o mais imprevisivel de todos, porque pode
conter nome, valor, telefone — qualquer coisa que o usuario tenha dito.

POR QUE ESTE E MAIS GRAVE QUE OS OUTROS DOIS VAZAMENTOS DESTA AUDITORIA

  analytics_dashboard  -> router NUNCA montado (codigo morto)
  notifications        -> montado, mas a UI nao chamava
  agent_media          -> montado E CHAMADO PELA UI TODO DIA
                          (AgentConfig.tsx:592 audio, :708 upload)

DOIS EFEITOS COLATERAIS DO MESMO DEFEITO

1. O historico de audio/imagem nunca aparecia para o proprio usuario, porque
   GET /api/chat/history/{agent_id} filtra por user_id e os registros estavam
   sob user_id=0.
2. Essas mensagens NAO CONTAVAM COTA — check_agent_message_limit
   (limit_service.py:232) conta ChatMessage por user_id. Audio e visao, as
   operacoes MAIS CARAS do produto, eram as unicas que nao consumiam cota.

    cd backend && pytest tests/test_isolamento_midia.py -v
"""

from __future__ import annotations

import io as _io
import os
import re
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("JWT_SECRET", "test-secret-midia")
os.environ.setdefault("NEXUS_DB_PATH", str(BACKEND / "data" / "test_midia.db"))

# Conteudo inconfundivel: se aparecer no prompt do outro, e vazamento.
SEGREDO_MARINA = "o cliente Beatriz me deve 4300 reais e o telefone dela e 11999887766"
SEGREDO_LUCAS = "encomenda de 200 paes para a firma do Ricardo"


@pytest.fixture(scope="module")
def app():
    from main import app as _app
    from database.models import init_db
    init_db()
    return _app


@pytest.fixture(scope="module")
def cenario(app):
    """Marina e Lucas, cada um com historico de conversa proprio no MESMO agente."""
    from starlette.testclient import TestClient
    from database.models import SessionLocal, User, ChatMessage

    cli = TestClient(app)
    tokens, ids = {}, {}
    for apelido, email in (("marina", "marina-midia@teste.com"),
                           ("lucas", "lucas-midia@teste.com")):
        dados = {"email": email, "password": "Senha1234!"}
        cli.post("/api/auth/signup", json={**dados, "full_name": apelido})
        r = cli.post("/api/auth/login", json=dados)
        tokens[apelido] = r.json()["access_token"]

        db = SessionLocal()
        try:
            u = db.query(User).filter(User.email == email).first()
            u.plan = "completo"          # audio/upload exigem acesso ao agente
            db.commit()
            ids[apelido] = u.id
        finally:
            db.close()

    # A pia (app/core/tenant.py) exige escopo declarado: semear conversas de
    # DOIS tenants e limpar o balde antigo sao operacoes de sistema.
    from app.core.tenant import sem_tenant
    db = SessionLocal()
    with sem_tenant("carga de historico de dois tenants para o teste"):
        try:
            # o .db de teste persiste entre execucoes
            db.query(ChatMessage).filter(
                ChatMessage.user_id.in_(list(ids.values()) + [0])).delete(
                synchronize_session=False)
            db.commit()
            for apelido, segredo in (("marina", SEGREDO_MARINA),
                                     ("lucas", SEGREDO_LUCAS)):
                db.add(ChatMessage(user_id=ids[apelido], agent_id="assistente",
                                   role="user", content=segredo))
                db.add(ChatMessage(user_id=ids[apelido], agent_id="assistente",
                                   role="assistant", content=f"anotado: {segredo}"))
            db.commit()
        finally:
            db.close()

    return {"tokens": tokens, "ids": ids, "client": cli}


# ==========================================================================
# A PROVA CENTRAL: o prompt montado para um NAO contem a conversa do outro
# ==========================================================================
def test_prompt_do_upload_nao_contem_conversa_alheia(cenario, monkeypatch):
    """Intercepta get_llm_response e inspeciona o `conversation_history` REAL
    que o backend montou. E a prova direta: nao e o que a rota devolve, e o que
    ela ENTREGA AO MODELO."""
    import app.api.agent_chat as chat_mod

    capturado: dict = {}

    def _falso(agent_id, mensagem, **kwargs):
        capturado["historico"] = kwargs.get("conversation_history") or []
        capturado["mensagem"] = mensagem
        return "ok"

    monkeypatch.setattr(chat_mod, "get_llm_response", _falso)

    cli = cenario["client"]
    r = cli.post(
        "/api/agents/upload",
        headers={"Authorization": f"Bearer {cenario['tokens']['lucas']}"},
        data={"agent": "assistente", "message": "veja este arquivo"},
        files={"files": ("nota.txt", _io.BytesIO(b"conteudo qualquer"), "text/plain")},
    )
    assert r.status_code == 200, f"upload falhou: {r.status_code} {r.text}"
    assert "historico" in capturado, (
        "get_llm_response nao foi chamado — o teste nao exercitou o caminho "
        "que monta o prompt. Sem isso ele nao prova nada.")

    texto = " ".join(m.get("content", "") for m in capturado["historico"])

    assert SEGREDO_MARINA not in texto, (
        "VAZAMENTO: a conversa da Marina entrou no prompt do LLM do Lucas.\n"
        f"historico entregue ao modelo: {capturado['historico']}")
    assert "Beatriz" not in texto and "11999887766" not in texto, (
        "VAZAMENTO: nome de cliente / telefone de outro usuario no prompt.")


def test_lucas_continua_vendo_o_proprio_historico(cenario, monkeypatch):
    """Contraprova. Sem ela, o teste acima passaria com o historico VAZIO —
    e um filtro quebrado demais pareceria seguranca."""
    import app.api.agent_chat as chat_mod

    capturado: dict = {}

    def _falso(agent_id, mensagem, **kwargs):
        capturado["historico"] = kwargs.get("conversation_history") or []
        return "ok"

    monkeypatch.setattr(chat_mod, "get_llm_response", _falso)

    cli = cenario["client"]
    r = cli.post(
        "/api/agents/upload",
        headers={"Authorization": f"Bearer {cenario['tokens']['lucas']}"},
        data={"agent": "assistente", "message": "veja este arquivo"},
        files={"files": ("nota.txt", _io.BytesIO(b"conteudo qualquer"), "text/plain")},
    )
    assert r.status_code == 200

    texto = " ".join(m.get("content", "") for m in capturado["historico"])
    assert SEGREDO_LUCAS in texto, (
        "Lucas deixou de ver o proprio historico — o filtro esta forte demais "
        f"e quebrou a funcionalidade. historico: {capturado['historico']}")


def test_gravacao_usa_o_usuario_real_e_nao_o_balde_zero(cenario, monkeypatch):
    """A raiz do defeito: gravava user_id=0.

    Consequencia da correcao, DECLARADA: com o user_id real, estas mensagens
    passam a contar cota (check_agent_message_limit conta ChatMessage por
    user_id). Audio e visao eram as unicas operacoes caras que nao consumiam
    cota nenhuma.
    """
    import app.api.agent_chat as chat_mod
    from database.models import SessionLocal, ChatMessage

    monkeypatch.setattr(chat_mod, "get_llm_response",
                        lambda *a, **k: "resposta do agente")

    from app.core.tenant import sem_tenant

    uid = cenario["ids"]["marina"]
    db = SessionLocal()
    # Contar o balde `user_id=0` e, por definicao, olhar fora do tenant —
    # e o proprio ponto do teste. Escopo declarado.
    with sem_tenant("verificar que o balde user_id=0 nao voltou"):
        try:
            antes_dela = db.query(ChatMessage).filter(
                ChatMessage.user_id == uid).count()
            antes_balde = db.query(ChatMessage).filter(
                ChatMessage.user_id == 0).count()
        finally:
            db.close()

    cli = cenario["client"]
    r = cli.post(
        "/api/agents/upload",
        headers={"Authorization": f"Bearer {cenario['tokens']['marina']}"},
        data={"agent": "assistente", "message": "arquivo novo"},
        files={"files": ("x.txt", _io.BytesIO(b"abc"), "text/plain")},
    )
    assert r.status_code == 200

    db = SessionLocal()
    with sem_tenant("verificar que o balde user_id=0 nao voltou"):
        try:
            depois_dela = db.query(ChatMessage).filter(
                ChatMessage.user_id == uid).count()
            depois_balde = db.query(ChatMessage).filter(
                ChatMessage.user_id == 0).count()
        finally:
            db.close()

    assert depois_dela > antes_dela, (
        "As mensagens do upload nao foram gravadas sob o user_id da Marina. "
        "Se voltaram para user_id=0, o balde comum voltou — e o historico dela "
        "some do proprio /api/chat/history.")
    assert depois_balde == antes_balde, (
        f"Foram gravadas {depois_balde - antes_balde} mensagem(ns) em "
        "user_id=0. Esse e exatamente o balde comum que causava o vazamento.")


# ==========================================================================
# REGRESSAO estrutural — pega a remocao do filtro nas DUAS rotas
# ==========================================================================
def test_as_duas_rotas_filtram_o_historico_por_user_id():
    """audio/transcribe e upload tem o MESMO bloco duplicado. Um teste de
    comportamento so exercita a rota que ele chama; este cobre as duas.
    """
    txt = _io.open(BACKEND / "app/api/agent_media.py", encoding="utf-8").read()

    leituras = re.findall(
        r"db\.query\(ChatMessage\)(.{0,400}?)\.limit\(", txt, re.S)
    assert len(leituras) == 2, (
        f"esperadas 2 leituras de ChatMessage (audio e upload), achei "
        f"{len(leituras)} — o arquivo mudou de forma; reveja este teste")
    for i, bloco in enumerate(leituras, 1):
        assert "ChatMessage.user_id" in bloco, (
            f"A leitura #{i} de ChatMessage voltou a NAO filtrar por user_id. "
            "O historico de outro usuario entra no prompt do LLM.")

    gravacoes = re.findall(r"CM\(\s*user_id\s*=\s*([^,]+),", txt)
    assert gravacoes, "nao encontrei as gravacoes de ChatMessage"
    for g in gravacoes:
        assert g.strip() != "0", (
            "Gravacao com user_id=0 de volta em agent_media.py. Esse literal "
            "e a raiz do balde comum: grava anonimo, le sem filtro.")
