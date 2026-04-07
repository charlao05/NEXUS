"""
NEXUS - Email Service (Resend Free Tier)
==========================================
Serviço de envio de email usando Resend (100 emails/dia grátis).
Usado para: password reset, verificação de email, notificações críticas.
"""

import os
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("EMAIL_FROM", "NEXUS <onboarding@resend.dev>")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://app.nexxusapp.com.br")

# Aviso crítico no startup se produção sem chave de email
if os.getenv("ENVIRONMENT", "development") == "production" and not RESEND_API_KEY:
    logging.getLogger(__name__).error(
        "CRITICAL: RESEND_API_KEY não configurada em produção. "
        "Emails de boas-vindas, recuperação de senha e faturas NÃO serão enviados."
    )


def _get_resend():
    """Importa e configura Resend apenas quando necessário."""
    if not RESEND_API_KEY:
        return None
    try:
        import resend  # type: ignore[import-unresolved]
        resend.api_key = RESEND_API_KEY
        return resend
    except ImportError:
        logger.warning("Pacote 'resend' não instalado")
        return None


def send_email(to: str, subject: str, html: str) -> dict:
    """Envia email via Resend. Retorna status."""
    resend = _get_resend()
    if not resend:
        logger.warning(f"Email não enviado (sem RESEND_API_KEY): {subject} → {to}")
        return {"status": "skipped", "reason": "RESEND_API_KEY not configured"}

    try:
        params = {
            "from": FROM_EMAIL,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        result = resend.Emails.send(params)
        logger.info(f"✅ Email enviado: {subject} → {to}")
        return {"status": "sent", "id": result.get("id", "")}
    except Exception as e:
        logger.error(f"❌ Erro ao enviar email: {e}")
        return {"status": "error", "message": str(e)}


def generate_reset_token() -> str:
    """Gera token seguro para password reset (URL-safe, 48 chars)."""
    return secrets.token_urlsafe(36)


def send_password_reset_email(to: str, token: str) -> dict:
    """Envia email de recuperação de senha com link seguro."""
    reset_url = f"{FRONTEND_URL}/reset-password?token={token}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #10b981; margin: 0;">NEXUS</h1>
            <p style="color: #6b7280; margin: 5px 0 0 0;">Sistema de Gestão MEI</p>
        </div>

        <h2 style="color: #1f2937;">Recuperação de Senha</h2>
        <p style="color: #4b5563; line-height: 1.6;">
            Recebemos uma solicitação para redefinir sua senha. Clique no botão abaixo
            para criar uma nova senha. Este link expira em <strong>1 hora</strong>.
        </p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}"
               style="background-color: #10b981; color: white; padding: 14px 32px;
                      text-decoration: none; border-radius: 8px; font-weight: bold;
                      display: inline-block;">
                Redefinir Senha
            </a>
        </div>

        <p style="color: #9ca3af; font-size: 14px; line-height: 1.5;">
            Se você não solicitou esta alteração, ignore este email. Sua senha
            permanecerá inalterada.
        </p>

        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        <p style="color: #9ca3af; font-size: 12px; text-align: center;">
            NEXUS — Gestão inteligente para MEI &bull;
            <a href="{FRONTEND_URL}/privacidade" style="color: #10b981;">Política de Privacidade</a>
        </p>
    </div>
    """
    return send_email(to, "NEXUS — Recuperação de Senha", html)


def send_welcome_email(to: str, name: str) -> dict:
    """Envia email de boas-vindas após cadastro."""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #10b981; margin: 0;">NEXUS</h1>
            <p style="color: #6b7280; margin: 5px 0 0 0;">Bem-vindo(a)!</p>
        </div>

        <h2 style="color: #1f2937;">Olá, {name}! 🎉</h2>
        <p style="color: #4b5563; line-height: 1.6;">
            Sua conta NEXUS foi criada com sucesso. Você tem acesso
            <strong>gratuito permanente</strong> ao agente Fiscal (contabilidade).
            Faça upgrade a qualquer momento para desbloquear todos os recursos.
        </p>

        <div style="background: #f0fdf4; border-radius: 8px; padding: 20px; margin: 20px 0;">
            <h3 style="color: #166534; margin: 0 0 10px 0;">O que você pode fazer:</h3>
            <ul style="color: #4b5563; line-height: 1.8; padding-left: 20px;">
                <li>📊 Contabilidade MEI com DAS, NFs e IRPF</li>
                <li>👥 CRM completo para gerenciar clientes</li>
                <li>📅 Agendamentos inteligentes</li>
                <li>💰 Controle de cobranças</li>
                <li>🤖 Assistente virtual 24h</li>
            </ul>
        </div>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{FRONTEND_URL}/dashboard"
               style="background-color: #10b981; color: white; padding: 14px 32px;
                      text-decoration: none; border-radius: 8px; font-weight: bold;
                      display: inline-block;">
                Acessar NEXUS
            </a>
        </div>

        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        <p style="color: #9ca3af; font-size: 12px; text-align: center;">
            NEXUS — Gestão inteligente para MEI &bull;
            <a href="{FRONTEND_URL}/privacidade" style="color: #10b981;">Política de Privacidade</a>
        </p>
    </div>
    """
    return send_email(to, "Bem-vindo(a) ao NEXUS! 🚀", html)


# ============================================================================
# NOTIFICAÇÕES FINANCEIRAS — Lacuna #6 (invoice + DAS reminders)
# ============================================================================


