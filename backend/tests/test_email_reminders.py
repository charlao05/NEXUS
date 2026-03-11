"""
NEXUS — Testes do Email Service para Lembretes (Lacuna #6)
============================================================
Testa send_invoice_reminder e send_das_reminder com mock do Resend.
"""

import os
from unittest.mock import patch, MagicMock

import pytest


class TestSendInvoiceReminder:
    """Testa envio de lembrete de fatura/cobrança por email."""

    @patch("app.api.email_service._get_resend")
    def test_invoice_reminder_sends_email(self, mock_get_resend):
        """Com RESEND_API_KEY configurada, deve enviar email com dados corretos."""
        mock_resend = MagicMock()
        mock_resend.Emails.send.return_value = {"id": "email_123"}
        mock_get_resend.return_value = mock_resend

        from app.api.email_service import send_invoice_reminder

        result = send_invoice_reminder(
            client_email="cliente@example.com",
            client_name="Maria Silva",
            amount=1500.50,
            due_date="15/01/2025",
            invoice_id=42,
        )

        assert result["status"] == "sent"
        assert result["id"] == "email_123"

        # Verificar que Resend foi chamado com params corretos
        call_args = mock_resend.Emails.send.call_args[0][0]
        assert call_args["to"] == ["cliente@example.com"]
        assert "Fatura em aberto" in call_args["subject"]
        assert "1,500.50" in call_args["subject"] or "1.500,50" in call_args["subject"] or "1500.50" in call_args["subject"]
        assert "Maria Silva" in call_args["html"]
        assert "15/01/2025" in call_args["html"]
        assert "#42" in call_args["html"]

    @patch("app.api.email_service._get_resend")
    def test_invoice_reminder_without_api_key(self, mock_get_resend):
        """Sem RESEND_API_KEY, retorna status 'skipped' sem erros."""
        mock_get_resend.return_value = None

        from app.api.email_service import send_invoice_reminder

        result = send_invoice_reminder(
            client_email="test@test.com",
            client_name="Teste",
            amount=100.0,
            due_date="01/01/2025",
        )

        assert result["status"] == "skipped"


class TestSendDasReminder:
    """Testa envio de lembrete de vencimento DAS."""

    @patch("app.api.email_service._get_resend")
    def test_das_reminder_sends_email(self, mock_get_resend):
        """Com RESEND_API_KEY, deve enviar email DAS com dados corretos."""
        mock_resend = MagicMock()
        mock_resend.Emails.send.return_value = {"id": "email_das_456"}
        mock_get_resend.return_value = mock_resend

        from app.api.email_service import send_das_reminder

        result = send_das_reminder(
            user_email="mei@example.com",
            user_name="João Empreendedor",
            due_date="20/01/2025",
            estimated_amount=75.90,
        )

        assert result["status"] == "sent"
        assert result["id"] == "email_das_456"

        call_args = mock_resend.Emails.send.call_args[0][0]
        assert call_args["to"] == ["mei@example.com"]
        assert "DAS" in call_args["subject"]
        assert "20/01/2025" in call_args["subject"]
        assert "João Empreendedor" in call_args["html"]
        assert "DAS" in call_args["html"]
        # Valor estimado deve estar no HTML
        assert "75.90" in call_args["html"] or "75,90" in call_args["html"]

    @patch("app.api.email_service._get_resend")
    def test_das_reminder_without_amount(self, mock_get_resend):
        """DAS sem valor estimado deve enviar normalmente, sem seção de valor."""
        mock_resend = MagicMock()
        mock_resend.Emails.send.return_value = {"id": "email_das_789"}
        mock_get_resend.return_value = mock_resend

        from app.api.email_service import send_das_reminder

        result = send_das_reminder(
            user_email="mei@test.com",
            user_name="Ana",
            due_date="20/02/2025",
            estimated_amount=None,
        )

        assert result["status"] == "sent"
        call_args = mock_resend.Emails.send.call_args[0][0]
        # Não deve conter "Valor estimado" quando amount é None
        assert "Valor estimado" not in call_args["html"]

    @patch("app.api.email_service._get_resend")
    def test_das_reminder_without_api_key(self, mock_get_resend):
        """Sem RESEND_API_KEY, retorna status 'skipped'."""
        mock_get_resend.return_value = None

        from app.api.email_service import send_das_reminder

        result = send_das_reminder(
            user_email="test@test.com",
            user_name="Teste",
            due_date="20/01/2025",
        )

        assert result["status"] == "skipped"
