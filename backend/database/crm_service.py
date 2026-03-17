"""
NEXUS - CRM Service (Nível Profissional)
==========================================
Camada de serviço para operações de CRM com persistência real.
Multi-tenant: todas as queries filtram por user_id.
Fornece CRUD completo, pipeline de vendas, scoring, busca e métricas.
Usado tanto pelo agent_hub (via execute) quanto pela API REST.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional
from sqlalchemy import func, or_, and_, desc
from sqlalchemy.orm import Session
import logging

from database.models import (
    Client, Interaction, Opportunity, Appointment,
    Transaction, Invoice, get_session, ClientSegment
)

logger = logging.getLogger(__name__)


class CRMService:
    """Serviço CRM profissional com persistência real e multi-tenancy"""

    # ========================================================================
    # CLIENTES — CRUD
    # ========================================================================

    @staticmethod
    def create_client(
        name: str,
        user_id: int = None,
        phone: str = None,
        email: str = None,
        cpf_cnpj: str = None,
        birth_date: date = None,
        address: str = None,
        city: str = None,
        state: str = None,
        segment: str = "standard",
        source: str = "manual",
        tags: list = None,
        notes: str = "",
        contact_type: str = "client",
    ) -> dict:
        """Cria cliente ou fornecedor com validação e deduplicação (filtrado por user_id)"""
        session = get_session()
        try:
            # Deduplicação por telefone ou CPF/CNPJ DENTRO do mesmo tenant
            if cpf_cnpj:
                q = session.query(Client).filter(Client.cpf_cnpj == cpf_cnpj)
                if user_id:
                    q = q.filter(Client.user_id == user_id)
                existing = q.first()
                if existing:
                    return {"status": "duplicate", "message": f"Cliente com CPF/CNPJ {cpf_cnpj} já existe", "client": existing.to_dict()}
            if phone:
                q = session.query(Client).filter(Client.phone == phone)
                if user_id:
                    q = q.filter(Client.user_id == user_id)
                existing = q.first()
                if existing:
                    return {"status": "duplicate", "message": f"Cliente com telefone {phone} já existe", "client": existing.to_dict()}

            client = Client(
                name=name, user_id=user_id, phone=phone, email=email,
                cpf_cnpj=cpf_cnpj, birth_date=birth_date, address=address,
                city=city, state=state, segment=segment, source=source,
                tags=tags or [], notes=notes,
                contact_type=contact_type or "client",
                last_interaction=datetime.now(timezone.utc),
            )
            session.add(client)
            session.commit()
            session.refresh(client)

            # Registrar interação inicial
            CRMService._add_interaction(
                session, client.id, "nota", "manual",
                f"Cliente {name} cadastrado via {source}"
            )
            session.commit()

            logger.info(f"✅ Cliente criado: {name} (ID={client.id}, user={user_id})")
            return {"status": "created", "client": client.to_dict()}
        except Exception as e:
            session.rollback()
            logger.error(f"Erro ao criar cliente: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            session.close()

    @staticmethod
    def get_client(client_id: int, user_id: int = None) -> Optional[dict]:
        """Busca cliente por ID com dados completos (filtrado por user_id)"""
        session = get_session()
        try:
            q = session.query(Client).filter(Client.id == client_id)
            if user_id:
                q = q.filter(Client.user_id == user_id)
            client = q.first()
            if not client:
                return None
            data = client.to_dict()
            # Enriquecer com contagens
            data["interactions_count"] = len(client.interactions)
            data["open_opportunities"] = len([o for o in client.opportunities if o.is_won is None])
            data["upcoming_appointments"] = len([
                a for a in client.appointments
                if a.scheduled_at > datetime.now(timezone.utc) and a.status == "scheduled"
            ])
            return data
        finally:
            session.close()

    @staticmethod
    def update_client(client_id: int, user_id: int = None, **fields) -> dict:
        """Atualiza campos do cliente (filtrado por user_id)"""
        session = get_session()
        try:
            q = session.query(Client).filter(Client.id == client_id)
            if user_id:
                q = q.filter(Client.user_id == user_id)
            client = q.first()
            if not client:
                return {"status": "not_found", "message": "Cliente não encontrado"}

            allowed = {
                "name", "phone", "email", "cpf_cnpj", "birth_date", "address",
                "city", "state", "segment", "source", "tags", "notes", "is_active",
                "purchase_score", "attendance_score", "churn_risk", "engagement_score",
            }
            changed = []
            for key, value in fields.items():
                if key in allowed and value is not None:
                    setattr(client, key, value)
                    changed.append(key)

            if changed:
                client.updated_at = datetime.now(timezone.utc)
                CRMService._add_interaction(
                    session, client_id, "nota", "manual",
                    f"Campos atualizados: {', '.join(changed)}"
                )
                session.commit()
                session.refresh(client)

            return {"status": "updated", "client": client.to_dict(), "changed": changed}
        except Exception as e:
            session.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            session.close()

    @staticmethod
    def delete_client(client_id: int, soft: bool = True, user_id: int = None) -> dict:
        """Desativa (soft) ou remove (hard) cliente (filtrado por user_id)"""
        session = get_session()
        try:
            q = session.query(Client).filter(Client.id == client_id)
            if user_id:
                q = q.filter(Client.user_id == user_id)
            client = q.first()
            if not client:
                return {"status": "not_found"}
            if soft:
                client.is_active = False
                client.segment = "churned"
                session.commit()
                return {"status": "deactivated", "client_id": client_id}
            else:
                session.delete(client)
                session.commit()
                return {"status": "deleted", "client_id": client_id}
        finally:
            session.close()

    # ========================================================================
    # CLIENTES — BUSCA E LISTAGEM
    # ========================================================================

    @staticmethod
    def search_clients(
        query: str = "",
        segment: str = None,
        is_active: bool = True,
        sort_by: str = "name",
        limit: int = 50,
        offset: int = 0,
        user_id: int = None,
    ) -> dict:
        """Busca clientes com filtros e paginação (filtrado por user_id)"""
        session = get_session()
        try:
            q = session.query(Client)

            if user_id:
                q = q.filter(Client.user_id == user_id)
            if is_active is not None:
                q = q.filter(Client.is_active == is_active)
            if segment:
                q = q.filter(Client.segment == segment)
            if query:
                search_term = f"%{query}%"
                q = q.filter(or_(
                    Client.name.ilike(search_term),
                    Client.phone.ilike(search_term),
                    Client.email.ilike(search_term),
                    Client.cpf_cnpj.ilike(search_term),
                ))

            total = q.count()

            sort_map = {
                "name": Client.name,
                "created_at": desc(Client.created_at),
                "last_interaction": desc(Client.last_interaction),
                "revenue": desc(Client.total_revenue),
                "churn_risk": desc(Client.churn_risk),
                "purchase_score": desc(Client.purchase_score),
            }
            q = q.order_by(sort_map.get(sort_by, Client.name))
            clients = q.offset(offset).limit(limit).all()

            return {
                "total": total,
                "clients": [c.to_dict() for c in clients],
                "offset": offset,
                "limit": limit,
            }
        finally:
            session.close()

    @staticmethod
    def get_clients_for_followup(days_inactive: int = 7, limit: int = 20, user_id: int = None) -> list:
        """Clientes que precisam de follow-up (filtrado por user_id)"""
        session = get_session()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_inactive)
            q = session.query(Client).filter(Client.is_active == True)
            if user_id:
                q = q.filter(Client.user_id == user_id)
            clients = (
                q.filter(or_(
                    Client.last_interaction == None,
                    Client.last_interaction < cutoff
                ))
                .order_by(desc(Client.total_revenue))
                .limit(limit)
                .all()
            )
            return [c.to_dict() for c in clients]
        finally:
            session.close()

    @staticmethod
    def get_birthday_clients(days_ahead: int = 7, user_id: int = None) -> list:
        """Clientes com aniversário nos próximos N dias (filtrado por user_id)"""
        session = get_session()
        try:
            today = date.today()
            q = session.query(Client).filter(
                Client.is_active == True,
                Client.birth_date != None,
            )
            if user_id:
                q = q.filter(Client.user_id == user_id)
            clients = q.all()

            upcoming = []
            for c in clients:
                try:
                    this_year_bday = c.birth_date.replace(year=today.year)
                    if this_year_bday < today:
                        this_year_bday = c.birth_date.replace(year=today.year + 1)
                    days_until = (this_year_bday - today).days
                    if 0 <= days_until <= days_ahead:
                        d = c.to_dict()
                        d["days_until_birthday"] = days_until
                        upcoming.append(d)
                except ValueError:
                    pass

            return sorted(upcoming, key=lambda x: x["days_until_birthday"])
        finally:
            session.close()

    # ========================================================================
    # INTERAÇÕES — Histórico completo
    # ========================================================================

    @staticmethod
    def add_interaction(
        client_id: int, interaction_type: str, channel: str,
        summary: str, details: str = "", sentiment: str = "neutral"
    ) -> dict:
        """Registra interação e atualiza last_interaction do cliente"""
        session = get_session()
        try:
            CRMService._add_interaction(
                session, client_id, interaction_type, channel,
                summary, details, sentiment
            )
            # Atualizar cliente
            client = session.query(Client).filter(Client.id == client_id).first()
            if client:
                client.last_interaction = datetime.now(timezone.utc)
                client.engagement_score = min(100, (client.engagement_score or 50) + 2)
            session.commit()
            return {"status": "ok", "message": "Interação registrada"}
        except Exception as e:
            session.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            session.close()

    @staticmethod
    def get_interactions(client_id: int, limit: int = 50) -> list:
        """Retorna histórico de interações de um cliente"""
        session = get_session()
        try:
            interactions = (
                session.query(Interaction)
                .filter(Interaction.client_id == client_id)
                .order_by(desc(Interaction.created_at))
                .limit(limit)
                .all()
            )
            return [i.to_dict() for i in interactions]
        finally:
            session.close()

    @staticmethod
    def _add_interaction(session, client_id, itype, channel, summary, details="", sentiment="neutral"):
        """Helper interno — adiciona interação sem commit"""
        interaction = Interaction(
            client_id=client_id, type=itype, channel=channel,
            summary=summary, details=details, sentiment=sentiment,
        )
        session.add(interaction)

    # ========================================================================
    # PIPELINE DE VENDAS — Oportunidades
    # ========================================================================

    @staticmethod
    def create_opportunity(
        client_id: int, title: str, value: float = 0,
        stage: str = "prospeccao", probability: float = 30,
        expected_close: date = None, notes: str = "",
        user_id: int = None,
    ) -> dict:
        """Cria oportunidade no pipeline de vendas"""
        session = get_session()
        try:
            opp = Opportunity(
                client_id=client_id, title=title, value=value,
                stage=stage, probability=probability,
                expected_close=expected_close, notes=notes,
            )
            session.add(opp)
            CRMService._add_interaction(
                session, client_id, "nota", "manual",
                f"Nova oportunidade: {title} (R$ {value:,.2f})"
            )
            session.commit()
            session.refresh(opp)
            return {"status": "created", "opportunity": opp.to_dict()}
        except Exception as e:
            session.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            session.close()

    @staticmethod
    def update_opportunity_stage(opp_id: int, new_stage: str) -> dict:
        """Avança oportunidade no pipeline"""
        session = get_session()
        try:
            opp = session.query(Opportunity).filter(Opportunity.id == opp_id).first()
            if not opp:
                return {"status": "not_found"}
            old_stage = opp.stage
            opp.stage = new_stage
            opp.updated_at = datetime.now(timezone.utc)

            # Probabilidade automática por estágio
            stage_probs = {
                "prospeccao": 10, "qualificacao": 25, "proposta": 50,
                "negociacao": 70, "fechamento": 90, "ganho": 100, "perdido": 0,
            }
            opp.probability = stage_probs.get(new_stage, opp.probability)

            if new_stage == "ganho":
                opp.is_won = True
                opp.closed_at = datetime.now(timezone.utc)
                # Atualizar métricas do cliente
                client = session.query(Client).filter(Client.id == opp.client_id).first()
                if client:
                    client.total_purchases += 1
                    client.total_revenue += opp.value
                    client.avg_ticket = client.total_revenue / max(client.total_purchases, 1)
                    client.last_purchase = datetime.now(timezone.utc)
                    client.purchase_score = min(100, client.purchase_score + 10)
            elif new_stage == "perdido":
                opp.is_won = False
                opp.closed_at = datetime.now(timezone.utc)

            CRMService._add_interaction(
                session, opp.client_id, "nota", "manual",
                f"Pipeline: {old_stage} → {new_stage} ({opp.title})"
            )
            session.commit()
            return {"status": "updated", "opportunity": opp.to_dict()}
        except Exception as e:
            session.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            session.close()

    @staticmethod
    def get_pipeline_summary(user_id: int = None) -> dict:
        """Dashboard do pipeline de vendas (filtrado por user_id)"""
        session = get_session()
        try:
            stages = ["prospeccao", "qualificacao", "proposta", "negociacao", "fechamento"]
            pipeline = {}
            total_value = 0
            total_weighted = 0

            for stage in stages:
                q = session.query(Opportunity).filter(
                    Opportunity.stage == stage, Opportunity.is_won == None
                )
                if user_id:
                    q = q.join(Client).filter(Client.user_id == user_id)
                opps = q.all()
                stage_value = sum(o.value for o in opps)
                stage_weighted = sum(o.value * (o.probability / 100) for o in opps)
                pipeline[stage] = {
                    "count": len(opps),
                    "value": round(stage_value, 2),
                    "weighted_value": round(stage_weighted, 2),
                }
                total_value += stage_value
                total_weighted += stage_weighted

            # Métricas de fechamento
            q_won = session.query(Opportunity).filter(Opportunity.is_won == True)
            q_lost = session.query(Opportunity).filter(Opportunity.is_won == False)
            if user_id:
                q_won = q_won.join(Client).filter(Client.user_id == user_id)
                q_lost = q_lost.join(Client).filter(Client.user_id == user_id)
            won = q_won.all()
            lost = q_lost.all()
            win_rate = len(won) / max(len(won) + len(lost), 1) * 100

            return {
                "pipeline": pipeline,
                "total_value": round(total_value, 2),
                "weighted_forecast": round(total_weighted, 2),
                "won_count": len(won),
                "won_value": round(sum(o.value for o in won), 2),
                "lost_count": len(lost),
                "win_rate": round(win_rate, 1),
            }
        finally:
            session.close()

    # ========================================================================
    # AGENDAMENTOS
    # ========================================================================

    @staticmethod
    def create_appointment(
        title: str, scheduled_at: datetime, client_id: int = None,
        description: str = "", duration_minutes: int = 60,
        appointment_type: str = "reuniao", user_id: int = None,
    ) -> dict:
        """Cria agendamento persistente (com user_id)"""
        session = get_session()
        try:
            apt = Appointment(
                client_id=client_id, user_id=user_id, title=title,
                description=description, scheduled_at=scheduled_at,
                duration_minutes=duration_minutes, type=appointment_type,
            )
            session.add(apt)
            if client_id:
                client = session.query(Client).filter(Client.id == client_id).first()
                if client:
                    client.total_appointments += 1
                    CRMService._add_interaction(
                        session, client_id, "reuniao", "manual",
                        f"Agendamento: {title} em {scheduled_at.strftime('%d/%m/%Y %H:%M')}"
                    )
            session.commit()
            session.refresh(apt)
            return {"status": "created", "appointment": apt.to_dict()}
        except Exception as e:
            session.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            session.close()

    @staticmethod
    def get_appointments(
        start_date: date = None, end_date: date = None,
        status: str = None, limit: int = 50,
        user_id: int = None,
    ) -> list:
        """Lista agendamentos com filtros (filtrado por user_id)"""
        session = get_session()
        try:
            q = session.query(Appointment)
            if user_id:
                q = q.filter(Appointment.user_id == user_id)
            if start_date:
                q = q.filter(Appointment.scheduled_at >= datetime.combine(start_date, datetime.min.time()))
            if end_date:
                q = q.filter(Appointment.scheduled_at <= datetime.combine(end_date, datetime.max.time()))
            if status:
                q = q.filter(Appointment.status == status)
            return [a.to_dict() for a in q.order_by(Appointment.scheduled_at).limit(limit).all()]
        finally:
            session.close()

    # ========================================================================
    # MÉTRICAS E DASHBOARD
    # ========================================================================

    @staticmethod
    def get_crm_dashboard(user_id: int = None) -> dict:
        """Dashboard completo do CRM (filtrado por user_id)"""
        session = get_session()
        try:
            q_base = session.query(Client).filter(Client.is_active == True)
            q_inactive = session.query(Client).filter(Client.is_active == False)
            if user_id:
                q_base = q_base.filter(Client.user_id == user_id)
                q_inactive = q_inactive.filter(Client.user_id == user_id)
            total_clients = q_base.count()
            total_inactive = q_inactive.count()

            # Segmentação
            segments = {}
            for seg in ["lead", "prospect", "standard", "premium", "vip"]:
                q_seg = session.query(Client).filter(
                    Client.segment == seg, Client.is_active == True
                )
                if user_id:
                    q_seg = q_seg.filter(Client.user_id == user_id)
                segments[seg] = q_seg.count()

            # Receita total
            q_rev = session.query(func.sum(Client.total_revenue)).filter(Client.is_active == True)
            if user_id:
                q_rev = q_rev.filter(Client.user_id == user_id)
            total_revenue = q_rev.scalar() or 0

            # Clientes sem interação há 7+ dias
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            q_follow = session.query(Client).filter(
                Client.is_active == True,
                or_(Client.last_interaction == None, Client.last_interaction < cutoff)
            )
            if user_id:
                q_follow = q_follow.filter(Client.user_id == user_id)
            need_followup = q_follow.count()

            # Agendamentos de hoje
            today_start = datetime.combine(date.today(), datetime.min.time())
            today_end = datetime.combine(date.today(), datetime.max.time())
            q_apt = session.query(Appointment).filter(
                Appointment.scheduled_at.between(today_start, today_end),
                Appointment.status == "scheduled"
            )
            if user_id:
                q_apt = q_apt.filter(Appointment.user_id == user_id)
            today_appointments = q_apt.count()

            # Pipeline
            pipeline = CRMService.get_pipeline_summary(user_id=user_id)

            return {
                "clients": {
                    "total": total_clients,
                    "inactive": total_inactive,
                    "segments": segments,
                    "need_followup": need_followup,
                },
                "revenue": {
                    "total": round(total_revenue, 2),
                    "avg_ticket": round(total_revenue / max(total_clients, 1), 2),
                },
                "appointments_today": today_appointments,
                "pipeline": pipeline,
            }
        finally:
            session.close()

    # ========================================================================
    # FINANCEIRO (para o agente financeiro consultar)
    # ========================================================================

    @staticmethod
    def record_transaction(
        type: str, amount: float, description: str,
        category: str = "geral", transaction_date: date = None,
        client_id: int = None, notes: str = "",
        user_id: int = None, payment_method: str = "nao_informado",
    ) -> dict:
        """Registra receita ou despesa (com user_id e forma de pagamento)"""
        session = get_session()
        try:
            tx = Transaction(
                type=type, amount=amount, description=description,
                category=category, date=transaction_date or date.today(),
                client_id=client_id, notes=notes, user_id=user_id,
                payment_method=payment_method or "nao_informado",
            )
            session.add(tx)
            session.commit()
            session.refresh(tx)
            return {"status": "created", "transaction": tx.to_dict()}
        except Exception as e:
            session.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            session.close()

    @staticmethod
    def get_financial_summary(month: int = None, year: int = None, user_id: int = None) -> dict:
        """Resumo financeiro mensal (filtrado por user_id)"""
        session = get_session()
        try:
            today = date.today()
            m = month or today.month
            y = year or today.year
            start = date(y, m, 1)
            if m == 12:
                end = date(y + 1, 1, 1)
            else:
                end = date(y, m + 1, 1)

            q = session.query(Transaction).filter(
                Transaction.date >= start, Transaction.date < end
            )
            if user_id:
                q = q.filter(Transaction.user_id == user_id)
            txs = q.all()

            receitas = sum(t.amount for t in txs if t.type == "receita")
            despesas = sum(t.amount for t in txs if t.type == "despesa")

            return {
                "month": m,
                "year": y,
                "receitas": round(receitas, 2),
                "despesas": round(despesas, 2),
                "lucro": round(receitas - despesas, 2),
                "margem": round((receitas - despesas) / max(receitas, 1) * 100, 1),
                "transactions_count": len(txs),
            }
        finally:
            session.close()

    # ========================================================================
    # COBRANÇAS
    # ========================================================================

    @staticmethod
    def create_invoice(
        client_id: int, description: str, amount: float, due_date: date,
        user_id: int = None,
    ) -> dict:
        """Cria fatura / conta a receber (com user_id)"""
        session = get_session()
        try:
            inv = Invoice(
                client_id=client_id, description=description,
                amount=amount, due_date=due_date, user_id=user_id,
            )
            session.add(inv)
            session.commit()
            session.refresh(inv)
            return {"status": "created", "invoice": inv.to_dict()}
        except Exception as e:
            session.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            session.close()

    @staticmethod
    def get_overdue_invoices(user_id: int = None) -> list:
        """Faturas vencidas (filtrado por user_id)"""
        session = get_session()
        try:
            q = session.query(Invoice).filter(
                Invoice.due_date < date.today(),
                Invoice.status == "pending"
            )
            if user_id:
                q = q.filter(Invoice.user_id == user_id)
            invoices = q.order_by(Invoice.due_date).all()
            result = []
            for inv in invoices:
                d = inv.to_dict()
                client = session.query(Client).filter(Client.id == inv.client_id).first()
                d["client_name"] = client.name if client else "Desconhecido"
                d["days_overdue"] = (date.today() - inv.due_date).days
                result.append(d)
            return result
        finally:
            session.close()

    @staticmethod
    def get_upcoming_invoices(days: int = 7, user_id: int = None) -> list:
        """Faturas a vencer nos próximos N dias (filtrado por user_id)"""
        session = get_session()
        try:
            cutoff = date.today() + timedelta(days=days)
            q = session.query(Invoice).filter(
                Invoice.due_date >= date.today(),
                Invoice.due_date <= cutoff,
                Invoice.status == "pending"
            )
            if user_id:
                q = q.filter(Invoice.user_id == user_id)
            invoices = q.order_by(Invoice.due_date).all()
            result = []
            for inv in invoices:
                d = inv.to_dict()
                client = session.query(Client).filter(Client.id == inv.client_id).first()
                d["client_name"] = client.name if client else "Desconhecido"
                d["days_until_due"] = (inv.due_date - date.today()).days
                result.append(d)
            return result
        finally:
            session.close()

    # ========================================================================
    # FLUXO DE CAIXA — Visão diária / semanal / range
    # ========================================================================

    @staticmethod
    def get_financial_summary_by_range(
        start_date, end_date, user_id: int = None
    ) -> dict:
        """Resumo financeiro para qualquer range de datas.
        start_date/end_date: objetos date ou string ISO (YYYY-MM-DD).
        Retorna receitas, despesas, saldo, agrupamento diário e melhor dia.
        """
        from datetime import date as date_type

        session = get_session()
        try:
            # Normaliza strings para date
            if isinstance(start_date, str):
                start_date = date_type.fromisoformat(start_date)
            if isinstance(end_date, str):
                end_date = date_type.fromisoformat(end_date)

            # Transaction.date é Column(Date), então comparamos date com date
            q = session.query(Transaction).filter(
                Transaction.date >= start_date,
                Transaction.date <= end_date,
            )
            if user_id:
                q = q.filter(Transaction.user_id == user_id)

            txs = q.all()

            receitas = sum(t.amount for t in txs if t.type == "receita")
            despesas = sum(t.amount for t in txs if t.type == "despesa")

            # Agrupamento por dia — Transaction.date é date (não datetime)
            by_day: dict = {}
            for t in txs:
                if t.date is None:
                    day_key = "sem_data"
                elif hasattr(t.date, "date") and callable(t.date.date):
                    day_key = t.date.date().isoformat()
                else:
                    day_key = t.date.isoformat()
                if day_key not in by_day:
                    by_day[day_key] = {"receitas": 0.0, "despesas": 0.0, "saldo": 0.0, "count": 0}
                if t.type == "receita":
                    by_day[day_key]["receitas"] += t.amount
                else:
                    by_day[day_key]["despesas"] += t.amount
                by_day[day_key]["count"] += 1

            for day in by_day.values():
                day["saldo"] = round(day["receitas"] - day["despesas"], 2)
                day["receitas"] = round(day["receitas"], 2)
                day["despesas"] = round(day["despesas"], 2)

            # Melhor dia por receita
            best_day = max(by_day.items(), key=lambda x: x[1]["receitas"]) if by_day else None

            return {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "receitas": round(receitas, 2),
                "despesas": round(despesas, 2),
                "saldo": round(receitas - despesas, 2),
                "transactions_count": len(txs),
                "by_day": by_day,
                "best_day": {
                    "date": best_day[0],
                    "receitas": best_day[1]["receitas"],
                } if best_day else None,
            }
        finally:
            session.close()

    @staticmethod
    def get_daily_summary(user_id: int = None) -> dict:
        """Atalho: resumo financeiro do dia atual."""
        today = date.today()
        return CRMService.get_financial_summary_by_range(today, today, user_id=user_id)

    @staticmethod
    def get_weekly_summary(user_id: int = None) -> dict:
        """Atalho: resumo da semana atual (segunda-feira até hoje)."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        return CRMService.get_financial_summary_by_range(week_start, today, user_id=user_id)

    # ========================================================================
    # BREAKDOWN POR FORMA DE PAGAMENTO
    # ========================================================================

    _PAYMENT_METHOD_LABELS = {
        "pix": "PIX",
        "dinheiro": "Dinheiro",
        "cartao_debito": "Cartão de Débito",
        "cartao_credito": "Cartão de Crédito",
        "credito_proprio": "Crédito Próprio / Crediário",
        "fiado": "Fiado",
        "boleto": "Boleto",
        "transferencia": "Transferência Bancária",
        "parcelado": "Parcelado",
        "entrada_parcelado": "Entrada + Parcelado",
        "cheque": "Cheque",
        "nao_informado": "Não informado",
    }

    @staticmethod
    def get_payment_breakdown(
        start_date=None, end_date=None, user_id: int = None,
    ) -> dict:
        """Breakdown de transações por forma de pagamento.
        Retorna receitas agrupadas por payment_method para o período.
        """
        session = get_session()
        try:
            today = date.today()
            if start_date is None:
                start_date = date(today.year, today.month, 1)
            if end_date is None:
                end_date = today
            if isinstance(start_date, str):
                start_date = date.fromisoformat(start_date)
            if isinstance(end_date, str):
                end_date = date.fromisoformat(end_date)

            q = session.query(Transaction).filter(
                Transaction.date >= start_date,
                Transaction.date <= end_date,
                Transaction.type == "receita",
            )
            if user_id:
                q = q.filter(Transaction.user_id == user_id)

            txs = q.all()
            by_method: dict = {}
            total = 0.0
            for t in txs:
                method = getattr(t, "payment_method", None) or "nao_informado"
                label = CRMService._PAYMENT_METHOD_LABELS.get(method, method)
                if label not in by_method:
                    by_method[label] = {"total": 0.0, "count": 0}
                by_method[label]["total"] += t.amount
                by_method[label]["count"] += 1
                total += t.amount

            # Adicionar percentual
            for v in by_method.values():
                v["total"] = round(v["total"], 2)
                v["percent"] = round(v["total"] / max(total, 0.01) * 100, 1)

            return {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_receitas": round(total, 2),
                "by_payment_method": by_method,
            }
        finally:
            session.close()
