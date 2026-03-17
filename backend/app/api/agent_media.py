"""
NEXUS - Agent Media Endpoints
==============================
Endpoints para processamento de mídia nos agentes:

1. POST /api/agents/audio/transcribe  — Transcreve áudio (Whisper) + envia pro agente
2. POST /api/agents/upload             — Upload de arquivos/imagens + processa com agente

Fluxo:
  Frontend grava áudio / seleciona arquivo
  → POST com FormData (multipart)
  → Backend transcreve (Whisper) ou descreve (Vision)
  → Texto resultante é enviado como mensagem ao agente via get_llm_response
  → Retorna resposta do agente ao frontend
"""

import os
import io
import base64
import logging
import tempfile
from typing import Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException

from app.api.auth import get_current_user  # type: ignore[import]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents-media"])

# Limites de tamanho
MAX_AUDIO_SIZE = 25 * 1024 * 1024   # 25 MB (limite do Whisper)
MAX_FILE_SIZE  = 20 * 1024 * 1024   # 20 MB
ALLOWED_AUDIO  = {"audio/webm", "audio/mp4", "audio/mpeg", "audio/ogg", "audio/wav", "audio/x-m4a"}
ALLOWED_IMAGE  = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_DOC    = {
    "application/pdf",
    "text/plain", "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _get_openai_raw():
    """Retorna cliente OpenAI cru (não o wrapper) para chamadas diretas (Whisper, Vision)."""
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key or api_key.startswith("sk-proj-test"):
            return None
        return OpenAI(api_key=api_key)
    except Exception as e:
        logger.warning(f"OpenAI client raw não disponível: {e}")
        return None


# ============================================================================
# 1. TRANSCRIÇÃO DE ÁUDIO (Whisper)
# ============================================================================

@router.post("/audio/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    agent: str = Form("assistente"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    Recebe áudio gravado pelo frontend, transcreve via Whisper,
    e envia o texto transcrito como mensagem para o agente.

    Retorna: { transcription, message, agent_id }
    """
    # Validar tipo
    content_type = audio.content_type or ""
    if content_type not in ALLOWED_AUDIO and not content_type.startswith("audio/"):
        raise HTTPException(400, f"Tipo de arquivo não suportado: {content_type}. Envie um áudio.")

    # Ler conteúdo
    content = await audio.read()
    if len(content) > MAX_AUDIO_SIZE:
        raise HTTPException(413, "Áudio muito grande. Limite: 25 MB.")
    if len(content) < 1000:
        raise HTTPException(400, "Áudio muito curto. Grave pelo menos 1 segundo.")

    # Transcrever via Whisper
    client = _get_openai_raw()
    if not client:
        raise HTTPException(503, "Serviço de transcrição indisponível. Configure OPENAI_API_KEY.")

    transcription_text = ""
    try:
        # Whisper aceita file-like objects com nome
        # Usar extensão correta baseada no content type
        ext_map = {
            "audio/webm": "webm", "audio/mp4": "mp4", "audio/mpeg": "mp3",
            "audio/ogg": "ogg", "audio/wav": "wav", "audio/x-m4a": "m4a",
        }
        ext = ext_map.get(content_type, "webm")
        filename = f"audio.{ext}"

        # Criar arquivo temporário para o Whisper
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as audio_file:
                result = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="pt",
                    response_format="text",
                )
            transcription_text = result.strip() if isinstance(result, str) else str(result).strip()
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"Erro na transcrição Whisper: {e}")
        raise HTTPException(500, "Erro ao transcrever áudio. Tente novamente.")

    if not transcription_text:
        return {
            "status": "success",
            "agent_id": agent,
            "transcription": "",
            "message": "Não consegui entender o áudio. Pode tentar de novo ou digitar o que você disse?"
        }

    # Enviar texto transcrito para o agente
    agent_response = ""
    try:
        from app.api.agent_chat import get_llm_response

        # Carregar histórico
        chat_history: list[dict] = []
        try:
            from database.models import ChatMessage, SessionLocal
            db = SessionLocal()
            try:
                recent = (
                    db.query(ChatMessage)
                    .filter(ChatMessage.agent_id == agent)
                    .order_by(ChatMessage.created_at.desc())
                    .limit(10)
                    .all()
                )
                chat_history = [{"role": m.role, "content": m.content} for m in reversed(recent)]
            finally:
                db.close()
        except Exception:
            pass

        agent_response = await get_llm_response(agent, transcription_text, history=chat_history)

        # Salvar no histórico
        if agent_response:
            try:
                from database.models import ChatMessage as CM, SessionLocal as SL
                db = SL()
                try:
                    db.add(CM(user_id=0, agent_id=agent, role="user", content=f"[áudio] {transcription_text}"))
                    db.add(CM(user_id=0, agent_id=agent, role="assistant", content=agent_response))
                    db.commit()
                finally:
                    db.close()
            except Exception:
                pass

    except Exception as e:
        logger.warning(f"Erro ao processar com agente: {e}")
        agent_response = f"Entendi o que você disse: \"{transcription_text}\"\n\nMas tive um problema ao processar. Pode repetir ou digitar?"

    return {
        "status": "success",
        "agent_id": agent,
        "transcription": transcription_text,
        "message": agent_response or f"Você disse: \"{transcription_text}\"\n\nProcessando sua solicitação..."
    }


# ============================================================================
# 2. UPLOAD DE ARQUIVOS / IMAGENS
# ============================================================================

@router.post("/upload")
async def upload_and_process(
    agent: str = Form("assistente"),
    message: str = Form(""),
    files: list[UploadFile] = File(...),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """
    Recebe arquivos (imagens, PDFs, docs) do frontend.
    - Imagens: descreve via GPT-4.1 Vision
    - Documentos: extrai texto e envia ao agente
    
    Retorna: { message, files_processed, agent_id }
    """
    if not files:
        raise HTTPException(400, "Nenhum arquivo enviado.")

    processed_files = []
    extracted_texts = []

    client = _get_openai_raw()

    for f in files:
        content = await f.read()
        if len(content) > MAX_FILE_SIZE:
            processed_files.append({"name": f.filename, "status": "error", "detail": "Arquivo muito grande (max 20MB)"})
            continue

        content_type = f.content_type or ""
        filename = f.filename or "arquivo"

        # ── IMAGEM → Vision API ─────────────────────────────────
        if content_type in ALLOWED_IMAGE or content_type.startswith("image/"):
            if client:
                try:
                    b64 = base64.b64encode(content).decode("utf-8")
                    vision_prompt = message or "Descreva o que você vê nesta imagem. Se for um documento, extraia o texto."

                    response = client.chat.completions.create(
                        model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": vision_prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{b64}"}},
                                ],
                            }
                        ],
                        max_tokens=800,
                    )
                    description = response.choices[0].message.content or "Imagem processada."
                    extracted_texts.append(f"[Imagem: {filename}]\n{description}")
                    processed_files.append({"name": filename, "status": "ok", "type": "image", "description": description[:200]})
                except Exception as e:
                    logger.error(f"Erro Vision API para {filename}: {e}")
                    extracted_texts.append(f"[Imagem: {filename}] Não consegui analisar a imagem.")
                    processed_files.append({"name": filename, "status": "error", "detail": "Erro ao processar imagem"})
            else:
                extracted_texts.append(f"[Imagem: {filename}] Recebi a imagem mas o serviço de visão não está disponível.")
                processed_files.append({"name": filename, "status": "no_vision", "type": "image"})

        # ── TEXTO PLANO / CSV ───────────────────────────────────
        elif content_type in ("text/plain", "text/csv"):
            try:
                text = content.decode("utf-8", errors="replace")[:5000]
                extracted_texts.append(f"[Arquivo: {filename}]\n{text}")
                processed_files.append({"name": filename, "status": "ok", "type": "text"})
            except Exception:
                processed_files.append({"name": filename, "status": "error", "detail": "Não consegui ler o texto"})

        # ── PDF ─────────────────────────────────────────────────
        elif content_type == "application/pdf":
            try:
                # Tentar extrair texto do PDF
                text = _extract_pdf_text(content)
                if text:
                    extracted_texts.append(f"[PDF: {filename}]\n{text[:5000]}")
                    processed_files.append({"name": filename, "status": "ok", "type": "pdf"})
                else:
                    extracted_texts.append(f"[PDF: {filename}] Não consegui extrair texto (pode ser um PDF de imagem).")
                    processed_files.append({"name": filename, "status": "partial", "type": "pdf", "detail": "Sem texto extraível"})
            except Exception as e:
                extracted_texts.append(f"[PDF: {filename}] Erro ao processar.")
                processed_files.append({"name": filename, "status": "error", "detail": str(e)[:100]})

        # ── OUTROS DOCUMENTOS ───────────────────────────────────
        elif content_type in ALLOWED_DOC:
            extracted_texts.append(f"[Documento: {filename}] Recebi o arquivo ({content_type}). Para análise completa, envie em formato texto ou PDF.")
            processed_files.append({"name": filename, "status": "ok", "type": "document"})

        else:
            processed_files.append({"name": filename, "status": "unsupported", "detail": f"Tipo não suportado: {content_type}"})

    # Montar contexto e enviar ao agente
    context_parts = []
    if message:
        context_parts.append(f"Mensagem do usuário: {message}")
    if extracted_texts:
        context_parts.append("Conteúdo dos arquivos enviados:\n" + "\n\n".join(extracted_texts))

    full_context = "\n\n".join(context_parts) if context_parts else "O usuário enviou arquivos sem mensagem adicional."

    # Enviar ao agente
    agent_response = ""
    try:
        from app.api.agent_chat import get_llm_response

        chat_history: list[dict] = []
        try:
            from database.models import ChatMessage, SessionLocal
            db = SessionLocal()
            try:
                recent = (
                    db.query(ChatMessage)
                    .filter(ChatMessage.agent_id == agent)
                    .order_by(ChatMessage.created_at.desc())
                    .limit(10)
                    .all()
                )
                chat_history = [{"role": m.role, "content": m.content} for m in reversed(recent)]
            finally:
                db.close()
        except Exception:
            pass

        agent_response = await get_llm_response(agent, full_context, history=chat_history)

        # Salvar histórico
        if agent_response:
            try:
                from database.models import ChatMessage as CM, SessionLocal as SL
                db = SL()
                try:
                    file_names = ", ".join(f.filename or "arquivo" for f in files)
                    db.add(CM(user_id=0, agent_id=agent, role="user", content=f"[upload: {file_names}] {message}"))
                    db.add(CM(user_id=0, agent_id=agent, role="assistant", content=agent_response))
                    db.commit()
                finally:
                    db.close()
            except Exception:
                pass

    except Exception as e:
        logger.warning(f"Erro ao processar upload com agente: {e}")

    # Fallback se agente não respondeu
    if not agent_response:
        file_summary = ", ".join(pf["name"] for pf in processed_files)
        agent_response = f"Recebi seus arquivos ({file_summary})! 📎\n\n"
        if extracted_texts:
            agent_response += "Consegui ler o conteúdo. Me diga o que você gostaria que eu fizesse com essas informações."
        else:
            agent_response += "Me conte mais sobre o que precisa que eu faça com esses arquivos."

    return {
        "status": "success",
        "agent_id": agent,
        "message": agent_response,
        "files_processed": processed_files,
    }


# ============================================================================
# HELPERS
# ============================================================================

def _extract_pdf_text(content: bytes) -> str:
    """Tenta extrair texto de um PDF. Retorna string vazia se falhar."""
    # Tentar PyMuPDF (fitz) primeiro — mais completo
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=content, filetype="pdf")
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return "\n".join(text_parts).strip()
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        text_parts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
        return "\n".join(text_parts).strip()
    except ImportError:
        pass
    except Exception:
        pass

    return ""
