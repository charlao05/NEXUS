import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'
import { apiUrl } from '../config/api'

export function PaymentSuccess() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { login } = useAuth()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const sessionId = searchParams.get('session_id')

  useEffect(() => {
    const verifyPayment = async () => {
      try {
        if (sessionId) {
          const token = localStorage.getItem('access_token') || ''
          // Verificar pagamento com o backend (com auth header)
          const response = await axios.post(apiUrl('/api/auth/verify-payment'), { 
            session_id: sessionId 
          }, {
            headers: { Authorization: `Bearer ${token}` }
          })
          
          // Atualizar plano no localStorage
          if (response.data.plan) {
            const email = localStorage.getItem('user_email') || ''
            login(token, email, response.data.plan)
          }
        }
        
        setStatus('success')
      } catch (e) {
        console.error('Erro verificando pagamento:', e)
        // Não assumir plano — redirecionar para erro e deixar o webhook atualizar
        setStatus('error')
      }
    }

    verifyPayment()
  }, [sessionId, login])

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        {status === 'loading' && (
          <div className="text-center">
            <div className="w-16 h-16 rounded-full border-4 border-slate-700 border-t-green-400 animate-spin mx-auto mb-6" />
            <h2 className="text-2xl font-bold text-white mb-2">Processando pagamento...</h2>
            <p className="text-slate-400">Aguarde enquanto confirmamos seu pagamento</p>
          </div>
        )}

        {status === 'success' && (
          <div className="text-center">
            <div className="w-20 h-20 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-6">
              <svg className="w-10 h-10 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            
            <h2 className="text-3xl font-bold text-white mb-4">
              Pagamento Confirmado! 🎉
            </h2>
            
            <p className="text-slate-300 mb-8">
              Seu plano foi atualizado com sucesso. Você já tem acesso a todas as funcionalidades do novo plano.
            </p>

            <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-6 mb-8">
              <h3 className="text-lg font-semibold text-white mb-4">O que você pode fazer agora:</h3>
              <ul className="space-y-3 text-left">
                <li className="flex items-start gap-3 text-slate-300">
                  <svg className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Acessar todas as APIs avançadas
                </li>
                <li className="flex items-start gap-3 text-slate-300">
                  <svg className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Configurar webhooks em tempo real
                </li>
                <li className="flex items-start gap-3 text-slate-300">
                  <svg className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Usar limites expandidos de requisições
                </li>
                <li className="flex items-start gap-3 text-slate-300">
                  <svg className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Suporte prioritário disponível
                </li>
              </ul>
            </div>

            <button
              onClick={() => navigate('/dashboard')}
              className="w-full py-4 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-400 hover:to-emerald-400 text-white rounded-xl font-bold text-lg transition shadow-lg shadow-green-500/30"
            >
              Ir para o Dashboard
            </button>
          </div>
        )}

        {status === 'error' && (
          <div className="text-center">
            <div className="w-20 h-20 rounded-full bg-red-500/20 flex items-center justify-center mx-auto mb-6">
              <svg className="w-10 h-10 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            
            <h2 className="text-3xl font-bold text-white mb-4">
              Ops! Algo deu errado
            </h2>
            
            <p className="text-slate-300 mb-8">
              Não conseguimos confirmar seu pagamento. Por favor, entre em contato com o suporte.
            </p>

            <div className="space-y-4">
              <button
                onClick={() => navigate('/pricing')}
                className="w-full py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-xl font-medium transition"
              >
                Tentar novamente
              </button>
              <button
                onClick={() => navigate('/dashboard')}
                className="w-full py-3 text-slate-400 hover:text-white transition"
              >
                Voltar
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default PaymentSuccess
