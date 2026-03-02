"""Cliente simples de envio de email via SMTP.

Usa `smtplib` para enviar mensagens. Configurável via variáveis de ambiente:
- EMAIL_SMTP_HOST
- EMAIL_SMTP_PORT
- EMAIL_SMTP_USER
- EMAIL_SMTP_PASSWORD
- SENDER_EMAIL

O envio é básico e adequado para notificações automatizadas.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Dict, Iterable, Optional

from backend.utils.logging_utils import get_logger

logger = get_logger("email_api")


class EmailAPI:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        sender: Optional[str] = None,
    ):
        self.host = host or os.getenv("EMAIL_SMTP_HOST")
        self.port = int(port or os.getenv("EMAIL_SMTP_PORT") or 0)
        self.user = user or os.getenv("EMAIL_SMTP_USER")
        self.password = password or os.getenv("EMAIL_SMTP_PASSWORD")
        self.sender = sender or os.getenv("SENDER_EMAIL")

    def send_email(
        self,
        recipients: Iterable[str],
        subject: str,
        body: str,
        attachments: Optional[Iterable[str]] = None,
    ) -> Dict[str, str]:
        if not self.host or not self.port:
            raise RuntimeError(
                "EMAIL_SMTP_HOST e EMAIL_SMTP_PORT devem estar configurados no .env"
            )
        if not self.sender:
            raise RuntimeError("SENDER_EMAIL deve estar configurado no .env")

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = ", ".join(recipients)
        msg.set_content(body)

        # attachments (caminhos de arquivo) — anexar como octet-stream
        if attachments:
            for path in attachments:
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    maintype = "application"
                    subtype = "octet-stream"
                    filename = path.split("/")[-1]
                    msg.add_attachment(
                        data, maintype=maintype, subtype=subtype, filename=filename
                    )
                except Exception:
                    logger.exception("Falha ao anexar arquivo %s", path)

        try:
            # Usa SSL se porta comum (465), caso contrário tenta STARTTLS
            if self.port == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, context=context) as server:
                    if self.user and self.password:
                        server.login(self.user, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                    server.ehlo()
                    try:
                        server.starttls(context=ssl.create_default_context())
                        server.ehlo()
                    except Exception:
                        # servidor pode não suportar STARTTLS — ignoramos
                        pass
                    if self.user and self.password:
                        server.login(self.user, self.password)
                    server.send_message(msg)

            logger.info("Email enviado para %s | assunto=%s", recipients, subject)
            return {"status": "sent"}
        except Exception as exc:
            logger.exception("Falha ao enviar email: %s", exc)
            return {"status": "failed", "error": str(exc)}


__all__ = ["EmailAPI"]
