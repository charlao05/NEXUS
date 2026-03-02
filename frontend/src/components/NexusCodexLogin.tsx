import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { login as authServiceLogin, signup as authServiceSignup } from '../services/authService';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { apiUrl } from '../config/api';
import { Mail, Lock, Zap, Clock, TrendingUp, Shield, User, Eye, EyeOff } from 'lucide-react';

export default function NexusCodexLogin() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSignupMode, setIsSignupMode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [rememberMe, setRememberMe] = useState(false);
  const [lgpdConsent, setLgpdConsent] = useState(false);
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [commPreference, setCommPreference] = useState('email');
  const auth = useAuth();

  // Carregar email salvo do "Lembrar-me"
  useEffect(() => {
    const savedEmail = localStorage.getItem('nexus_remember_email');
    const savedRemember = localStorage.getItem('nexus_remember_me');
    if (savedEmail && savedRemember === 'true') {
      setEmail(savedEmail);
      setRememberMe(true);
    }
    // Limpar senha em base64 de versões anteriores (segurança)
    localStorage.removeItem('nexus_remember_pwd');
  }, []);

  const handleLogin = useCallback(async () => {
    if (!email || !password) {
      setError('Preencha email e senha');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      console.log('[Login] Iniciando login para:', email)
      console.log('[Login] API_BASE:', import.meta.env.VITE_API_URL || '(vazio - proxy Vite)')
      const result = await authServiceLogin(email, password);
      console.log('[Login] Sucesso! plan:', result.plan, 'uid:', result.user_id)
      // Salvar "Lembrar-me" se marcado (apenas email, nunca senha)
      if (rememberMe) {
        localStorage.setItem('nexus_remember_email', email);
        localStorage.setItem('nexus_remember_me', 'true');
      } else {
        localStorage.removeItem('nexus_remember_email');
        localStorage.removeItem('nexus_remember_me');
      }
      localStorage.removeItem('nexus_remember_pwd');
      
      // Buscar perfil real do backend para obter nome e plano
      try {
        const token = result.access_token || localStorage.getItem('access_token');
        if (token) {
          const profileRes = await fetch(apiUrl('/api/auth/me'), {
            headers: { Authorization: `Bearer ${token}` }
          });
          if (profileRes.ok) {
            const profile = await profileRes.json();
            if (profile.full_name && profile.full_name !== 'Usuário') {
              localStorage.setItem('user_name', profile.full_name);
            } else {
              const nameFromEmail = email.split('@')[0].replace(/[._]/g, ' ');
              localStorage.setItem('user_name', nameFromEmail.split(' ').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(' '));
            }
            if (profile.plan) {
              localStorage.setItem('user_plan', profile.plan);
            }
          }
        }
      } catch {
        // Fallback: nome do email
        const nameFromEmail = email.split('@')[0].replace(/[._]/g, ' ');
        localStorage.setItem('user_name', nameFromEmail.split(' ').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(' '));
      }
      
      // Marcar onboarding como completo para logins de retorno (pular tela de configuração)
      localStorage.setItem('onboarding_completed', 'true');
      // Atualizar estado React compartilhado via AuthContext
      auth.login(result.access_token || localStorage.getItem('access_token') || '', email, localStorage.getItem('user_plan') || 'free');
      // Navegação SPA (sem reload)
      navigate('/dashboard');
    } catch (err) {
      console.error('Erro no login:', err);
      console.error('[Login] Detalhes:', {
        isAxios: axios.isAxiosError(err),
        status: axios.isAxiosError(err) ? err.response?.status : 'N/A',
        data: axios.isAxiosError(err) ? err.response?.data : 'N/A',
        message: err instanceof Error ? err.message : String(err),
        url: axios.isAxiosError(err) ? err.config?.url : 'N/A',
        baseURL: axios.isAxiosError(err) ? err.config?.baseURL : 'N/A',
      });
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        const detail = err.response?.data?.detail;
        if (status === 401) {
          setError('Email ou senha inválidos.');
        } else if (status === 403) {
          setError(detail || 'Conta suspensa. Entre em contato com o suporte.');
        } else if (status === 500) {
          setError('Erro interno no servidor. Tente novamente em instantes.');
        } else if (!err.response) {
          setError('Servidor indisponível. Verifique se o backend está rodando.');
        } else {
          setError(detail || `Erro ${status}. Tente novamente.`);
        }
      } else {
        setError('Erro de conexão. Verifique sua rede.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [email, password, rememberMe, navigate, auth]);

  const handleSignup = useCallback(async () => {
    if (!email || !password || !fullName) {
      setError('Preencha todos os campos');
      return;
    }
    
    if (password.length < 8) {
      setError('Senha deve ter no mínimo 8 caracteres');
      return;
    }

    if (!lgpdConsent) {
      setError('Você precisa aceitar os Termos de Uso e a Política de Privacidade para criar uma conta');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      await authServiceSignup(email, password, fullName, commPreference);
      // Salvar nome do usuário
      localStorage.setItem('user_name', fullName);
      // Salvar "Lembrar-me" se marcado
      if (rememberMe) {
        localStorage.setItem('nexus_remember_email', email);
        localStorage.setItem('nexus_remember_me', 'true');
      }
      // Atualizar estado React compartilhado via AuthContext
      const savedToken = localStorage.getItem('access_token') || '';
      auth.login(savedToken, email, 'free');
      // Após cadastro, ir direto para o dashboard (plano gratuito ativado)
      navigate('/dashboard');
    } catch (err) {
      console.error('Erro no cadastro:', err);
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
      setError(detail || 'Erro ao criar conta. Tente novamente.');
    } finally {
      setIsLoading(false);
    }
  }, [email, password, fullName, lgpdConsent, commPreference, rememberMe, navigate, auth]);

  const handleGoogleLogin = useCallback(() => {
    // Usa proxy do Vite para redirecionar ao backend
    window.location.href = apiUrl('/api/auth/google/start');
  }, []);

  const handleForgotPassword = useCallback(() => {
    setShowForgotPassword(true);
    setForgotEmail(email);
  }, [email]);

  const handleSendRecovery = useCallback(async () => {
    if (!forgotEmail) {
      setError('Informe seu email para recuperar a senha');
      setShowForgotPassword(false);
      return;
    }
    // Tenta chamar endpoint de recovery no backend
    try {
      await fetch(apiUrl('/api/auth/forgot-password'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: forgotEmail })
      });
    } catch {
      // Silencia - mostrar sucesso de qualquer forma (anti-enumeração)
    }
    setShowForgotPassword(false);
    setError(null);
    setSuccessMsg(`Enviamos um link de recuperação para ${forgotEmail}. Verifique sua caixa de entrada e a pasta de spam.`);
    setTimeout(() => setSuccessMsg(null), 8000);
  }, [forgotEmail]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-900 to-slate-900 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Modal Recuperar Senha */}
      {showForgotPassword && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-8 shadow-2xl">
            <h3 className="text-xl font-bold text-gray-800 mb-2">Recuperar senha</h3>
            <p className="text-gray-500 text-sm mb-6">Informe seu email e enviaremos um link para redefinir sua senha.</p>
            <input
              type="email"
              value={forgotEmail}
              onChange={(e) => setForgotEmail(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg text-gray-900 bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
              placeholder="seu@email.com"
            />
            <div className="flex gap-3">
              <button
                onClick={() => setShowForgotPassword(false)}
                className="flex-1 py-3 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 font-medium transition"
              >Cancelar</button>
              <button
                onClick={handleSendRecovery}
                className="flex-1 py-3 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 transition"
              >Enviar link</button>
            </div>
          </div>
        </div>
      )}

      {/* Toast de sucesso recuperação */}
      {successMsg && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 bg-green-600 text-white px-6 py-3 rounded-lg shadow-lg flex items-center gap-2 text-sm font-medium max-w-md text-center">
          ✉️ {successMsg}
        </div>
      )}
      {/* Padrão de fundo decorativo */}
      <div className="absolute inset-0 opacity-5">
        <div className="absolute top-0 right-0 w-96 h-96 bg-blue-400 rounded-full blur-3xl"></div>
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-purple-400 rounded-full blur-3xl"></div>
      </div>

      {/* Container Principal */}
      <div className="relative z-10 w-full max-w-6xl grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
        {/* COLUNA ESQUERDA - BENEFÍCIOS E RESULTADOS */}
        <div className="text-white space-y-6 lg:pr-12">
          {/* Logo + Título */}
          <div className="mb-8">
            <div className="flex items-center space-x-4 mb-6">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500 via-purple-500 to-cyan-500 flex items-center justify-center shadow-2xl shadow-blue-500/30 ring-4 ring-white/10">
                <span className="text-white font-black text-3xl">N</span>
              </div>
              <div>
                <h1 className="text-5xl font-black tracking-tight bg-gradient-to-r from-blue-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
                  NEXUS
                </h1>
                <p className="text-indigo-300 font-semibold text-sm">
                  Automação Empresarial Inteligente
                </p>
              </div>
            </div>
          </div>

          {/* Proposta de Valor */}
          <div className="space-y-4">
            <h2 className="text-3xl font-bold leading-tight">
              Economize horas por semana automatizando tarefas do seu negócio
            </h2>
            <p className="text-indigo-200 text-lg leading-relaxed">
              Sistema completo de automação para MEI e pequenos negócios. Gerencie agenda, clientes, financeiro e cobranças em um só lugar.
            </p>
          </div>

          {/* Benefícios Tangíveis */}
          <div className="space-y-4 pt-4">
            {/* Benefício 1: Economia de Tempo */}
            <div className="flex items-start space-x-3">
              <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                <Clock className="w-6 h-6 text-blue-400" />
              </div>
              <div>
                <p className="font-bold text-lg mb-1">Economize tempo</p>
                <p className="text-indigo-300 text-sm leading-relaxed">
                  Automação de agenda, lembretes de cobrança e geração de notas fiscais. Foque no que importa: crescer seu negócio.
                </p>
              </div>
            </div>
            {/* Benefício 2: Aumento de Receita */}
            <div className="flex items-start space-x-3">
              <div className="w-12 h-12 rounded-xl bg-green-500/20 flex items-center justify-center flex-shrink-0">
                <TrendingUp className="w-6 h-6 text-green-400" />
              </div>
              <div>
                <p className="font-bold text-lg mb-1">Aumente sua receita</p>
                <p className="text-indigo-300 text-sm leading-relaxed">
                  Nunca mais perca um cliente. Sistema de CRM completo com follow-up automatizado e análise financeira em tempo real.
                </p>
              </div>
            </div>
            {/* Benefício 3: Segurança */}
            <div className="flex items-start space-x-3">
              <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                <Shield className="w-6 h-6 text-purple-400" />
              </div>
              <div>
                <p className="font-bold text-lg mb-1">100% seguro e confiável</p>
                <p className="text-indigo-300 text-sm leading-relaxed">
                  Seus dados protegidos com criptografia de nível empresarial. Backup automático e disponibilidade 24/7.
                </p>
              </div>
            </div>
          </div>

          {/* Prova Social */}
          <div className="pt-6 border-t border-indigo-700/30">
            <div className="flex items-center gap-2 text-sm">
              <div className="flex -space-x-2">
                <div className="w-8 h-8 rounded-full bg-blue-500 border-2 border-slate-900"></div>
                <div className="w-8 h-8 rounded-full bg-purple-500 border-2 border-slate-900"></div>
                <div className="w-8 h-8 rounded-full bg-cyan-500 border-2 border-slate-900"></div>
              </div>
              <span className="text-indigo-200">
                <strong className="text-white">Centenas</strong> de empresas já economizam horas com NEXUS
              </span>
            </div>
          </div>
        </div>

        {/* COLUNA DIREITA - FORMULÁRIO DE LOGIN */}
        <div className="bg-white rounded-2xl shadow-2xl p-8 lg:p-10">
          {/* Header */}
          <div className="mb-8">
            <h3 className="text-3xl font-black text-gray-900 mb-2">
              {isSignupMode ? 'Criar conta no NEXUS' : 'Entrar no NEXUS'}
            </h3>
            <p className="text-gray-600 text-sm">
              {isSignupMode 
                ? 'Crie sua conta e comece a automatizar seu negócio' 
                : 'Acesse sua conta e automatize seu negócio agora'}
            </p>
          </div>

          {/* Mensagem de Erro */}
          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          {/* Formulário */}
          <div className="space-y-5">
            {/* Input Nome (apenas no cadastro) */}
            {isSignupMode && (
              <div>
                <label htmlFor="fullName" className="block text-sm font-semibold text-gray-700 mb-2">
                  Nome completo
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <User className="h-5 w-5 text-gray-400" />
                  </div>
                  <input
                    id="fullName"
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="block w-full pl-10 pr-3 py-3.5 border border-gray-300 rounded-lg 
                             text-gray-900 placeholder-gray-400 bg-gray-50
                             focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 focus:bg-white
                             transition-all duration-300"
                    placeholder="Seu nome completo"
                  />
                </div>
              </div>
            )}

            {/* Input Email */}
            <div>
              <label htmlFor="email" className="block text-sm font-semibold text-gray-700 mb-2">
                Email
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                  className="block w-full pl-10 pr-3 py-3.5 border border-gray-300 rounded-lg 
                           text-gray-900 placeholder-gray-400 bg-gray-50
                           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 focus:bg-white
                           transition-all duration-300"
                  placeholder="seu@email.com"
                />
              </div>
            </div>

            {/* Input Senha */}
            <div>
              <label htmlFor="password" className="block text-sm font-semibold text-gray-700 mb-2">
                Senha
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                  className="block w-full pl-10 pr-12 py-3.5 border border-gray-300 rounded-lg 
                           text-gray-900 placeholder-gray-400 bg-gray-50
                           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 focus:bg-white
                           transition-all duration-300"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 transition-colors"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            {/* Lembrar / Esqueceu */}
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <input
                  id="remember"
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded cursor-pointer"
                />
                <label htmlFor="remember" className="ml-2 block text-sm text-gray-700 cursor-pointer">
                  Lembrar-me
                </label>
              </div>
              <button 
                onClick={handleForgotPassword}
                className="text-sm font-semibold text-blue-600 hover:text-blue-700 transition-colors"
              >
                Esqueceu a senha?
              </button>
            </div>

            {/* LGPD Consent (apenas no cadastro) */}
            {isSignupMode && (
              <>
                {/* Preferência de comunicação */}
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Como prefere se comunicar?
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { id: 'email', label: 'Email', icon: '✉️' },
                      { id: 'whatsapp', label: 'WhatsApp', icon: '📱' },
                      { id: 'sms', label: 'SMS', icon: '💬' },
                    ].map((opt) => (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => setCommPreference(opt.id)}
                        className={`flex items-center justify-center gap-1.5 py-2.5 rounded-lg border text-sm font-medium transition-all ${
                          commPreference === opt.id
                            ? 'border-blue-500 bg-blue-50 text-blue-700 ring-2 ring-blue-200'
                            : 'border-gray-300 text-gray-600 hover:border-gray-400 hover:bg-gray-50'
                        }`}
                      >
                        <span>{opt.icon}</span>
                        <span>{opt.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-start gap-2">
                <input
                  id="lgpd-consent"
                  type="checkbox"
                  checked={lgpdConsent}
                  onChange={(e) => setLgpdConsent(e.target.checked)}
                  className="h-4 w-4 mt-0.5 text-blue-600 focus:ring-blue-500 border-gray-300 rounded cursor-pointer"
                />
                <label htmlFor="lgpd-consent" className="text-xs text-gray-600 cursor-pointer leading-relaxed">
                  Li e aceito os{' '}
                  <a href="/termos" target="_blank" className="text-blue-600 hover:underline font-medium">Termos de Uso</a>
                  {' '}e a{' '}
                  <a href="/privacidade" target="_blank" className="text-blue-600 hover:underline font-medium">Política de Privacidade</a>
                  {' '}(LGPD).
                </label>
              </div>
              </>
            )}

            {/* Botão Entrar/Cadastrar */}
            <button
              onClick={isSignupMode ? handleSignup : handleLogin}
              disabled={isLoading}
              className="w-full bg-gradient-to-r from-blue-600 to-blue-700 
                       text-white font-bold py-4 rounded-lg
                       hover:from-blue-700 hover:to-blue-800 
                       hover:shadow-xl hover:scale-[1.02]
                       active:scale-[0.98]
                       focus:ring-4 focus:ring-blue-300 focus:outline-none
                       transition-all duration-300
                       disabled:opacity-50 disabled:cursor-not-allowed
                       flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>{isSignupMode ? 'Criando conta...' : 'Entrando...'}</span>
                </>
              ) : (
                <>
                  <Zap className="w-5 h-5" />
                  <span>{isSignupMode ? 'Criar minha conta' : 'Entrar no NEXUS'}</span>
                </>
              )}
            </button>

            {/* Divisor */}
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-gray-500 font-medium">ou continue com</span>
              </div>
            </div>

            {/* Botão Google (CORRIGIDO) */}
            <button
              onClick={handleGoogleLogin}
              type="button"
              className="w-full bg-white border-2 border-gray-300 text-gray-700 font-semibold py-3.5 rounded-lg
                       hover:bg-gray-50 hover:border-gray-400 hover:shadow-md
                       active:scale-[0.98]
                       transition-all duration-300
                       flex items-center justify-center gap-3"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              <span>Continuar com Google</span>
            </button>
          </div>

          {/* Footer - Alternar Login/Cadastro */}
          <div className="mt-8 pt-6 border-t border-gray-200 text-center">
            <p className="text-sm text-gray-600">
              {isSignupMode ? 'Já tem uma conta?' : 'Não tem uma conta?'}{' '}
              <button 
                onClick={() => {
                  setIsSignupMode(!isSignupMode);
                  setError(null);
                }}
                className="font-bold text-blue-600 hover:text-blue-700 hover:underline transition-colors"
              >
                {isSignupMode ? 'Fazer login' : 'Criar conta grátis'}
              </button>
            </p>
          </div>

          {/* Badge de Garantia */}
          <div className="mt-6 p-4 bg-gradient-to-r from-green-50 to-blue-50 rounded-lg border border-green-200">
            <div className="flex items-center justify-center gap-2 text-sm">
              <Shield className="w-4 h-4 text-green-600" />
              <span className="text-gray-700">
                <span className="font-bold text-green-700">Comece grátis — para sempre</span> • Sem cartão de crédito
              </span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
