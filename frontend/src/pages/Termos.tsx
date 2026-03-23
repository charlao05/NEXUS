import { ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

export default function Termos() {
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

        <h1 className="text-3xl font-bold text-white mb-2">Termos de Uso</h1>
        <p className="text-slate-400 mb-8">Última atualização: 12 de fevereiro de 2026</p>

        <div className="space-y-8 text-slate-300 leading-relaxed">
          <section>
            <h2 className="text-xl font-semibold text-white mb-3">1. Aceitação dos Termos</h2>
            <p>
              Ao criar uma conta ou utilizar o NEXUS ("Plataforma"), você concorda com estes
              Termos de Uso. Se não concordar, não utilize a Plataforma.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">2. Descrição do Serviço</h2>
            <p>
              O NEXUS é uma plataforma online de gestão para Microempreendedores Individuais (MEI)
              que oferece: gestão contábil (boleto mensal do MEI, notas fiscais, imposto de renda), gestão de clientes, agendamentos, cobranças e
              assistente virtual com inteligência artificial.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">3. Cadastro e Conta</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li>Você deve fornecer informações verdadeiras e manter seus dados atualizados.</li>
              <li>É sua responsabilidade manter a segurança das credenciais de acesso.</li>
              <li>Cada conta é pessoal e intransferível.</li>
              <li>Menores de 18 anos devem ter autorização de responsável legal.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">4. Planos e Pagamento</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li><strong>Gratuito (R$ 0):</strong> Acesso permanente ao agente Fiscal (contabilidade), até 5 clientes cadastrados, 10 mensagens/dia com IA. Sem cartão de crédito.</li>
              <li><strong>Essencial (R$ 29,90/mês):</strong> 3 agentes (Fiscal, Clientes, Cobranças), até 100 clientes, 200 mensagens/dia, lembretes automáticos.</li>
              <li><strong>Profissional (R$ 59,90/mês):</strong> 5 agentes, até 500 clientes, 1.000 mensagens/dia, automação completa e relatórios avançados.</li>
              <li><strong>Completo (R$ 89,90/mês):</strong> Todos os agentes (incluindo futuros), clientes e mensagens ilimitados, integrações, notificações automáticas, suporte 24/7 e garantia de disponibilidade 99,9%.</li>
              <li>Pagamentos processados via Stripe. Cancelamento a qualquer momento.</li>
              <li>Não há reembolso proporcional ao cancelar antes do fim do período.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">5. Uso Aceitável</h2>
            <p>Você concorda em NÃO:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Usar a Plataforma para atividades ilegais ou fraudulentas.</li>
              <li>Tentar acessar dados de outros usuários.</li>
              <li>Realizar engenharia reversa ou scraping do serviço.</li>
              <li>Sobrecarregar a infraestrutura com uso automatizado excessivo.</li>
              <li>Compartilhar credenciais de acesso com terceiros.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">6. Inteligência Artificial</h2>
            <p>
              A Plataforma utiliza modelos de IA para sugestões contábeis, atendimento
              e automações. As informações geradas são <strong>orientativas</strong> e
              não substituem consultoria profissional contábil, jurídica ou financeira.
              O NEXUS não se responsabiliza por decisões tomadas exclusivamente com base
              nas respostas da IA.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">7. Propriedade Intelectual</h2>
            <p>
              Todo o conteúdo da Plataforma (código, design, textos, ícones) é de propriedade
              do NEXUS ou seus licenciantes. Os dados inseridos por você permanecem sua propriedade.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">8. Suspensão e Encerramento</h2>
            <p>
              Reservamo-nos o direito de suspender ou encerrar contas que violem estes Termos,
              com notificação prévia quando possível. Você pode encerrar sua conta a qualquer
              momento solicitando a exclusão dos seus dados.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">9. Limitação de Responsabilidade</h2>
            <p>
              A Plataforma é fornecida "como está". Não garantimos disponibilidade ininterrupta
              ou ausência de erros. Nossa responsabilidade máxima é limitada ao valor pago nos
              últimos 12 meses.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">10. Alterações nos Termos</h2>
            <p>
              Podemos atualizar estes Termos periodicamente. Alterações significativas serão
              notificadas por email ou na Plataforma com 30 dias de antecedência.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">11. Legislação e Foro</h2>
            <p>
              Estes Termos são regidos pelas leis da República Federativa do Brasil.
              Fica eleito o foro da comarca do domicílio do usuário para resolver
              eventuais controvérsias.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">12. Contato</h2>
            <p>
              Para dúvidas sobre estes Termos, entre em contato pelo email:
              <a href="mailto:suporte@nexus.app" className="text-emerald-400 hover:text-emerald-300 ml-1">
                suporte@nexus.app
              </a>
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
