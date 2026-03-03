"""
Testes — Integrações Governamentais MEI.

Testa:
- Domain models (MEIProfile, CNDStatus, etc.)
- ExternalAPIClient (http_base)
- CNPJClient (com mock)
- MEIService (diagnóstico completo)
- Router endpoints

Usa respx para mockar httpx.
"""

import sys
import os
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest

# Garantir que backend/ está no path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ══════════════════════════════════════════════════════════════════════════════
# 1. DOMAIN MODELS
# ══════════════════════════════════════════════════════════════════════════════

class TestMEIProfile:
    """Testes para MEIProfile.from_cnpj_payload."""

    def test_from_brasilapi_payload(self):
        from app.integrations.domain.mei_models import MEIProfile

        payload = {
            "cnpj": "12345678000199",
            "razao_social": "JOAO DA SILVA 12345678901",
            "nome_fantasia": "JS SERVICOS",
            "natureza_juridica": "213-5 - Empresário (Individual)",
            "situacao_cadastral": "02",
            "data_inicio_atividade": "2020-03-15",
            "cnae_fiscal_principal": {
                "codigo": "6201501",
                "descricao": "Desenvolvimento de programas de computador sob encomenda",
            },
            "uf": "ES",
            "municipio": "Vitoria",
            "cep": "29000000",
            "simples": {
                "optante": True,
                "mei": True,
                "data_opcao": "2020-03-15",
            },
        }

        profile = MEIProfile.from_cnpj_payload(payload, fonte="brasilapi")

        assert profile.cnpj == "12345678000199"
        assert profile.is_mei is True
        assert profile.is_simples is True
        assert profile.razao_social == "JOAO DA SILVA 12345678901"
        assert profile.nome_fantasia == "JS SERVICOS"
        assert profile.uf == "ES"
        assert profile.cnae_principal is not None
        assert profile.cnae_principal.codigo == "6201501"
        assert profile.fonte == "brasilapi"

    def test_from_natureza_juridica_213(self):
        """Infere MEI pela natureza jurídica 213-5."""
        from app.integrations.domain.mei_models import MEIProfile

        payload = {
            "cnpj": "99999999000100",
            "razao_social": "MARIA TESTE",
            "natureza_juridica": "213-5 - Empresário (Individual)",
            "simples": {},
        }

        profile = MEIProfile.from_cnpj_payload(payload)
        assert profile.is_mei is True

    def test_from_payload_not_mei(self):
        """CNPJ que não é MEI."""
        from app.integrations.domain.mei_models import MEIProfile

        payload = {
            "cnpj": "11222333000144",
            "razao_social": "EMPRESA LTDA",
            "natureza_juridica": "206-2 - Sociedade Empresária Limitada",
            "simples": {"optante": False, "mei": False},
            "situacao_cadastral": "ativa",
        }

        profile = MEIProfile.from_cnpj_payload(payload)
        assert profile.is_mei is False
        assert profile.is_simples is False
        assert profile.situacao_cadastral.value == "ativa"

    def test_from_payload_missing_fields(self):
        """Payload mínimo — tolerância a campos ausentes."""
        from app.integrations.domain.mei_models import MEIProfile

        payload = {"cnpj": "00000000000000"}
        profile = MEIProfile.from_cnpj_payload(payload)

        assert profile.cnpj == "00000000000000"
        assert profile.razao_social == ""
        assert profile.is_mei is False


