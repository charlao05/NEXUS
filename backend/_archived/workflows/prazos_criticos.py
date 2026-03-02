"""
Workflow: Prazos Críticos

Fluxo completo de execução do agente de deadlines:
1. Carrega obrigações do MEI
2. Detecta alertas (prazos próximos)
3. Gera mensagem humanizada
4. (Futuro) Envia via WhatsApp / e-mail
"""

import json
from pathlib import Path
from datetime import datetime

try:
    from backend.agents.deadlines_agent import (
        check_deadlines,
        generate_reminder_message,
        suggest_action,
        load_obligations,
    )
    from backend.utils.logging_utils import get_logger
except ImportError:
    from ..agents.deadlines_agent import (
        check_deadlines,
        generate_reminder_message,
        suggest_action,
        load_obligations,
    )
    from ..utils.logging_utils import get_logger

logger = get_logger(__name__)


def executar_prazos_criticos(
    obligations_path: str = "data/mei_obligations.json",
    save_report: bool = False,
    send_notification: bool = False,
) -> dict:
    """
    Fluxo principal: Detecta prazos críticos e prepara notificação.

    Args:
        obligations_path: Caminho para arquivo JSON de obrigações
        save_report: Se True, salva relatório em arquivo
        send_notification: Se True, simula envio via WhatsApp (future)

    Returns:
        dict: Estrutura com alertas, mensagem e ações sugeridas
    """
    logger.info("=== INICIANDO: Workflow Prazos Críticos ===")

    # Step 1: Carregar dados
    logger.info(f"Step 1: Carregando obrigações de {obligations_path}...")
    data = load_obligations(obligations_path)
    if not data:
        return {"success": False, "error": "Arquivo de obrigações não encontrado"}

    mei_id = data.get("mei_id")
    mei_name = data.get("mei_name", "MEI Desconhecido")
    logger.info(f"MEI: {mei_name} ({mei_id})")

    # Step 2: Detectar alertas
    logger.info("Step 2: Verificando prazos próximos...")
    alerts = check_deadlines(obligations_path)
    logger.info(f"Alertas detectados: {len(alerts)}")

    if not alerts:
        logger.info("Nenhum alerta no momento.")
        return {
            "success": True,
            "mei_id": mei_id,
            "mei_name": mei_name,
            "alerts": [],
            "message": "Tudo em dia! ✅",
            "actions": [],
        }

    # Step 3: Gerar mensagem
    logger.info("Step 3: Gerando mensagem humanizada...")
    message = generate_reminder_message(alerts, mei_name=mei_name)

    # Step 4: Sugerir ações
    logger.info("Step 4: Sugerindo ações...")
    actions = []
    for alert in alerts[:3]:  # Top 3 mais urgentes
        action = suggest_action(alert)
        actions.append(action)

    # Step 5: Preparar resultado
    result = {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "mei_id": mei_id,
        "mei_name": mei_name,
        "alerts": [alert.to_dict() for alert in alerts],
        "message": message,
        "actions": actions,
        "total_alerts": len(alerts),
        "critical_count": sum(1 for a in alerts if a.priority == "critical"),
        "high_count": sum(1 for a in alerts if a.priority == "high"),
    }

    # Step 6: Salvar relatório (opcional)
    if save_report:
        logger.info("Step 6: Salvando relatório...")
        report_path = Path("logs/deadlines_report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Relatório salvo: {report_path}")

    # Step 7: Enviar notificação (futuro)
    if send_notification:
        logger.info("Step 7: (Futuro) Enviando notificação via WhatsApp...")
        # TODO: Integrar com WhatsApp API
        pass

    logger.info("=== CONCLUÍDO: Workflow Prazos Críticos ===\n")
    return result


def exibir_resultado(resultado: dict) -> None:
    """
    Exibe o resultado do workflow de forma legível.
    """
    if not resultado.get("success"):
        print(f"[ERRO] {resultado.get('error')}")
        return

    print("\n" + "=" * 60)
    print(f"[RELATORIO] PRAZOS - {resultado['mei_name']}")
    print("=" * 60)

    # Resumo
    print("\n[RESUMO]")
    print(f"   Total de alertas: {resultado['total_alerts']}")
    print(f"   [CRITICO] Críticos: {resultado['critical_count']}")
    print(f"   [ALTO] Altos: {resultado['high_count']}")

    # Alertas
    if resultado["alerts"]:
        print("\n[PRAZOS PROXIMOS]")
        for alert in resultado["alerts"][:5]:
            icon = (
                "[CRITICO]"
                if alert["priority"] == "critical"
                else "[ALTO]"
                if alert["priority"] == "high"
                else "[INFO]"
            )
            print(f"\n   {icon} {alert['name']}")
            print(f"      Vence: {alert['due_date']} ({alert['days_remaining']}d)")
            if alert["estimated_value"]:
                print(f"      Valor: R$ {alert['estimated_value']:.2f}")

    # Mensagem
    print("\n[NOTIFICACAO]")
    print(f"\n{resultado['message']}\n")

    # Ações
    if resultado["actions"]:
        print("[ACOES SUGERIDAS]")
        for i, action in enumerate(resultado["actions"], 1):
            print(f"\n   {i}. {action['suggested_action']}")
            if action.get("url"):
                print(f"      {action['url']}")
            if action.get("steps"):
                print("      Passos:")
                for step in action["steps"][:2]:
                    print(f"        * {step}")

    print("\n" + "=" * 60 + "\n")


# --- CLI / MAIN ---

if __name__ == "__main__":
    import sys

    # Opções de linha de comando
    save_report = "--salvar" in sys.argv or "--save-report" in sys.argv
    send_notification = "--enviar" in sys.argv or "--notify" in sys.argv

    # Executar
    resultado = executar_prazos_criticos(
        obligations_path="data/mei_obligations.json",
        save_report=save_report,
        send_notification=send_notification,
    )

    # Exibir
    exibir_resultado(resultado)

    # Debug: salvar JSON completo
    if "--debug" in sys.argv:
        print("\n[DEBUG] Resultado completo (JSON):")
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
