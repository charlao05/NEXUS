import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Mail, Lock, User, Eye, EyeOff, Loader2, AlertCircle } from 'lucide-react';
import axios from 'axios';
import { AuthLayout } from './AuthLayout';

export function LoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const navigate = useNavigate();
  const [, setSearchParams] = useSearchParams();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await axios.post('/api/auth/login', { email, password });
      
      localStorage.setItem('access_token', response.data.access_token);
      localStorage.setItem('user_plan', response.data.plan);
      localStorage.setItem('user_email', response.data.email);
      
      navigate('/agents');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao fazer login');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title="Bem-vindo de Volta">
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Error message */}
        {error && (
          <motion.div
            className="flex items-center gap-3 bg-red-900/20 border border-red-700/50 rounded-lg p-4 text-red-200"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <p className="text-sm">{error}</p>
          </motion.div>
        )}

        {/* Email Field */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-200">Email</label>
          <div className="relative">
            <Mail className="absolute left-4 top-3.5 w-5 h-5 text-slate-400 pointer-events-none" />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="seu@email.com"
              required
              className="w-full bg-slate-700/50 border border-slate-600 rounded-lg pl-12 pr-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-400/20 transition-all"
            />
          </div>
        </div>

        {/* Password Field */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-200">Senha</label>
          <div className="relative">
            <Lock className="absolute left-4 top-3.5 w-5 h-5 text-slate-400 pointer-events-none" />
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full bg-slate-700/50 border border-slate-600 rounded-lg pl-12 pr-12 py-3 text-white placeholder-slate-400 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-400/20 transition-all"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-4 top-3.5 text-slate-400 hover:text-slate-200 transition"
            >
              {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Remember me */}
        <div className="flex items-center justify-between text-sm">
          <label className="flex items-center gap-2 text-slate-300 cursor-pointer hover:text-white transition">
            <input type="checkbox" className="rounded" />
            Lembrar-me
          </label>
          <a href="#" className="text-green-400 hover:text-green-300 transition">
            Esqueceu a senha?
          </a>
        </div>

        {/* Submit Button */}
        <motion.button
          type="submit"
          disabled={loading}
          className="w-full bg-gradient-to-r from-green-400 to-green-500 hover:from-green-500 hover:to-green-600 disabled:from-slate-600 disabled:to-slate-700 text-white font-bold py-3 rounded-lg transition-all flex items-center justify-center gap-2 group"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          {loading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Entrando...</span>
            </>
          ) : (
            <>
              <span>Entrar</span>
              <span className="group-hover:translate-x-1 transition">→</span>
            </>
          )}
        </motion.button>

        {/* Divider */}
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-600"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-slate-800 text-slate-400">ou continue com</span>
          </div>
        </div>

        {/* Social Buttons */}
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            className="flex items-center justify-center gap-2 bg-slate-700/50 border border-slate-600 hover:border-slate-500 rounded-lg py-3 text-slate-200 transition-all hover:bg-slate-700/70"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            <span className="text-sm font-medium">Google</span>
          </button>
          <button
            type="button"
            className="flex items-center justify-center gap-2 bg-slate-700/50 border border-slate-600 hover:border-slate-500 rounded-lg py-3 text-slate-200 transition-all hover:bg-slate-700/70"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M11.4 24c6.3 0 9.8-5.2 9.8-9.7 0-.1 0-.3 0-.5 0-.4.3-.8.7-1 .5-.3 1-.8 1.4-1.3.4-.5.6-1.1.5-1.7-.2-.4-.6-.6-1-.5-.5.1-1 .3-1.5.4-1.2-.8-2.7-1.3-4.2-1.2-.7 0-1.4.1-2.1.3.7-2.2 2.8-3.8 5.3-3.8 1.3 0 2.6.4 3.7 1.2.4.3.9.4 1.4.3.4 0 .8-.2 1-.5.3-.4.3-1 0-1.4-1.5-1.5-3.4-2.3-5.5-2.3-4.5 0-8.3 3.4-8.9 7.8H6c-.6 0-1 .4-1 1s.4 1 1 1h1.3c.1.6.1 1.2.1 1.8 0 .6 0 1.2-.1 1.8H6c-.6 0-1 .4-1 1s.4 1 1 1h1.8c.5 3.1 3.2 5.4 6.6 5.4z"/>
            </svg>
            <span className="text-sm font-medium">Microsoft</span>
          </button>
        </div>

        {/* Sign up link */}
        <p className="text-center text-slate-400 text-sm">
          Não tem conta?{' '}
          <button
            type="button"
            onClick={() => setSearchParams({ mode: 'signup' })}
            className="text-green-400 hover:text-green-300 font-semibold transition"
          >
            Criar agora
          </button>
        </p>
      </form>
    </AuthLayout>
  );
}

