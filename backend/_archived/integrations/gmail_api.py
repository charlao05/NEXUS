"""Cliente para envio de mensagens via Gmail API.

Suporta três métodos de autenticação:
1. Service Account + Domain-Wide Delegation (`GMAIL_SERVICE_ACCOUNT_FILE` + `GMAIL_DELEGATED_USER`)
2. Arquivo OAuth Credentials (`GMAIL_CREDENTIALS_FILE`)
3. Access Token Bearer (melhor para Cloud Shell: `GMAIL_ACCESS_TOKEN`)

Nos casos em que as bibliotecas Google não estejam instaladas, o módulo
levanta um RuntimeError com instruções.
"""

from __future__ import annotations

import base64
import os
from email.message import EmailMessage
from typing import Any, Dict, Iterable, Optional

from backend.utils.logging_utils import get_logger

logger = get_logger("gmail_api")


class GmailAPI:
    def __init__(
        self,
        service_account_file: Optional[str] = None,
        delegated_user: Optional[str] = None,
        credentials_file: Optional[str] = None,
        access_token: Optional[str] = None,
    ):
        self.service_account_file = service_account_file or os.getenv(
            "GMAIL_SERVICE_ACCOUNT_FILE"
        )
        self.delegated_user = delegated_user or os.getenv("GMAIL_DELEGATED_USER")
        self.credentials_file = credentials_file or os.getenv("GMAIL_CREDENTIALS_FILE")
        self.access_token = access_token or os.getenv("GMAIL_ACCESS_TOKEN")

    def _build_service(self):
        try:
            from google.oauth2 import service_account  # type: ignore
            from googleapiclient.discovery import build  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "Dependências Google não encontradas. Instale 'google-api-python-client' e 'google-auth'."
            ) from exc

        # Prioridade 1: Service account + delegated user (domain-wide delegation)
        if self.service_account_file and self.delegated_user:
            creds = service_account.Credentials.from_service_account_file(
                self.service_account_file,
                scopes=["https://www.googleapis.com/auth/gmail.send"],
            )
            creds = creds.with_subject(self.delegated_user)
            service = build("gmail", "v1", credentials=creds)
            logger.info("Gmail service built with Service Account + Delegation")
            return service

        # Prioridade 1b: Service account (simples, sem delegação)
        if self.service_account_file:
            creds = service_account.Credentials.from_service_account_file(
                self.service_account_file,
                scopes=["https://www.googleapis.com/auth/gmail.send"],
            )
            service = build("gmail", "v1", credentials=creds)
            logger.info("Gmail service built with Service Account (no delegation)")
            return service

        # Prioridade 2: OAuth credentials file
        if self.credentials_file:
            from google.oauth2.credentials import Credentials  # type: ignore

            creds = Credentials.from_authorized_user_file(
                self.credentials_file,
                scopes=["https://www.googleapis.com/auth/gmail.send"],
            )
            service = build("gmail", "v1", credentials=creds)
            logger.info("Gmail service built with OAuth credentials file")
            return service

        # Prioridade 3: Access token Bearer (Cloud Shell / gcloud)
        if self.access_token:
            from google.oauth2.credentials import Credentials  # type: ignore

            creds = Credentials(token=self.access_token)
            service = build("gmail", "v1", credentials=creds)
            logger.info("Gmail service built with Bearer access token")
            return service

        raise RuntimeError(
            "Nenhuma configuração de credenciais do Gmail encontrada. "
            "Configure um destes:\n"
            "1. GMAIL_SERVICE_ACCOUNT_FILE (com ou sem GMAIL_DELEGATED_USER)\n"
            "2. GMAIL_CREDENTIALS_FILE\n"
            "3. GMAIL_ACCESS_TOKEN (para Cloud Shell)"
        )

    def _prepare_raw_message(
        self, sender: str, to: Iterable[str], subject: str, body: str
    ) -> str:
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        return raw

    def send_message(
        self,
        recipients: Iterable[str],
        subject: str,
        body: str,
        sender: Optional[str] = None,
        service: Optional[Any] = None,
    ) -> Dict[str, Any]:
        sender = sender or os.getenv("SENDER_EMAIL")
        if not sender:
            raise RuntimeError("SENDER_EMAIL não configurado para envio via Gmail")

        if service is None:
            try:
                service = self._build_service()
            except RuntimeError as exc:
                # Fallback: tentar SMTP via EmailAPI (App Password ou SMTP config)
                logger.warning("Gmail API não disponível: %s. Tentando fallback SMTP.", exc)
                try:
                    from backend.integrations.email_api import EmailAPI

                    # mapear GMAIL_APP_PASSWORD para EMAIL_SMTP_PASSWORD se presente
                    gmail_app_pwd = os.getenv("GMAIL_APP_PASSWORD")
                    smtp_host = os.getenv("EMAIL_SMTP_HOST")
                    smtp_port = os.getenv("EMAIL_SMTP_PORT")
                    smtp_user = os.getenv("EMAIL_SMTP_USER") or os.getenv("SENDER_EMAIL")
                    smtp_password = os.getenv("EMAIL_SMTP_PASSWORD") or gmail_app_pwd

                    email_client = EmailAPI(
                        host=smtp_host,
                        port=int(smtp_port) if smtp_port else None,
                        user=smtp_user,
                        password=smtp_password,
                        sender=sender,
                    )
                    res = email_client.send_email(recipients, subject, body)
                    return {"status": "sent-via-smtp", "detail": res}
                except Exception:
                    logger.exception("Fallback SMTP falhou")
                    raise

        raw = self._prepare_raw_message(sender, recipients, subject, body)
        try:
            res = (
                service.users()
                .messages()
                .send(userId="me", body={"raw": raw})
                .execute()
            )
            logger.info("Gmail sent message id=%s", res.get("id"))
            return {"status": "sent", "id": res.get("id"), "raw": res}
        except Exception as exc:
            logger.exception("Falha ao enviar via Gmail API: %s", exc)
            # Se falhar via API, tentar fallback SMTP como última alternativa
            try:
                from backend.integrations.email_api import EmailAPI

                gmail_app_pwd = os.getenv("GMAIL_APP_PASSWORD")
                smtp_host = os.getenv("EMAIL_SMTP_HOST")
                smtp_port = os.getenv("EMAIL_SMTP_PORT")
                smtp_user = os.getenv("EMAIL_SMTP_USER") or os.getenv("SENDER_EMAIL")
                smtp_password = os.getenv("EMAIL_SMTP_PASSWORD") or gmail_app_pwd

                email_client = EmailAPI(
                    host=smtp_host,
                    port=int(smtp_port) if smtp_port else None,
                    user=smtp_user,
                    password=smtp_password,
                    sender=sender,
                )
                res2 = email_client.send_email(recipients, subject, body)
                return {"status": "sent-via-smtp-after-api-fail", "detail": res2}
            except Exception:
                logger.exception("Fallback SMTP também falhou")
                return {"status": "failed", "error": str(exc)}

    def send_message_from_sale(
        self, sale: Dict[str, Any], service: Optional[Any] = None
    ) -> Dict[str, Any]:
        recipient = sale.get("client_email") or sale.get("email")
        if not recipient:
            return {"status": "skipped", "reason": "no_email"}
        subject = f"Instruções para emissão da NFS-e — {sale.get('id', '')}"
        body = (
            sale.get("instructions")
            or sale.get("note")
            or "Segue instruções para emissão da nota."
        )
        return self.send_message([recipient], subject, body, service=service)


__all__ = ["GmailAPI"]
