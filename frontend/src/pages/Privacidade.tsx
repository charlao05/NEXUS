import { ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

export default function Privacidade() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-slate-200">
      <div className="max-w-4xl mx-auto px-6 py-12">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-emerald-400 hover:text-emerald-300 mb-8 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" /> Voltar
        </button>

        <h1 className="text-3xl font-bold text-white mb-2">Política de Privacidade</h1>
        <p className="text-slate-400 mb-8">Última atualização: 12 de fevereiro de 2026</p>

        <div className="space-y-8 text-slate-300 leading-relaxed">
          <section>
            <h2 className="text-xl font-semibold text-white mb-3">1. Introdução</h2>
            <p>
              Esta Política de Privacidade descreve como o NEXUS coleta, utiliza, armazena
              e protege seus dados pessoais, em conformidade com a Lei Geral de Proteção
              de Dados (LGPD — Lei nº 13.709/2018).
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">2. Dados Coletados</h2>
            <h3 className="text-lg font-medium text-slate-100 mb-2">2.1. Dados fornecidos por você</h3>
            <ul className="list-disc pl-6 space-y-1 mb-4">
              <li>Nome completo e email (cadastro)</li>
              <li>CNPJ, CPF, dados da empresa (funcionalidades MEI)</li>
              <li>Informações de clientes inseridas no CRM</li>
              <li>Dados financeiros (receitas, despesas, notas fiscais)</li>
              <li>Dados de agendamento e contatos</li>
            </ul>
            <h3 className="text-lg font-medium text-slate-100 mb-2">2.2. Dados coletados automaticamente</h3>
            <ul className="list-disc pl-6 space-y-1">
              <li>Endereço IP e dados de geolocalização aproximada</li>
              <li>Tipo de navegador e sistema operacional</li>
              <li>Páginas acessadas e tempo de uso</li>
              <li>Cookies essenciais e de análise</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">3. Finalidades do Tratamento</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li><strong>Prestação do serviço:</strong> Gerenciar sua conta, processar dados contábeis, CRM e agendamentos.</li>
              <li><strong>Comunicação:</strong> Enviar notificações sobre sua conta, cobranças e atualizações do serviço.</li>
              <li><strong>Melhoria do produto:</strong> Análise de uso agregada e anônima para aprimorar funcionalidades.</li>
              <li><strong>Segurança:</strong> Prevenir fraudes e acessos não autorizados.</li>
              <li><strong>Obrigação legal:</strong> Cumprir requisitos legais e regulatórios aplicáveis.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">4. Base Legal (LGPD)</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li><strong>Consentimento (Art. 7º, I):</strong> Para comunicações de marketing e cookies não essenciais.</li>
              <li><strong>Execução de contrato (Art. 7º, V):</strong> Para prestação dos serviços contratados.</li>
              <li><strong>Legítimo interesse (Art. 7º, IX):</strong> Para segurança e melhoria do produto.</li>
              <li><strong>Obrigação legal (Art. 7º, II):</strong> Para compliance fiscal e regulatório.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">5. Compartilhamento de Dados</h2>
            <p className="mb-3">Seus dados podem ser compartilhados com:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li><strong>Stripe:</strong> Processamento de pagamentos (dados de cobrança).</li>
              <li><strong>OpenAI:</strong> Processamento de IA (dados anonimizados de contexto).</li>
              <li><strong>Google:</strong> Analytics e AdSense (dados agregados).</li>
              <li><strong>Resend:</strong> Envio de emails transacionais.</li>
            </ul>
            <p className="mt-3">
              <strong>Não vendemos</strong> seus dados pessoais a terceiros.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">6. Armazenamento e Retenção</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li>Dados armazenados em servidores seguros com criptografia em trânsito (TLS) e em repouso.</li>
              <li>Dados da conta: mantidos enquanto a conta estiver ativa.</li>
              <li>Após encerramento: dados mantidos por até 5 anos para obrigações fiscais, depois anonimizados ou excluídos.</li>
              <li>Logs de acesso: retidos por 6 meses.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">7. Seus Direitos (LGPD Art. 18)</h2>
            <p className="mb-3">Você tem direito a:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li><strong>Confirmação e acesso:</strong> Saber se tratamos seus dados e acessá-los.</li>
              <li><strong>Correção:</strong> Corrigir dados incompletos ou desatualizados.</li>
              <li><strong>Anonimização/Bloqueio/Eliminação:</strong> De dados desnecessários ou excessivos.</li>
              <li><strong>Portabilidade:</strong> Exportar seus dados em formato estruturado.</li>
              <li><strong>Eliminação:</strong> Solicitar a exclusão de dados tratados com base em consentimento.</li>
              <li><strong>Revogação do consentimento:</strong> A qualquer momento, sem afetar tratamentos anteriores.</li>
            </ul>
            <p className="mt-3">
              Para exercer seus direitos, envie email para{' '}
              <a href="mailto:privacidade@nexus.app" className="text-emerald-400 hover:text-emerald-300">
                privacidade@nexus.app
              </a>
              . Responderemos em até 15 dias úteis.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">8. Cookies</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li><strong>Essenciais:</strong> Necessários para o funcionamento da Plataforma (sessão, autenticação).</li>
              <li><strong>Análise:</strong> Google Analytics para entender uso agregado (podem ser desativados).</li>
              <li><strong>Publicidade:</strong> Google AdSense para anúncios relevantes (podem ser desativados).</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">9. Segurança</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li>Senhas armazenadas com hash BCrypt (nunca em texto plano).</li>
              <li>Comunicações via HTTPS/TLS.</li>
              <li>Autenticação com JWT e tokens de curta duração.</li>
              <li>Isolamento de dados por tenant (multi-tenancy).</li>
              <li>Monitoramento de acessos e alertas de segurança.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">10. Transferência Internacional</h2>
            <p>
              Alguns de nossos provedores (Stripe, OpenAI, Resend) processam dados fora do Brasil.
              Essas transferências são realizadas com base em cláusulas contratuais padrão e
              conformidade com o Capítulo V da LGPD.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">11. Menores de Idade</h2>
            <p>
              A Plataforma não é destinada a menores de 18 anos. Não coletamos intencionalmente
              dados de menores sem autorização do responsável legal.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">12. Encarregado de Dados (DPO)</h2>
            <p>
              Para questões relacionadas à proteção de dados, entre em contato com nosso
              Encarregado de Dados:
              <a href="mailto:dpo@nexus.app" className="text-emerald-400 hover:text-emerald-300 ml-1">
                dpo@nexus.app
              </a>
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">13. Autoridade Nacional</h2>
            <p>
              Caso entenda que o tratamento de seus dados viola a legislação, você pode
              apresentar reclamação à Autoridade Nacional de Proteção de Dados (ANPD) —
              <a
                href="https://www.gov.br/anpd"
                target="_blank"
                rel="noopener noreferrer"
                className="text-emerald-400 hover:text-emerald-300 ml-1"
              >
                www.gov.br/anpd
              </a>
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">14. Alterações</h2>
            <p>
              Esta Política pode ser atualizada periodicamente. Alterações serão comunicadas
              por email ou na Plataforma com antecedência de 30 dias.
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
