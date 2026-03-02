"""Exemplo simples de workflow que reaproveita o agente genérico."""

from __future__ import annotations

try:
    from backend.agents.site_agent import executar_plano, planejar
except ImportError:
    from ..agents.site_agent import executar_plano, planejar

# Este módulo serve como referência para criar novos workflows específicos.


def executar_exemplo() -> None:
    objetivo = (
        "abrir a página de login do Instagram e esperar o campo de usuário aparecer"
    )
    plano = planejar("instagram", objetivo)
    executar_plano("instagram", plano)


if __name__ == "__main__":  # pragma: no cover
    executar_exemplo()