class TestCNDStatus:
    """Testes para CNDStatus."""

    def test_from_negativa(self):
        from app.integrations.domain.fiscal_models import CNDStatus, TipoCertidao

        status = CNDStatus.from_api_payload(
            "12345678000199",
            {"tipo": "negativa", "codigo": "ABC123"},
            fonte="serpro",
        )
        assert status.tipo_certidao == TipoCertidao.NEGATIVA
        assert status.apto_contratar_governo is True

    def test_from_positiva(self):
        from app.integrations.domain.fiscal_models import CNDStatus, TipoCertidao

        status = CNDStatus.from_api_payload(
            "12345678000199",
            {"tipo": "positiva"},
            fonte="serpro",
        )
        assert status.tipo_certidao == TipoCertidao.POSITIVA
        assert status.apto_contratar_governo is False

    def test_from_positiva_efeito_negativa(self):
        from app.integrations.domain.fiscal_models import CNDStatus, TipoCertidao

        status = CNDStatus.from_api_payload(
            "12345678000199",
            {"tipo": "positiva com efeito de negativa"},
            fonte="serpro",
        )
        assert status.tipo_certidao == TipoCertidao.POSITIVA_EFEITO_NEGATIVA
        assert status.apto_contratar_governo is True


class TestSituacaoFiscal:
    """Testes para SituacaoFiscalMEI."""

    def test_calcular_indicadores_regular(self):
        from app.integrations.domain.fiscal_models import (
            CNDStatus, TipoCertidao, DividaAtivaStatus, SituacaoFiscalMEI,
        )

        situacao = SituacaoFiscalMEI(
            cnpj="12345678000199",
            cnd=CNDStatus(
                cnpj="12345678000199",
                tipo_certidao=TipoCertidao.NEGATIVA,
                apto_contratar_governo=True,
                fonte="serpro",
            ),
            divida_ativa=DividaAtivaStatus(
                cnpj="12345678000199",
                tem_divida=False,
                fonte="serpro",
            ),
        )

        situacao.calcular_indicadores()
        assert situacao.regular is True
        assert situacao.pode_contratar_governo is True
        assert len(situacao.alertas) == 0

    def test_calcular_indicadores_com_divida(self):
        from app.integrations.domain.fiscal_models import (
            CNDStatus, TipoCertidao, DividaAtivaStatus,
            InscricaoDividaAtiva, SituacaoDividaAtiva, SituacaoFiscalMEI,
        )

        situacao = SituacaoFiscalMEI(
            cnpj="12345678000199",
            cnd=CNDStatus(
                cnpj="12345678000199",
                tipo_certidao=TipoCertidao.POSITIVA,
                apto_contratar_governo=False,
                fonte="serpro",
            ),
            divida_ativa=DividaAtivaStatus(
                cnpj="12345678000199",
                tem_divida=True,
                total_dividas=1,
                valor_total=5000.00,
                inscricoes=[
                    InscricaoDividaAtiva(
                        numero_inscricao="123",
                        valor_consolidado=5000.00,
                        situacao=SituacaoDividaAtiva.EM_COBRANCA,
                    )
                ],
                fonte="serpro",
            ),
        )

        situacao.calcular_indicadores()
        assert situacao.regular is False
        assert situacao.pode_contratar_governo is False
        assert len(situacao.alertas) >= 2  # CND positiva + dívida


# ══════════════════════════════════════════════════════════════════════════════
# 2. HTTP BASE
# ══════════════════════════════════════════════════════════════════════════════

class TestExternalAPIClient:
    """Testes para ExternalAPIClient base."""

    def test_mask_cnpj(self):
        from app.integrations.http_base import ExternalAPIClient

        assert "***" in ExternalAPIClient.mask_cnpj("12345678000199")
        assert "12.345" in ExternalAPIClient.mask_cnpj("12345678000199")

    def test_validate_cnpj_valid(self):
        from app.integrations.http_base import ExternalAPIClient

        assert ExternalAPIClient.validate_cnpj("12.345.678/0001-99") == "12345678000199"

    def test_validate_cnpj_invalid(self):
        from app.integrations.http_base import ExternalAPIClient

        with pytest.raises(ValueError, match="CNPJ inválido"):
            ExternalAPIClient.validate_cnpj("123")

    def test_clean_cnpj(self):
        from app.integrations.http_base import ExternalAPIClient

        assert ExternalAPIClient.clean_cnpj("12.345.678/0001-99") == "12345678000199"