export function SignUpForm() {
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const navigate = useNavigate();
  const [, setSearchParams] = useSearchParams();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('As senhas não coincidem');
      return;
    }

    if (formData.password.length < 8) {
      setError('A senha deve ter pelo menos 8 caracteres');
      return;
    }

    setLoading(true);

    try {
      const response = await axios.post('/api/auth/signup', {
        email: formData.email,
        password: formData.password,
        full_name: formData.full_name
      });
      
      localStorage.setItem('access_token', response.data.access_token);
      localStorage.setItem('user_plan', response.data.plan);
      localStorage.setItem('user_email', response.data.email);
      
      navigate('/agents');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao criar conta');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title="Comece Sua Jornada">
      <form onSubmit={handleSubmit} className="space-y-5">
        {error && (
          <motion.div
            className="flex items-center gap-3 bg-red-900/20 border border-red-700/50 rounded-lg p-4 text-red-200"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <p className="text-sm">{error}</p>
          </motion.div>
        )}

        {/* Name Field */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-200">Nome Completo</label>
          <div className="relative">
            <User className="absolute left-4 top-3.5 w-5 h-5 text-slate-400 pointer-events-none" />
            <input
              type="text"
              name="full_name"
              value={formData.full_name}
              onChange={handleChange}
              placeholder="João Silva"
              required
              className="w-full bg-slate-700/50 border border-slate-600 rounded-lg pl-12 pr-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-400/20 transition-all"
            />
          </div>
        </div>

        {/* Email Field */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-200">Email</label>
          <div className="relative">
            <Mail className="absolute left-4 top-3.5 w-5 h-5 text-slate-400 pointer-events-none" />
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="seu@email.com"
              required
              className="w-full bg-slate-700/50 border border-slate-600 rounded-lg pl-12 pr-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-400/20 transition-all"
            />
          </div>
        </div>

        {/* Password Field */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-200">Senha</label>
          <div className="relative">
            <Lock className="absolute left-4 top-3.5 w-5 h-5 text-slate-400 pointer-events-none" />
            <input
              type={showPassword ? 'text' : 'password'}
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="••••••••"
              required
              minLength={8}
              className="w-full bg-slate-700/50 border border-slate-600 rounded-lg pl-12 pr-12 py-3 text-white placeholder-slate-400 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-400/20 transition-all"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-4 top-3.5 text-slate-400 hover:text-slate-200 transition"
            >
              {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
          <p className="text-xs text-slate-400">Mínimo 8 caracteres</p>
        </div>

        {/* Confirm Password */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-200">Confirmar Senha</label>
          <div className="relative">
            <Lock className="absolute left-4 top-3.5 w-5 h-5 text-slate-400 pointer-events-none" />
            <input
              type={showConfirm ? 'text' : 'password'}
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              placeholder="••••••••"
              required
              className="w-full bg-slate-700/50 border border-slate-600 rounded-lg pl-12 pr-12 py-3 text-white placeholder-slate-400 focus:outline-none focus:border-green-400 focus:ring-2 focus:ring-green-400/20 transition-all"
            />
            <button
              type="button"
              onClick={() => setShowConfirm(!showConfirm)}
              className="absolute right-4 top-3.5 text-slate-400 hover:text-slate-200 transition"
            >
              {showConfirm ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Terms checkbox */}
        <label className="flex items-start gap-3 text-sm text-slate-300 cursor-pointer group">
          <input type="checkbox" required className="mt-1 rounded" />
          <span>
            Concordo com os{' '}
            <a href="#" className="text-green-400 hover:text-green-300 transition">
              Termos de Serviço
            </a>
            {' '}e{' '}
            <a href="#" className="text-green-400 hover:text-green-300 transition">
              Política de Privacidade
            </a>
          </span>
        </label>

        {/* Submit Button */}
        <motion.button
          type="submit"
          disabled={loading}
          className="w-full bg-gradient-to-r from-green-400 to-green-500 hover:from-green-500 hover:to-green-600 disabled:from-slate-600 disabled:to-slate-700 text-white font-bold py-3 rounded-lg transition-all flex items-center justify-center gap-2 group"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          {loading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Criando conta...</span>
            </>
          ) : (
            <>
              <span>Começar Grátis</span>
              <span className="group-hover:translate-x-1 transition">→</span>
            </>
          )}
        </motion.button>

        {/* Divider */}
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-slate-600"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-slate-800 text-slate-400">ou continue com</span>
          </div>
        </div>

        {/* Social Buttons */}
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            className="flex items-center justify-center gap-2 bg-slate-700/50 border border-slate-600 hover:border-slate-500 rounded-lg py-3 text-slate-200 transition-all hover:bg-slate-700/70"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            <span className="text-sm font-medium">Google</span>
          </button>
          <button
            type="button"
            className="flex items-center justify-center gap-2 bg-slate-700/50 border border-slate-600 hover:border-slate-500 rounded-lg py-3 text-slate-200 transition-all hover:bg-slate-700/70"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M11.4 24c6.3 0 9.8-5.2 9.8-9.7 0-.1 0-.3 0-.5 0-.4.3-.8.7-1 .5-.3 1-.8 1.4-1.3.4-.5.6-1.1.5-1.7-.2-.4-.6-.6-1-.5-.5.1-1 .3-1.5.4-1.2-.8-2.7-1.3-4.2-1.2-.7 0-1.4.1-2.1.3.7-2.2 2.8-3.8 5.3-3.8 1.3 0 2.6.4 3.7 1.2.4.3.9.4 1.4.3.4 0 .8-.2 1-.5.3-.4.3-1 0-1.4-1.5-1.5-3.4-2.3-5.5-2.3-4.5 0-8.3 3.4-8.9 7.8H6c-.6 0-1 .4-1 1s.4 1 1 1h1.3c.1.6.1 1.2.1 1.8 0 .6 0 1.2-.1 1.8H6c-.6 0-1 .4-1 1s.4 1 1 1h1.8c.5 3.1 3.2 5.4 6.6 5.4z"/>
            </svg>
            <span className="text-sm font-medium">Microsoft</span>
          </button>
        </div>

        {/* Login link */}
        <p className="text-center text-slate-400 text-sm">
          Já tem conta?{' '}
          <button
            type="button"
            onClick={() => setSearchParams({ mode: 'login' })}
            className="text-green-400 hover:text-green-300 font-semibold transition"
          >
            Entrar
          </button>
        </p>
      </form>
    </AuthLayout>
  );
}
