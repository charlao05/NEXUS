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
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


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
