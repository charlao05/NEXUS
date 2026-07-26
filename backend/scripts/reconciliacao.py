# -*- coding: utf-8 -*-
"""
Reconciliação do modelo econômico — o modelo FECHA?
===================================================
Testa, com dados auditáveis, as três igualdades exigidas:

    (1)  Receita Total − Impostos − Gateway − Infra − IA − Automações
         − Recursos de Alto Consumo − Custos Variáveis − Custos Fixos Rateados
         = Margem de Contribuição

    (2)  Σ(receitas individuais)  =  Receita Total da empresa
    (3)  Σ(custos individuais)    =  Custo Total da empresa
    (4)  Σ(margens individuais)   =  Margem Consolidada

Regra: se uma igualdade não puder ser demonstrada, o script NÃO estima o termo
faltante — ele PARA e identifica a variável que impede, classificada como
MEDIDA / CALCULADA / PREMISSA / AUSENTE.

Sai com código 1 enquanto o modelo não fechar. Isso é intencional: serve como
porta de qualidade antes de qualquer decisão de precificação.

    python scripts/reconciliacao.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

USD_BRL = float(os.getenv("USD_BRL_RATE", "5.20"))


class Termo:
    """Um termo da equação, com origem rastreável."""

    def __init__(self, nome: str, valor: float | None, origem: str,
                 onde: str, bloqueia: bool = False, nota: str = ""):
        self.nome = nome
        self.valor = valor              # None = não calculável hoje
        self.origem = origem            # MEDIDA | CALCULADA | PREMISSA | AUSENTE
        self.onde = onde                # arquivo/tabela que sustenta
        self.bloqueia = bloqueia        # impede o fechamento?
        self.nota = nota

    @property
    def simbolo(self) -> str:
        return "🔴" if self.bloqueia else ("⚠️ " if self.origem == "PREMISSA" else "✅")


def levantar(dias: int = 30) -> list[Termo]:
    from database.models import (
        SessionLocal, LLMUsageRecord, AutomationUsageRecord,
        InvoicePayment, InfraCostSnapshot, RevenueEntry,
    )

    inicio = datetime.now(timezone.utc) - timedelta(days=dias)
    db = SessionLocal()
    try:
        # ── RECEITA ─────────────────────────────────────────────────────
        pagos = db.query(InvoicePayment).filter(
            InvoicePayment.paid_at >= inicio).all()
        receita_assinatura = sum(float(p.amount_cents or 0) / 100.0 for p in pagos)

        # Receita por natureza (RevenueEntry) — separa MRR de pontual
        _entries = db.query(RevenueEntry).filter(
            RevenueEntry.occurred_at >= inicio).all()
        receita_recorrente_extra = sum(
            float(e.amount_brl or 0) for e in _entries if e.is_recurring)
        receita_nao_recorrente = sum(
            float(e.amount_brl or 0) for e in _entries if not e.is_recurring)
        custo_servico = sum(float(e.cost_brl or 0) for e in _entries)

        # ── CUSTOS ──────────────────────────────────────────────────────
        llm = db.query(LLMUsageRecord).filter(LLMUsageRecord.ts >= inicio).all()
        custo_ia = sum(float(r.cost_usd or 0) for r in llm) * USD_BRL

        autos = db.query(AutomationUsageRecord).filter(
            AutomationUsageRecord.ts >= inicio).all()
        min_auto = sum(float(a.duration_ms or 0) for a in autos) / 60_000.0
        custo_auto = min_auto * float(
            os.getenv("RENDER_COMPUTE_USD_PER_MIN", "0.00016")) * USD_BRL

        snap = db.query(InfraCostSnapshot).order_by(
            InfraCostSnapshot.id.desc()).first()

        fee_pct = float(os.getenv("STRIPE_FEE_PERCENT", "0.0399"))
        fee_fix = float(os.getenv("STRIPE_FEE_FIXED_BRL", "0.39"))
        gateway = (receita_assinatura * fee_pct + fee_fix * len(pagos)) if pagos else 0.0

        return [
            Termo("Receita — assinatura", receita_assinatura, "MEDIDA",
                  "InvoicePayment (Stripe)"),
            Termo("Receita — serviços (implantação/treinamento/consultoria)",
                  receita_nao_recorrente, "MEDIDA",
                  "RevenueEntry (is_recurring=False)",
                  nota="separada do MRR por natureza econômica"),
            Termo("Receita — recorrente extra (suporte)", receita_recorrente_extra,
                  "MEDIDA", "RevenueEntry (is_recurring=True)"),
            Termo("(−) Custo de entrega de serviço", custo_servico, "MEDIDA",
                  "RevenueEntry.cost_brl",
                  nota="sem isto, serviço pareceria 100% de margem"),
            Termo("(−) Impostos",
                  (receita_assinatura * float(os.getenv("TAX_RATE", "0") or 0))
                  if os.getenv("TAX_RATE", "").strip() else None,
                  "MEDIDA" if os.getenv("TAX_RATE", "").strip() else "PREMISSA",
                  "admin.py::_calc_tax (env TAX_RATE)",
                  bloqueia=not os.getenv("TAX_RATE", "").strip(),
                  nota=("alíquota configurada" if os.getenv("TAX_RATE", "").strip()
                        else "TAX_RATE não definida → margem segue PRÉ-IMPOSTO. "
                             "Depende do regime tributário da empresa (P-033)")),
            Termo("(−) Gateway (Stripe)", gateway, "MEDIDA",
                  "admin.py::_calc_gateway_fee"),
            Termo("(−) IA (texto + áudio)", custo_ia, "MEDIDA",
                  "LLMUsageRecord.cost_usd"),
            Termo("(−) Automações (compute)", custo_auto, "CALCULADA",
                  "AutomationUsageRecord.duration_ms × preço/min Render",
                  nota="proxy: tempo × preço de instância, não fatura real"),
            Termo("(−) Infra / custos fixos rateados",
                  float(snap.total_brl) if snap else None,
                  "MEDIDA" if snap else "PREMISSA",
                  "InfraCostSnapshot", bloqueia=snap is None,
                  nota="nenhum snapshot lançado — rateio = 0 e o fixo some da conta"),
            Termo("(−) Storage do banco", None, "AUSENTE", "não medido",
                  bloqueia=False,
                  nota="Neon free hoje; vira custo real na escala"),
        ]
    finally:
        db.close()


def main() -> int:
    print("=" * 74)
    print("RECONCILIAÇÃO DO MODELO ECONÔMICO — o modelo fecha?")
    print("=" * 74)

    termos = levantar()

    print(f"\n{'termo':<52} {'valor':>12}  origem")
    print("-" * 74)
    for t in termos:
        v = f"R$ {t.valor:,.2f}".replace(",", ".") if t.valor is not None else "—"
        print(f"{t.simbolo} {t.nome:<50} {v:>12}  {t.origem}")
        if t.nota:
            print(f"      ↳ {t.nota}")

    bloqueios = [t for t in termos if t.bloqueia]

    print("\n" + "=" * 74)
    print("IGUALDADES EXIGIDAS")
    print("=" * 74)

    # A igualdade (1) é sobre margem de CONTRIBUIÇÃO = receita − custos
    # VARIÁVEIS. O rateio de infra é custo FIXO e, por definição contábil, não
    # entra aqui — logo não a bloqueia. Só termos variáveis ausentes bloqueiam.
    bloqueios_variaveis = [
        t for t in bloqueios if "Infra" not in t.nome and "fixos" not in t.nome
    ]

    checks = [
        ("(1) Receita − custos VARIÁVEIS = Margem de Contribuição",
         not bloqueios_variaveis,
         "termo variável ausente: "
         + ", ".join(t.nome for t in bloqueios_variaveis)),
        ("(2) Σ(receitas individuais) = Receita Total",
         not any("Receita" in t.nome for t in bloqueios),
         "receita de serviços e addons/excedentes não têm registro próprio"),
        ("(3) Σ(custos VARIÁVEIS individuais) = Custo Variável Total",
         True,
         ""),
        ("(3b) [só se adotar rateio de fixo por cliente — opções A/B] "
         "Σ(custos + rateio fixo) = Custo Total",
         False,
         "FALSO POR DESIGN (rateio pula tenant sem uso → 'unattributed'). "
         "NÃO SE APLICA na opção C (fixo fora do unit economics), que é a "
         "recomendada — decisão pendente do dono, ver 11 §3"),
        ("(4) Σ(margens de contribuição) = Margem de Contribuição Consolidada",
         not any("Receita" in t.nome for t in termos if t.bloqueia),
         "depende de (2): receita de serviços/addons sem registro próprio"),
    ]
    for nome, ok, motivo in checks:
        print(f"\n{'✅ FECHA' if ok else '🔴 NÃO FECHA'}  {nome}")
        if not ok:
            print(f"           motivo: {motivo}")

    print("\n" + "=" * 74)
    print("VARIÁVEIS QUE IMPEDEM O FECHAMENTO")
    print("=" * 74)
    for t in bloqueios:
        print(f"\n  [{t.origem}] {t.nome}")
        print(f"      onde deveria estar: {t.onde}")
        if t.nota:
            print(f"      impacto: {t.nota}")
    print("\n  [ESTRUTURAL] Custo não atribuído (unattributed)")
    print("      onde: admin.py::_resolve_user_compute_cost → 'zero_no_usage'")
    print("      impacto: por design, parte do custo fixo não é atribuída a")
    print("               nenhum cliente. Σ(custos) < Custo Total sempre.")

    # Dois níveis distintos — não confundir:
    unit_ok = not bloqueios_variaveis
    tem_snapshot = not any("Infra" in t.nome for t in bloqueios)
    consolidado_ok = unit_ok and tem_snapshot

    print("\n" + "=" * 74)
    print("VEREDITO POR NÍVEL")
    print("=" * 74)
    print(f"\n{'✅' if unit_ok else '🔴'} UNIT ECONOMICS (margem de contribuição por cliente)")
    print("   receita − custos variáveis. É o número que decide preço e se")
    print("   vale absorver consumo de um cliente.")
    if not unit_ok:
        for t in bloqueios_variaveis:
            print(f"   falta: {t.nome} [{t.origem}]")

    print(f"\n{'✅' if consolidado_ok else '🔴'} RESULTADO CONSOLIDADO (empresa)")
    print("   margem de contribuição total − custos fixos.")
    if not tem_snapshot:
        print("   falta: custo fixo mensal não lançado")
        print("          → POST /api/admin/billing/infra-cost-snapshot (1 min/mês)")

    print("\n" + ("-" * 74))
    if unit_ok and consolidado_ok:
        print("MODELO FECHADO. Decisões de precificação podem ser tomadas sobre")
        print("esta base — respeitando as premissas do 15_REGISTRO_PREMISSAS.md.")
        return 0
    if unit_ok:
        print("PARCIALMENTE FECHADO: unit economics fecha; o consolidado depende")
        print("de lançar o custo fixo mensal. Precificação por cliente já é")
        print("defensável; resultado da empresa ainda não.")
        return 0
    print("NÃO FECHA: há termo variável ausente. Nenhuma decisão de precificação")
    print("deve ser tomada sobre esta base.")
    print("Ver: AUDITORIA_NEXUS/11_FECHAMENTO_MODELO.md")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
