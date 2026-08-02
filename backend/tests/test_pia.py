# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
A PIA — prova de que o isolamento e garantia da arquitetura
============================================================

O QUE ESTE ARQUIVO PROVA, E POR QUE E DIFERENTE DOS OUTROS

Os outros testes de isolamento (dashboard, notificacoes, midia) provam o
RESULTADO: ninguem ve dado alheio. Mas depois da pia eles passam a ter DUAS
barreiras — o filtro escrito a mao em cada query E o filtro automatico. Eles
nao dizem qual das duas segurou.

Aqui as queries sao escritas SEM NENHUM `.filter(user_id == ...)`. Se o
isolamento aparecer, foi a pia. Nao ha outra explicacao possivel.

    Antes:   esquecer o filtro  ->  ver tudo       (vaza)
    Depois:  esquecer o filtro  ->  ver so o seu   (ou excecao)

E exatamente esse esquecimento que estes testes reproduzem de proposito.

CONTEXTO — POR QUE A PIA EXISTE

Tres vazamentos em tres dias (analytics_dashboard, notifications, agent_media),
todos com a mesma causa: o isolamento dependia de alguem LEMBRAR de escrever
user_id. Corrigir cada query e lavar a mao; isto e a pia na saida da cozinha.

    cd backend && pytest tests/test_pia.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("JWT_SECRET", "test-secret-pia")
os.environ.setdefault("NEXUS_DB_PATH", str(BACKEND / "data" / "test_pia.db"))

CLIENTE_A = "Padaria da Ana (tenant A)"
CLIENTE_B = "Oficina do Bruno (tenant B)"


@pytest.fixture(scope="module")
def dois_tenants():
    from database.models import init_db, SessionLocal, User, Client, Invoice
    from app.core.tenant import sem_tenant
    from datetime import date

    init_db()
    db = SessionLocal()
    with sem_tenant("carga de dois tenants para provar a pia"):
        try:
            ids = {}
            for apelido, email in (("a", "pia-a@teste.com"), ("b", "pia-b@teste.com")):
                u = db.query(User).filter(User.email == email).first()
                if not u:
                    u = User(email=email, full_name=apelido, password_hash="x")
                    db.add(u); db.commit(); db.refresh(u)
                ids[apelido] = u.id

            for uid in ids.values():
                db.query(Invoice).filter(Invoice.user_id == uid).delete()
                db.query(Client).filter(Client.user_id == uid).delete()
            db.commit()

            for apelido, nome in (("a", CLIENTE_A), ("b", CLIENTE_B)):
                c = Client(user_id=ids[apelido], name=nome, is_active=True)
                db.add(c); db.commit(); db.refresh(c)
                db.add(Invoice(user_id=ids[apelido], client_id=c.id,
                               description=nome, amount=100.0,
                               due_date=date.today(), status="pending"))
            db.commit()
            return ids
        finally:
            db.close()


# ==========================================================================
# 1. A PROVA CENTRAL — query SEM filtro nenhum
# ==========================================================================
def test_query_sem_filtro_nenhum_devolve_so_o_do_tenant(dois_tenants):
    """A query abaixo e EXATAMENTE o bug que causou os tres vazamentos.

    Nao ha `.filter(Client.user_id == ...)`. Antes da pia, isto devolvia todo
    mundo. Se agora devolve so um, quem filtrou foi a arquitetura.
    """
    from database.models import SessionLocal, Client
    from app.core.tenant import tenant_scope

    db = SessionLocal()
    try:
        with tenant_scope(dois_tenants["a"]):
            nomes = [c.name for c in db.query(Client).all()]   # <- sem filtro
        assert CLIENTE_A in nomes
        assert CLIENTE_B not in nomes, (
            f"VAZAMENTO: o tenant A viu {CLIENTE_B!r} numa query sem filtro. "
            "A pia nao esta segurando.")
        assert len(nomes) == 1
    finally:
        db.close()


def test_o_outro_tenant_ve_o_dele_e_so_o_dele(dois_tenants):
    from database.models import SessionLocal, Client
    from app.core.tenant import tenant_scope

    db = SessionLocal()
    try:
        with tenant_scope(dois_tenants["b"]):
            nomes = [c.name for c in db.query(Client).all()]
        assert nomes == [CLIENTE_B]
    finally:
        db.close()


