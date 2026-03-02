/**
 * Queue Service - NEXUS Frontend
 * ===============================
 * 
 * Serviço para gerenciar a fila de prioridades de agentes
 */

import API from './api'

export interface QueueTask {
  task_id: string
  priority: number
  agent_name: string
  client_id: string
  deadline: string
  cost: number
  is_overdue: boolean
  seconds_until_deadline: number
}

export interface QueueStats {
  total_pushed: number
  total_popped: number
  total_rejected: number
  size_atual: number
  max_size: number | null
}

export interface PushTaskRequest {
  priority: number  // 1-5
  days_ahead?: number
  cost?: number
  agent_name: string
  client_id: string
  payload?: Record<string, any>
}

class QueueService {
  /**
   * Obter informações da fila
   */
  async getInfo(): Promise<{ status: string; description: string; endpoints: Record<string, string> }> {
    const response = await API.get('/api/queue/')
    return response.data
  }

  /**
   * Obter estatísticas da fila
   */
  async getStats(): Promise<{ status: string; stats: QueueStats; summary: string }> {
    const response = await API.get('/api/queue/stats')
    return response.data
  }

  /**
   * Listar tarefas na fila
   */
  async listTasks(): Promise<{ status: string; total: number; tasks: QueueTask[] }> {
    const response = await API.get('/api/queue/tasks')
    return response.data
  }

  /**
   * Adicionar tarefa à fila
   */
  async pushTask(request: PushTaskRequest): Promise<{ status: string; task_id: string; message: string; deadline: string }> {
    const response = await API.post('/api/queue/push', request)
    return response.data
  }

  /**
   * Processar N tarefas da fila
   */
  async processTasks(count = 1): Promise<{ status: string; processed: number; tasks: any[] }> {
    const response = await API.post('/api/queue/process', null, {
      params: { count }
    })
    return response.data
  }

  /**
   * Limpar toda a fila
   */
  async clearQueue(): Promise<{ status: string; message: string; removed: number }> {
    const response = await API.delete('/api/queue/clear')
    return response.data
  }

  /**
   * Ver próxima tarefa sem remover
   */
  async peekNext(): Promise<{ status: string; next_task?: QueueTask; message?: string }> {
    const response = await API.get('/api/queue/peek')
    return response.data
  }
}

export default new QueueService()