# ══════════════════════════════════════════════════════════════════════════════
# 3. MEI SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class TestMEIServiceObrigacoes:
    """Testes para cálculo de obrigações do MEI."""

    def test_calcular_obrigacoes_servico(self):
        from app.integrations.services.mei_service import _calcular_obrigacoes
        from app.integrations.domain.mei_models import MEIProfile, CNAEInfo

        profile = MEIProfile(
            cnpj="12345678000199",
            razao_social="TESTE",
            is_mei=True,
            cnae_principal=CNAEInfo(codigo="6201501", descricao="Desenvolvimento de software"),
        )

        obrigacoes = _calcular_obrigacoes(profile)
        assert obrigacoes.das_valor_mensal == 86.05  # Serviço
        assert obrigacoes.das_componentes["iss"] == 5.00
        assert obrigacoes.das_componentes["icms"] == 0.00
        assert obrigacoes.nfse_obrigatoria is True

    def test_calcular_obrigacoes_comercio(self):
        from app.integrations.services.mei_service import _calcular_obrigacoes
        from app.integrations.domain.mei_models import MEIProfile, CNAEInfo

        profile = MEIProfile(
            cnpj="12345678000199",
            razao_social="TESTE",
            is_mei=True,
            cnae_principal=CNAEInfo(codigo="4711302", descricao="Comércio varejista"),
        )

        obrigacoes = _calcular_obrigacoes(profile)
        assert obrigacoes.das_valor_mensal == 82.05  # Comércio
        assert obrigacoes.das_componentes["icms"] == 1.00
        assert obrigacoes.das_componentes["iss"] == 0.00
        assert obrigacoes.nfse_obrigatoria is False

    def test_proximo_vencimento_das(self):
        from app.integrations.services.mei_service import _proximo_vencimento_das

        venc = _proximo_vencimento_das()
        assert venc.day == 20
        assert venc >= date.today()

    def test_inferir_tipo_industria(self):
        from app.integrations.services.mei_service import _inferir_tipo_atividade
        from app.integrations.domain.mei_models import MEIProfile, CNAEInfo, AtividadeTipo

        profile = MEIProfile(
            cnpj="12345678000199",
            razao_social="TESTE",
            cnae_principal=CNAEInfo(codigo="1099699", descricao="Fabricação de alimentos"),
        )

        tipo = _inferir_tipo_atividade(profile)
        assert tipo == AtividadeTipo.INDUSTRIA


# ══════════════════════════════════════════════════════════════════════════════
# 4. CNPJ CLIENT
# ══════════════════════════════════════════════════════════════════════════════

class TestCNPJClient:
    """Testes para CNPJClient com mock httpx."""

    @pytest.mark.asyncio
    async def test_consultar_mei_mock(self):
        """Testa consulta CNPJ com resposta mockada."""
        from app.integrations.cnpj_client import CNPJClient, CNPJProvider

        mock_response = {
            "cnpj": "12345678000199",
            "razao_social": "JOAO SILVA MEI",
            "natureza_juridica": "213-5 - Empresário (Individual)",
            "simples": {"optante": True, "mei": True},
            "situacao_cadastral": "ativa",
            "cnae_fiscal_principal": {"codigo": "6201501", "descricao": "Dev software"},
            "uf": "ES",
            "municipio": "Vitoria",
        }

        client = CNPJClient(provider=CNPJProvider.BRASILAPI)
        client._request = AsyncMock(return_value=mock_response)

        profile = await client.consultar_mei("12345678000199")

        assert profile.is_mei is True
        assert profile.razao_social == "JOAO SILVA MEI"
        assert profile.uf == "ES"
        assert profile.fonte == "brasilapi"

        await client.close()

    @pytest.mark.asyncio
    async def test_consultar_cnpj_invalido(self):
        """CNPJ com dígitos insuficientes deve levantar ValueError."""
        from app.integrations.cnpj_client import CNPJClient

        client = CNPJClient()

        with pytest.raises(ValueError, match="CNPJ inválido"):
            await client.consultar_mei("123")

        await client.close()


