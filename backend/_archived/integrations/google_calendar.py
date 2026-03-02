"""Integração com Google Calendar usando Service Account (opcional).

Funcionalidade mínima: criar eventos a partir de dados estruturados.
Se as dependências do Google não estiverem instaladas, a biblioteca retorna
erro instrutivo ao tentar usar o cliente real — os testes podem injetar um
`service` falso para evitar essa dependência.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

from backend.utils.logging_utils import get_logger

logger = get_logger("google_calendar")


class GoogleCalendarAPI:
    def __init__(
        self,
        service_account_file: Optional[str] = None,
        calendar_id: Optional[str] = None,
    ):
        self.service_account_file = service_account_file or os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_FILE"
        )
        self.calendar_id = calendar_id or os.getenv("GOOGLE_CALENDAR_ID")

    def _build_service(self):
        try:
            from google.oauth2 import service_account  # type: ignore
            from googleapiclient.discovery import build  # type: ignore
        except (
            Exception
        ) as exc:  # pragma: no cover - hard to trigger in tests without deps
            raise RuntimeError(
                "Dependências Google não encontradas. Instale 'google-api-python-client' e 'google-auth'."
            ) from exc

        if not self.service_account_file:
            raise RuntimeError("Variável GOOGLE_SERVICE_ACCOUNT_FILE não configurada")
        credentials = service_account.Credentials.from_service_account_file(
            self.service_account_file,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        service = build("calendar", "v3", credentials=credentials)
        return service

    def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        attendees: Optional[Iterable[str]] = None,
        description: Optional[str] = None,
        service: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Cria um evento no calendário.

        Se `service` for fornecido (usado em testes), ele será usado em vez de
        construir o cliente real.
        """
        if service is None:
            service = self._build_service()

        event_body: Dict[str, Any] = {
            "summary": title,
            "description": description or "",
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
        }
        if attendees:
            event_body["attendees"] = [{"email": a} for a in attendees]

        try:
            created = (
                service.events()
                .insert(calendarId=self.calendar_id, body=event_body)
                .execute()
            )
            logger.info("Evento criado no Google Calendar: %s", created.get("id"))
            return {"status": "success", "id": created.get("id"), "raw": created}
        except Exception as exc:
            logger.exception("Falha ao criar evento no Google Calendar: %s", exc)
            return {"status": "failed", "error": str(exc)}

    def create_event_from_sale(
        self, sale: Dict[str, Any], service: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Mapeia um registro de venda para um evento simples: 'Emitir NFS-e'.

        - Título: Emitir NFS-e — {client_name}
        - Data: agora + 10 minutos por padrão
        - Duração: 15 minutos
        - Participantes: tenta usar `client_email` se disponível
        """
        client_name = sale.get("client_name") or sale.get("cliente_nome") or "Cliente"
        title = f"Emitir NFS-e — {client_name}"
        start = datetime.now(timezone.utc) + timedelta(minutes=10)
        end = start + timedelta(minutes=15)
        attendees = []
        if sale.get("client_email"):
            attendees.append(sale.get("client_email"))
        elif sale.get("email"):
            attendees.append(sale.get("email"))

        description_parts = []
        if sale.get("id"):
            description_parts.append(f"Sale ID: {sale.get('id')}")
        if sale.get("amount") or sale.get("valor_total"):
            description_parts.append(
                f"Valor: {sale.get('amount') or sale.get('valor_total')}"
            )

        description = "\n".join(description_parts) if description_parts else None

        return self.create_event(
            title,
            start,
            end,
            attendees=attendees or None,
            description=description,
            service=service,
        )


__all__ = ["GoogleCalendarAPI"]
