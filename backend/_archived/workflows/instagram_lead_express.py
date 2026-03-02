"""
Instagram Lead Express
======================

Workflow comercial: Automação de acesso ao painel de login do Instagram.

Caso de uso:
- Demonstrate o poder do agente de automação
- Prova de conceito pra clientes de agência
- Base pra fluxos mais complexos (captura de leads, qualificação, resposta automática)

Produto que você vende:
- Setup: Adaptação do fluxo pra o account da cliente (URLs, seletores específicos)
- Recorrência: Monitoramento, ajuste de prompts, relatório mensal
"""

from __future__ import annotations

try:
    from backend.agents import site_agent
    from backend.utils.logging_utils import get_logger
except ImportError:
    from ..agents import site_agent
    from ..utils.logging_utils import get_logger

logger = get_logger(__name__)


def executar_lead_express() -> dict:
    """
    Executa o fluxo 'Instagram Lead Express':
    1. Abre o painel de login do Instagram
    2. Aguarda o campo de usuário aparecer
    3. Clica no campo de usuário (preparando para digitação futura)
    4. Aguarda 3 segundos para inspeção

    Retorna dict com status e detalhes da execução.
    """

    logger.info("=" * 60)
    logger.info("INICIANDO: Instagram Lead Express")
    logger.info("=" * 60)

    objetivo = (
        "Abrir a página de login do Instagram em https://www.instagram.com/accounts/login/ "
        "e clicar no campo de entrada de usuário para ativá-lo."
    )

    try:
        logger.info("Fase 1: Planejando automação com IA...")
        plano = site_agent.planejar("instagram", objetivo)

        logger.info("Fase 2: Executando plano no navegador...")
        logger.info("Plano gerado:\n%s", plano)
        site_agent.executar_plano("instagram", plano)

        logger.info("=" * 60)
        logger.info("[SUCESSO] Instagram Lead Express completou com sucesso!")
        logger.info("=" * 60)

        return {
            "status": "sucesso",
            "mensagem": "Fluxo de login do Instagram executado com sucesso.",
            "passos_executados": len(plano.get("steps", [])),
        }

    except Exception as exc:  # noqa: BLE001
        logger.exception("[ERRO] Erro ao executar Instagram Lead Express: %s", exc)
        return {
            "status": "erro",
            "mensagem": f"Falha no fluxo: {exc}",
            "passos_executados": 0,
        }


if __name__ == "__main__":  # pragma: no cover
    resultado = executar_lead_express()
    print(f"\nResultado: {resultado}")
