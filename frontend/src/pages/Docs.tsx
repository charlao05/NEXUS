/**
 * Documentation Page - NEXUS
 * Documentação e guias de uso
 */

import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Book } from 'lucide-react';

const docs: Record<string, { title: string; content: string[] }> = {
  quickstart: {
    title: 'Guia de Início Rápido',
    content: [
      '## Bem-vindo ao NEXUS!',
      'O NEXUS é uma plataforma de automação empresarial com 6 agentes de IA especializados.',
      '',
      '### Primeiros Passos',
      '1. **Escolha um agente** - Acesse a página de Agentes e selecione qual automação deseja configurar',
      '2. **Configure as integrações** - Conecte suas contas (Google Calendar, Telegram, etc)',
      '3. **Defina as regras** - Configure quando e como cada automação deve executar',
      '4. **Monitore os resultados** - Acompanhe pelo Painel em tempo real',
      '',
      '### Agentes Disponíveis',
      '- **Agenda**: Gerenciamento de compromissos e lembretes',
      '- **Clientes**: Gestão de clientes completa com acompanhamento automático',
      '- **Contabilidade**: Boleto mensal do MEI, notas fiscais, imposto de renda e todas as obrigações',
      '- **Cobrança**: Lembretes de pagamento automáticos',
      '- **Cobrança**: Gestão de inadimplência e lembretes',
      '- **Assistente**: Chat de IA para dúvidas',
    ]
  },
  api: {
    title: 'Referência da API',
    content: [
      '## API REST do NEXUS',
      'Base URL: `https://api.nexus.app/v1`',
      '',
      '### Autenticação',
      'Todas as requisições devem incluir o header:',
      '```',
      'Authorization: Bearer SEU_TOKEN_JWT',
      '```',
      '',
      '### Endpoints Disponíveis',
      '',
      '#### GET /api/auth/me',
      'Retorna informações do usuário autenticado.',
      '',
      '#### GET /api/auth/plans',
      'Lista os planos disponíveis e seus limites.',
      '',
      '#### POST /api/agents/{agent_id}/execute',
      'Executa uma ação de um agente específico.',
      '',
      '#### GET /api/dashboard/stats',
      'Retorna estatísticas de uso do dashboard.',
    ]
  },
  examples: {
    title: 'Exemplos de Código',
    content: [
      '## Exemplos de Integração',
      '',
      '### JavaScript/Node.js',
      '```javascript',
      'const axios = require("axios");',
      '',
      'const api = axios.create({',
      '  baseURL: "https://api.nexus.app/v1",',
      '  headers: { Authorization: `Bearer ${TOKEN}` }',
      '});',
      '',
      '// Listar agendamentos',
      'const agenda = await api.get("/agents/agenda/items");',
      '```',
      '',
      '### Python',
      '```python',
      'import requests',
      '',
      'headers = {"Authorization": f"Bearer {TOKEN}"}',
      'response = requests.get(',
      '    "https://api.nexus.app/v1/agents/agenda/items",',
      '    headers=headers',
      ')',
      '```',
      '',
      '### cURL',
      '```bash',
      'curl -X GET "https://api.nexus.app/v1/agents/agenda/items" \\',
      '  -H "Authorization: Bearer $TOKEN"',
      '```',
    ]
  }
};

export default function Docs() {
  const navigate = useNavigate();
  const { section } = useParams<{ section: string }>();
  const doc = docs[section || 'quickstart'] || docs.quickstart;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      {/* Header */}
      <div className="border-b border-slate-700/50 bg-slate-900/50 backdrop-blur-sm">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-2 text-slate-400 hover:text-white transition mb-4"
          >
            <ArrowLeft className="w-5 h-5" />
            Voltar
          </button>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Book className="w-8 h-8 text-blue-400" />
            Documentação
          </h1>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 flex gap-8">
        {/* Sidebar */}
        <aside className="w-48 flex-shrink-0">
          <nav className="space-y-2">
            {Object.entries(docs).map(([key, value]) => (
              <button
                key={key}
                onClick={() => navigate(`/docs/${key}`)}
                className={`w-full text-left px-4 py-2 rounded-lg transition ${
                  section === key 
                    ? 'bg-blue-600 text-white' 
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                }`}
              >
                {value.title}
              </button>
            ))}
          </nav>
        </aside>

        {/* Content */}
        <main className="flex-1 bg-slate-800/50 rounded-2xl border border-slate-700/50 p-8">
          <h2 className="text-2xl font-bold mb-6">{doc.title}</h2>
          <div className="prose prose-invert prose-slate max-w-none">
            {doc.content.map((line, idx) => {
              if (line.startsWith('## ')) {
                return <h2 key={idx} className="text-xl font-bold mt-6 mb-3">{line.replace('## ', '')}</h2>;
              }
              if (line.startsWith('### ')) {
                return <h3 key={idx} className="text-lg font-semibold mt-4 mb-2 text-blue-400">{line.replace('### ', '')}</h3>;
              }
              if (line.startsWith('#### ')) {
                return <h4 key={idx} className="font-mono text-green-400 mt-3 mb-1">{line.replace('#### ', '')}</h4>;
              }
              if (line.startsWith('```')) {
                return null; // Skip code markers
              }
              if (line.startsWith('- ')) {
                return <li key={idx} className="text-slate-300 ml-4">{line.replace('- ', '')}</li>;
              }
              if (line.match(/^\d\./)) {
                return <li key={idx} className="text-slate-300 ml-4 list-decimal">{line.replace(/^\d\.\s*/, '')}</li>;
              }
              if (line.includes('`') && !line.startsWith('```')) {
                // Renderização segura sem dangerouslySetInnerHTML
                const parts = line.split(/`([^`]+)`/);
                return (
                  <p key={idx} className="text-slate-300 my-2">
                    {parts.map((part, i) =>
                      i % 2 === 1
                        ? <code key={i} className="bg-slate-700 px-1.5 py-0.5 rounded text-green-400">{part}</code>
                        : <span key={i}>{part}</span>
                    )}
                  </p>
                );
              }
              return <p key={idx} className="text-slate-300 my-2">{line}</p>;
            })}
          </div>
        </main>
      </div>
    </div>
  );
}
