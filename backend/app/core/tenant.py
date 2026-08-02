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


class EscotilhaVencida(RuntimeError):
    """Uma exceção temporária passou do prazo e ninguém a reviu.

    Levantada só em dev/CI. Em produção vira aviso: uma data vencida não pode
    virar indisponibilidade para o usuário.
    """


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


#: Sentinela para exceção que é permanente POR DESENHO (painel do dono,
#: webhook). Não é atalho para "não quero pensar no prazo": é a declaração
#: consciente de que esta exceção não tem data para acabar.
PERMANENTE = "permanente"


@contextmanager
def sem_tenant(motivo: str, *, ticket: str | None = None,
               expires: str | None = None) -> Iterator[None]:
    """Escotilha de visão global — explícita, restrita, auditada e com prazo.

    `motivo` não é decoração: vai para o log de auditoria e é o que responde
    "quantos lugares deste sistema enxergam tudo, e por quê?" sem abrir o
    projeto.

    `ticket` e `expires` são OBRIGATÓRIOS em código de produção. A razão é um
    problema que só aparece com o tempo:

        "O campo expires parece exagero agora, mas evita um problema comum:
         exceções temporárias virarem permanentes."

    Uma escotilha aberta "só por enquanto" some do radar em duas semanas e vira
    parte invisível da arquitetura. Com prazo, ela se anuncia sozinha.

    Passado o prazo: aviso em log SEMPRE, e falha em dev/CI. **Nunca derruba
    produção** — uma data vencida não pode virar indisponibilidade para o
    usuário; o objetivo é forçar a revisão, não punir quem está no ar.

    Para exceção permanente por desenho, use `expires=PERMANENTE` — explícito,
    consciente, e grepável.

    QUEM PODE: execução SEM tenant no contexto (script, worker, webhook, cron)
    ou usuário marcado admin no `tenant_scope`. Uma rota de usuário comum não
    consegue pedir visão global — é a diferença entre poder e ser autorizado.

    Em teste, `motivo` sozinho basta: um `sem_tenant` de fixture é escopo
    efêmero de carga de dados, não decisão de arquitetura que possa apodrecer.
    A distinção é automática (ver `_e_codigo_de_producao`), então ninguém
    precisa lembrar dela.
    """
    if not motivo or not motivo.strip():
        raise ValueError("sem_tenant exige um motivo escrito. Se não dá para "
                         "explicar por que este código vê todos os tenants, "
                         "provavelmente ele não deveria ver.")

    origem = _origem_do_chamador()
    if _e_codigo_de_producao(origem):
        if not ticket or not str(ticket).strip():
            raise ValueError(
                f"sem_tenant em código de produção ({origem}) exige `ticket`.\n"
                "  É o identificador que liga esta exceção à decisão que a "
                "criou (ex.: ticket=\"E-042\"). Sem ele, daqui a um ano "
                "ninguém sabe por que esta porta foi aberta."
            )
        if not expires or not str(expires).strip():
            raise ValueError(
                f"sem_tenant em código de produção ({origem}) exige `expires`.\n"
                "  Use uma data ISO (expires=\"2027-03-01\") para exceção "
                "temporária, ou expires=PERMANENTE se ela for permanente POR "
                "DESENHO.\n"
                "  Sem prazo, toda exceção temporária vira permanente — e "
                "ninguém percebe."
            )
        _avisar_se_vencida(motivo, ticket, expires, origem)

    tenant_ativo = _tenant.get()
    if tenant_ativo is not None and not _admin.get():
        raise EscopoGlobalNegado(
            f"Escopo global negado para o tenant {tenant_ativo}.\n"
            f"  motivo pedido: {motivo!r}\n"
            "  `sem_tenant` é para código de sistema (admin, webhook, script, "
            "cron), não para rota de usuário. Se o usuário precisa desse dado, "
            "ele precisa ser dele."
        )

    _auditar_escopo_global(motivo, tenant_ativo, ticket=ticket,
                           expires=expires, origem=origem)
    tok = _global.set(motivo)
    try:
        yield
    finally:
        _global.reset(tok)


