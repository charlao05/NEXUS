"""
API Router para Gerenciamento de Filas
=======================================

Gerenciar a fila de prioridades de tarefas dos agentes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging

try:
    import sys
    from pathlib import Path
    backend_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(backend_dir))
    
    from core.agent_queue import AgentQueue, TaskPriority, create_deadline
    QUEUE_AVAILABLE = True
    # Instância global da fila
    agent_queue = AgentQueue(max_size=1000)
except ImportError as e:
    QUEUE_AVAILABLE = False
    logging.warning(f"Agent Queue não disponível: {e}")

router = APIRouter(prefix="/api/queue", tags=["queue"])
logger = logging.getLogger(__name__)


# ==================== MODELS ====================

class PushTaskRequest(BaseModel):
    priority: int = Field(..., ge=1, le=5, description="Prioridade: 1=CRITICAL, 5=DEFERRED")
    days_ahead: int = Field(default=1, description="Dias até deadline")
    cost: int = Field(default=1, description="Custo computacional")
    agent_name: str = Field(..., description="Nome do agente")
    client_id: str = Field(..., description="ID do cliente")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Dados da tarefa")


# ==================== ENDPOINTS ====================

@router.get("/")
async def queue_info():
    """Informações sobre a fila"""
    if not QUEUE_AVAILABLE:
        return {
            "status": "unavailable",
            "message": "Sistema de filas não disponível"
        }
    
    return {
        "status": "available",
        "description": "Sistema de fila de prioridades para agentes",
        "endpoints": {
            "stats": "/api/queue/stats",
            "tasks": "/api/queue/tasks",
            "push": "/api/queue/push",
            "process": "/api/queue/process",
            "clear": "/api/queue/clear"
        }
    }


@router.get("/stats")
async def get_stats():
    """Obter estatísticas da fila"""
    if not QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Sistema de filas não disponível")
    
    stats = agent_queue.get_stats()
    return {
        "status": "ok",
        "stats": stats,
        "summary": agent_queue.print_stats()
    }


@router.get("/tasks")
async def list_tasks():
    """Listar todas as tarefas na fila"""
    if not QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Sistema de filas não disponível")
    
    tasks = agent_queue.get_all_tasks()
    
    return {
        "status": "ok",
        "total": len(tasks),
        "tasks": [
            {
                "task_id": task.task_id,
                "priority": task.priority,
                "agent_name": task.agent_name,
                "client_id": task.client_id,
                "deadline": datetime.fromtimestamp(task.deadline).isoformat(),
                "cost": task.cost,
                "is_overdue": task.is_overdue(),
                "seconds_until_deadline": task.seconds_until_deadline()
            }
            for task in tasks
        ]
    }


@router.post("/push")
async def push_task(request: PushTaskRequest):
    """Adicionar tarefa à fila"""
    if not QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Sistema de filas não disponível")
    
    try:
        deadline = create_deadline(days_ahead=request.days_ahead)
        
        task_id = agent_queue.push(
            priority=request.priority,
            deadline=deadline,
            cost=request.cost,
            agent_name=request.agent_name,
            client_id=request.client_id,
            payload=request.payload
        )
        
        if task_id is None:
            raise HTTPException(status_code=507, detail="Fila cheia")
        
        return {
            "status": "ok",
            "task_id": task_id,
            "message": f"Tarefa adicionada: {task_id}",
            "deadline": deadline.isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Erro ao adicionar tarefa: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process")
async def process_tasks(count: int = 1):
    """Processar N tarefas da fila"""
    if not QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Sistema de filas não disponível")
    
    if agent_queue.is_empty():
        return {
            "status": "ok",
            "message": "Fila vazia",
            "processed": 0
        }
    
    processed = []
    for i in range(count):
        task = agent_queue.pop()
        if task is None:
            break
        
        processed.append({
            "task_id": task.task_id,
            "agent_name": task.agent_name,
            "client_id": task.client_id,
            "was_overdue": task.is_overdue()
        })
    
    return {
        "status": "ok",
        "processed": len(processed),
        "tasks": processed
    }


@router.delete("/clear")
async def clear_queue():
    """Limpar toda a fila"""
    if not QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Sistema de filas não disponível")
    
    size_before = agent_queue.size()
    agent_queue.clear()
    
    return {
        "status": "ok",
        "message": f"Fila limpa ({size_before} tarefas removidas)",
        "removed": size_before
    }


@router.get("/peek")
async def peek_next():
    """Ver próxima tarefa sem remover"""
    if not QUEUE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Sistema de filas não disponível")
    
    task = agent_queue.peek()
    if task is None:
        return {"status": "empty", "message": "Fila vazia"}
    
    return {
        "status": "ok",
        "next_task": {
            "task_id": task.task_id,
            "priority": task.priority,
            "agent_name": task.agent_name,
            "client_id": task.client_id,
            "deadline": datetime.fromtimestamp(task.deadline).isoformat(),
            "is_overdue": task.is_overdue()
        }
    }
