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
    # ADICIONADA 29/07/2026 — LACUNA DO CHECKLIST, encontrada do pior jeito.
    # Esta lista tinha STRIPE_WEBHOOK_SECRET (receber eventos) e NAO tinha a
    # chave que COBRA. Em 28/07 23:05 UTC o Sentry acusou AuthenticationError
    # em create_checkout: o checkout estava quebrado em producao e o /health
    # dizia que estava tudo bem.
    EnvSpec(
        "STRIPE_SECRET_KEY", DEGRADADA,
        "NINGUEM CONSEGUE ASSINAR. /api/auth/checkout devolve 503 e o frontend "
        "mostra 'Sistema de pagamento em manutencao' (Pricing.tsx:182-183) — "
        "mensagem honesta para o usuario que ESCONDE a causa do dono. "
        "ATENCAO: presenca nao basta; ver stripe_autentica().",
        "app/api/auth.py:1260-1265; app/api/billing.py",
        placeholders=("sk_cole", "cole_aqui", "sk_test_51…", "sua_chave"),
    ),
    EnvSpec(
        "STRIPE_PRICE_ESSENCIAL", DEGRADADA,
        "plano Essencial nao pode ser assinado (price_id vazio no checkout).",
        "app/api/billing.py:21",
        placeholders=("price_cole", "cole_aqui"),
    ),
    EnvSpec(
        "STRIPE_PRICE_PROFISSIONAL", DEGRADADA,
        "plano Profissional nao pode ser assinado.",
        "app/api/billing.py:27",
        placeholders=("price_cole", "cole_aqui"),
    ),
    EnvSpec(
        "STRIPE_PRICE_COMPLETO", DEGRADADA,
        "plano Completo nao pode ser assinado.",
        "app/api/billing.py:33",
        placeholders=("price_cole", "cole_aqui"),
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
        "TAX_REGIME", DEGRADADA,
        "/api/admin/margin e /margin/all respondem 503 em producao (por decisao: "
        "margem sem tributacao definida nao e margem). Valores: mei | "
        "simples_anexo_iii | simples_anexo_v. NOTA: no MEI nao existe aliquota "
        "- o imposto e DAS FIXO -, por isso TAX_RATE nao e exigido neste regime.",
        "app/core/tributacao.py; app/api/admin.py::_require_tax_configured",
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

    # Automacao web: falha de build NAO pode ficar muda ate o primeiro uso.
    ok_browser, motivo_browser = browser_disponivel()
    if not ok_browser:
        logger.critical(
            "[CONFIG] AUTOMACAO WEB INDISPONIVEL: %s. As rotas de "
            "/api/agents/automation vao falhar quando o usuario tentar usar.",
            motivo_browser,
        )

    # Stripe: se a chave nao autentica, NINGUEM consegue assinar — e o unico
    # sinal hoje seria um cliente clicando em "Assinar" e vendo o banner de
    # manutencao. Descobrir por alerta e melhor que descobrir por cliente.
    ok_stripe, motivo_stripe = stripe_autentica()
    if not ok_stripe:
        logger.critical(
            "[CONFIG] STRIPE NAO AUTENTICA: %s. O checkout vai responder 503 e "
            "a pagina de planos vai mostrar 'Sistema de pagamento em manutencao'.",
            motivo_stripe,
        )
    else:
        # Chave OK nao basta. So checa precos se a chave autentica — senao o
        # erro seria consequencia, nao causa, e poluiria o diagnostico.
        ok_precos, motivo_precos = stripe_precos_coerentes()
        if not ok_precos:
            logger.critical(
                "[CONFIG] STRIPE: chave valida, mas os PRECOS nao: %s. "
                "NINGUEM CONSEGUE ASSINAR, apesar de a chave autenticar.",
                motivo_precos,
            )

    return estado


# ---------------------------------------------------------------------------
# Automacao web (Playwright)
# ---------------------------------------------------------------------------
#
# POR QUE ISTO EXISTE: render.yaml instala o browser com
#     playwright install chromium || true
# O `|| true` e deliberado — impede que uma falha do browser derrube o deploy
# inteiro. O efeito colateral e que, se o download falhar, o app sobe verde, o
# router carrega (o PACOTE playwright esta no requirements e importa bem) e a
# automacao so quebra no PRIMEIRO USO REAL do usuario, com
# "Executable doesn't exist at /ms-playwright/...".
#
# Esta checagem torna esse estado visivel no boot e no /health, sem remover o
# `|| true` (que continua sendo o comportamento certo para o build).
#
# Verifica apenas o FILESYSTEM — nao inicia o browser, que custaria segundos a
# cada health check.

# ---------------------------------------------------------------------------
# Stripe: a chave AUTENTICA? (presenca nao basta)
# ---------------------------------------------------------------------------
#
# POR QUE ISTO EXISTE (29/07/2026): em 28/07 23:05 UTC o Sentry acusou
#
#     Stripe AuthenticationError — STRIPE_SECRET_KEY invalida ou ausente
#     HTTPException: Stripe nao configurado corretamente (app.api.auth.create_checkout)
#
# A variavel ESTAVA definida no Render. O checklist de presenca teria dito
# "tudo ok" — e o checkout estava quebrado. Quem descobriu foi um clique em
# "Assinar", ou seja, seria um CLIENTE descobrindo.
#
# Uma chave pode existir e nao autenticar por varios motivos: revogada,
# truncada, com espaco, de outra conta, ou de um modo diferente do resto da
# configuracao. Nenhum deles e visivel olhando se a env "existe".
#
# Mesma logica de browser_disponivel(), que provou que a automacao web estava
# morta: testar o EFEITO, nao a declaracao.

_stripe_cache: tuple[bool, str] | None = None


def stripe_autentica(forcar: bool = False) -> tuple[bool, str]:
    """A STRIPE_SECRET_KEY autentica de verdade? Retorna (ok, motivo).

    Faz UMA chamada somente-leitura (Account.retrieve) e cacheia. Nunca lanca:
    quem consome e um health check, e derrubar o /health por causa do Stripe
    seria trocar um problema por outro pior.

    Distingue chave ruim de erro de rede DE PROPOSITO: reportar um blip de rede
    como "chave invalida" gera alarme falso, e alarme falso destroi a confianca
    no alerta — que e justamente o que faz ninguem mais olhar.
    """
    global _stripe_cache
    if _stripe_cache is not None and not forcar:
        return _stripe_cache

    resultado = _checar_stripe()
    _stripe_cache = resultado
    return resultado


def _checar_stripe() -> tuple[bool, str]:
    chave = (os.getenv("STRIPE_SECRET_KEY", "") or "").strip()
    if not chave:
        return False, "STRIPE_SECRET_KEY ausente"

    try:
        import stripe
    except ImportError:
        return False, "pacote 'stripe' nao instalado"

    modo = "live" if chave.startswith("sk_live_") else (
        "test" if chave.startswith("sk_test_") else "prefixo_desconhecido")

    try:
        stripe.api_key = chave
        stripe.Account.retrieve()
        return True, f"chave valida (modo {modo})"
    except Exception as e:  # noqa: BLE001
        nome = type(e).__name__
        if "Authentication" in nome:
            return False, (
                f"chave REJEITADA pelo Stripe (modo aparente: {modo}) — "
                "revogada, truncada ou de outra conta. Ninguem consegue assinar."
            )
        if "APIConnection" in nome or "Timeout" in nome:
            # NAO e problema de chave. Nao alarmar como se fosse.
            return True, f"indeterminado: falha de rede ao verificar ({nome})"
        return False, f"erro ao verificar a chave: {nome}"


# ---------------------------------------------------------------------------
# Stripe: os PRICE IDs existem no MESMO MODO da chave?
# ---------------------------------------------------------------------------
#
# POR QUE ISTO EXISTE (29/07/2026): validar a chave NAO e validar a cobranca.
#
# Numa migracao test -> live, a STRIPE_SECRET_KEY foi trocada para sk_live e os
# tres STRIPE_PRICE_* ficaram apontando para precos de TEST. Resultado:
#
#   /health dizia  stripe.autentica: true   (a CHAVE autentica mesmo)
#   e o checkout continuava quebrado        ("No such price" — o Stripe nao
#                                             enxerga price de test com chave live)
#
# O sistema declarava saude total enquanto ninguem conseguia pagar. E o mesmo
# erro de nivel do que ja aconteceu duas vezes aqui — presenca nao e validade,
# e agora: chave valida nao e cobranca funcionando.
#
# Esta checagem tenta recuperar cada price ID configurado. Se a chave e o price
# forem de modos diferentes, o Stripe devolve erro e nos sabemos ANTES do
# cliente.

_precos_cache: tuple[bool, str] | None = None

_ENVS_PRECO = (
    "STRIPE_PRICE_ESSENCIAL",
    "STRIPE_PRICE_PROFISSIONAL",
    "STRIPE_PRICE_COMPLETO",
)


def stripe_precos_coerentes(forcar: bool = False) -> tuple[bool, str]:
    """Cada STRIPE_PRICE_* existe no mesmo modo da chave? Retorna (ok, motivo).

    Cacheado e nunca lanca, pelas mesmas razoes de stripe_autentica().
    """
    global _precos_cache
    if _precos_cache is not None and not forcar:
        return _precos_cache

    resultado = _checar_precos()
    _precos_cache = resultado
    return resultado


def _checar_precos() -> tuple[bool, str]:
    chave = (os.getenv("STRIPE_SECRET_KEY", "") or "").strip()
    if not chave:
        return False, "sem STRIPE_SECRET_KEY — nao da para verificar os precos"

    try:
        import stripe
    except ImportError:
        return False, "pacote 'stripe' nao instalado"

    modo_chave = "live" if chave.startswith("sk_live_") else (
        "test" if chave.startswith("sk_test_") else "desconhecido")

    ausentes = [n for n in _ENVS_PRECO if not (os.getenv(n, "") or "").strip()]
    if ausentes:
        return False, f"price IDs nao configurados: {', '.join(ausentes)}"

    stripe.api_key = chave
    quebrados: list[str] = []

    for nome in _ENVS_PRECO:
        price_id = os.getenv(nome, "").strip()
        try:
            stripe.Price.retrieve(price_id)
        except Exception as e:  # noqa: BLE001
            tipo = type(e).__name__
            if "APIConnection" in tipo or "Timeout" in tipo:
                return True, f"indeterminado: falha de rede ao verificar ({tipo})"
            quebrados.append(nome)

    if quebrados:
        return False, (
            f"chave em modo {modo_chave}, mas estes price IDs nao existem nesse "
            f"modo: {', '.join(quebrados)}. O checkout vai falhar com 'No such "
            "price'. Causa tipica: migracao test->live que trocou a chave e "
            "esqueceu os precos."
        )

    return True, f"{len(_ENVS_PRECO)} price IDs validos no modo {modo_chave}"


_browser_cache: tuple[bool, str] | None = None


def browser_disponivel(forcar: bool = False) -> tuple[bool, str]:
    """O Playwright consegue abrir um browser AGORA? Retorna (ok, motivo).

    Resultado e cacheado: o binario nao aparece nem some durante a vida do
    processo. Passe forcar=True para reavaliar (usado em teste).
    """
    global _browser_cache
    if _browser_cache is not None and not forcar:
        return _browser_cache

    resultado = _checar_browser()
    _browser_cache = resultado
    return resultado


def _checar_browser() -> tuple[bool, str]:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False, "pacote 'playwright' nao instalado"

    import glob

    # Locais onde o Playwright guarda os browsers, em ordem de precedencia.
    candidatos = []
    if os.getenv("PLAYWRIGHT_BROWSERS_PATH"):
        candidatos.append(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
    candidatos += [
        "/ms-playwright",                                   # imagem oficial
        os.path.expanduser("~/.cache/ms-playwright"),        # Linux (Render)
        os.path.expanduser("~/AppData/Local/ms-playwright"),  # Windows
    ]

    for base in candidatos:
        if not base or not os.path.isdir(base):
            continue
        if glob.glob(os.path.join(base, "chromium*")):
            return True, f"chromium encontrado em {base}"

    return False, (
        "binario do chromium ausente — 'playwright install chromium' "
        "provavelmente falhou no build (render.yaml usa '|| true', que engole o erro)"
    )


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

    # Automacao web — visivel aqui em vez de descoberta pelo usuario.
    ok_browser, motivo_browser = browser_disponivel()
    estado["automacao_web"] = {
        "disponivel": ok_browser,
        "motivo": motivo_browser,
    }

    # Stripe — a chave AUTENTICA? Sem isto, o dono so descobre que o checkout
    # esta quebrado quando um cliente tenta pagar e nao consegue.
    ok_stripe, motivo_stripe = stripe_autentica()
    ok_precos, motivo_precos = stripe_precos_coerentes()
    estado["stripe"] = {
        "autentica": ok_stripe,
        "motivo": motivo_stripe,
        # Chave valida NAO significa cobranca funcionando: chave live com price
        # de test da "No such price" no checkout. Ver stripe_precos_coerentes().
        "precos_ok": ok_precos,
        "precos_motivo": motivo_precos,
        "cobranca_operacional": ok_stripe and ok_precos,
    }
    return estado
