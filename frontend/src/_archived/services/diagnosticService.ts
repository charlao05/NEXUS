/**
 * Diagnostic Service - NEXUS Frontend
 * ====================================
 * 
 * Serviço para análise de problemas com IA (OpenAI)
 */

import API from './api'

export interface DiagnosticRequest {
  problem: string
  context?: string
  industry?: string
}

export interface Solution {
  title: string
  description: string
  priority: string
}

export interface DiagnosticResponse {
  diagnostic_id: string
  problem: string
  root_causes: string[]
  solutions: Solution[]
  next_steps: string[]
  created_at: string
}

class DiagnosticService {
  /**
   * Analisar problema com IA
   */
  async analyzeProblem(
    problem: string,
    context?: string,
    industry?: string
  ): Promise<DiagnosticResponse> {
    const response = await API.post('/api/diagnostics/analyze', {
      problem,
      context,
      industry
    })
    return response.data
  }

  /**
   * Obter histórico de diagnósticos
   */
  async getHistory(limit = 10): Promise<{ total: number; diagnostics: DiagnosticResponse[] }> {
    const response = await API.get('/api/diagnostics/history', {
      params: { limit }
    })
    return response.data
  }

  /**
   * Obter detalhes de um diagnóstico específico
   */
  async getDiagnostic(diagnosticId: string): Promise<DiagnosticResponse> {
    const response = await API.get(`/api/diagnostics/${diagnosticId}`)
    return response.data
  }

  /**
   * Deletar diagnóstico
   */
  async deleteDiagnostic(diagnosticId: string): Promise<{ status: string; message: string }> {
    const response = await API.delete(`/api/diagnostics/${diagnosticId}`)
    return response.data
  }
}

export default new DiagnosticService()
