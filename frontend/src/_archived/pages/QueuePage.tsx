import React, { useState, useEffect } from 'react'
import queueService, { QueueTask, QueueStats, PushTaskRequest } from '../services/queueService'
import './QueuePage.css'

const QueuePage: React.FC = () => {
  const [stats, setStats] = useState<QueueStats | null>(null)
  const [tasks, setTasks] = useState<QueueTask[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [newTask, setNewTask] = useState<PushTaskRequest>({
    priority: 3,
    days_ahead: 1,
    cost: 1,
    agent_name: '',
    client_id: '',
    payload: {}
  })

  useEffect(() => {
    loadQueueData()
    const interval = setInterval(loadQueueData, 3000) // refresh a cada 3s
    return () => clearInterval(interval)
  }, [])

  const loadQueueData = async () => {
    try {
      const [statsRes, tasksRes] = await Promise.all([
        queueService.getStats(),
        queueService.listTasks()
      ])
      setStats(statsRes.stats)
      setTasks(tasksRes.tasks)
      setLoading(false)
    } catch (error) {
      console.error('Erro ao carregar dados da fila:', error)
      setLoading(false)
    }
  }

  const handleProcessTasks = async (count: number) => {
    try {
      const response = await queueService.processTasks(count)
      alert(`✅ ${response.processed} tarefa(s) processada(s)`)
      loadQueueData()
    } catch (error: any) {
      alert(`Erro: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleClearQueue = async () => {
    if (!confirm('⚠️ Tem certeza que deseja limpar TODA a fila?')) return

    try {
      const response = await queueService.clearQueue()
      alert(`✅ ${response.removed} tarefa(s) removida(s)`)
      loadQueueData()
    } catch (error: any) {
      alert(`Erro: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleAddTask = async () => {
    if (!newTask.agent_name || !newTask.client_id) {
      alert('Por favor, preencha agent_name e client_id')
      return
    }

    try {
      const response = await queueService.pushTask(newTask)
      alert(`✅ Tarefa criada: ${response.task_id}`)
      setShowAddModal(false)
      setNewTask({
        priority: 3,
        days_ahead: 1,
        cost: 1,
        agent_name: '',
        client_id: '',
        payload: {}
      })
      loadQueueData()
    } catch (error: any) {
      alert(`Erro: ${error.response?.data?.detail || error.message}`)
    }
  }

  const getPriorityLabel = (priority: number): string => {
    const labels: Record<number, string> = {
      1: 'CRÍTICA',
      2: 'ALTA',
      3: 'MÉDIA',
      4: 'BAIXA',
      5: 'ADIADA'
    }
    return labels[priority] || `P${priority}`
  }

  const getPriorityColor = (priority: number): string => {
    const colors: Record<number, string> = {
      1: 'priority-critical',
      2: 'priority-high',
      3: 'priority-medium',
      4: 'priority-low',
      5: 'priority-deferred'
    }
    return colors[priority] || 'priority-medium'
  }

  const formatDeadline = (deadline: string): string => {
    return new Date(deadline).toLocaleString('pt-BR')
  }

  const formatTimeUntil = (seconds: number): string => {
    if (seconds < 0) return 'VENCIDO'
    
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    
    if (hours > 24) {
      const days = Math.floor(hours / 24)
      return `${days}d ${hours % 24}h`
    }
    if (hours > 0) return `${hours}h ${minutes}m`
    return `${minutes}m`
  }

  return (
    <div className="queue-page">
      <header className="page-header">
        <h1>📊 Fila de Prioridades</h1>
        <p>Gerenciamento inteligente de tarefas de agentes</p>
      </header>

      {loading ? (
        <div className="loading-state">Carregando...</div>
      ) : (
        <>
          {/* Stats Dashboard */}
          <section className="stats-dashboard">
            <div className="stat-card">
              <h3>Tarefas na Fila</h3>
              <div className="stat-value">{stats?.size_atual || 0}</div>
              <small>de {stats?.max_size || '∞'} máximo</small>
            </div>

            <div className="stat-card">
              <h3>Total Processadas</h3>
              <div className="stat-value">{stats?.total_popped || 0}</div>
            </div>

            <div className="stat-card">
              <h3>Total Adicionadas</h3>
              <div className="stat-value">{stats?.total_pushed || 0}</div>
            </div>

            <div className="stat-card">
              <h3>Rejeitadas</h3>
              <div className="stat-value">{stats?.total_rejected || 0}</div>
              <small>fila cheia</small>
            </div>
          </section>

          {/* Actions Bar */}
          <section className="actions-bar">
            <button onClick={() => setShowAddModal(true)} className="btn-primary">
              ➕ Adicionar Tarefa
            </button>
            <button onClick={() => handleProcessTasks(1)} className="btn-secondary">
              ▶️ Processar 1
            </button>
            <button onClick={() => handleProcessTasks(5)} className="btn-secondary">
              ▶️ Processar 5
            </button>
            <button onClick={handleClearQueue} className="btn-danger">
              🗑️ Limpar Fila
            </button>
          </section>

          {/* Tasks Table */}
          <section className="tasks-section">
            <h2>🎯 Tarefas Agendadas ({tasks.length})</h2>
            
            {tasks.length === 0 ? (
              <p className="empty-state">Nenhuma tarefa na fila.</p>
            ) : (
              <div className="tasks-table-container">
                <table className="tasks-table">
                  <thead>
                    <tr>
                      <th>Prioridade</th>
                      <th>Agente</th>
                      <th>Cliente</th>
                      <th>Deadline</th>
                      <th>Tempo Restante</th>
                      <th>Custo</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tasks.map(task => (
                      <tr key={task.task_id} className={task.is_overdue ? 'overdue-row' : ''}>
                        <td>
                          <span className={`priority-badge ${getPriorityColor(task.priority)}`}>
                            {getPriorityLabel(task.priority)}
                          </span>
                        </td>
                        <td>{task.agent_name}</td>
                        <td>{task.client_id}</td>
                        <td>{formatDeadline(task.deadline)}</td>
                        <td className={task.is_overdue ? 'overdue-text' : ''}>
                          {formatTimeUntil(task.seconds_until_deadline)}
                        </td>
                        <td>{task.cost}</td>
                        <td>
                          {task.is_overdue && <span className="overdue-badge">⚠️ VENCIDA</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}

      {/* Add Task Modal */}
      {showAddModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2>➕ Adicionar Tarefa à Fila</h2>

            <div className="form-group">
              <label>Agente *</label>
              <select
                value={newTask.agent_name}
                onChange={(e) => setNewTask({ ...newTask, agent_name: e.target.value })}
              >
                <option value="">Selecione um agente</option>
                <option value="site_agent">Site Agent (Automação Web)</option>
                <option value="deadlines_agent">Deadlines Agent (Prazos)</option>
                <option value="attendance_agent">Attendance Agent (Agendamento)</option>
                <option value="finance_agent">Finance Agent (Finanças)</option>
                <option value="nf_agent">NF Agent (Notas Fiscais)</option>
                <option value="collections_agent">Collections Agent (Cobranças)</option>
              </select>
            </div>

            <div className="form-group">
              <label>ID do Cliente *</label>
              <input
                type="text"
                value={newTask.client_id}
                onChange={(e) => setNewTask({ ...newTask, client_id: e.target.value })}
                placeholder="Ex: client_123"
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Prioridade</label>
                <select
                  value={newTask.priority}
                  onChange={(e) => setNewTask({ ...newTask, priority: parseInt(e.target.value) })}
                >
                  <option value={1}>1 - CRÍTICA</option>
                  <option value={2}>2 - ALTA</option>
                  <option value={3}>3 - MÉDIA</option>
                  <option value={4}>4 - BAIXA</option>
                  <option value={5}>5 - ADIADA</option>
                </select>
              </div>

              <div className="form-group">
                <label>Dias até Deadline</label>
                <input
                  type="number"
                  min={1}
                  value={newTask.days_ahead}
                  onChange={(e) => setNewTask({ ...newTask, days_ahead: parseInt(e.target.value) })}
                />
              </div>

              <div className="form-group">
                <label>Custo</label>
                <input
                  type="number"
                  min={1}
                  value={newTask.cost}
                  onChange={(e) => setNewTask({ ...newTask, cost: parseInt(e.target.value) })}
                />
              </div>
            </div>

            <div className="modal-actions">
              <button onClick={handleAddTask} className="btn-primary">
                Adicionar
              </button>
              <button onClick={() => setShowAddModal(false)} className="btn-secondary">
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default QueuePage