def test_get_por_id_de_outro_tenant_devolve_nada(dois_tenants):
    """Buscar pelo id de um registro alheio — o ataque mais obvio."""
    from database.models import SessionLocal, Client
    from app.core.tenant import tenant_scope, sem_tenant

    db = SessionLocal()
    try:
        with sem_tenant("descobrir o id do registro do outro tenant"):
            alheio = db.query(Client).filter(Client.name == CLIENTE_B).first()
        assert alheio is not None

        with tenant_scope(dois_tenants["a"]):
            achou = db.query(Client).filter(Client.id == alheio.id).first()
        assert achou is None, (
            "VAZAMENTO: o tenant A leu o registro do B informando o id direto.")
    finally:
        db.close()


# ==========================================================================
# 2. FAIL-CLOSED — as duas camadas
# ==========================================================================
def test_sem_contexto_o_orm_e_bloqueado(dois_tenants):
    from database.models import SessionLocal, Client
    from app.core.tenant import TenantContextMissing

    db = SessionLocal()
    try:
        with pytest.raises(TenantContextMissing):
            db.query(Client).all()
    finally:
        db.close()


def test_sem_contexto_o_count_tambem_e_bloqueado(dois_tenants):
    """CAMADA 2 — e a razao de ela existir.

    `Query.count()` gera SELECT count(*) FROM (subquery). O statement externo
    nao tem mapper (`all_mappers` vem vazio), entao a camada 1 e CEGA para ele.
    Sem a camada 2 este acesso passaria direto. Medido, nao suposto.
    """
    from database.models import SessionLocal, Client
    from app.core.tenant import TenantContextMissing

    db = SessionLocal()
    try:
        with pytest.raises(TenantContextMissing):
            db.query(Client).count()
    finally:
        db.close()


def test_sem_contexto_o_sql_cru_tambem_e_bloqueado(dois_tenants):
    """A camada 1 nao consegue reescrever SQL cru. A camada 2 o RECUSA."""
    from sqlalchemy import text
    from database.models import SessionLocal
    from app.core.tenant import TenantContextMissing

    db = SessionLocal()
    try:
        with pytest.raises(TenantContextMissing):
            db.execute(text("SELECT name FROM clients")).all()
    finally:
        db.close()


def test_a_mensagem_de_erro_diz_o_que_fazer(dois_tenants):
    """Mensagem ruim custa horas. Esta precisa se explicar sozinha."""
    from database.models import SessionLocal, Client
    from app.core.tenant import TenantContextMissing

    db = SessionLocal()
    try:
        with pytest.raises(TenantContextMissing) as e:
            db.query(Client).all()
        msg = str(e.value)
        assert "tenant_scope" in msg
        assert "sem_tenant" in msg
        assert "get_current_user" in msg
        assert "Client" in msg
    finally:
        db.close()


# ==========================================================================
# 3. O QUE A PIA NAO PODE QUEBRAR
# ==========================================================================
def test_tabela_global_passa_sem_contexto():
    """User e a RAIZ do tenant, nao um dado dentro dele. Sem isso, login
    (que busca User por email antes de existir tenant) seria impossivel."""
    from database.models import SessionLocal, User

    db = SessionLocal()
    try:
        db.query(User).count()   # nao levanta
    finally:
        db.close()


def test_tabelas_do_operador_nao_sao_filtradas():
    """StripeEvent, WebhookHit e afins sao do operador, nao de um tenant."""
    from database.models import SessionLocal, StripeEvent, WebhookHit
    from app.core.tenant import tabelas_tenant

    db = SessionLocal()
    try:
        db.query(StripeEvent).count()
        db.query(WebhookHit).count()
    finally:
        db.close()
    assert "stripe_events" not in tabelas_tenant()
    assert "webhook_hits" not in tabelas_tenant()


# ==========================================================================
# 4. A ESCOTILHA — explicita, restrita, auditada
# ==========================================================================
def test_sem_tenant_ve_todos(dois_tenants):
    from database.models import SessionLocal, Client
    from app.core.tenant import sem_tenant

    db = SessionLocal()
    try:
        with sem_tenant("teste do escopo global"):
            nomes = [c.name for c in db.query(Client).all()]
        assert CLIENTE_A in nomes and CLIENTE_B in nomes
    finally:
        db.close()


def test_usuario_comum_nao_consegue_pedir_visao_global(dois_tenants):
    """`sem_tenant` e para codigo de sistema, nao para rota de usuario.

    Nem todo codigo pode pedir visao global — senao a escotilha vira porta.
    """
    from app.core.tenant import tenant_scope, sem_tenant, EscopoGlobalNegado

    with tenant_scope(dois_tenants["a"]):           # admin=False
        with pytest.raises(EscopoGlobalNegado):
            with sem_tenant("tentando burlar"):
                pass


