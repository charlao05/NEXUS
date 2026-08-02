# -*- coding: utf-8 -*-
"""
A PIA — isolamento por tenant como garantia arquitetural
=========================================================

POR QUE ISTO EXISTE

Em três dias esta auditoria encontrou três vazamentos entre tenants
(`analytics_dashboard`, `notifications`, `agent_media`). Não eram três bugs
iguais: eram três bugs da MESMA NATUREZA. Nos três, o isolamento dependia de
alguém lembrar de escrever `user_id` na query.

Isso não é um bug. É um mecanismo que produz bugs.

    "Um cozinheiro esquece de lavar a mão. Você corrige. Outro esquece. Outro
     esquece de novo. Chega uma hora em que fica claro que o problema não são
     os cozinheiros — é que não existe pia na saída da cozinha."

Corrigir cada query é lavar a mão. Este módulo é a pia.

A REGRA QUE PASSA A VALER

    Nenhum dado pertence ao sistema. Todo dado pertence a um tenant.
    O acesso global é uma exceção explicitamente declarada e auditável.

O QUE MUDA NO MODO DE FALHA — e é este o ponto todo

    ANTES:   esquecer o filtro  ->  VER TUDO      (vaza)
    DEPOIS:  esquecer o filtro  ->  VER SÓ O SEU  (ou exceção)

Ver tudo passa a exigir uma escolha explícita, visível e registrada.

DUAS CAMADAS, E A SEGUNDA NÃO É REDUNDÂNCIA

    Camada 1 (ORM)    do_orm_execute + with_loader_criteria  ->  FILTRA
    Camada 2 (motor)  before_cursor_execute                  ->  BLOQUEIA

A camada 1 sozinha tem um buraco MEDIDO: `Query.count()` gera
`SELECT count(*) FROM (subquery)`, e o statement externo não tem mapper —
`all_mappers` vem vazio e o listener é cego. O mesmo vale para SQL cru.
A camada 2 fecha isso: não consegue reescrever esses statements, mas consegue
RECUSÁ-LOS quando não há tenant definido.

Resultado medido:
    sem contexto  ->  nada que toque tabela de tenant passa
    com contexto  ->  tudo filtrado, EXCETO Query.count() (ver AVISO abaixo)

⚠️ AVISO — o resíduo conhecido

`db.query(Modelo).count()` COM contexto ainda devolve a contagem global. Use
`db.query(func.count(Modelo.id)).scalar()`, que É filtrado pela camada 1.
Há lint no CI proibindo o primeiro padrão.

USO

    from app.core.tenant import tenant_scope, sem_tenant

    with tenant_scope(user_id):          # rota HTTP, worker, script
        db.query(Invoice).all()          # já vem filtrado

    with sem_tenant("painel do dono agrega todos os tenants"):
        db.query(Invoice).all()          # visão global, declarada e auditada

NUNCA manipule o ContextVar diretamente. Os context managers limpam no
`finally` — sem isso, um `set()` sem `reset()` faz o contexto de uma requisição
vazar para a seguinte, que é a pior falha possível num mecanismo de isolamento.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import traceback
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, Optional

from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria

logger = logging.getLogger(__name__)

# ============================================================================
# CONTEXTO — só os context managers abaixo tocam nestes
# ============================================================================

_tenant: ContextVar[Optional[int]] = ContextVar("nexus_tenant", default=None)
_admin: ContextVar[bool] = ContextVar("nexus_tenant_admin", default=False)
_global: ContextVar[Optional[str]] = ContextVar("nexus_sem_tenant", default=None)

# Desliga a pia durante DDL/bootstrap (init_db, alembic). Não é escotilha de
# uso geral: é para a fase em que ainda não existe request nem tabela.
_bootstrap = threading.local()


class TenantContextMissing(RuntimeError):
    """Consulta a modelo multi-tenant sem tenant definido.

    Nome próprio de propósito: `RuntimeError` genérico custa horas de
    investigação, e esta exceção precisa dizer sozinha o que fazer.
    """


class EscopoGlobalNegado(PermissionError):
    """Alguém pediu visão global sem autoridade para isso."""


# ============================================================================
# MARCAÇÃO POR TIPO — não por nome, não por regex
# ============================================================================

class TenantScopedModel:
    """Marcador para toda tabela de negócio que pertence a um tenant.

    Por TIPO de propósito: uma tabela nova que não herde disto salta aos olhos
    na revisão, e o CI reclama. Comparar nome de tabela com uma lista é o mesmo
    problema de novo — alguém precisa lembrar de atualizar a lista.

    Tabelas naturalmente globais (CNAE, municípios, feriados, tabela fiscal,
    eventos de webhook) simplesmente NÃO herdam disto: não são filtradas e não
    exigem contexto.
    """

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        # Só valida quem é tabela de fato (mixins intermediários passam).
        if getattr(cls, "__tablename__", None) and not hasattr(cls, "user_id"):
            raise TypeError(
                f"{cls.__name__} herda TenantScopedModel mas não tem coluna "
                "`user_id`. O marcador é o contrato: ou a tabela pertence a um "
                "tenant e tem a coluna, ou não deveria herdar daqui."
            )


def _modelos_tenant() -> list[type]:
    return [c for c in TenantScopedModel.__subclasses__()
            if getattr(c, "__tablename__", None)]


def tabelas_tenant() -> set[str]:
    return {c.__tablename__ for c in _modelos_tenant()}


# ============================================================================
# ESCOPOS — a única API para mexer no contexto
# ============================================================================

@contextmanager
def tenant_scope(user_id: int, *, admin: bool = False) -> Iterator[None]:
    """Abre o escopo de um tenant. Toda query dentro sai filtrada por ele.

    `admin=True` NÃO dá visão global — só autoriza o código a PEDIR visão
    global via `sem_tenant`. São coisas diferentes de propósito: um admin
    navegando o próprio CRM continua vendo só o dele.
    """
    if user_id is None:
        raise ValueError("tenant_scope exige user_id; use sem_tenant() se a "
                         "intenção for acesso global.")
    t1 = _tenant.set(int(user_id))
    t2 = _admin.set(bool(admin))
    try:
        yield
    finally:
        _tenant.reset(t1)
        _admin.reset(t2)


@contextmanager
def sem_tenant(motivo: str) -> Iterator[None]:
    """Escotilha de visão global — explícita, restrita e auditada.

    `motivo` não é decoração: vai para o log de auditoria e é o que responde
    "quantos lugares deste sistema enxergam tudo, e por quê?" sem abrir o
    projeto.

    Quem pode: execução SEM tenant no contexto (script, worker, webhook, cron)
    ou usuário marcado admin no `tenant_scope`. Uma rota de usuário comum não
    consegue pedir visão global — é a diferença entre poder e ser autorizado.
    """
    if not motivo or not motivo.strip():
        raise ValueError("sem_tenant exige um motivo escrito. Se não dá para "
                         "explicar por que este código vê todos os tenants, "
                         "provavelmente ele não deveria ver.")

    tenant_ativo = _tenant.get()
    if tenant_ativo is not None and not _admin.get():
        raise EscopoGlobalNegado(
            f"Escopo global negado para o tenant {tenant_ativo}.\n"
            f"  motivo pedido: {motivo!r}\n"
            "  `sem_tenant` é para código de sistema (admin, webhook, script, "
            "cron), não para rota de usuário. Se o usuário precisa desse dado, "
            "ele precisa ser dele."
        )

    _auditar_escopo_global(motivo, tenant_ativo)
    tok = _global.set(motivo)
    try:
        yield
    finally:
        _global.reset(tok)


@contextmanager
def _bootstrap_sem_pia() -> Iterator[None]:
    """Só para DDL/bootstrap (init_db, alembic). Não é escotilha de uso geral."""
    anterior = getattr(_bootstrap, "ativo", False)
    _bootstrap.ativo = True
    try:
        yield
    finally:
        _bootstrap.ativo = anterior


def tenant_atual() -> Optional[int]:
    """Leitura do tenant corrente. Só leitura — para escrever, use os escopos."""
    return _tenant.get()


def entrar_no_tenant_do_request(user_id: int, *, admin: bool = False) -> None:
    """⚠️ O ÚNICO lugar autorizado a abrir escopo sem context manager.

    Chamado por `get_current_user` (auth.py). Uma dependency do FastAPI não
    envolve o resto da requisição num `with`, então aqui não há como usar o
    context manager — o escopo precisa sobreviver ao retorno da função.

    POR QUE ISSO É SEGURO AQUI, e não seria em código de aplicação: Starlette
    executa cada requisição na sua própria task, e toda task recebe uma CÓPIA
    do contexto. Um `set()` feito dentro da requisição morre com ela e não
    atravessa para a próxima. Fora de um servidor ASGI essa garantia não
    existe — por isso script, worker e cron usam `tenant_scope`.

    Qualquer outro `set()` direto no ContextVar é bug: sem o `finally` do
    context manager, um erro no meio deixa o tenant pendurado, e o próximo
    trecho de código roda com a identidade errada. É a pior falha possível
    num mecanismo de isolamento — silenciosa e cruzada.
    """
    _tenant.set(int(user_id))
    _admin.set(bool(admin))


def entrar_em_escopo_global_do_request(motivo: str) -> None:
    """Abre visão global para o resto da requisição. Só para `require_admin`.

    Mesma restrição de `entrar_no_tenant_do_request`: dependency do FastAPI não
    envolve a requisição num `with`, e a segurança vem de cada requisição rodar
    na própria task, com a própria cópia de contexto.

    Fica no guard de autorização de propósito — é lá que a decisão "esta pessoa
    pode ver tudo" já é tomada. Uma linha em `require_admin` cobre as 30 rotas
    do painel, em vez de 30 `with` espalhados que alguém esqueceria de repetir
    na trigésima primeira.
    """
    _auditar_escopo_global(motivo, _tenant.get())
    _global.set(motivo)


def _auditar_escopo_global(motivo: str, tenant: Optional[int]) -> None:
    """Registra QUEM pediu visão global, ONDE e POR QUÊ."""
    origem = "desconhecida"
    for frame in reversed(traceback.extract_stack()[:-2]):
        if "app/core/tenant.py" in frame.filename.replace("\\", "/"):
            continue
        origem = f"{os.path.basename(frame.filename)}:{frame.lineno}"
        break
    logger.info(
        "AUDITORIA escopo_global",
        extra={"evento": "sem_tenant", "motivo": motivo,
               "origem": origem, "tenant_no_contexto": tenant},
    )


# ============================================================================
# CAMADA 1 — ORM: filtra
# ============================================================================

def _instalar_camada_orm(session_factory: Any) -> None:
    @event.listens_for(session_factory, "do_orm_execute")
    def _filtrar_por_tenant(estado: Any) -> None:  # noqa: ANN401
        if not estado.is_select:
            return
        if getattr(_bootstrap, "ativo", False) or _global.get() is not None:
            return

        alvos = [m for m in estado.all_mappers
                 if issubclass(m.class_, TenantScopedModel)]
        if not alvos:
            # Pode ser tabela global (ok) ou Query.count(), que não expõe
            # mapper nenhum. A camada 2 cobre o segundo caso.
            return

        uid = _tenant.get()
        if uid is None:
            raise TenantContextMissing(_mensagem(alvos[0].class_.__name__))

        for m in alvos:
            estado.statement = estado.statement.options(
                with_loader_criteria(
                    m.class_, m.class_.user_id == uid, include_aliases=True)
            )


# ============================================================================
# CAMADA 2 — motor: bloqueia o que a camada 1 não enxerga
# ============================================================================

_DDL = re.compile(r"^\s*(create|drop|alter|pragma|begin|commit|rollback|savepoint|release)\b", re.I)
_LEITURA_OU_ESCRITA = re.compile(r"^\s*(select|update|delete|with)\b", re.I)


def _instalar_camada_motor(engine: Any) -> None:
    padrao_cache: dict[str, re.Pattern] = {}

    def _padrao() -> Optional[re.Pattern]:
        tabelas = tabelas_tenant()
        chave = "|".join(sorted(tabelas))
        if not chave:
            return None
        if chave not in padrao_cache:
            padrao_cache.clear()
            padrao_cache[chave] = re.compile(
                r"\b(" + "|".join(re.escape(t) for t in sorted(tabelas)) + r")\b", re.I)
        return padrao_cache[chave]

    @event.listens_for(engine, "before_cursor_execute")
    def _bloquear_sem_tenant(conn, cursor, sql, params, contexto, executemany):  # noqa: ANN001
        if getattr(_bootstrap, "ativo", False) or _global.get() is not None:
            return
        if _tenant.get() is not None:
            return  # a camada 1 já filtrou o que sabia filtrar
        if _DDL.match(sql) or not _LEITURA_OU_ESCRITA.match(sql):
            return

        padrao = _padrao()
        if padrao is None:
            return
        achou = padrao.search(sql)
        if achou:
            raise TenantContextMissing(_mensagem(achou.group(1), sql=sql))


# ============================================================================
# A mensagem — economiza horas de investigação
# ============================================================================

def _mensagem(alvo: str, sql: str | None = None) -> str:
    extra = f"\n\n  SQL: {sql[:160]}" if sql else ""
    return (
        f"consulta ao modelo multi-tenant `{alvo}` sem tenant definido.\n\n"
        "  Em rota HTTP: o tenant vem de get_current_user — confirme que a "
        "rota tem Depends(get_current_user).\n"
        "  Em script, worker, webhook ou cron: abra o escopo\n"
        "      with tenant_scope(user_id): ...\n"
        "  Se o acesso global for INTENCIONAL:\n"
        '      with sem_tenant("por que este código precisa ver todos os '
        'tenants"): ...\n\n'
        "  (Nenhum dado pertence ao sistema. Todo dado pertence a um tenant.)"
        + extra
    )


# ============================================================================
# INSTALAÇÃO
# ============================================================================

_instalada = False


def instalar_pia(session_factory: Any, engine: Any) -> None:
    """Registra as duas camadas. Idempotente."""
    global _instalada
    if _instalada:
        return
    _instalar_camada_orm(session_factory)
    _instalar_camada_motor(engine)
    _instalada = True
    logger.info(
        "pia de tenant instalada — %d modelos multi-tenant protegidos",
        len(_modelos_tenant()),
    )