def send_invoice_reminder(
    client_email: str,
    client_name: str,
    amount: float,
    due_date: str,
    invoice_id: Optional[int] = None,
) -> dict:
    """Envia lembrete de fatura/cobrança para cliente.

    Conectado ao evento PAGAMENTO_ATRASADO do hub.
    Template HTML em português com branding NEXUS.

    Args:
        client_email: Email do cliente devedor
        client_name: Nome do cliente
        amount: Valor da fatura em R$
        due_date: Data de vencimento (string formatada)
        invoice_id: ID opcional da fatura para referência
    """
    ref = f" (Ref: #{invoice_id})" if invoice_id else ""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #10b981; margin: 0;">NEXUS</h1>
            <p style="color: #6b7280; margin: 5px 0 0 0;">Gestão Inteligente para MEI</p>
        </div>

        <h2 style="color: #1f2937;">Lembrete de Pagamento</h2>
        <p style="color: #4b5563; line-height: 1.6;">
            Olá, <strong>{client_name}</strong>!
        </p>
        <p style="color: #4b5563; line-height: 1.6;">
            Identificamos que a fatura abaixo encontra-se em aberto.
            Por favor, regularize o pagamento o mais breve possível.
        </p>

        <div style="background: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px;
                    padding: 16px; margin: 20px 0;">
            <p style="color: #92400e; margin: 0;">
                <strong>Valor:</strong> R$ {amount:,.2f}{ref}<br>
                <strong>Vencimento:</strong> {due_date}
            </p>
        </div>

        <p style="color: #4b5563; line-height: 1.6;">
            Caso o pagamento já tenha sido efetuado, por favor desconsidere este lembrete.
            Em caso de dúvidas, entre em contato conosco.
        </p>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{FRONTEND_URL}/dashboard"
               style="background-color: #10b981; color: white; padding: 14px 32px;
                      text-decoration: none; border-radius: 8px; font-weight: bold;
                      display: inline-block;">
                Acessar NEXUS
            </a>
        </div>

        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        <p style="color: #9ca3af; font-size: 12px; text-align: center;">
            NEXUS — Gestão inteligente para MEI &bull;
            <a href="{FRONTEND_URL}/privacidade" style="color: #10b981;">Política de Privacidade</a>
        </p>
    </div>
    """
    subject = f"NEXUS — Lembrete: Fatura em aberto (R$ {amount:,.2f})"
    return send_email(client_email, subject, html)


def send_das_reminder(
    user_email: str,
    user_name: str,
    due_date: str,
    estimated_amount: Optional[float] = None,
) -> dict:
    """Envia lembrete de vencimento do DAS (Documento de Arrecadação do Simples).

    Conectado ao evento DAS_VENCENDO do hub.
    Template HTML em português com branding NEXUS.

    Args:
        user_email: Email do MEI
        user_name: Nome do empreendedor
        due_date: Data de vencimento do DAS (ex: "20/01/2025")
        estimated_amount: Valor estimado do DAS em R$ (opcional)
    """
    amount_html = ""
    if estimated_amount is not None:
        amount_html = f"""
            <p style="color: #92400e; margin: 5px 0 0 0;">
                <strong>Valor estimado:</strong> R$ {estimated_amount:,.2f}
            </p>
        """

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #10b981; margin: 0;">NEXUS</h1>
            <p style="color: #6b7280; margin: 5px 0 0 0;">Gestão Inteligente para MEI</p>
        </div>

        <h2 style="color: #1f2937;">⚠️ DAS próximo do vencimento</h2>
        <p style="color: #4b5563; line-height: 1.6;">
            Olá, <strong>{user_name}</strong>!
        </p>
        <p style="color: #4b5563; line-height: 1.6;">
            Seu <strong>DAS (Documento de Arrecadação do Simples Nacional)</strong>
            está próximo do vencimento. Evite multas e juros pagando dentro do prazo.
        </p>

        <div style="background: #fef2f2; border-left: 4px solid #ef4444; border-radius: 4px;
                    padding: 16px; margin: 20px 0;">
            <p style="color: #991b1b; margin: 0;">
                <strong>Vencimento:</strong> {due_date}
            </p>
            {amount_html}
        </div>

        <div style="background: #f0fdf4; border-radius: 8px; padding: 16px; margin: 20px 0;">
            <h3 style="color: #166534; margin: 0 0 10px 0;">Como pagar:</h3>
            <ol style="color: #4b5563; line-height: 1.8; padding-left: 20px;">
                <li>Acesse o <a href="https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATSPO/pgmei.app/Identificacao" style="color: #10b981;">Portal PGMEI</a></li>
                <li>Informe seu CNPJ</li>
                <li>Gere o boleto ou pague via Pix</li>
            </ol>
        </div>

        <div style="text-align: center; margin: 30px 0;">
            <a href="{FRONTEND_URL}/dashboard"
               style="background-color: #10b981; color: white; padding: 14px 32px;
                      text-decoration: none; border-radius: 8px; font-weight: bold;
                      display: inline-block;">
                Ver no NEXUS
            </a>
        </div>

        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        <p style="color: #9ca3af; font-size: 12px; text-align: center;">
            NEXUS — Gestão inteligente para MEI &bull;
            <a href="{FRONTEND_URL}/privacidade" style="color: #10b981;">Política de Privacidade</a>
        </p>
    </div>
    """
    subject = f"NEXUS — DAS vencendo em {due_date}"
    return send_email(user_email, subject, html)