def test_admin_consegue(dois_tenants):
    from app.core.tenant import tenant_scope, sem_tenant

    with tenant_scope(dois_tenants["a"], admin=True):
        with sem_tenant("painel do dono"):
            pass


def test_sem_tenant_exige_motivo_escrito():
    """Se nao da para explicar por que este codigo ve todos os tenants,
    provavelmente ele nao deveria ver."""
    from app.core.tenant import sem_tenant

    for vazio in ("", "   "):
        with pytest.raises(ValueError):
            with sem_tenant(vazio):
                pass


def test_escotilha_de_producao_exige_ticket_e_prazo(monkeypatch):
    """A exigencia que impede exceção temporária de virar permanente.

    Em codigo de producao, `sem_tenant` exige `ticket` (o que a criou) e
    `expires` (ate quando). Em teste, `motivo` basta — fixture e escopo
    efemero, nao decisao de arquitetura que possa apodrecer.

    A distincao e AUTOMATICA (pelo arquivo do chamador). Se dependesse de o
    autor passar uma flag, seria mais uma coisa para lembrar — e este modulo
    inteiro existe porque memoria humana falha.
    """
    import app.core.tenant as t

    # finge que a chamada veio de codigo de producao
    monkeypatch.setattr(t, "_origem_do_chamador", lambda: "app/api/qualquer.py:10")

    with pytest.raises(ValueError, match="ticket"):
        with t.sem_tenant("motivo sem ticket"):
            pass

    with pytest.raises(ValueError, match="expires"):
        with t.sem_tenant("motivo com ticket", ticket="E-999"):
            pass

    # com os tres, passa
    with t.sem_tenant("completo", ticket="E-999", expires=t.PERMANENTE):
        pass


def test_escotilha_vencida_falha_em_teste(monkeypatch):
    """Prazo vencido: avisa sempre, falha onde ha quem conserte.

    NUNCA derruba producao — uma data que passou nao pode virar
    indisponibilidade para o usuario. O objetivo e forcar a revisao.
    """
    import app.core.tenant as t

    monkeypatch.setattr(t, "_origem_do_chamador", lambda: "app/api/qualquer.py:10")

    with pytest.raises(t.EscotilhaVencida, match="VENCIDA"):
        with t.sem_tenant("exceção que alguem esqueceu",
                          ticket="E-001", expires="2020-01-01"):
            pass


def test_escotilha_vencida_nao_derruba_producao(monkeypatch, caplog):
    import logging
    import app.core.tenant as t

    monkeypatch.setattr(t, "_origem_do_chamador", lambda: "app/api/qualquer.py:10")
    monkeypatch.setenv("ENVIRONMENT", "production")

    with caplog.at_level(logging.WARNING, logger="app.core.tenant"):
        with t.sem_tenant("vencida em producao", ticket="E-001",
                          expires="2020-01-01"):
            pass   # nao levanta

    assert any(getattr(r, "evento", None) == "sem_tenant_vencida"
               for r in caplog.records), "deveria ter avisado no log"


def test_expires_invalido_e_recusado(monkeypatch):
    """`expires="em breve"` nao e prazo. Ou e data ISO, ou e PERMANENTE."""
    import app.core.tenant as t

    monkeypatch.setattr(t, "_origem_do_chamador", lambda: "app/api/qualquer.py:10")
    with pytest.raises(ValueError, match="ISO"):
        with t.sem_tenant("motivo", ticket="E-1", expires="em breve"):
            pass


def test_escotilhas_de_producao_estao_declaradas():
    """REGRESSAO: toda `sem_tenant` de producao tem ticket e prazo.

    Pega quem acrescentar uma escotilha nova sem declarar — antes de virar
    exceção permanente invisivel.
    """
    import io
    import re

    faltando = []
    for arq in (BACKEND / "app").rglob("*.py"):
        if arq.name == "tenant.py":
            continue
        linhas = io.open(arq, encoding="utf-8").read().splitlines()
        for i, ln in enumerate(linhas):
            # so CHAMADA conta: comentario que cita sem_tenant() e documentacao,
            # nao escotilha aberta. Foi o primeiro falso-positivo deste teste.
            if ln.lstrip().startswith("#") or "sem_tenant(" not in ln:
                continue
            trecho = "\n".join(linhas[i:i + 12])
            if "ticket=" not in trecho or "expires=" not in trecho:
                faltando.append(f"{arq.name}:{i + 1}")

    assert not faltando, (
        f"sem_tenant sem ticket/expires em producao: {faltando}. "
        "Toda escotilha precisa dizer o que a criou e ate quando vale.")


