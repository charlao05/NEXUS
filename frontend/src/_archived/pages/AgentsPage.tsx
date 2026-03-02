import React, { useState, useEffect } from 'react'
import agentService, { Agent, TaskStatus } from '../services/agentService'
import clientService, { Client } from '../services/clientService'
import UploadModal from '../components/modals/UploadModal'
import ExternalCrmModal from '../components/modals/ExternalCrmModal'
import NfModal from '../components/modals/NfModal'
import './AgentsPage.css'

interface AgentCardProps {
  agent: Agent & { displayName?: string }
  onExecute: (agentName: string) => void
}

// Mapa de classes CSS para cada tipo de agente (gradientes psicológicos únicos)
const getAgentButtonClass = (agentName: string): string => {
  const classMap: Record<string, string> = {
    'site_agent': 'btn-automation',       // 🌐 Azul - Confiança técnica
    'agenda_agent': 'btn-agenda',         // 📅 Roxo - Organização
    'clients_agent': 'btn-clients',       // 👥 Cyan - Relacionamento
    'finance_agent': 'btn-financial',     // 💰 Verde - Crescimento
    'nf_agent': 'btn-invoice',            // 📄 Indigo - Profissionalismo
    'collections_agent': 'btn-billing'    // 💳 Rosa - Urgência suave
  }
  return classMap[agentName] || 'btn-execute'
}

const AgentCard: React.FC<AgentCardProps> = ({ agent, onExecute }) => {
  const buttonClass = `agent-card__button ${getAgentButtonClass(agent.name)}`
  
  return (
    <div className="agent-card">
      <div className="agent-card__header">
        <h3>{agent.displayName || agent.name}</h3>
      </div>
      <div className="agent-card__body">
        <p>{agent.description}</p>
      </div>
      <div className="agent-card__actions">
        <button className={buttonClass} onClick={() => onExecute(agent.name)}>
          Executar
        </button>
      </div>
    </div>
  )
}

