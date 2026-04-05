"""Rotas API para LLM/OpenAI"""
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# Import com fallback para execução direta ou como pacote
try:
    from ..services.llm_service import get_llm_service, LLMService
except ImportError:
    from services.llm_service import get_llm_service, LLMService  # type: ignore

router = APIRouter(prefix="/api/llm", tags=["LLM"])
llm_service: LLMService = get_llm_service()  # type: ignore[assignment]

class ChatRequest(BaseModel):
    mensagem: str
    historico: Optional[List[Any]] = None  # type: ignore

class AgendamentoRequest(BaseModel):
    texto: str
    contexto: Optional[str] = None

@router.post("/chat")
async def chat(request: ChatRequest) -> Dict[str, Any]:
    """Endpoint de chat conversacional"""
    try:
        # Garantir que historico seja convertido para o tipo correto
        historico = request.historico if request.historico else []
        resposta = llm_service.gerar_resposta_chat(request.mensagem, historico)  # type: ignore
        return {"resposta": resposta, "sucesso": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agendar")
async def agendar(request: AgendamentoRequest) -> Dict[str, Any]:
    """Endpoint para processar agendamentos"""
    try:
        resultado = llm_service.processar_agendamento(request.texto, request.contexto)
        return {"dados": resultado, "sucesso": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sentimento")
async def sentimento(texto: str = Body(..., embed=True)) -> Dict[str, Any]:
    """Endpoint para análise de sentimento"""
    try:
        resultado = llm_service.analisar_sentimento(texto)
        return {"sentimento": resultado, "sucesso": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health():
    """Health check"""
    return {"status": "ok", "provider": "openai"}
