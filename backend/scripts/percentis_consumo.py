# -*- coding: utf-8 -*-
"""
Distribuição de consumo por usuário (P50 → P99,9).
==================================================
Substitui cenários inventados por DISTRIBUIÇÃO OBSERVADA.

Por que existe: o stress test (scripts/stress_test_margem.py) usa perfis de
carga que são PREMISSA — alguém escolheu "20k mensagens, 100h de áudio". Isso
responde "e se?", não "como é". Política de uso justo dimensionada por cenário
hipotético protege do caso errado: ou é frouxa demais (não protege) ou apertada
demais (incomoda cliente normal).

Este script lê o consumo REAL registrado e devolve os percentis. Com eles se
dimensiona a política pelo P99 — o cliente pesado de verdade — em vez do
extremo imaginado.

IMPORTANTE: sem clientes, ele NÃO inventa distribuição. Ele diz que não há
dados. Esse é o comportamento correto.

    python scripts/percentis_consumo.py [--dias 30]
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

USD_BRL = float(os.getenv("USD_BRL_RATE", "5.20"))
RENDER_USD_MIN = float(os.getenv("RENDER_COMPUTE_USD_PER_MIN", "0.00016"))

PERCENTIS = [50, 75, 90, 95, 99, 99.9]


def percentil(valores: list[float], p: float) -> float:
    """Percentil por interpolação linear (método simples, sem numpy)."""
    if not valores:
        return 0.0
    ordenado = sorted(valores)
    if len(ordenado) == 1:
        return ordenado[0]
    k = (len(ordenado) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ordenado) - 1)
    return ordenado[f] + (ordenado[c] - ordenado[f]) * (k - f)


def coletar(dias: int) -> dict:
    """Custo por usuário no período, separado por driver."""
    from database.models import SessionLocal, LLMUsageRecord, AutomationUsageRecord

    inicio = datetime.now(timezone.utc) - timedelta(days=dias)
    db = SessionLocal()
    try:
        por_usuario: dict[int, dict[str, float]] = defaultdict(
            lambda: {"ia_brl": 0.0, "audio_brl": 0.0, "auto_brl": 0.0,
                     "chamadas": 0, "audio_min": 0.0, "auto_min": 0.0}
        )

        for r in db.query(LLMUsageRecord).filter(LLMUsageRecord.ts >= inicio).all():
            u = por_usuario[r.user_id or 0]
            custo = float(r.cost_usd or 0) * USD_BRL
            # Áudio é gravado com 0 tokens (ver track_audio_usage)
            if (r.total_tokens or 0) == 0 and custo > 0:
                u["audio_brl"] += custo
            else:
                u["ia_brl"] += custo
            u["chamadas"] += 1

        for a in db.query(AutomationUsageRecord).filter(
                AutomationUsageRecord.ts >= inicio).all():
            u = por_usuario[a.user_id or 0]
            minutos = float(a.duration_ms or 0) / 60_000.0
            u["auto_min"] += minutos
            u["auto_brl"] += minutos * RENDER_USD_MIN * USD_BRL

        return dict(por_usuario)
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=30)
    args = ap.parse_args()

    print("=" * 70)
    print(f"DISTRIBUIÇÃO DE CONSUMO POR USUÁRIO — últimos {args.dias} dias")
    print("=" * 70)

    dados = coletar(args.dias)
    # user_id 0 = chamadas sem contexto (cron/webhook), não é cliente
    clientes = {u: v for u, v in dados.items() if u != 0}

    if not clientes:
        print("""
SEM DADOS — nenhum consumo de cliente registrado no período.

Isto NÃO é um erro: a base ainda não tem clientes ativos. O script não
inventa distribuição, e nenhuma política de uso justo deve ser dimensionada
sem estes números.

O que fazer: quando houver clientes usando o produto, rodar de novo. Os
percentis produzidos aqui SUBSTITUEM os perfis hipotéticos usados em
scripts/stress_test_margem.py.

Enquanto isso, a única afirmação sustentável é a matemática: existe um ponto
em que o consumo supera a receita do plano (ver 07_STRESS_TEST_E_PRECO.md) —
mas ONDE os clientes reais caem nessa curva é desconhecido.
""")
        return 0

    total = [c["ia_brl"] + c["audio_brl"] + c["auto_brl"] for c in clientes.values()]
    ia = [c["ia_brl"] for c in clientes.values()]
    audio = [c["audio_brl"] for c in clientes.values()]
    auto = [c["auto_brl"] for c in clientes.values()]

    print(f"\nclientes com consumo: {len(clientes)}")
    print(f"custo total do período: R$ {sum(total):.2f}\n")
    print(f"{'percentil':>10} | {'custo total':>12} | {'IA':>10} | "
          f"{'áudio':>10} | {'automação':>10}")
    print("-" * 70)
    for p in PERCENTIS:
        print(f"{'P' + str(p):>10} | R$ {percentil(total, p):>9.2f} | "
              f"R$ {percentil(ia, p):>7.2f} | R$ {percentil(audio, p):>7.2f} | "
              f"R$ {percentil(auto, p):>7.2f}")

    p99 = percentil(total, 99)
    print(f"\nO cliente do P99 custa R$ {p99:.2f}/período.")
    print("Dimensione a política de uso justo por este número — não pelo extremo")
    print("hipotético. O extremo protege do caso que talvez nunca aconteça;")
    print("o P99 protege do caso que acontece com 1 em cada 100 clientes.")

    if len(clientes) < 30:
        print(f"\n⚠️  AMOSTRA PEQUENA ({len(clientes)} clientes): percentis altos")
        print("   (P99, P99,9) não são confiáveis com esta base. Trate como")
        print("   indicativo, não como parâmetro.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
