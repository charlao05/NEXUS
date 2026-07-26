# -*- coding: utf-8 -*-
"""
Stress test de margem por perfil de carga.
==========================================
Responde: "o preço do plano aguenta o pior caso de uso permitido?"

Lê as CONSTANTES REAIS do código instrumentado — não tem número hardcoded de
custo. Se a OpenAI mudar o preço, se o câmbio mudar ou se a taxa do gateway
for renegociada, basta rodar de novo:

    python scripts/stress_test_margem.py

Origem de cada número (metodologia MEDIDO/CALCULADO/PREMISSA):
  MEDIDO     — preços de LLM e áudio (helpers/openai_tracking.py), taxa do
               gateway e preço/min de compute (envs usadas por admin.py)
  PREMISSA   — tamanho médio de interação, duração média de automação e os
               perfis de carga. São o que se troca por dado real quando
               houver clientes.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Console do Windows usa cp1252 e quebra em acento/emoji. Como este script é
# para rodar em qualquer terminal, força UTF-8 na saída quando possível.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001 — terminal sem suporte, segue com o padrão
    pass

from helpers.openai_tracking import _PRICES_PER_1M, calc_audio_cost_usd  # noqa: E402

# ── Constantes MEDIDAS (mesmas que o /margin usa em produção) ────────────────
USD_BRL = float(os.getenv("USD_BRL_RATE", "5.20"))
RENDER_USD_MIN = float(os.getenv("RENDER_COMPUTE_USD_PER_MIN", "0.00016"))
FEE_PCT = float(os.getenv("STRIPE_FEE_PERCENT", "0.0399"))
FEE_FIX = float(os.getenv("STRIPE_FEE_FIXED_BRL", "0.39"))
CHAT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
AUDIO_MODEL = os.getenv("OPENAI_AUDIO_MODEL", "whisper-1")

# ── PREMISSAS (trocar por dado observado quando houver clientes) ─────────────
TOKENS_IN, TOKENS_OUT = 1500, 500   # tamanho médio de uma interação de chat
AUTOMACAO_MIN = 2.0                 # duração média de uma automação (minutos)


def custo_chat_usd(model: str = CHAT_MODEL) -> float:
    p = _PRICES_PER_1M.get(model, _PRICES_PER_1M["gpt-4o-mini"])
    return (TOKENS_IN * p["input"] + TOKENS_OUT * p["output"]) / 1_000_000


def avaliar(nome: str, plano: str, preco: float, msgs: int,
            horas_audio: float, automacoes: int,
            audio_model: str = AUDIO_MODEL) -> dict:
    """Margem de contribuição de um perfil de carga."""
    llm_usd = msgs * custo_chat_usd()
    audio_usd = calc_audio_cost_usd(horas_audio * 3600, audio_model)
    auto_usd = automacoes * AUTOMACAO_MIN * RENDER_USD_MIN

    variavel_brl = (llm_usd + audio_usd + auto_usd) * USD_BRL
    taxa_brl = (preco * FEE_PCT + FEE_FIX) if preco > 0 else 0.0
    margem = preco - taxa_brl - variavel_brl

    return {
        "nome": nome, "plano": plano, "preco": preco,
        "llm_brl": llm_usd * USD_BRL,
        "audio_brl": audio_usd * USD_BRL,
        "auto_brl": auto_usd * USD_BRL,
        "taxa_brl": taxa_brl,
        "custo_brl": variavel_brl + taxa_brl,
        "margem_brl": margem,
        "margem_pct": (margem / preco * 100) if preco else 0.0,
    }


def imprimir(r: dict) -> None:
    alerta = "  🔴 NEGATIVA" if r["margem_brl"] < 0 else (
        "  ⚠️  APERTADA" if r["margem_pct"] < 50 else "")
    print(f"\n{r['nome']}  [{r['plano']} R$ {r['preco']:.2f}]")
    print(f"  - IA texto     R$ {r['llm_brl']:>8.2f}")
    print(f"  - áudio        R$ {r['audio_brl']:>8.2f}")
    print(f"  - automação    R$ {r['auto_brl']:>8.2f}")
    print(f"  - taxa gateway R$ {r['taxa_brl']:>8.2f}")
    print(f"  = CUSTO        R$ {r['custo_brl']:>8.2f}")
    print(f"  = MARGEM       R$ {r['margem_brl']:>8.2f}  "
          f"({r['margem_pct']:.1f}%){alerta}")


def ponto_de_virada(preco: float) -> None:
    """Quanto de CADA recurso, sozinho, zera a margem do plano."""
    liquido = preco - (preco * FEE_PCT + FEE_FIX)
    c_chat = custo_chat_usd() * USD_BRL
    c_audio_min = calc_audio_cost_usd(60, AUDIO_MODEL) * USD_BRL
    c_auto = AUTOMACAO_MIN * RENDER_USD_MIN * USD_BRL
    print(f"\nPONTO DE VIRADA do plano R$ {preco:.2f} "
          f"(líquido após gateway: R$ {liquido:.2f}):")
    print(f"  só áudio:     {liquido / c_audio_min / 60:>10.1f} horas/mês")
    print(f"  só chat:      {liquido / c_chat:>10,.0f} mensagens/mês".replace(",", "."))
    print(f"  só automação: {liquido / c_auto:>10,.0f} automações/mês".replace(",", "."))


# ── PERFIS DE CARGA (PREMISSA — ajuste conforme observar clientes reais) ─────
PERFIS = [
    # nome,                        plano,          preço,  msgs, horas_áudio, automações
    ("1. LEVE (MEI típico)",       "Essencial",    29.90,    200,   1,    10),
    ("2. MÉDIO (negócio ativo)",   "Profissional", 59.90,   1500,   5,    60),
    ("3. PESADO (usa de verdade)", "Completo",     89.90,   5000,  20,   200),
    ("4. EXTREMO (agência)",       "Completo",     89.90,  20000, 100,   800),
]


def main() -> int:
    print("=" * 68)
    print("STRESS TEST DE MARGEM — NEXUS")
    print(f"chat={CHAT_MODEL} (US$ {custo_chat_usd():.6f}/interação) | "
          f"áudio={AUDIO_MODEL}")
    print(f"câmbio={USD_BRL} | gateway={FEE_PCT*100:.2f}%+R${FEE_FIX:.2f} | "
          f"compute=US${RENDER_USD_MIN}/min")
    print("=" * 68)

    negativos = []
    for perfil in PERFIS:
        r = avaliar(*perfil)
        imprimir(r)
        if r["margem_brl"] < 0:
            negativos.append(r)

    ponto_de_virada(89.90)

    if negativos:
        print("\n" + "!" * 68)
        print(f"ATENÇÃO: {len(negativos)} perfil(is) com MARGEM NEGATIVA.")
        print("Um único cliente nesse padrão consome o lucro de vários outros.")
        print("Ver política de recursos de alto consumo (Fair Use) em")
        print("Desktop/negocio-automacao/AUDITORIA_NEXUS/07_STRESS_TEST_E_PRECO.md")
        print("!" * 68)
    return 1 if negativos else 0


if __name__ == "__main__":
    raise SystemExit(main())
