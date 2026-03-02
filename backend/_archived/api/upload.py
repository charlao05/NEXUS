"""
Upload e Processamento de Documentos (OCR stub)
- Recebe arquivo (foto/PDF em base64 ou multipart)
- Extrai dados estruturados (OCR stub → retorna dados de exemplo)
- Retorna JSON para pré-visualização/edição
"""
from __future__ import annotations

import base64
import json
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/upload", tags=["upload"])


class DocumentProcessRequest(BaseModel):
    document_type: str  # "obligation", "sale", "invoice", "customer"
    file_base64: Optional[str] = None  # base64 do arquivo


class DocumentProcessResponse(BaseModel):
    status: str
    extracted_data: Dict[str, Any]
    confidence: float
    message: str


@router.post("/process")
async def process_document(request: DocumentProcessRequest) -> Dict[str, Any]:
    """
    Processa um documento (foto/PDF) e extrai dados.
    
    Por enquanto: stub que retorna dados de exemplo.
    Em produção: integrar com Tesseract, AWS Textract ou Google Vision.
    """
    if not request.file_base64:
        raise HTTPException(status_code=400, detail="file_base64 obrigatório")

    doc_type = request.document_type.lower()
    
    # Stub: simular OCR retornando dados de exemplo (em produção, chamar Tesseract/Vision)
    extracted = _extract_stub(doc_type)
    
    return {
        "status": "ok",
        "extracted_data": extracted,
        "confidence": 0.85,  # stub: sempre 85%
        "message": f"Documento do tipo '{doc_type}' processado com sucesso (stub OCR)."
    }


@router.post("/multipart")
async def process_document_multipart(
    document_type: str = Form(...),
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    """
    Processa documento via upload multipart.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Arquivo obrigatório")
    
    # Ler arquivo
    content = await file.read()
    file_base64 = base64.b64encode(content).decode('utf-8')
    
    # Processar
    return await process_document(DocumentProcessRequest(
        document_type=document_type,
        file_base64=file_base64
    ))


def _extract_stub(doc_type: str) -> Dict[str, Any]:
    """Retorna dados de exemplo por tipo de documento (stub OCR)."""
    
    if doc_type == "obligation":
        return {
            "id": "OBL-001",
            "name": "DAS - Janeiro",
            "type": "DAS",
            "due_date": "2026-01-20",
            "estimated_value": 80.50,
            "priority": "high",
            "notes": "Extraído via OCR"
        }
    
    elif doc_type == "sale":
        return {
            "id": "SALE-001",
            "cliente_nome": "João Silva Santos",
            "valor_total": 1250.00,
            "descricao_servicos": "Serviço de consultoria",
            "data_venda": "2025-12-28",
            "client_email": "joao@email.com"
        }
    
    elif doc_type == "invoice":
        return {
            "id": "NFS-001",
            "cliente_nome": "Maria Oliveira",
            "valor_total": 3500.00,
            "descricao_servicos": "Manutenção preventiva",
            "data_venda": "2025-12-25",
            "serie": "001",
            "numero": "12345"
        }
    
    elif doc_type == "customer":
        return {
            "name": "Empresa XYZ Ltda",
            "email": "contato@empresa.com",
            "phone": "11999999999",
            "cnpj_cpf": "12.345.678/0001-90",
            "address": "Rua Principal, 123 - SP"
        }
    
    else:
        return {
            "type": "unknown",
            "confidence_note": "Tipo de documento não reconhecido. Retornando estrutura padrão."
        }
