from __future__ import annotations

from pathlib import Path

try:
    from backend.agents.attendance_agent import processar_mensagens
    from backend.utils.logging_utils import get_logger
except ImportError:
    from ..agents.attendance_agent import processar_mensagens
    from ..utils.logging_utils import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"


def executar_atendimento_demo() -> dict:
    agenda_path = DATA_DIR / "mei_schedule.json"
    mensagens_path = DATA_DIR / "mensagens_clientes.json"

    contexto_negocio = (
        "Salão de estética e beleza para público feminino, "
        "focado em cuidados com cabelo e hidratação, atendimento em Vila Velha/ES."
    )

    logger.info("Executando atendimento automático (demo)...")

    resultados = processar_mensagens(
        agenda_path=agenda_path,
        mensagens_path=mensagens_path,
        contexto_negocio=contexto_negocio,
    )

    print("=" * 60)
    print("ATENDIMENTO AUTOMÁTICO - DEMO")
    print("=" * 60)

    for r in resultados:
        print("\n----------------------------------------")
        print(f"Mensagem ID: {r['id']} ({r['canal']})")
        print(f"Cliente: {r['nome_cliente']}")
        print("Texto original:")
        print(r["texto_original"])
        print("\nResposta sugerida:")
        print(r["resposta"])
        print("\nSlots sugeridos:")
        for s in r["slots_sugeridos"]:
            print(f"  - {s}")

    return {
        "total_mensagens": len(resultados),
        "resultados": resultados,
    }


if __name__ == "__main__":
    executar_atendimento_demo()
