import axios from 'axios'

const API_BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000'

interface DiagnosisRequest {
  challenge: string
}

interface DiagnosisResponse {
  user_id?: number
  challenge: string
  analysis: {
    title: string
    summary: string
    root_causes: string[]
    solutions: Array<{
      title: string
      description: string
      relevance: number
      effort?: string
    }>
    next_steps: string[]
    urgency: 'crítico' | 'alto' | 'médio' | 'baixo'
  }
  status: 'completed' | 'processing' | 'failed'
  id?: string
}

/**
 * Analisar problema com IA
 * @param challenge Descrição do desafio
 * @param token Token JWT de autenticação
 * @returns Análise estruturada
 */
export async function analyzeWithAI(
  challenge: string,
  token: string
): Promise<DiagnosisResponse> {
  try {
    const response = await axios.post(
      \\/api/diagnosis/diagnosis\,
      { problem: challenge },
      {
        headers: {
          Authorization: \Bearer \\,
          'Content-Type': 'application/json',
        },
        timeout: 60000, // 60 segundos
      }
    )

    // Normaliza resposta: backend pode retornar analysis como string (mock)
    const data = response.data
    if (typeof data.analysis === 'string') {
      return {
        challenge,
        analysis: {
          title: data.analysis,
          summary: data.analysis,
          root_causes: [],
          solutions: [],
          next_steps: [],
          urgency: 'médio',
        },
        status: data.status || 'completed',
        id: data.id,
      }
    }
    
    return data
  } catch (error: any) {
    const message = error.response?.data?.detail || 'Erro ao analisar'
    throw new Error(message)
  }
}

/**
 * Verificar saúde do serviço de diagnóstico
 */
export async function checkDiagnosisHealth() {
  try {
    const response = await axios.get(\\/api/diagnosis/health\)
    return response.data
  } catch (error) {
    return null
  }
}
