"""
Google AdSense API Integration
Endpoints para métricas de revenue, ad units, e reporting
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from datetime import datetime, timedelta
import os
# from google.ads.admanager import ad_manager_client  # Não disponível nesta versão
from googleapiclient.discovery import build  # type: ignore
from google.oauth2 import service_account  # type: ignore
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/adsense", tags=["AdSense"])


# ============================================================================
# MODELS
# ============================================================================

class AdUnitRequest(BaseModel):
    """Request para criar/atualizar Ad Unit"""
    name: str = Field(..., description="Nome da Ad Unit")
    size: str = Field(..., description="Tamanho do anúncio (ex: 300x250, 728x90)")
    type: str = Field(default="display", description="Tipo: display, text, video")
    placement: str = Field(..., description="Local de exibição (ex: sidebar, header)")


class RevenueMetrics(BaseModel):
    """Métricas de revenue do AdSense"""
    earnings: float = Field(..., description="Ganhos totais")
    impressions: int = Field(..., description="Total de impressões")
    clicks: int = Field(..., description="Total de cliques")
    ctr: float = Field(..., description="Click-through rate (%)")
    cpc: float = Field(..., description="Cost per click")
    rpm: float = Field(..., description="Revenue per mille (1000 impressions)")
    date_range: str = Field(..., description="Período dos dados")


class AdPerformance(BaseModel):
    """Performance de anúncios específicos"""
    ad_unit_id: str
    ad_unit_name: str
    earnings: float
    impressions: int
    clicks: int
    ctr: float


# ============================================================================
# GOOGLE ADSENSE CLIENT SETUP
# ============================================================================

def get_adsense_client():
    """Inicializa Google AdSense API client"""
    try:
        # Caminho para service account key
        sa_key_path = os.getenv("GOOGLE_ADSENSE_SA_KEY", "config/adsense-sa-key.json")

        if not os.path.exists(sa_key_path):
            raise HTTPException(
                status_code=500,
                detail=f"Service Account Key não encontrada: {sa_key_path}"
            )

        # Scopes necessários para AdSense API
        SCOPES = [
            'https://www.googleapis.com/auth/adsense.readonly',
            'https://www.googleapis.com/auth/adsense'
        ]

        credentials = service_account.Credentials.from_service_account_file(
            sa_key_path, scopes=SCOPES
        )

        # Build AdSense API client
        service = build('adsense', 'v2', credentials=credentials)
        return service

    except Exception as e:
        logger.error(f"Erro ao inicializar AdSense client: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AdSense client error: {str(e)}")


def get_account_id() -> str:
    """Retorna Account ID do AdSense configurado"""
    account_id = os.getenv("GOOGLE_ADSENSE_ACCOUNT_ID")
    if not account_id:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_ADSENSE_ACCOUNT_ID não configurado no .env"
        )
    return account_id


# ============================================================================
# ENDPOINTS - REVENUE METRICS
# ============================================================================

@router.get("/revenue/today", response_model=RevenueMetrics)
async def get_today_revenue():
    """
    Retorna métricas de revenue do dia atual

    Returns:
        RevenueMetrics com dados de hoje
    """
    try:
        service = get_adsense_client()
        account_id = get_account_id()

        # Data de hoje
        today = datetime.now().strftime("%Y-%m-%d")

        # Request para AdSense Reporting API
        request = service.accounts().reports().generate(
            account=f"accounts/{account_id}",
            dateRange="TODAY",
            metrics=[
                "EARNINGS",
                "IMPRESSIONS",
                "CLICKS",
                "COST_PER_CLICK",
                "PAGE_VIEWS_RPM"
            ]
        )

        response = request.execute()

        # Parse response
        if not response.get('rows'):
            return RevenueMetrics(
                earnings=0.0,
                impressions=0,
                clicks=0,
                ctr=0.0,
                cpc=0.0,
                rpm=0.0,
                date_range=today
            )

        data = response['rows'][0]['cells']
        earnings = float(data[0].get('value', 0))
        impressions = int(data[1].get('value', 0))
        clicks = int(data[2].get('value', 0))
        cpc = float(data[3].get('value', 0))
        rpm = float(data[4].get('value', 0))

        ctr = (clicks / impressions * 100) if impressions > 0 else 0.0

        return RevenueMetrics(
            earnings=round(earnings, 2),
            impressions=impressions,
            clicks=clicks,
            ctr=round(ctr, 2),
            cpc=round(cpc, 2),
            rpm=round(rpm, 2),
            date_range=today
        )

    except Exception as e:
        logger.error(f"Erro ao buscar revenue de hoje: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/revenue/month", response_model=RevenueMetrics)
async def get_month_revenue():
    """
    Retorna métricas de revenue do mês atual

    Returns:
        RevenueMetrics com dados do mês
    """
    try:
        service = get_adsense_client()
        account_id = get_account_id()

        # Primeiro e último dia do mês
        today = datetime.now()
        start_date = today.replace(day=1).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        request = service.accounts().reports().generate(
            account=f"accounts/{account_id}",
            dateRange="MONTH_TO_DATE",
            metrics=[
                "EARNINGS",
                "IMPRESSIONS",
                "CLICKS",
                "COST_PER_CLICK",
                "PAGE_VIEWS_RPM"
            ]
        )

        response = request.execute()

        if not response.get('rows'):
            return RevenueMetrics(
                earnings=0.0,
                impressions=0,
                clicks=0,
                ctr=0.0,
                cpc=0.0,
                rpm=0.0,
                date_range=f"{start_date} to {end_date}"
            )

        data = response['rows'][0]['cells']
        earnings = float(data[0].get('value', 0))
        impressions = int(data[1].get('value', 0))
        clicks = int(data[2].get('value', 0))
        cpc = float(data[3].get('value', 0))
        rpm = float(data[4].get('value', 0))

        ctr = (clicks / impressions * 100) if impressions > 0 else 0.0

        return RevenueMetrics(
            earnings=round(earnings, 2),
            impressions=impressions,
            clicks=clicks,
            ctr=round(ctr, 2),
            cpc=round(cpc, 2),
            rpm=round(rpm, 2),
            date_range=f"{start_date} to {end_date}"
        )

    except Exception as e:
        logger.error(f"Erro ao buscar revenue do mês: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/revenue/custom")
async def get_custom_revenue(
    start_date: str = Query(..., description="Data inicial (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Data final (YYYY-MM-DD)")
) -> RevenueMetrics:
    """
    Retorna métricas de revenue para período customizado

    Args:
        start_date: Data inicial no formato YYYY-MM-DD
        end_date: Data final no formato YYYY-MM-DD

    Returns:
        RevenueMetrics para o período especificado
    """
    try:
        service = get_adsense_client()
        account_id = get_account_id()

        request = service.accounts().reports().generate(
            account=f"accounts/{account_id}",
            startDate=start_date,
            endDate=end_date,
            metrics=[
                "EARNINGS",
                "IMPRESSIONS",
                "CLICKS",
                "COST_PER_CLICK",
                "PAGE_VIEWS_RPM"
            ]
        )

        response = request.execute()

        if not response.get('rows'):
            return RevenueMetrics(
                earnings=0.0,
                impressions=0,
                clicks=0,
                ctr=0.0,
                cpc=0.0,
                rpm=0.0,
                date_range=f"{start_date} to {end_date}"
            )

        data = response['rows'][0]['cells']
        earnings = float(data[0].get('value', 0))
        impressions = int(data[1].get('value', 0))
        clicks = int(data[2].get('value', 0))
        cpc = float(data[3].get('value', 0))
        rpm = float(data[4].get('value', 0))

        ctr = (clicks / impressions * 100) if impressions > 0 else 0.0

        return RevenueMetrics(
            earnings=round(earnings, 2),
            impressions=impressions,
            clicks=clicks,
            ctr=round(ctr, 2),
            cpc=round(cpc, 2),
            rpm=round(rpm, 2),
            date_range=f"{start_date} to {end_date}"
        )

    except Exception as e:
        logger.error(f"Erro ao buscar revenue customizado: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINTS - AD UNITS MANAGEMENT
# ============================================================================

@router.get("/adunits", response_model=List[Dict[str, Any]])
async def list_ad_units():
    """
    Lista todas as Ad Units configuradas

    Returns:
        Lista de Ad Units com suas configurações
    """
    try:
        service = get_adsense_client()
        account_id = get_account_id()

        request = service.accounts().adunits().list(
            parent=f"accounts/{account_id}"
        )

        response = request.execute()

        ad_units = []
        for unit in response.get('adUnits', []):
            ad_units.append({
                "id": unit.get('name', '').split('/')[-1],
                "name": unit.get('displayName', 'Unnamed'),
                "status": unit.get('state', 'UNKNOWN'),
                "code": unit.get('name', '')
            })

        return ad_units

    except Exception as e:
        logger.error(f"Erro ao listar ad units: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/adunits/performance", response_model=List[AdPerformance])
async def get_ad_units_performance(
    days: int = Query(default=7, description="Número de dias para análise")
):
    """
    Retorna performance de cada Ad Unit

    Args:
        days: Número de dias para análise (default: 7)

    Returns:
        Lista de AdPerformance para cada unit
    """
    try:
        service = get_adsense_client()
        account_id = get_account_id()

        # Calcular período
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Request com dimensão AD_UNIT_NAME
        request = service.accounts().reports().generate(
            account=f"accounts/{account_id}",
            startDate=start_date.strftime("%Y-%m-%d"),
            endDate=end_date.strftime("%Y-%m-%d"),
            dimensions=["AD_UNIT_NAME"],
            metrics=[
                "EARNINGS",
                "IMPRESSIONS",
                "CLICKS"
            ]
        )

        response = request.execute()

        performance_list = []
        for row in response.get('rows', []):
            ad_unit_name = row['cells'][0].get('value', 'Unknown')
            earnings = float(row['cells'][1].get('value', 0))
            impressions = int(row['cells'][2].get('value', 0))
            clicks = int(row['cells'][3].get('value', 0))

            ctr = (clicks / impressions * 100) if impressions > 0 else 0.0

            performance_list.append(AdPerformance(
                ad_unit_id=ad_unit_name.replace(' ', '_').lower(),
                ad_unit_name=ad_unit_name,
                earnings=round(earnings, 2),
                impressions=impressions,
                clicks=clicks,
                ctr=round(ctr, 2)
            ))

        return performance_list

    except Exception as e:
        logger.error(f"Erro ao buscar performance de ad units: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINTS - HEALTH CHECK
# ============================================================================

@router.get("/health")
async def health_check():
    """
    Verifica status da integração AdSense

    Returns:
        Status da API e configurações
    """
    try:
        # Verificar se SA key existe
        sa_key_path = os.getenv("GOOGLE_ADSENSE_SA_KEY", "config/adsense-sa-key.json")
        sa_key_exists = os.path.exists(sa_key_path)

        # Verificar se account ID está configurado
        account_id = os.getenv("GOOGLE_ADSENSE_ACCOUNT_ID")
        account_configured = bool(account_id)

        # Tentar conexão com AdSense API
        api_connected = False
        try:
            if sa_key_exists and account_configured:
                service = get_adsense_client()
                # Teste simples de listagem
                request = service.accounts().adunits().list(
                    parent=f"accounts/{account_id}",
                    pageSize=1
                )
                request.execute()
                api_connected = True
        except Exception:
            pass

        return {
            "status": "healthy" if api_connected else "configuration_needed",
            "checks": {
                "service_account_key": sa_key_exists,
                "account_id_configured": account_configured,
                "api_connection": api_connected
            },
            "message": "AdSense API ready" if api_connected else "Configure credentials first"
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
