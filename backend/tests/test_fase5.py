# pyright: reportMissingImports=false
"""
NEXUS — Testes Fase 5
======================
Agente de Contabilidade MEI unificado.
Testa: valores DAS 2026, obrigações MEI, calendário fiscal,
       checklist, desenquadramento, IRPF, penalidades,
       endpoints renomeados e compatibilidade legada.
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Setup paths ──
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(backend_dir.parent))

os.environ.setdefault("JWT_SECRET", "test-secret-fase5")
os.environ.setdefault("ENVIRONMENT", "test")

from fastapi.testclient import TestClient


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def app():
    """Cria app de teste."""
    try:
        from app.api.redis_client import reset_redis
        reset_redis()
    except ImportError:
        pass
    os.environ.pop("REDIS_URL", None)
    os.environ.pop("SENTRY_DSN", None)

    from main import app as nexus_app
    return nexus_app


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_token(client):
    """Cria user e retorna token."""
    email = f"fase5user_{int(time.time())}@nexus.com"
    signup_r = client.post("/api/auth/signup", json={
        "email": email,
        "password": "TesteFase5!@#",
        "full_name": "Teste Fase5",
    })
    assert signup_r.status_code in (200, 201), f"Signup failed: {signup_r.json()}"
    r = client.post("/api/auth/login", json={
        "email": email,
        "password": "TesteFase5!@#",
    })
    assert r.status_code == 200, f"Login failed: {r.json()}"
    return r.json()["access_token"]


@pytest.fixture
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ============================================================================
# TESTES DO AGENTE DE CONTABILIDADE (import direto)
# ============================================================================

class TestContabilidadeAgent:
    """Testa o ContabilidadeAgent diretamente."""

    def setup_method(self):
        from agents.contabilidade_agent import ContabilidadeAgent
        self.agent = ContabilidadeAgent()

    # ── Valores DAS 2026 ────────────────────────────────────────

    def test_das_valores_2026_comercio(self):
        """DAS Comércio/Indústria = R$ 82,05"""
        result = self.agent.execute({"action": "calcular_das", "tipo_atividade": "comercio"})
        assert result["status"] == "ok"
        assert result["valor_das"] == 82.05
        assert result["composicao"]["inss_5_percent"] == 81.05
        assert result["composicao"]["icms"] == 1.00

    def test_das_valores_2026_servicos(self):
        """DAS Serviços = R$ 86,05"""
        result = self.agent.execute({"action": "calcular_das", "tipo_atividade": "servicos"})
        assert result["status"] == "ok"
        assert result["valor_das"] == 86.05
        assert result["composicao"]["iss"] == 5.00

    def test_das_valores_2026_comercio_servicos(self):
        """DAS Comércio+Serviços = R$ 87,05"""
        result = self.agent.execute({"action": "calcular_das", "tipo_atividade": "comercio_servicos"})
        assert result["status"] == "ok"
        assert result["valor_das"] == 87.05

    def test_das_caminhoneiro(self):
        """DAS MEI Caminhoneiro (INSS 12%)."""
        result = self.agent.execute({
            "action": "calcular_das",
            "caminhoneiro": True,
            "subtipo_caminhoneiro": "interestadual_intermunicipal",
        })
        assert result["status"] == "ok"
        assert result["tipo"] == "MEI Caminhoneiro"
        assert result["composicao"]["inss_12_percent"] == 194.52

    # ── DAS Status ─────────────────────────────────────────────

    def test_das_status(self):
        """DAS status retorna vencimento, valor e urgência."""
        result = self.agent.execute({"action": "das_status", "tipo_atividade": "servicos"})
        assert result["status"] == "ok"
        das = result["das"]
        assert das["valor"] == 86.05
        assert "vencimento" in das
        assert "dias_restantes" in das
        assert "urgencia" in das
        assert len(das["como_pagar"]) >= 3

    # ── DASN-SIMEI ─────────────────────────────────────────────

    def test_dasn_status(self):
        """DASN-SIMEI status com prazo e multas."""
        result = self.agent.execute({"action": "dasn_status", "ano": 2025})
        assert result["status"] == "ok"
        dasn = result["dasn"]
        assert dasn["ano_referencia"] == 2025
        assert "31/05" in dasn["prazo"]
        assert dasn["multa_atraso"]["minima"] == 50.00

    # ── Limite MEI / Desenquadramento ──────────────────────────

    def test_mei_status(self):
        """Status do limite MEI retorna percentual."""
        result = self.agent.execute({"action": "mei_status", "month": "2026-06"})
        assert "percentual_usado" in result
        assert result["limite_anual"] == 81000.00

    def test_desenquadramento_dentro_limite(self):
        """Receita dentro do limite = tudo ok."""
        result = self.agent.execute({"action": "check_desenquadramento", "receita_anual": 70000})
        assert "DENTRO DO LIMITE" in result["desenquadramento"]["situacao"]

    def test_desenquadramento_excesso_20(self):
        """Receita entre 81k e 97.2k = excesso até 20%."""
        result = self.agent.execute({"action": "check_desenquadramento", "receita_anual": 90000})
        assert "EXCESSO ATÉ 20%" in result["desenquadramento"]["situacao"]

    def test_desenquadramento_excesso_acima_20(self):
        """Receita acima de 97.2k = desenquadramento retroativo."""
        result = self.agent.execute({"action": "check_desenquadramento", "receita_anual": 100000})
        assert "ACIMA DE 20%" in result["desenquadramento"]["situacao"]

    # ── IRPF ───────────────────────────────────────────────────

    def test_irpf_isento_servicos(self):
        """IRPF: serviços = 32% isento."""
        result = self.agent.execute({
            "action": "calcular_irpf_isento",
            "receita_bruta_anual": 81000,
            "tipo_atividade": "servicos",
            "despesas_comprovadas": 10000,
        })
        assert result["status"] == "ok"
        irpf = result["irpf"]
        assert irpf["percentual_isento"] == "32.0%"
        assert irpf["lucro_isento"] == 25920.00  # 81000 * 0.32
        assert irpf["rendimento_tributavel"] >= 0

    def test_irpf_isento_comercio(self):
        """IRPF: comércio = 8% isento."""
        result = self.agent.execute({
            "action": "calcular_irpf_isento",
            "receita_bruta_anual": 81000,
            "tipo_atividade": "comercio",
        })
        assert result["irpf"]["percentual_isento"] == "8.0%"
        assert result["irpf"]["lucro_isento"] == 6480.00  # 81000 * 0.08

    # ── Calendário Fiscal ──────────────────────────────────────

    def test_calendario_fiscal(self):
        """Calendário fiscal retorna obrigações mensais e anuais."""
        result = self.agent.execute({"action": "calendario_fiscal", "ano": 2026})
        assert result["status"] == "ok"
        cal = result["calendario"]
        assert "mensal" in cal
        assert "anual" in cal
        assert "eventual" in cal
        assert "dia_20" in cal["mensal"]
        assert "31_maio" in cal["anual"]

    # ── Checklist ──────────────────────────────────────────────

    def test_checklist_mensal(self):
        """Checklist mensal lista pendências."""
        result = self.agent.execute({"action": "checklist_mensal", "month": "2026-03"})
        assert result["status"] == "ok"
        assert len(result["checklist"]) >= 5
        assert "total_pendentes" in result

    def test_checklist_mensal_com_empregado(self):
        """Checklist mensal com empregado adiciona eSocial/FGTS."""
        result = self.agent.execute({
            "action": "checklist_mensal",
            "month": "2026-03",
            "tem_empregado": True,
        })
        items = [i["item"] for i in result["checklist"]]
        assert any("FGTS" in i for i in items)
        assert any("eSocial" in i for i in items)

    def test_checklist_anual(self):
        """Checklist anual lista DASN, IRPF, licenças."""
        result = self.agent.execute({"action": "checklist_anual", "ano": 2026})
        assert result["status"] == "ok"
        items = [i["item"] for i in result["checklist"]]
        assert any("DASN" in i for i in items)
        assert any("IRPF" in i for i in items)
        assert any("81.000" in i for i in items)

    # ── eSocial ────────────────────────────────────────────────

    def test_esocial_sem_empregado(self):
        """eSocial não aplicável se sem empregado."""
        result = self.agent.execute({"action": "esocial_status", "tem_empregado": False})
        assert result["esocial"]["aplicavel"] is False

    def test_esocial_com_empregado(self):
        """eSocial calcula FGTS e INSS patronal."""
        result = self.agent.execute({
            "action": "esocial_status",
            "tem_empregado": True,
            "salario_empregado": 1621.00,
        })
        esocial = result["esocial"]
        assert esocial["aplicavel"] is True
        assert esocial["empregado"]["fgts_mensal"] == 129.68  # 1621 * 0.08
        assert esocial["empregado"]["inss_patronal_3_percent"] == 48.63  # 1621 * 0.03

    # ── Penalidades ────────────────────────────────────────────

    def test_multa_das_em_dia(self):
        """DAS em dia = sem multa."""
        result = self.agent.execute({"action": "calcular_multa_das", "dias_atraso": 0})
        assert result["multa"] == 0

    def test_multa_das_atrasado(self):
        """DAS atrasado 30 dias calcula multa + juros."""
        result = self.agent.execute({
            "action": "calcular_multa_das",
            "valor_das": 86.05,
            "dias_atraso": 30,
        })
        assert result["multa"] > 0
        assert result["juros_estimados"] > 0
        assert result["total_a_pagar"] > 86.05

    def test_consultar_penalidades(self):
        """Lista todas as penalidades possíveis."""
        result = self.agent.execute({"action": "consultar_penalidades"})
        assert len(result["penalidades"]) >= 4

    # ── CCMEI ──────────────────────────────────────────────────

    def test_ccmei_status(self):
        """CCMEI retorna info sobre licenças."""
        result = self.agent.execute({"action": "ccmei_status"})
        assert result["status"] == "ok"
        assert "ccmei" in result
        assert "licencas" in result

    # ── DTE-SN ─────────────────────────────────────────────────

    def test_dte_status(self):
        """DTE-SN retorna orientações."""
        result = self.agent.execute({"action": "dte_status"})
        assert "quinzenalmente" in result["dte"]["frequencia_verificacao"]

    # ── Guarda de Documentos ───────────────────────────────────

    def test_guarda_documentos(self):
        """Guarda de documentos retorna prazo e lista."""
        result = self.agent.execute({"action": "guarda_documentos"})
        assert "5 anos" in result["guarda"]["prazo_geral"]
        assert len(result["guarda"]["documentos_obrigatorios"]) >= 6

    # ── NFS-e / NF-e ──────────────────────────────────────────

    def test_prepare_invoice_nfse(self):
        """Preparar NFS-e retorna passos com CRT 4."""
        result = self.agent.execute({
            "action": "prepare_invoice",
            "tipo_nf": "nfse",
            "cliente": "João Silva",
            "valor": 500,
            "descricao": "Consultoria",
        })
        assert result["status"] == "ok"
        steps_text = " ".join(result["steps"])
        assert "CRT" in steps_text
        assert "João Silva" in steps_text

    def test_prepare_invoice_nfe(self):
        """Preparar NF-e retorna passos com CRT 4."""
        result = self.agent.execute({
            "action": "prepare_invoice",
            "tipo_nf": "nfe",
        })
        assert result["status"] == "ok"
        steps_text = " ".join(result["steps"])
        assert "CRT" in steps_text

    # ── Análise financeira ─────────────────────────────────────

    def test_analyze_month(self):
        """Análise mensal retorna resumo completo."""
        result = self.agent.execute({
            "action": "analyze_month",
            "month": "2026-03",
            "tipo_atividade": "servicos",
        })
        assert result["status"] == "analyzed"
        assert result["resumo"]["das_mensal"] == 86.05
        assert "limite_mei" in result
        assert "insights" in result

    def test_health_check(self):
        """Health check retorna saúde geral."""
        result = self.agent.execute({"action": "health_check"})
        assert "saude_geral" in result

    # ── Relatórios e contratos ─────────────────────────────────

    def test_generate_report(self):
        """Lista relatórios disponíveis."""
        result = self.agent.execute({"action": "generate_report"})
        assert len(result["relatorios_disponiveis"]) >= 5

    def test_generate_contract(self):
        """Gera modelo de contrato."""
        result = self.agent.execute({"action": "generate_contract", "tipo": "servico"})
        assert result["status"] == "ok"
        assert "Prestação de Serviço" in result["contrato"]["tipo"]

    def test_relatorio_mensal(self):
        """Relatório mensal de receitas brutas."""
        result = self.agent.execute({"action": "relatorio_mensal", "month": "2026-03"})
        assert result["status"] == "ok"
        assert "receita_bruta_total" in result["relatorio"]

    # ── Ação desconhecida ──────────────────────────────────────

    def test_acao_desconhecida(self):
        """Ação desconhecida retorna erro."""
        result = self.agent.execute({"action": "nao_existe"})
        assert result["status"] == "error"


# ============================================================================
# TESTES DE CONSTANTES
# ============================================================================

class TestConstantesMEI2026:
    """Valida todas as constantes MEI 2026."""

    def test_salario_minimo(self):
        from agents.contabilidade_agent import SALARIO_MINIMO_2026
        assert SALARIO_MINIMO_2026 == 1621.00

    def test_inss_mei(self):
        from agents.contabilidade_agent import INSS_MEI_2026
        assert INSS_MEI_2026 == 81.05

    def test_das_comercio(self):
        from agents.contabilidade_agent import DAS_VALORES_2026
        assert DAS_VALORES_2026["comercio"] == 82.05

    def test_das_servicos(self):
        from agents.contabilidade_agent import DAS_VALORES_2026
        assert DAS_VALORES_2026["servicos"] == 86.05

    def test_das_comercio_servicos(self):
        from agents.contabilidade_agent import DAS_VALORES_2026
        assert DAS_VALORES_2026["comercio_servicos"] == 87.05

    def test_limite_anual(self):
        from agents.contabilidade_agent import LIMITE_ANUAL_MEI
        assert LIMITE_ANUAL_MEI == 81000.00

    def test_limite_excesso(self):
        from agents.contabilidade_agent import LIMITE_EXCESSO_20_PERCENT
        assert LIMITE_EXCESSO_20_PERCENT == 97200.00

    def test_inss_caminhoneiro(self):
        from agents.contabilidade_agent import INSS_CAMINHONEIRO_2026
        assert INSS_CAMINHONEIRO_2026 == 194.52


# ============================================================================
# TESTES DE ENDPOINTS (API)
# ============================================================================

class TestEndpointsContabilidade:
    """Testa endpoints da API para o agente contabilidade."""

    def test_list_agents_contabilidade(self, client, headers):
        """Lista de agentes inclui contabilidade (não financeiro/documentos)."""
        r = client.get("/api/agents/list", headers=headers)
        assert r.status_code == 200
        agents = r.json()["agents"]
        ids = [a["id"] for a in agents]
        assert "contabilidade" in ids
        assert "financeiro" not in ids
        assert "documentos" not in ids

    def test_contabilidade_config(self, client, headers):
        """Config do agente contabilidade existe."""
        r = client.get("/api/agents/contabilidade/config", headers=headers)
        assert r.status_code == 200
        assert r.json()["agent_id"] == "contabilidade"

    def test_legacy_financeiro_config_redirect(self, client, headers):
        """Chamada legada /financeiro/config redireciona para contabilidade."""
        r = client.get("/api/agents/financeiro/config", headers=headers)
        assert r.status_code == 200
        assert r.json()["agent_id"] == "contabilidade"

    def test_legacy_documentos_config_redirect(self, client, headers):
        """Chamada legada /documentos/config redireciona para contabilidade."""
        r = client.get("/api/agents/documentos/config", headers=headers)
        assert r.status_code == 200
        assert r.json()["agent_id"] == "contabilidade"

    def test_execute_contabilidade_das_status(self, client, headers):
        """Executa ação das_status no agente contabilidade."""
        r = client.post("/api/agents/contabilidade/execute", headers=headers, json={
            "action": "das_status",
            "parameters": {"tipo_atividade": "servicos"}
        })
        assert r.status_code == 200
        data = r.json()
        # Pode ser resposta do LLM ou fallback local
        assert "agent_id" in data or "message" in data

    def test_execute_legacy_financeiro(self, client, headers):
        """Executa via endpoint legado /financeiro/execute."""
        r = client.post("/api/agents/financeiro/execute", headers=headers, json={
            "action": "analyze_month",
            "parameters": {"month": "2026-03"}
        })
        assert r.status_code == 200

    def test_execute_legacy_documentos(self, client, headers):
        """Executa via endpoint legado /documentos/execute."""
        r = client.post("/api/agents/documentos/execute", headers=headers, json={
            "action": "prepare_invoice",
            "parameters": {"tipo_nf": "nfse"}
        })
        assert r.status_code == 200

    def test_hub_status(self, client, headers):
        """Hub status funciona após renomear agentes."""
        r = client.get("/api/agents/hub/status", headers=headers)
        assert r.status_code == 200

    def test_contabilidade_status(self, client, headers):
        """Status do agente contabilidade."""
        r = client.get("/api/agents/contabilidade/status", headers=headers)
        assert r.status_code == 200


# ============================================================================
# TESTES DO CORE AGENT HUB
# ============================================================================

class TestCoreAgentHub:
    """Testa AgentType, resolve_agent_type e EventType."""

    def test_agent_type_contabilidade(self):
        from agents.agent_hub import AgentType
        assert AgentType.CONTABILIDADE.value == "contabilidade"

    def test_agent_type_no_financeiro(self):
        from agents.agent_hub import AgentType
        members = [m.value for m in AgentType]
        assert "contabilidade" in members
        assert "financeiro" not in members
        assert "documentos" not in members

    def test_resolve_agent_type_direct(self):
        from agents.agent_hub import resolve_agent_type, AgentType
        assert resolve_agent_type("contabilidade") == AgentType.CONTABILIDADE

    def test_resolve_agent_type_legacy_financeiro(self):
        from agents.agent_hub import resolve_agent_type, AgentType
        assert resolve_agent_type("financeiro") == AgentType.CONTABILIDADE

    def test_resolve_agent_type_legacy_documentos(self):
        from agents.agent_hub import resolve_agent_type, AgentType
        assert resolve_agent_type("documentos") == AgentType.CONTABILIDADE

    def test_event_type_das_vencendo(self):
        from agents.agent_hub import EventType
        assert EventType.DAS_VENCENDO.value == "das_vencendo"

    def test_event_type_dasn_vencendo(self):
        from agents.agent_hub import EventType
        assert EventType.DASN_VENCENDO.value == "dasn_vencendo"

    def test_event_type_desenquadramento(self):
        from agents.agent_hub import EventType
        assert EventType.DESENQUADRAMENTO_RISCO.value == "desenquadramento_risco"


# ============================================================================
# TESTES DO SYSTEM PROMPT
# ============================================================================

class TestSystemPrompts:
    """Valida que os prompts estão corretos e atualizados."""

    def test_contabilidade_prompt_exists(self):
        from app.api.agent_chat import AGENT_SYSTEM_PROMPTS
        assert "contabilidade" in AGENT_SYSTEM_PROMPTS

    def test_financeiro_prompt_removed(self):
        from app.api.agent_chat import AGENT_SYSTEM_PROMPTS
        assert "financeiro" not in AGENT_SYSTEM_PROMPTS

    def test_documentos_prompt_removed(self):
        from app.api.agent_chat import AGENT_SYSTEM_PROMPTS
        assert "documentos" not in AGENT_SYSTEM_PROMPTS

    def test_prompt_has_correct_das_values(self):
        from app.api.agent_chat import AGENT_SYSTEM_PROMPTS
        prompt = AGENT_SYSTEM_PROMPTS["contabilidade"]
        assert "82,05" in prompt  # DAS comércio
        assert "86,05" in prompt  # DAS serviços
        assert "87,05" in prompt  # DAS comércio+serviços
        assert "81,05" in prompt  # INSS
        assert "1.621" in prompt  # Salário mínimo

    def test_prompt_has_no_outdated_values(self):
        from app.api.agent_chat import AGENT_SYSTEM_PROMPTS
        prompt = AGENT_SYSTEM_PROMPTS["contabilidade"]
        assert "71,60" not in prompt  # valores antigos
        assert "75,60" not in prompt
        assert "76,60" not in prompt

    def test_prompt_mentions_crt4(self):
        from app.api.agent_chat import AGENT_SYSTEM_PROMPTS
        prompt = AGENT_SYSTEM_PROMPTS["contabilidade"]
        assert "CRT 4" in prompt

    def test_prompt_mentions_nfse_2026(self):
        from app.api.agent_chat import AGENT_SYSTEM_PROMPTS
        prompt = AGENT_SYSTEM_PROMPTS["contabilidade"]
        assert "2026" in prompt

    def test_action_prompts_contabilidade(self):
        from app.api.agent_chat import ACTION_PROMPTS
        assert "das_status" in ACTION_PROMPTS
        assert "dasn_status" in ACTION_PROMPTS
        assert "calendario_fiscal" in ACTION_PROMPTS
        assert "checklist_mensal" in ACTION_PROMPTS
        assert "irpf_calculo" in ACTION_PROMPTS
        assert "penalidades" in ACTION_PROMPTS
