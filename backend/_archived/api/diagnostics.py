"""
API Router para Diagnósticos com IA
====================================

Análise de problemas empresariais usando OpenAI
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime
import os

try:
    from openai import OpenAI
    openai_available = True
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
except ImportError:
    openai_available = False
    logging.warning("OpenAI não disponível")

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])
logger = logging.getLogger(__name__)

# Storage temporário de diagnósticos
diagnostics_storage: Dict[str, Dict[str, Any]] = {}


# ==================== MODELS ====================

class DiagnosticRequest(BaseModel):
    problem: str = Field(..., description="Descrição do problema")
    context: Optional[str] = Field(None, description="Contexto adicional")
    industry: Optional[str] = Field(None, description="Indústria/setor")


class DiagnosticResponse(BaseModel):
    diagnostic_id: str
    problem: str
    root_causes: List[str]
    solutions: List[Dict[str, str]]
    next_steps: List[str]
    created_at: str


# ==================== ENDPOINTS ====================

@router.post("/analyze")
async def analyze_problem(request: DiagnosticRequest) -> DiagnosticResponse:
    """Analisar problema com IA e retornar diagnóstico"""
    if not openai_available or not os.getenv('OPENAI_API_KEY'):
        raise HTTPException(
            status_code=503,
            detail="OpenAI não configurado. Adicione OPENAI_API_KEY ao .env"
        )
    
    try:
        # Construir prompt
        system_prompt = """Você é um consultor empresarial especializado em análise de problemas.
        
Sua tarefa é:
1. Identificar as causas raiz do problema
2. Propor soluções priorizadas
3. Sugerir próximos passos práticos

Responda em formato JSON estruturado."""

        user_prompt = f"""Problema: {request.problem}

Contexto: {request.context or 'Não fornecido'}
Indústria: {request.industry or 'Geral'}

Analise e forneça:
1. root_causes: lista de causas raiz (3-5 itens)
2. solutions: lista de objetos {{title, description, priority}} (3-5 soluções)
3. next_steps: lista de ações práticas (3-5 passos)"""

        # Chamar OpenAI
        response = client.chat.completions.create(
            model=os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        # Parsear resposta
        analysis_text = response.choices[0].message.content
        
        # Tentar extrair JSON da resposta
        import json
        import re
        
        # Type guard para analysis_text
        if analysis_text is None:
            analysis_text = "{}"
        
        # Procurar por JSON na resposta
        json_match = re.search(r'\{[\s\S]*\}', analysis_text)
        if json_match:
            analysis_data = json.loads(json_match.group())
        else:
            # Fallback: criar estrutura básica
            analysis_data = {
                "root_causes": ["Análise em andamento"],
                "solutions": [{"title": "Solução", "description": analysis_text, "priority": "high"}],
                "next_steps": ["Revisar análise completa"]
            }
        
        # Criar diagnóstico
        diagnostic_id = f"diag_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        diagnostic = {
            "diagnostic_id": diagnostic_id,
            "problem": request.problem,
            "root_causes": analysis_data.get("root_causes", []),
            "solutions": analysis_data.get("solutions", []),
            "next_steps": analysis_data.get("next_steps", []),
            "created_at": datetime.now().isoformat()
        }
        
        # Armazenar
        diagnostics_storage[diagnostic_id] = diagnostic
        
        return DiagnosticResponse(**diagnostic)
        
    except Exception as e:
        logger.exception(f"Erro ao analisar problema: {e}")
        raise HTTPException(status_code=500, detail=f"Erro na análise: {str(e)}")


@router.get("/history")
async def get_history(limit: int = 10):
    """Obter histórico de diagnósticos"""
    diagnostics = list(diagnostics_storage.values())
    diagnostics.sort(key=lambda x: x["created_at"], reverse=True)
    return {
        "total": len(diagnostics),
        "diagnostics": diagnostics[:limit]
    }


@router.get("/{diagnostic_id}")
async def get_diagnostic(diagnostic_id: str):
    """Obter detalhes de um diagnóstico específico"""
    if diagnostic_id not in diagnostics_storage:
        raise HTTPException(status_code=404, detail="Diagnóstico não encontrado")
    
    return diagnostics_storage[diagnostic_id]


@router.delete("/{diagnostic_id}")
async def delete_diagnostic(diagnostic_id: str):
    """Deletar diagnóstico"""
    if diagnostic_id in diagnostics_storage:
        del diagnostics_storage[diagnostic_id]
        return {"status": "ok", "message": f"Diagnóstico {diagnostic_id} removido"}
    raise HTTPException(status_code=404, detail="Diagnóstico não encontrado")

