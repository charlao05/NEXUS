import React, { useState, useEffect } from 'react'
import diagnosticService, { DiagnosticResponse, Solution } from '../services/diagnosticService'
import './DiagnosticsPage.css'

const DiagnosticsPage: React.FC = () => {
  const [problem, setProblem] = useState('')
  const [context, setContext] = useState('')
  const [industry, setIndustry] = useState('')
  const [loading, setLoading] = useState(false)
  const [currentDiagnostic, setCurrentDiagnostic] = useState<DiagnosticResponse | null>(null)
  const [history, setHistory] = useState<DiagnosticResponse[]>([])

  useEffect(() => {
    loadHistory()
  }, [])

  const loadHistory = async () => {
    try {
      const response = await diagnosticService.getHistory(10)
      setHistory(response.diagnostics)
    } catch (error) {
      console.error('Erro ao carregar histórico:', error)
    }
  }

  const handleAnalyze = async () => {
    if (!problem.trim()) {
      alert('Por favor, descreva o problema')
      return
    }

    setLoading(true)
    try {
      const response = await diagnosticService.analyzeProblem(
        problem,
        context || undefined,
        industry || undefined
      )
      setCurrentDiagnostic(response)
      loadHistory() // Atualizar histórico
    } catch (error: any) {
      alert(`Erro: ${error.response?.data?.detail || error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleClear = () => {
    setProblem('')
    setContext('')
    setIndustry('')
    setCurrentDiagnostic(null)
  }

  const getPriorityBadge = (priority: string) => {
    const colors: Record<string, string> = {
      'Alta': 'priority-high',
      'Média': 'priority-medium',
      'Baixa': 'priority-low'
    }
    return <span className={`priority-badge ${colors[priority] || 'priority-medium'}`}>{priority}</span>
  }

  return (
    <div className="diagnostics-page">
      <header className="page-header">
        <h1>🔍 Diagnóstico Inteligente</h1>
        <p>Análise de problemas com IA para decisões estratégicas</p>
      </header>

      <div className="diagnostics-container">
        <section className="input-section">
          <h2>Descreva seu problema</h2>
          
          <div className="form-group">
            <label>Problema Principal *</label>
            <textarea
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              placeholder="Ex: Minhas vendas caíram recentemente"
              rows={4}
            />
          </div>

          <div className="form-group">
            <label>Contexto Adicional</label>
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="Ex: Sou MEI no ramo de consultoria, trabalho com B2B"
              rows={3}
            />
          </div>

          <div className="form-group">
            <label>Setor/Indústria</label>
            <input
              type="text"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              placeholder="Ex: Consultoria, E-commerce, Serviços"
            />
          </div>

          <div className="form-actions">
            <button 
              onClick={handleAnalyze} 
              disabled={loading}
              className="btn-primary"
            >
              {loading ? '🔄 Analisando...' : '🚀 Analisar'}
            </button>
            <button onClick={handleClear} className="btn-secondary">
              Limpar
            </button>
          </div>
        </section>

        {currentDiagnostic && (
          <section className="results-section">
            <h2>📊 Resultado da Análise</h2>
            
            <div className="result-card">
              <h3>Problema Analisado</h3>
              <p className="problem-text">{currentDiagnostic.problem}</p>
            </div>

            <div className="result-card">
              <h3>🎯 Causas Raiz Identificadas</h3>
              <ul className="causes-list">
                {currentDiagnostic.root_causes.map((cause, index) => (
                  <li key={index}>{cause}</li>
                ))}
              </ul>
            </div>

            <div className="result-card">
              <h3>💡 Soluções Recomendadas</h3>
              <div className="solutions-grid">
                {currentDiagnostic.solutions.map((solution: Solution, index) => (
                  <div key={index} className="solution-item">
                    <div className="solution-header">
                      <h4>{solution.title}</h4>
                      {getPriorityBadge(solution.priority)}
                    </div>
                    <p>{solution.description}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="result-card">
              <h3>📋 Próximos Passos</h3>
              <ol className="next-steps-list">
                {currentDiagnostic.next_steps.map((step, index) => (
                  <li key={index}>{step}</li>
                ))}
              </ol>
            </div>

            <div className="result-meta">
              <small>ID: {currentDiagnostic.diagnostic_id}</small>
              <small>Criado: {new Date(currentDiagnostic.created_at).toLocaleString('pt-BR')}</small>
            </div>
          </section>
        )}

        <section className="history-section">
          <h2>📜 Histórico de Diagnósticos</h2>
          
          {history.length === 0 ? (
            <p>Nenhum diagnóstico no histórico.</p>
          ) : (
            <div className="history-list">
              {history.map(diagnostic => (
                <div key={diagnostic.diagnostic_id} className="history-item">
                  <div className="history-header">
                    <strong>{diagnostic.problem}</strong>
                    <small>{new Date(diagnostic.created_at).toLocaleString('pt-BR')}</small>
                  </div>
                  <div className="history-summary">
                    <span>{diagnostic.root_causes.length} causas</span>
                    <span>{diagnostic.solutions.length} soluções</span>
                    <button 
                      onClick={() => setCurrentDiagnostic(diagnostic)}
                      className="btn-view"
                    >
                      Ver detalhes
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

export default DiagnosticsPage
