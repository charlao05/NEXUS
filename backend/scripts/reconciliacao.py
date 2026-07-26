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
        InvoicePayment, InfraCostSnapshot,
    )

    inicio = datetime.now(timezone.utc) - timedelta(days=dias)
    db = SessionLocal()
    try:
        # ── RECEITA ─────────────────────────────────────────────────────
        pagos = db.query(InvoicePayment).filter(
            InvoicePayment.paid_at >= inicio).all()
        receita_assinatura = sum(float(p.amount_cents or 0) / 100.0 for p in pagos)

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
                  None, "AUSENTE", "não existe tabela", bloqueia=True,
                  nota="cliente que paga R$2.500 de implantação aparece como R$89,90"),
            Termo("Receita — addons / excedentes", None, "AUSENTE",
                  "sem categoria própria", bloqueia=True,
                  nota="addon existe no checkout, mas não é separado da assinatura"),
            Termo("(−) Impostos", None, "AUSENTE", "nenhum cálculo no código",
                  bloqueia=True,
                  nota="toda margem reportada até hoje é PRÉ-IMPOSTO"),
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

    checks = [
        ("(1) Receita − todos os custos = Margem de Contribuição",
         not bloqueios,
         "impossível: termos ausentes na equação"),
        ("(2) Σ(receitas individuais) = Receita Total",
         not any("Receita" in t.nome for t in bloqueios),
         "receita de serviços e addons/excedentes não têm registro próprio"),
        ("(3) Σ(custos individuais) = Custo Total",
         False,
         "FALSO POR DESIGN: o rateio pula tenant sem uso (zero_no_usage), "
         "gerando custo 'unattributed' que não é atribuído a ninguém"),
        ("(4) Σ(margens individuais) = Margem Consolidada",
         False,
         "consequência de (2) e (3)"),
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

    print("\n" + "!" * 74)
    print("VEREDITO: o modelo NÃO FECHA hoje.")
    print("Nenhuma decisão de precificação deve ser tomada sobre esta base")
    print("até que os termos acima estejam medidos ou explicitamente")
    print("assumidos como premissa documentada.")
    print("Ver: AUDITORIA_NEXUS/11_FECHAMENTO_MODELO.md")
    print("!" * 74)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
