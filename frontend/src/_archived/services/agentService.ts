/**
 * Agent Service - NEXUS Frontend
 * ================================
 * 
 * Serviço para interagir com os 6 agentes de IA via API
 */

import API from './api'

export interface SiteAutomationRequest {
  site: string
  objetivo: string
  dry_run?: boolean
}

export interface LeadQualificationRequest {
  lead_data: Record<string, any>
  contexto_nicho?: string
}

export interface InvoiceGenerationRequest {
  sale_data: Record<string, any>
}

export interface TaskStatus {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  agent: string
  created_at: string
  completed_at?: string
  result?: any
  error?: string
}

export interface Agent {
  name: string
  description: string
  endpoint: string
}

class AgentService {
  /**
   * Listar todos os agentes disponíveis
   */
  async listAgents(): Promise<{ status: string; agents: Agent[] }> {
    const response = await API.get('/api/agents/')
    return response.data
  }

  /**
   * Executar automação web (Site Agent)
   */
  async executeSiteAutomation(
    site: string,
    objetivo: string,
    dryRun = false
  ): Promise<{ status: string; task_id: string; message: string }> {
    const response = await API.post('/api/agents/site-automation', {
      site,
      objetivo,
      dry_run: dryRun
    })
    return response.data
  }

  /**
   * Qualificar lead com IA
   */
  async qualifyLead(
    leadData: Record<string, any>,
    contextoNicho?: string
  ): Promise<{ status: string; task_id: string; message: string }> {
    const response = await API.post('/api/agents/lead-qualification', {
      lead_data: leadData,
      contexto_nicho: contextoNicho
    })
    return response.data
  }

  /**
   * Gerar instruções para emissão de NFS-e
   */
  async generateInvoice(
    saleData: Record<string, any>
  ): Promise<{ status: string; task_id: string; message: string }> {
    const response = await API.post('/api/agents/invoice', {
      sale_data: saleData
    })
    return response.data
  }

  /**
   * Executar agente genérico
   */
  async executeAgent(
    agentName: string,
    parameters: Record<string, any>
  ): Promise<{ status: string; task_id: string; agent: string; message: string }> {
    const response = await API.post('/api/agents/execute', {
      agent_name: agentName,
      parameters
    })
    return response.data
  }

  /**
   * Verificar status de uma tarefa
   */
  async getTaskStatus(taskId: string): Promise<TaskStatus> {
    const response = await API.get(`/api/agents/status/${taskId}`)
    return response.data
  }

  /**
   * Listar tarefas recentes
   */
  async listTasks(limit = 10): Promise<{ total: number; tasks: TaskStatus[] }> {
    const response = await API.get('/api/agents/tasks', {
      params: { limit }
    })
    return response.data
  }

  /**
   * Deletar tarefa
   */
  async deleteTask(taskId: string): Promise<{ status: string; message: string }> {
    const response = await API.delete(`/api/agents/tasks/${taskId}`)
    return response.data
  }

  /**
   * Poll task status até completar
   * @param taskId ID da tarefa
   * @param maxAttempts Máximo de tentativas (padrão: 30)
   * @param interval Intervalo entre checks em ms (padrão: 2000)
   */
  async pollTaskUntilComplete(
    taskId: string,
    maxAttempts = 30,
    interval = 2000
  ): Promise<TaskStatus> {
    for (let i = 0; i < maxAttempts; i++) {
      const status = await this.getTaskStatus(taskId)
      
      if (status.status === 'completed' || status.status === 'failed') {
        return status
      }
      
      await new Promise(resolve => setTimeout(resolve, interval))
    }
    
    throw new Error(`Task ${taskId} não completou em ${maxAttempts} tentativas`)
  }
}

export default new AgentService()
