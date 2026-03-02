// Componentes Frontend para Autenticação e Pagamento
// React + TypeScript

import React, { useState } from 'react';
import { useNavigate, Navigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../hooks/useAuth';

interface SignUpFormData {
  email: string;
  password: string;
  full_name: string;
}

export function SignUp() {
  const [formData, setFormData] = useState<SignUpFormData>({
    email: '',
    password: '',
    full_name: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await axios.post('/api/auth/signup', formData);
      
      // Salvar token no localStorage (ou sessionStorage em produção)
      localStorage.setItem('access_token', response.data.access_token);
      localStorage.setItem('user_plan', response.data.plan);
      
      // Redirecionar para dashboard
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao cadastrar');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 flex items-center justify-center p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-8 max-w-md w-full">
        <h2 className="text-3xl font-bold text-white mb-6">Criar Conta NEXUS</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-900 border border-red-700 text-red-200 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <div>
            <label className="block text-slate-300 text-sm font-medium mb-2">
              Nome Completo
            </label>
            <input
              type="text"
              name="full_name"
              value={formData.full_name}
              onChange={handleChange}
              className="w-full bg-slate-700 border border-slate-600 rounded px-4 py-2 text-white"
              required
            />
          </div>

          <div>
            <label className="block text-slate-300 text-sm font-medium mb-2">
              Email
            </label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              className="w-full bg-slate-700 border border-slate-600 rounded px-4 py-2 text-white"
              required
            />
          </div>

          <div>
            <label className="block text-slate-300 text-sm font-medium mb-2">
              Senha
            </label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              className="w-full bg-slate-700 border border-slate-600 rounded px-4 py-2 text-white"
              required
              minLength={8}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold py-2 rounded"
          >
            {loading ? 'Criando conta...' : 'Cadastrar'}
          </button>
        </form>

        <p className="text-slate-400 text-center mt-4">
          Já tem conta?{' '}
          <a href="/login" className="text-blue-400 hover:text-blue-300">
            Faça login
          </a>
        </p>
      </div>
    </div>
  );
}


// src/pages/Pricing.tsx
interface PlanData {
  name: string;
  price: number;
  priceDisplay: string;
  description: string;
  features: string[];
  popular?: boolean;
  cta: string;
  planKey: string;
}

const PLANS_DATA: PlanData[] = [
  {
    name: "Free",
    price: 0,
    priceDisplay: "R$ 0",
    description: "Para começar e testar",
    planKey: "free",
    features: [
      "100 requisições/dia",
      "2.000 requisições/mês",
      "Acesso à API básica",
      "Documentação completa",
      "Suporte por email"
    ],
    cta: "Começar Grátis"
  },
  {
    name: "Pro",
    price: 97,
    priceDisplay: "R$ 97",
    description: "Para profissionais",
    planKey: "pro",
    popular: true,
    features: [
      "10.000 requisições/dia",
      "300.000 requisições/mês",
      "API avançada completa",
      "Webhooks em tempo real",
      "Suporte prioritário",
      "10 conexões simultâneas"
    ],
    cta: "Assinar Pro"
  },
  {
    name: "Enterprise",
    price: 497,
    priceDisplay: "R$ 497",
    description: "Para grandes operações",
    planKey: "enterprise",
    features: [
      "Requisições ilimitadas",
      "API completa + integrações",
      "Suporte dedicado 24/7",
      "Conexões ilimitadas",
      "SLA garantido",
      "Customizações sob demanda"
    ],
    cta: "Falar com Vendas"
  }
];

export function Pricing() {
  const navigate = useNavigate();
  const { token } = useAuth();
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState('');

  const handleSelectPlan = async (plan: PlanData) => {
    if (plan.planKey === 'free') {
      navigate('/?mode=signup');
      return;
    }

    if (!token) {
      // Usuário não logado, redirecionar para signup
      navigate('/?mode=signup');
      return;
    }

    // Iniciar checkout Stripe
    setLoading(plan.planKey);
    setError('');

    try {
      // Pegar email do token JWT (ou usar um default)
      const tokenPayload = JSON.parse(atob(token.split('.')[1]));
      const email = tokenPayload.email || 'user@example.com';

      const response = await axios.post('/api/auth/checkout', {
        plan: plan.planKey,
        email: email
      });

      // Redirecionar para Stripe Checkout
      if (response.data.checkout_url) {
        window.location.href = response.data.checkout_url;
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao iniciar checkout');
      setLoading(null);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 py-16 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-white mb-4">
            Planos <span className="text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-500">NEXUS</span>
          </h1>
          <p className="text-xl text-slate-400 max-w-2xl mx-auto">
            Escolha o plano ideal para automatizar seus processos e escalar seu negócio
          </p>
        </div>

        {error && (
          <div className="max-w-md mx-auto mb-8 bg-red-900/50 border border-red-700 text-red-200 px-4 py-3 rounded-lg text-center">
            {error}
          </div>
        )}

        {/* Plans Grid */}
        <div className="grid md:grid-cols-3 gap-8">
          {PLANS_DATA.map((plan) => (
            <div
              key={plan.planKey}
              className={`relative rounded-2xl p-8 transition-all duration-300 ${
                plan.popular
                  ? 'bg-gradient-to-br from-green-900/40 to-emerald-900/40 border-2 border-green-500 scale-105 shadow-2xl shadow-green-500/20'
                  : 'bg-slate-800/70 border border-slate-700 hover:border-slate-600'
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="px-4 py-1 bg-gradient-to-r from-green-500 to-emerald-500 text-white text-sm font-bold rounded-full">
                    MAIS POPULAR
                  </span>
                </div>
              )}

              <div className="text-center mb-6">
                <h3 className="text-2xl font-bold text-white mb-2">{plan.name}</h3>
                <p className="text-slate-400 text-sm">{plan.description}</p>
              </div>

              <div className="text-center mb-8">
                <span className="text-5xl font-bold text-white">{plan.priceDisplay}</span>
                {plan.price > 0 && <span className="text-slate-400">/mês</span>}
              </div>

              <ul className="space-y-4 mb-8">
                {plan.features.map((feature, idx) => (
                  <li key={idx} className="flex items-start gap-3 text-slate-300">
                    <svg className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    {feature}
                  </li>
                ))}
              </ul>

              <button
                onClick={() => handleSelectPlan(plan)}
                disabled={loading !== null}
                className={`w-full py-3 rounded-xl font-bold transition-all duration-200 ${
                  plan.popular
                    ? 'bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-400 hover:to-emerald-400 text-white shadow-lg shadow-green-500/30'
                    : 'bg-slate-700 hover:bg-slate-600 text-white'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {loading === plan.planKey ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Processando...
                  </span>
                ) : (
                  plan.cta
                )}
              </button>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="text-center mt-16">
          <p className="text-slate-400 mb-4">
            Teste grátis por 14 dias • Sem cartão de crédito
          </p>
          <button
            onClick={() => navigate('/?mode=login')}
            className="text-green-400 hover:text-green-300 transition"
          >
            ← Voltar para Login
          </button>
        </div>
      </div>
    </div>
  );
}


// src/components/ProtectedRoute.tsx
interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredPlan?: string;
}

export function ProtectedRoute({ children, requiredPlan: _requiredPlan }: ProtectedRouteProps) {
  const { token } = useAuth();

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
