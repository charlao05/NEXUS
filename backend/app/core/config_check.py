# -*- coding: utf-8 -*-
"""
Verificação de configuração de ambiente — dois níveis
======================================================

POR QUE ESTE MÓDULO EXISTE
--------------------------
Auditoria de 26/07/2026 encontrou um padrão: os mecanismos de proteção do NEXUS
falhavam em ABERTO quando sua configuração faltava — e o `/health` respondia
"ok" do mesmo jeito. Um deploy incompleto era indistinguível de um saudável.

O princípio, definido pelo dono:

    "O perigo maior não é apenas falhar, é falhar em silêncio.
     O objetivo é tornar impossível um deploy incompleto parecer saudável."

DOIS NÍVEIS, PROPOSITALMENTE
----------------------------
CRITICA   — derruba o boot em produção. Reservado para envs cuja ausência faz o
            sistema operar INCORRETAMENTE de forma invisível e irreversível.
            Hoje são duas, e o critério é estreito de propósito: classificar
            algo como crítico por engano derruba o serviço num redeploy, e no
            Render isso significa app fora do ar até corrigir pelo painel.

DEGRADADA — sobe, mas com log CRITICAL e aparecendo no /health. Para envs cuja
            ausência desliga uma funcionalidade de forma JÁ VISÍVEL (a rota
            recusa, o agente não responde). O risco aqui não é o dano, é o
            esquecimento.

SILENCIOSA — sobe com WARNING. A categoria mais traiçoeira: o sistema continua
            respondendo 200 e entregando NÚMERO ERRADO. Nada quebra, e por isso
            ninguém percebe.

NOTA SOBRE app/core/settings.py: existe um singleton `settings` com 30
propriedades que NINGUÉM importa (código morto). Não foi reaproveitado aqui de
propósito — ele tem defaults DIVERGENTES do código vivo (ex.: EMAIL_FROM), e
adotá-lo mudaria comportamento em produção junto com esta mudança. Unificar os
dois é trabalho separado, não efeito colateral de um validador.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

CRITICA = "critica"
DEGRADADA = "degradada"
SILENCIOSA = "silenciosa"


@dataclass(frozen=True)
class EnvSpec:
    nome: str
    nivel: str
    o_que_quebra: str
    onde: str
    placeholders: tuple[str, ...] = field(default=())

    def valor(self) -> str:
        return (os.getenv(self.nome, "") or "").strip()

    def ausente(self) -> bool:
        v = self.valor()
        if not v:
            return True
        # Placeholder preenchido conta como ausente — .env.render carregou
        # "re_COLE_AQUI" por semanas sem ninguém notar.
        return any(p.lower() in v.lower() for p in self.placeholders)


# ---------------------------------------------------------------------------
# O CHECKLIST. Cada linha veio de um caminho de código auditado, não de suposição.
# ---------------------------------------------------------------------------
ENVS: tuple[EnvSpec, ...] = (
    EnvSpec(
        "DATABASE_URL", CRITICA,
        "models.py cai para SQLite local em disco EFEMERO: banco novo e vazio a "
        "cada deploy, sem nenhum erro. Perda de dados de cliente, invisivel.",
        "database/models.py:34,84-101",
    ),
    EnvSpec(
        "JWT_SECRET", CRITICA,
        "toda rota autenticada levanta RuntimeError -> 500. O deploy sobe verde "
        "e so quebra na primeira requisicao real de usuario.",
        "app/api/auth.py:167-175",
        placeholders=("troque", "changeme", "your-secret"),
    ),
    EnvSpec(
        "STRIPE_WEBHOOK_SECRET", DEGRADADA,
        "webhook RECUSA eventos da Stripe em producao (fail-closed). Pagamentos, "
        "renovacoes e cancelamentos deixam de ser registrados. Consistencia "
        "FINANCEIRA — o mais grave desta categoria.",
        "app/api/_stripe_webhook_handler.py:76-95",
        placeholders=("whsec_cole", "cole_aqui"),
    ),
    EnvSpec(
        "RESEND_API_KEY", DEGRADADA,
        "recuperacao de senha responde 503: nenhum usuario consegue recuperar "
        "acesso. Bloqueia validacao com usuarios reais.",
        "app/api/email_service.py:16-25; app/api/auth.py forgot-password",
        placeholders=("re_cole", "cole_aqui"),
    ),
    EnvSpec(
        "ADMIN_EMAILS", DEGRADADA,
        "ninguem e admin por e-mail (fail-closed correto), mas se a conta do dono "
        "nao tiver role=admin no banco, TODO /api/admin responde 403. "
        "CUIDADO: .env.render declara ADMIN_EMAIL no SINGULAR, que ninguem le.",
        "app/api/admin.py:31-52; main.py:234-240",
    ),
    EnvSpec(
        "OPENAI_API_KEY", DEGRADADA,
        "agentes de IA param de responder.",
        "utils/llm_client.py",
        placeholders=("sk-cole", "cole_aqui"),
    ),
    EnvSpec(
        "TAX_RATE", DEGRADADA,
        "/api/admin/margin e /margin/all respondem 503 em producao (por decisao: "
        "margem sem aliquota nao e margem).",
        "app/api/admin.py::_require_tax_configured",
    ),
    EnvSpec(
        "USD_BRL_RATE", SILENCIOSA,
        "assume 5.20. O repo registra 5.08 como conferido em 26/07/2026. "
        "Custo de IA e margem saem ERRADOS sem erro, sem log, sem 503.",
        "app/api/admin.py::_resolve_usd_brl",
    ),
    EnvSpec(
        "USD_BRL_UPDATED_AT", SILENCIOSA,
        "sem carimbo de data, o cambio vira 'manual_override' e o sistema PERDE "
        "a capacidade de avisar que esta defasado — a unica protecao existente.",
        "app/api/admin.py::_resolve_usd_brl",
    ),
    EnvSpec(
        "STRIPE_FEE_PERCENT", SILENCIOSA,
        "assume cartao BR (3,99%). Se o mix migrar para Pix (1,19%), o custo "
        "fica superestimado e a margem subestimada.",
        "app/api/admin.py::_calc_gateway_fee",
    ),
    EnvSpec(
        "RENDER_COMPUTE_USD_PER_MIN", SILENCIOSA,
        "assume plano Starter (US$0,00016/min). Mudanca de plano nao se reflete "
        "no custo de automacao.",
        "app/api/admin.py (custo de automacao)",
    ),
    EnvSpec(
        "SENTRY_DSN", SILENCIOSA,
        "sem monitoramento de erros — o canal que avisaria sobre tudo acima "
        "fica desligado.",
        "app/api/monitoring.py:19-22",
    ),
)


def _producao() -> bool:
    return (os.getenv("ENVIRONMENT") or "").lower() == "production"


def verificar() -> dict:
    """Estado da configuracao. Nao levanta — quem decide e o caller."""
    faltando = {CRITICA: [], DEGRADADA: [], SILENCIOSA: []}
    for spec in ENVS:
        if spec.ausente():
            faltando[spec.nivel].append(spec)

    return {
        "environment": os.getenv("ENVIRONMENT", "development"),
        "is_production": _producao(),
        "ok": not faltando[CRITICA] and not faltando[DEGRADADA],
        "criticas_faltando": [s.nome for s in faltando[CRITICA]],
        "degradadas_faltando": [s.nome for s in faltando[DEGRADADA]],
        "silenciosas_faltando": [s.nome for s in faltando[SILENCIOSA]],
        "_specs": faltando,
    }


def validar_no_startup() -> dict:
    """Chamado no boot. Derruba SO por env CRITICA em producao.

    Fora de producao nada derruba — desenvolvimento nao pode ficar refem de
    configuracao de produção. Mas os avisos aparecem igual.
    """
    estado = verificar()
    faltando = estado.pop("_specs")

    for spec in faltando[SILENCIOSA]:
        logger.warning(
            "[CONFIG] %s ausente — NUMERO ERRADO EM SILENCIO: %s (%s)",
            spec.nome, spec.o_que_quebra, spec.onde,
        )

    for spec in faltando[DEGRADADA]:
        logger.critical(
            "[CONFIG] %s ausente — FUNCIONALIDADE DESLIGADA: %s (%s)",
            spec.nome, spec.o_que_quebra, spec.onde,
        )

    if faltando[CRITICA]:
        detalhe = "\n".join(
            f"  - {s.nome}: {s.o_que_quebra} [{s.onde}]" for s in faltando[CRITICA]
        )
        msg = (
            "Variaveis de ambiente CRITICAS ausentes:\n" + detalhe +
            "\n\nO app NAO vai subir: operar sem elas corromperia dados ou "
            "quebraria toda requisicao autenticada, de forma invisivel.\n"
            "Configure em: Render -> nexus-backend -> Environment.\n"
            "Checklist completo: AUDITORIA_NEXUS/17_CHECKLIST_AMBIENTE.md"
        )
        if _producao():
            logger.critical("[CONFIG] %s", msg)
            raise RuntimeError(msg)
        logger.warning("[CONFIG] (nao-producao, seguindo mesmo assim)\n%s", msg)

    if estado["ok"]:
        logger.info("[CONFIG-OK] nenhuma variavel critica ou degradada ausente")
    return estado


def resumo_para_health() -> dict:
    """Bloco de configuracao do /health.

    Sem isto, o healthCheckPath do Render aprova um deploy sem RESEND_API_KEY,
    sem STRIPE_WEBHOOK_SECRET e sem TAX_RATE como se estivesse tudo certo.
    NAO expoe valores — apenas nomes e estado.
    """
    estado = verificar()
    estado.pop("_specs", None)
    if estado["criticas_faltando"]:
        estado["status"] = "critical"
    elif estado["degradadas_faltando"]:
        estado["status"] = "degraded"
    elif estado["silenciosas_faltando"]:
        estado["status"] = "ok_with_warnings"
    else:
        estado["status"] = "ok"
    return estado
