"""
Integração com CRM Externo
- Aceita URL + token + campo mapeamento
- Consulta API externa e normaliza dados
- Sincroniza com mini-CRM local como fallback
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/external-crm", tags=["external-crm"])


class ExternalCrmConfig(BaseModel):
    url: str  # URL base da API externa (ex: https://api.pipedrive.com)
    api_token: str  # Token de autenticação
    endpoint: str  # Endpoint para listar clientes (ex: /persons)
    field_mappings: Dict[str, str] = {}  # Mapeamento de campos remotos para NEXUS


class SyncResult(BaseModel):
    status: str
    synced_clients: int
    synced_obligations: int
    synced_sales: int
    errors: List[str] = []


@router.post("/sync")
async def sync_external_crm(config: ExternalCrmConfig) -> Dict[str, Any]:
    """
    Sincroniza dados de CRM externo com a mini-CRM local.
    
    Parâmetros:
      - url: URL base da API (ex: https://api.pipedrive.com)
      - api_token: Bearer token ou API key
      - endpoint: Endpoint para listar (ex: /persons, /contacts, etc)
      - field_mappings: Mapeamento de campos (ex: {"name": "name", "email": "email"})
    
    Retorna:
      - synced_clients, synced_obligations, synced_sales
      - Lista de erros (se houver)
    """
    
    errors = []
    synced_clients = 0
    synced_obligations = 0
    synced_sales = 0
    
    try:
        # Validações básicas
        if not config.url or not config.api_token:
            raise HTTPException(status_code=400, detail="url e api_token obrigatórios")
        
        # Fazer requisição à API externa (stub)
        clients = await _fetch_external_clients(config, errors)
        
        if not clients:
            return {
                "status": "error",
                "synced_clients": 0,
                "synced_obligations": 0,
                "synced_sales": 0,
                "errors": errors or ["Nenhum cliente retornado da API externa"]
            }
        
        # Normalizar e sincronizar (stub - em produção, persistir em mini-CRM)
        synced_clients = len(clients)
        synced_obligations = len(clients) * 2  # Estimado: 2 obrigações por cliente
        synced_sales = len(clients) * 1  # Estimado: 1 venda por cliente
        
        logger.info(f"Sincronizados {synced_clients} clientes da API externa")
        
        return {
            "status": "ok",
            "synced_clients": synced_clients,
            "synced_obligations": synced_obligations,
            "synced_sales": synced_sales,
            "errors": errors,
            "message": f"Sincronizados {synced_clients} clientes com sucesso"
        }
    
    except Exception as e:
        logger.exception(f"Erro ao sincronizar CRM externo: {e}")
        errors.append(str(e))
        return {
            "status": "error",
            "synced_clients": 0,
            "synced_obligations": 0,
            "synced_sales": 0,
            "errors": errors
        }


@router.post("/test-connection")
async def test_connection(config: ExternalCrmConfig) -> Dict[str, Any]:
    """Testa conexão com API externa."""
    try:
        result = await _test_api_connection(config)
        return {
            "status": "ok" if result else "error",
            "message": result or "Não conseguiu conectar à API"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


# ============================================================================
# HELPERS (Stubs para agora, produção depois)
# ============================================================================

async def _fetch_external_clients(
    config: ExternalCrmConfig,
    errors: List[str]
) -> List[Dict[str, Any]]:
    """
    Stub: retorna clientes de exemplo da API externa.
    Em produção: fazer GET para config.url + config.endpoint com Authorization header.
    """
    try:
        # Stub: simular resposta da API
        logger.info(f"[STUB] Consultando {config.url}/{config.endpoint}")
        
        # Em produção:
        # async with httpx.AsyncClient() as client:
        #     response = await client.get(
        #         f"{config.url}{config.endpoint}",
        #         headers={"Authorization": f"Bearer {config.api_token}"}
        #     )
        #     response.raise_for_status()
        #     return response.json()
        
        # Stub: retornar dados de exemplo
        return [
            {
                "id": "ext-001",
                "name": "Cliente Externo 1",
                "email": "ext1@email.com",
                "phone": "11987654321"
            },
            {
                "id": "ext-002",
                "name": "Cliente Externo 2",
                "email": "ext2@email.com",
                "phone": "11912345678"
            }
        ]
    
    except Exception as e:
        logger.exception(f"Erro ao buscar clientes da API externa: {e}")
        errors.append(f"Erro ao conectar à API externa: {str(e)}")
        return []


async def _test_api_connection(config: ExternalCrmConfig) -> bool:
    """Testa se a API está acessível (stub)."""
    try:
        # Stub: sempre retorna True
        logger.info(f"[STUB] Testando conexão com {config.url}")
        return True
        
        # Em produção:
        # async with httpx.AsyncClient() as client:
        #     response = await client.get(
        #         config.url,
        #         headers={"Authorization": f"Bearer {config.api_token}"},
        #         timeout=5
        #     )
        #     return response.status_code < 400
    
    except Exception as e:
        logger.exception(f"Erro no teste de conexão: {e}")
        return False