# ══════════════════════════════════════════════════════════════════════════════
# 5. CND CLIENT
# ══════════════════════════════════════════════════════════════════════════════

class TestCNDClient:
    """Testes para CNDClient."""

    @pytest.mark.asyncio
    async def test_mock_cnd(self):
        """Mock provider retorna CND indisponível."""
        from app.integrations.cnd_client import CNDClient
        from app.integrations.domain.fiscal_models import TipoCertidao

        async with CNDClient(provider="mock") as client:
            cnd = await client.consultar_cnd("12345678000199")

        assert cnd.tipo_certidao == TipoCertidao.INDISPONIVEL
        assert cnd.fonte == "mock"
        assert cnd.apto_contratar_governo is False


# ══════════════════════════════════════════════════════════════════════════════
# 6. DIVIDA ATIVA CLIENT
# ══════════════════════════════════════════════════════════════════════════════

class TestDividaAtivaClient:
    """Testes para DividaAtivaClient."""

    @pytest.mark.asyncio
    async def test_mock_divida_ativa(self):
        """Mock provider retorna sem dívida."""
        from app.integrations.divida_ativa_client import DividaAtivaClient

        async with DividaAtivaClient(provider="mock") as client:
            da = await client.consultar("12345678000199")

        assert da.tem_divida is False
        assert da.valor_total == 0.0
        assert da.fonte == "mock"


# ══════════════════════════════════════════════════════════════════════════════
# 7. NFSe MODELS
# ══════════════════════════════════════════════════════════════════════════════

class TestNFSeModels:
    """Testes para modelos de NFSe e Transparência."""

    def test_emissao_request(self):
        from app.integrations.domain.nfse_transparencia_models import EmissaoNFSeRequest

        req = EmissaoNFSeRequest(
            cnpj_prestador="12345678000199",
            descricao_servico="Desenvolvimento web",
            valor_servico=1500.00,
        )
        assert req.cnpj_prestador == "12345678000199"
        assert req.valor_servico == 1500.00

    def test_pagamento_governo(self):
        from app.integrations.domain.nfse_transparencia_models import PagamentoGoverno

        pgto = PagamentoGoverno(
            cnpj_favorecido="12345678000199",
            orgao="Ministério da Economia",
            valor=25000.50,
            ano=2025,
            fonte="transparencia_federal",
        )
        assert pgto.valor == 25000.50


# ══════════════════════════════════════════════════════════════════════════════
# 8. ROUTER (via TestClient)
# ══════════════════════════════════════════════════════════════════════════════

class TestGovRouter:
    """Testes para endpoints do router gov_integrations."""

    def test_get_tabela_das(self):
        """Endpoint /api/gov/info/das-tabela (sem auth)."""
        from fastapi.testclient import TestClient

        # Importar app com path ajustado
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from main import app

        client = TestClient(app)
        resp = client.get("/api/gov/info/das-tabela")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ano_referencia"] == 2026
        assert "tabela" in data
        assert data["tabela"]["servico"]["total"] == 86.05
        assert data["tabela"]["comercio"]["total"] == 82.05
        assert data["tabela"]["misto"]["total"] == 87.05
        assert "links" in data

    def test_get_provedores(self):
        """Endpoint /api/gov/info/provedores (sem auth)."""
        from fastapi.testclient import TestClient

        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from main import app

        client = TestClient(app)
        resp = client.get("/api/gov/info/provedores")

        assert resp.status_code == 200
        data = resp.json()
        assert "cnpj" in data
        assert "cnd" in data
        assert "nfse_nacional" in data
        assert "brasilapi" in data["cnpj"]["provedores_disponiveis"]