def _e_codigo_de_producao(origem: str) -> bool:
    """Distingue código que vai ao ar de fixture de teste.

    Automático de propósito: se dependesse de o autor passar uma flag, seria
    mais uma coisa para lembrar — e este módulo inteiro existe porque memória
    humana falha.
    """
    caminho = origem.replace("\\", "/").lower()
    return not any(m in caminho for m in ("test_", "/tests/", "conftest"))


def _avisar_se_vencida(motivo: str, ticket: str | None, expires: str,
                       origem: str) -> None:
    """Prazo vencido: avisa sempre, falha em dev/CI, nunca derruba produção."""
    if str(expires).strip().lower() == PERMANENTE:
        return
    try:
        from datetime import date
        limite = date.fromisoformat(str(expires).strip())
    except ValueError:
        raise ValueError(
            f"sem_tenant: `expires={expires!r}` não é data ISO (AAAA-MM-DD) "
            f"nem PERMANENTE. Origem: {origem}"
        ) from None

    from datetime import date as _d
    if _d.today() <= limite:
        return

    recado = (
        f"ESCOTILHA VENCIDA em {origem}: sem_tenant({motivo!r}, "
        f"ticket={ticket!r}) expirou em {expires}. Reveja se ela ainda é "
        "necessária — ou renove o prazo conscientemente."
    )
    logger.warning(recado, extra={"evento": "sem_tenant_vencida",
                                 "ticket": ticket, "expires": expires,
                                 "origem": origem})
    # Falha onde há quem conserte; nunca em produção, onde só faria o usuário
    # pagar por uma data que passou.
    if (os.getenv("ENVIRONMENT", "").lower() != "production"
            and os.getenv("PYTEST_CURRENT_TEST")):
        raise EscotilhaVencida(recado)


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
    _auditar_escopo_global(motivo, _tenant.get(), ticket="ARQ-ADMIN",
                           expires=PERMANENTE)
    _global.set(motivo)


#: Frames a ignorar ao procurar quem realmente chamou. `contextlib` está aqui
#: porque `@contextmanager` insere um frame proprio entre o `with` e o corpo do
#: gerador — sem isso a origem vira "__init__.py" da stdlib, e a distincao
#: producao x teste (que depende do caminho do arquivo) sai errada em TODA
#: chamada. Foi exatamente o que aconteceu na primeira versao.
_FRAMES_INTERNOS = ("app/core/tenant.py", "/contextlib.py", "\\contextlib.py")


def _origem_do_chamador() -> str:
    """`arquivo.py:linha` de quem chamou, pulando os frames de infraestrutura."""
    for frame in reversed(traceback.extract_stack()[:-1]):
        caminho = frame.filename.replace("\\", "/")
        if any(m.replace("\\", "/") in caminho for m in _FRAMES_INTERNOS):
            continue
        return f"{os.path.basename(frame.filename)}:{frame.lineno}"
    return "desconhecida"


def _auditar_escopo_global(motivo: str, tenant: Optional[int], *,
                           ticket: str | None = None,
                           expires: str | None = None,
                           origem: str | None = None) -> None:
    """Registra QUEM pediu visão global, ONDE, POR QUÊ e ATÉ QUANDO.

    Um dos DOIS únicos eventos que a pia registra em produção (o outro é
    TenantContextMissing). Não registra query, tempo nem contagem: instrumenta
    a DECISÃO ARQUITETURAL, não tudo o que acontece.
    """
    logger.info(
        "AUDITORIA escopo_global",
        extra={"evento": "sem_tenant", "motivo": motivo,
               "ticket": ticket, "expires": expires,
               "origem": origem or _origem_do_chamador(),
               "tenant_no_contexto": tenant},
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
