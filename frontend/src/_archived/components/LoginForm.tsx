import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mail, Lock, Eye, EyeOff, Loader2, AlertCircle } from 'lucide-react'
import axios from 'axios'

interface LoginFormProps {
  disabled?: boolean
}

export default function LoginForm({ disabled = false }: LoginFormProps) {
  const navigate = useNavigate()
  const [, setSearchParams] = useSearchParams()

  const [formData, setFormData] = useState({
    email: '',
    password: ''
  })

  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [rememberMe, setRememberMe] = useState(false)

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError('')
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value
    }))
  }

  const validateForm = () => {
    if (!formData.email.trim()) {
      setError('Email é obrigatório')
      return false
    }
    if (!formData.email.includes('@')) {
      setError('Email inválido')
      return false
    }
    if (!formData.password) {
      setError('Senha é obrigatória')
      return false
    }
    return true
  }

  const goToSignup = () => {
    // Garante troca de tela mesmo em ambientes sem querystring pré-carregada
    setSearchParams({ mode: 'signup' })
    navigate('/?mode=signup')
  }

  const startGoogle = () => {
    window.location.href = '/api/auth/google/start'
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) return

    setLoading(true)
    setError('')

    try {
      const response = await axios.post('/api/auth/login', {
        email: formData.email,
        password: formData.password
      })

      // Salvar token e dados
      localStorage.setItem('access_token', response.data.access_token)
      localStorage.setItem('user_email', response.data.email)
      localStorage.setItem('user_plan', response.data.plan || 'free')

      if (rememberMe) {
        localStorage.setItem('remember_email', formData.email)
      }

      // Redirecionar
      navigate('/dashboard')
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
        err.message ||
        'Erro ao fazer login. Verifique suas credenciais.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Email Field */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <label className="block text-sm font-medium text-slate-300 mb-2">
          Email
        </label>
        <div className="relative">
          <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-500 pointer-events-none" />
          <input
            type="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            disabled={loading || disabled}
            placeholder="seu.email@example.com"
            className="w-full pl-10 pr-4 py-3 bg-slate-700/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-400/20 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>
      </motion.div>

      {/* Password Field */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-slate-300">
            Senha
          </label>
          <a
            href="#"
            className="text-xs text-green-400 hover:text-green-300 transition-colors"
          >
            Esqueceu a senha?
          </a>
        </div>
        <div className="relative">
          <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-500 pointer-events-none" />
          <input
            type={showPassword ? 'text' : 'password'}
            name="password"
            value={formData.password}
            onChange={handleChange}
            disabled={loading || disabled}
            placeholder="••••••••"
            className="w-full pl-10 pr-12 py-3 bg-slate-700/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-400/20 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            disabled={loading || disabled}
            className="absolute right-3 top-1/2 transform -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors disabled:cursor-not-allowed"
          >
            {showPassword ? (
              <EyeOff className="w-5 h-5" />
            ) : (
              <Eye className="w-5 h-5" />
            )}
          </button>
        </div>
      </motion.div>

      {/* Remember Me */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="flex items-center"
      >
        <input
          type="checkbox"
          id="remember"
          checked={rememberMe}
          onChange={(e) => setRememberMe(e.target.checked)}
          disabled={loading || disabled}
          className="w-4 h-4 rounded border-slate-600 bg-slate-700/50 text-green-400 focus:ring-green-400/20 cursor-pointer disabled:cursor-not-allowed"
        />
        <label
          htmlFor="remember"
          className="ml-2 text-sm text-slate-400 cursor-pointer select-none"
        >
          Lembrar-me neste dispositivo
        </label>
      </motion.div>

      {/* Error Message */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg flex items-start gap-3"
        >
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-300">{error}</p>
        </motion.div>
      )}

      {/* Submit Button */}
      <motion.button
        type="submit"
        disabled={loading || disabled}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className="w-full py-3 bg-gradient-to-r from-green-400 to-blue-500 text-white font-semibold rounded-lg hover:from-green-300 hover:to-blue-400 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-6"
      >
        {loading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Entrando...
          </>
        ) : (
          'Entrar'
        )}
      </motion.button>

      {/* Divider */}
      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-slate-600" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="px-2 bg-slate-800/80 text-slate-400">ou continue com</span>
        </div>
      </div>

      {/* Social Button - Google */}
      <motion.button
        type="button"
        disabled={loading || disabled}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={startGoogle}
        className="w-full py-3 bg-white hover:bg-gray-100 border border-slate-300 rounded-lg text-sm font-medium text-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
      >
        <svg className="w-5 h-5" viewBox="0 0 24 24">
          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
        </svg>
        Continuar com Google
      </motion.button>

      {/* Sign Up Link */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="text-center pt-4"
      >
        <p className="text-sm text-slate-400">
          Não tem conta?{' '}
          <button
            type="button"
            onClick={goToSignup}
            disabled={loading || disabled}
            className="text-green-400 hover:text-green-300 font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Criar conta
          </button>
        </p>
      </motion.div>
    </form>
  )
}
