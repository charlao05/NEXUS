import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Lock, ArrowLeft, CheckCircle, AlertCircle } from 'lucide-react'
import { apiUrl } from '../config/api'

export default function ResetPassword() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  const valid = password.length >= 8 && password === confirm && token.length > 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!valid) return

    setStatus('loading')
    try {
      const res = await fetch(apiUrl(`/api/auth/reset-password`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      })
      const data = await res.json()
      if (res.ok) {
        setStatus('success')
        setMessage('Senha redefinida com sucesso! Redirecionando...')
        setTimeout(() => navigate('/login'), 3000)
      } else {
        setStatus('error')
        setMessage(data.detail || 'Erro ao redefinir senha. Tente novamente.')
      }
    } catch {
      setStatus('error')
      setMessage('Erro de conexão. Verifique sua internet e tente novamente.')
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center px-4">
        <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-8 max-w-md w-full text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-white mb-2">Link Inválido</h2>
          <p className="text-slate-400 mb-6">
            O link de redefinição de senha é inválido ou expirou.
            Solicite um novo na página de login.
          </p>
          <button
            onClick={() => navigate('/login')}
            className="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors"
          >
            Ir para Login
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center px-4">
      <div className="bg-slate-800/50 border border-slate-700 rounded-2xl p-8 max-w-md w-full">
        <button
          onClick={() => navigate('/login')}
          className="flex items-center gap-2 text-emerald-400 hover:text-emerald-300 mb-6 transition-colors text-sm"
        >
          <ArrowLeft className="w-4 h-4" /> Voltar ao Login
        </button>

        <div className="text-center mb-6">
          <Lock className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
          <h1 className="text-2xl font-bold text-white">Redefinir Senha</h1>
          <p className="text-slate-400 text-sm mt-1">Digite sua nova senha abaixo</p>
        </div>

        {status === 'success' ? (
          <div className="text-center py-4">
            <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
            <p className="text-emerald-300 font-medium">{message}</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Nova Senha</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Mínimo 8 caracteres"
                className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                minLength={8}
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Confirmar Senha</label>
              <input
                type="password"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                placeholder="Repita a senha"
                className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                minLength={8}
                required
              />
              {confirm.length > 0 && password !== confirm && (
                <p className="text-red-400 text-xs mt-1">As senhas não coincidem</p>
              )}
            </div>

            {status === 'error' && (
              <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-lg p-3">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {message}
              </div>
            )}

            <button
              type="submit"
              disabled={!valid || status === 'loading'}
              className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-600 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
            >
              {status === 'loading' ? 'Redefinindo...' : 'Redefinir Senha'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