def test_sem_tenant_gera_registro_de_auditoria(caplog):
    """Responde 'quantos lugares enxergam tudo, e por que?' sem abrir o projeto."""
    import logging
    from app.core.tenant import sem_tenant

    with caplog.at_level(logging.INFO, logger="app.core.tenant"):
        with sem_tenant("motivo rastreavel do teste"):
            pass

    registros = [r for r in caplog.records
                 if getattr(r, "evento", None) == "sem_tenant"]
    assert registros, "nenhum registro de auditoria foi emitido"
    assert registros[-1].motivo == "motivo rastreavel do teste"
    assert getattr(registros[-1], "origem", "").endswith(".py:" .rstrip()) or \
        ":" in getattr(registros[-1], "origem", ""), "faltou arquivo:linha na origem"


# ==========================================================================
# 5. O CONTEXTO NAO VAZA — a falha mais perigosa de todas
# ==========================================================================
def test_contexto_nao_sobrevive_a_excecao(dois_tenants):
    """Um `set()` sem `reset()` deixa o tenant pendurado, e o proximo trecho
    roda com a identidade errada. Silencioso e cruzado — a pior falha possivel
    num mecanismo de isolamento. Por isso a API e context manager, nunca set().
    """
    from database.models import SessionLocal, Client
    from app.core.tenant import tenant_scope, TenantContextMissing, tenant_atual

    try:
        with tenant_scope(dois_tenants["a"]):
            raise ValueError("erro no meio da requisicao")
    except ValueError:
        pass

    assert tenant_atual() is None, "o tenant ficou pendurado apos a excecao"

    db = SessionLocal()
    try:
        with pytest.raises(TenantContextMissing):
            db.query(Client).all()
    finally:
        db.close()


def test_escopos_aninhados_restauram_o_anterior(dois_tenants):
    from app.core.tenant import tenant_scope, tenant_atual

    with tenant_scope(dois_tenants["a"]):
        assert tenant_atual() == dois_tenants["a"]
        with tenant_scope(dois_tenants["b"]):
            assert tenant_atual() == dois_tenants["b"]
        assert tenant_atual() == dois_tenants["a"], (
            "o escopo interno nao restaurou o externo ao sair")
    assert tenant_atual() is None


# ==========================================================================
# 6. O CONTRATO DO MARCADOR — para a proxima tabela que alguem criar
# ==========================================================================
def test_marcador_exige_a_coluna_user_id():
    """Herdar TenantScopedModel sem ter user_id e contradicao: o marcador E o
    contrato."""
    from app.core.tenant import TenantScopedModel

    with pytest.raises(TypeError, match="user_id"):
        class TabelaMalFeita(TenantScopedModel):
            __tablename__ = "tabela_mal_feita"


def test_toda_tabela_de_negocio_esta_marcada():
    """REGRESSAO para a proxima tabela.

    Quem criar `Task`, `Reminder` ou `Budget` com user_id e esquecer de herdar
    TenantScopedModel quebra aqui — antes de virar o quarto vazamento.

    Criterio: tem coluna user_id -> e dado de tenant -> tem de estar marcada.
    A unica excecao aceita esta declarada abaixo, com prazo.
    """
    from database.models import Base
    from app.core.tenant import TenantScopedModel

    # Interaction e Opportunity: nao tem user_id proprio, isolam por join com
    # Client. E a migration da Fase 2 — ate la, sao a unica excecao a regra.
    EXCECOES_DECLARADAS = {"interactions", "opportunities"}

    nao_marcadas = []
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        tabela = getattr(cls, "__tablename__", None)
        if not tabela or tabela in EXCECOES_DECLARADAS:
            continue
        if cls.__name__ == "User":          # raiz do tenant, nao dado dele
            continue
        if "user_id" in mapper.columns and not issubclass(cls, TenantScopedModel):
            nao_marcadas.append(f"{cls.__name__} ({tabela})")

    assert not nao_marcadas, (
        f"Tabela(s) com user_id fora da pia: {nao_marcadas}. "
        "Toda tabela de negocio herda TenantScopedModel — senao o isolamento "
        "dela volta a depender de alguem lembrar.")