const AgentsPage: React.FC = () => {
  const [tasks, setTasks] = useState<TaskStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const [parameters, setParameters] = useState<Record<string, any>>({})
  const [clients, setClients] = useState<Client[]>([])
  const [loadingClients, setLoadingClients] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [showCrmModal, setShowCrmModal] = useState(false)
  const [showNfModal, setShowNfModal] = useState(false)
  // Removido estado não utilizado para evitar avisos de compilação
  
  // Agentes pré-configurados
  const AGENTS = [
    {
      name: 'site_agent',
      displayName: '🌐 Automação Web',
      description: 'Automação de sites com Playwright (login, formulários, etc)',
      form: ['site', 'objetivo', 'dry_run']
    },
    {
      name: 'agenda_agent',
      displayName: '📆 Agenda Completa',
      description: 'Todos os compromissos: prazos fiscais (DAS, DARF), pagamentos, NFs, fornecedores, compras e deadlines. A IA monitora e lembra você.',
      form: ['commitment_type', 'description', 'due_date', 'priority', 'estimated_value', 'reminder_days', 'obligations_json']
    },
    {
      name: 'clients_agent',
      displayName: '👥 Clientes',
      description: 'CRM Completo: Cadastro, agendamento, análise, probabilidades de compra e comparecimento',
      icon: '👥',
      form: ['action', 'client_name', 'phone', 'email', 'cpf_cnpj', 'birth_date', 'address', 'city', 'state', 'segment', 'tags', 'source', 'appointment_datetime', 'appointment_type', 'appointment_notes', 'opportunity_type', 'opportunity_value', 'opportunity_stage', 'notes'],
    },
    {
      name: 'finance_agent',
      displayName: '💰 Análise Financeira',
      description: 'Seu contador pessoal: analisa entradas e saídas, calcula lucro real, compara meses, prevê faturamento. Tudo em linguagem simples!',
      form: ['action', 'month', 'months', 'categoria_mei', 'receitas', 'despesas', 'impostos_pagos', 'historical_months']
    },
    {
      name: 'nf_agent',
      displayName: '📄 Nota Fiscal',
      description: 'Gera instruções para emissão de Nota Fiscal (NFS-e)',
      form: ['sale_data']
    },
    {
      name: 'collections_agent',
      displayName: '💳 Cobranças',
      description: 'Envio automático de cobranças e lembretes de pagamento',
      form: ['invoice_id', 'client_email']
    }
  ]

  useEffect(() => {
    loadTasks()
    const interval = setInterval(loadTasks, 5000) // refresh a cada 5s
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    loadClients()
  }, [])

  const loadTasks = async () => {
    try {
      const response = await agentService.listTasks(20)
      setTasks(response.tasks)
      setLoading(false)
    } catch (error) {
      console.error('Erro ao carregar tarefas:', error)
      setLoading(false)
    }
  }

  const loadClients = async () => {
    try {
      setLoadingClients(true)
      const response = await clientService.listClients()
      setClients(response.clients || [])
    } catch (error) {
      console.error('Erro ao carregar clientes:', error)
    } finally {
      setLoadingClients(false)
    }
  }

  const getAgentDisplayName = (agentName: string): string => {
    const agent = AGENTS.find(a => a.name === agentName)
    return agent?.displayName || agentName
  }

  const getFieldLabel = (field: string): string => {
    const labels: Record<string, string> = {
      // Site Agent
      'site': 'Site',
      'objetivo': 'Objetivo',
      'dry_run': 'Apenas planejar (sem executar)?',
      
      'client_id': 'ID do Cliente',
      
      // Agenda Agent (Unificado: fiscal + geral)
      'commitment_type': 'Tipo de Compromisso',
      'description': 'Descrição',
      'due_date': 'Data de Vencimento',
      'priority': 'Prioridade',
      'estimated_value': 'Valor Estimado (R$)',
      'reminder_days': 'Dias de Antecedência (Lembrete)',
      'obligations_json': 'JSON de Obrigações (opcional)',
      
      // Clients Agent (CRM Completo)
      'action': 'Ação',
      'client_name': 'Nome do Cliente',
      'phone': 'Telefone',
      'email': 'Email',
      'cpf_cnpj': 'CPF/CNPJ',
      'birth_date': 'Data de Nascimento',
      'address': 'Endereço',
      'city': 'Cidade',
      'state': 'Estado',
      'segment': 'Segmento',
      'tags': 'Tags (separe com vírgula)',
      'source': 'Origem do Lead',
      'appointment_datetime': 'Data/Hora do Agendamento',
      'appointment_type': 'Tipo de Agendamento',
      'appointment_notes': 'Notas do Agendamento',
      'opportunity_type': 'Tipo de Oportunidade',
      'opportunity_value': 'Valor da Oportunidade (R$)',
      'opportunity_stage': 'Estágio da Oportunidade',
      'notes': 'Observações',
      
      // Legacy
      'lead_data': 'Dados do Lead',
      'datetime': 'Data e Hora',
      
      // Finance Agent (Análise Financeira)
      // 'action' já definido acima
      'month': 'Mês (YYYY-MM)',
      'months': 'Meses para Comparar (separados por vírgula)',
      'categoria_mei': 'Categoria MEI',
      'receitas': 'Receitas (JSON)',
      'despesas': 'Despesas (JSON)',
      'impostos_pagos': 'Impostos Pagos (R$)',
      'historical_months': 'Meses Históricos (para previsão)',
      
      // NF Agent
      'sale_data': 'Dados da Venda',
      
      // Collections Agent
      'invoice_id': 'ID da Fatura',
      'days_overdue': 'Dias em Atraso',
      'client_email': 'Email do Cliente'
    }
    return labels[field] || field
  }

  const getFieldDescription = (field: string): string | null => {
    const descriptions: Record<string, string> = {
      'dry_run': '✓ Gera o plano com os passos, mas não executa no navegador',
      'lead_data': 'Formato JSON com dados do cliente (nome, email, interesse, etc)',
      'sale_data': 'Formato JSON com dados da venda (cliente, valor, descrição)',
      'commitment_type': 'Tipos: fiscal (DAS/DARF), payment (pagamento), invoice (NF), supplier (fornecedor), purchase (compra), deadline (prazo)',
      'reminder_days': 'Quantos dias antes do vencimento você quer ser lembrado? (padrão: 3 dias)',
      'estimated_value': 'Valor estimado do compromisso (opcional)',
      'obligations_json': 'JSON com lista de obrigações MEI. Deixe vazio para compromisso único.'
    }
    return descriptions[field] || null
  }

  const getFieldExample = (field: string): string => {
    const examples: Record<string, string> = {
      'site': 'instagram',
      'objetivo': 'fazer login e clicar em perfil',
      'dry_run': 'true',
      'client_id': 'cliente123',
      
      // Agenda Agent (Unificado)
      'commitment_type': 'fiscal',
      'description': 'Pagamento DAS Janeiro',
      'due_date': '2026-01-20',
      'priority': 'high',
      'estimated_value': '80.50',
      'reminder_days': '3',
      'obligations_json': '[{"id":"DAS-001","name":"DAS Janeiro","due_date":"2026-01-20","estimated_value":80.5}]',
      
      // Attendance Agent
      'lead_data': '{"nome": "João Silva", "email": "joao@email.com", "interesse": "Serviço X"}',
      'client_name': 'João Silva',
      'phone': '11999999999',
      'datetime': '2026-01-10T14:30',
      'month': '01/2025',
      'report_type': 'mensal',
      'start_date': '2025-01-01',
      'end_date': '2025-01-31',
      'sale_data': '{"cliente_nome": "João", "valor_total": 250.00, "descricao_servicos": "Serviço de manutenção", "data_venda": "2025-01-05"}',
      'invoice_id': 'FAT001',
      'days_overdue': '5',
      'client_email': 'cliente@email.com'
    }
    return examples[field] || `Digite ${field}`
  }

  const handleExecuteAgent = async (agentName: string) => {
    // Se for nf_agent, abrir modal especial
    if (agentName === 'nf_agent') {
      setShowNfModal(true)
      return
    }
    
    setSelectedAgent(agentName)
  }

  const handleSubmitExecution = async () => {
    if (!selectedAgent) return

    try {
      const response = await agentService.executeAgent(selectedAgent, parameters)
      alert(`Tarefa criada: ${response.task_id}`)
      setSelectedAgent(null)
      setParameters({})
      loadTasks()
    } catch (error: any) {
      alert(`Erro: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleParameterChange = (key: string, value: any) => {
    setParameters({ ...parameters, [key]: value })
  }

  const renderExecutionForm = () => {
    const agent = AGENTS.find(a => a.name === selectedAgent)
    if (!agent) return null

    return (
      <div className="execution-modal">
        <div className="modal-content">
          <h2>Executar: {agent.displayName}</h2>
          <p className="modal-description">{agent.description}</p>
          
          {agent.form.map(field => (
            <div key={field} className="form-field">
              <label>{getFieldLabel(field)}:</label>
              {getFieldDescription(field) && (
                <div className="field-description">{getFieldDescription(field)}</div>
              )}

              {field === 'client_id' ? (
                <div className="client-picker">
                  <select
                    value={parameters[field] || ''}
                    onChange={(e) => handleParameterChange(field, e.target.value)}
                  >
                    <option value="">Selecione um cliente</option>
                    {loadingClients && <option>Carregando...</option>}
                    {clients.map(c => (
                      <option key={c.id} value={c.id}>
                        {c.id} — {c.name}
                      </option>
                    ))}
                    <option value="__manual__">Digitar manualmente</option>
                  </select>
                  {(parameters[field] === '__manual__' || !parameters[field]) && (
                    <input
                      type="text"
                      value={parameters[field] === '__manual__' ? '' : parameters[field] || ''}
                      onChange={(e) => handleParameterChange(field, e.target.value)}
                      placeholder={getFieldExample(field)}
                    />
                  )}
                </div>
              ) : field === 'commitment_type' ? (
                <select
                  value={parameters[field] || 'fiscal'}
                  onChange={(e) => handleParameterChange(field, e.target.value)}
                >
                  <option value="fiscal">📋 Fiscal (DAS, DARF, tributos MEI)</option>
                  <option value="payment">💰 Pagamento (fornecedores, salários)</option>
                  <option value="invoice">📄 Nota Fiscal (emissão, entrega)</option>
                  <option value="supplier">🏢 Fornecedor (reunião, compra)</option>
                  <option value="purchase">🛒 Compra / Pedido</option>
                  <option value="deadline">⏰ Outro Prazo / Deadline</option>
                </select>
              ) : field === 'action' ? (
                <select
                  value={parameters[field] || ''}
                  onChange={(e) => handleParameterChange(field, e.target.value)}
                >
                  <option value="">Selecione...</option>
                  {selectedAgent === 'clients_agent' && (
                    <>
                      <option value="create">➕ Criar Cliente</option>
                      <option value="schedule">📅 Agendar Reunião</option>
                      <option value="analyze">📊 Analisar Cliente (IA)</option>
                      <option value="update">✏️ Atualizar Dados</option>
                    </>
                  )}
                  {selectedAgent === 'finance_agent' && (
                    <>
                      <option value="analyze_month">📊 Analisar Mês</option>
                      <option value="compare_months">🔄 Comparar Meses</option>
                      <option value="health_check">🏥 Checkup de Saúde</option>
                      <option value="forecast">🔮 Previsão</option>
                    </>
                  )}
                </select>
              ) : field === 'segment' ? (
                <select
                  value={parameters[field] || ''}
                  onChange={(e) => handleParameterChange(field, e.target.value)}
                >
                  <option value="">Selecione...</option>
                  <option value="Premium">💎 Premium</option>
                  <option value="Standard">⭐ Standard</option>
                  <option value="Lead">🌱 Lead</option>
                </select>
              ) : field === 'opportunity_stage' ? (
                <select
                  value={parameters[field] || ''}
                  onChange={(e) => handleParameterChange(field, e.target.value)}
                >
                  <option value="">Selecione...</option>
                  <option value="prospecção">🔍 Prospecção</option>
                  <option value="negociação">🤝 Negociação</option>
                  <option value="fechamento">✅ Fechamento</option>
                </select>
              ) : field === 'priority' ? (
                <select
                  value={parameters[field] || 'normal'}
                  onChange={(e) => handleParameterChange(field, e.target.value)}
                >
                  <option value="critical">🔴 Crítica</option>
                  <option value="high">🟠 Alta</option>
                  <option value="normal">🟡 Normal</option>
                  <option value="low">🟢 Baixa</option>
                </select>
              ) : field === 'categoria_mei' ? (
                <select
                  value={parameters[field] || 'servicos'}
                  onChange={(e) => handleParameterChange(field, e.target.value)}
                >
                  <option value="servicos">💼 Serviços</option>
                  <option value="comercio">🏪 Comércio</option>
                  <option value="comercio_servicos">🏪💼 Comércio + Serviços</option>
                </select>
              ) : field === 'due_date' || field === 'datetime' || field === 'birth_date' ? (
                <input
                  type={field === 'datetime' ? 'datetime-local' : 'date'}
                  value={parameters[field] || ''}
                  onChange={(e) => handleParameterChange(field, e.target.value)}
                />
              ) : field === 'appointment_datetime' ? (
                <input
                  type="datetime-local"
                  value={parameters[field] || ''}
                  onChange={(e) => handleParameterChange(field, e.target.value)}
                />
              ) : field === 'email' ? (
                <input
                  type="email"
                  value={parameters[field] || ''}
                  onChange={(e) => handleParameterChange(field, e.target.value)}
                  placeholder="email@exemplo.com"
                />
              ) : field === 'phone' ? (
                <input
                  type="tel"
                  value={parameters[field] || ''}
                  onChange={(e) => handleParameterChange(field, e.target.value)}
                  placeholder="(99) 99999-9999"
                />
              ) : (
                <input
                  type="text"
                  value={parameters[field] || ''}
                  onChange={(e) => handleParameterChange(field, e.target.value)}
                  placeholder={getFieldExample(field)}
                />
              )}
            </div>
          ))}

          {selectedAgent === 'deadlines_agent' && (
            <div className="form-field">
              <label>Dados de Obrigações (JSON opcional)</label>
              <div className="field-description">Deixe em branco para usar obrigações do cliente selecionado.</div>
              <textarea
                rows={4}
                value={parameters.obligations_json || ''}
                onChange={(e) => handleParameterChange('obligations_json', e.target.value)}
                placeholder='[{"id":"DAS-001","name":"DAS","due_date":"2026-01-20","estimated_value":80.5}]'
              />
            </div>
          )}

          <div className="preview-block">
            <h4>Pré-visualização dos parâmetros</h4>
            <pre>{JSON.stringify(parameters, null, 2)}</pre>
          </div>

          <div className="integration-buttons">
            <button 
              className="btn-integration" 
              onClick={() => setShowUploadModal(true)}
              title="Carregar documento (foto/PDF) para extrair dados automaticamente"
            >
              📄 Carregar Documento (OCR)
            </button>
            <button 
              className="btn-integration" 
              onClick={() => setShowCrmModal(true)}
              title="Sincronizar com CRM externo (Pipedrive, Zendesk, etc)"
            >
              🔗 Integrar CRM Externo
            </button>
          </div>

          <div className="modal-actions">
            <button onClick={handleSubmitExecution}>Executar</button>
            <button onClick={() => setSelectedAgent(null)}>Cancelar</button>
          </div>
        </div>
      </div>
    )
  }

  const getStatusBadge = (status: string) => {
    const statusLabels: Record<string, string> = {
      pending: 'Pendente',
      running: 'Executando',
      completed: 'Concluído',
      failed: 'Falhou'
    }
    const colors: Record<string, string> = {
      pending: 'badge-yellow',
      running: 'badge-blue',
      completed: 'badge-green',
      failed: 'badge-red'
    }
    return <span className={`badge ${colors[status] || 'badge-gray'}`}>{statusLabels[status] || status}</span>
  }

  return (
    <div className="agents-page">
      {/* HERO SECTION - Sem navbar duplicada (já existe em App.tsx) */}
      <header className="page-header">
        <div className="hero-decorative"></div>
        <div className="hero-content">
          <div className="hero-inner">
            <h2 className="hero-title">
              🤖 Agentes de <span className="hero-title-gradient">IA</span>
            </h2>
            <div className="hero-badge">
              <span className="hero-badge-text">Automações inteligentes para MEI e pequenos negócios</span>
            </div>
          </div>
        </div>
      </header>

      <section className="agents-section">
        <div className="agents-grid">
          {AGENTS.map(agent => (
            <AgentCard
              key={agent.name}
              agent={{ ...agent, endpoint: `/api/agents/execute` }}
              onExecute={handleExecuteAgent}
            />
          ))}
        </div>
      </section>

      <section className="tasks-section">
        <h2>📋 Tarefas Recentes</h2>
        
        {loading ? (
          <p>Carregando...</p>
        ) : tasks.length === 0 ? (
          <p>Nenhuma tarefa executada ainda.</p>
        ) : (
          <table className="tasks-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Agente</th>
                <th>Status</th>
                <th>Criado em</th>
                <th>Resultado</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map(task => (
                <tr key={task.task_id}>
                  <td>{task.task_id.substring(0, 8)}</td>
                  <td>{getAgentDisplayName(task.agent)}</td>
                  <td>{getStatusBadge(task.status)}</td>
                  <td>{new Date(task.created_at).toLocaleString('pt-BR')}</td>
                  <td>
                    {task.result ? (
                      <details>
                        <summary>Ver</summary>
                        <pre>{JSON.stringify(task.result, null, 2)}</pre>
                      </details>
                    ) : task.error ? (
                      <span className="error-text">{task.error}</span>
                    ) : (
                      '-'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {selectedAgent && renderExecutionForm()}

      <UploadModal 
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        onDataExtracted={(data) => {
          // Auto-preencher campos extraídos
          setParameters(prev => ({ ...prev, ...data }))
          setShowUploadModal(false)
        }}
      />

      <ExternalCrmModal 
        isOpen={showCrmModal}
        onClose={() => setShowCrmModal(false)}
        onSyncComplete={(result) => {
          alert(`✅ Sincronizados ${result.synced_clients} clientes`)
          loadClients() // Recarregar lista de clientes
        }}
      />

      <NfModal
        show={showNfModal}
        onClose={() => setShowNfModal(false)}
        onSubmit={async (nfData) => {
          try {
            // Executar nf_agent com os dados extraídos/inseridos
            const taskId = await agentService.executeAgent('nf_agent', nfData)
            alert(`✅ Instruções de NF geradas! Task ID: ${taskId}`)
            setShowNfModal(false)
            loadTasks() // Recarregar tarefas
          } catch (error) {
            console.error('Erro ao gerar NF:', error)
            alert('❌ Erro ao gerar instruções de NF')
          }
        }}
      />
    </div>
  )
}

export default AgentsPage
