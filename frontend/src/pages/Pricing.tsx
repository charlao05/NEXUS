/**
 * Pricing Page - NEXUS
 * Página de escolha de plano — modelo freemium permanente + 3 planos pagos
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { createCheckout, createAddonCheckout } from '../services/authService';
import { Check, Zap, Crown, Gift, Rocket, ArrowLeft, Star, Users } from 'lucide-react';
import axios from 'axios';

interface Plan {
  id: string;
  name: string;
  price: string;
  priceNote?: string;
  description: string;
  features: string[];
  popular?: boolean;
  free?: boolean;
  icon: React.ReactNode;
  buttonText: string;
}

const plans: Plan[] = [
  {
    id: 'free',
    name: 'Gratuito',
    price: 'R$ 0',
    priceNote: 'para sempre',
    description: 'Comece sem pagar nada',
    icon: <Gift className="w-7 h-7" />,
    free: true,
    buttonText: 'Plano Atual',
    features: [
      '10 mensagens/dia com IA',
      '1 agente: Fiscal (contabilidade)',
      'Até 5 clientes e 5 fornecedores',
      '3 notas fiscais/mês',
      'Suporte por email',
      'Sem cartão de crédito',
      'Opção: +10 clientes/fornecedores por R$ 12,90 (compra única)',
    ],
  },
  {
    id: 'essencial',
    name: 'Essencial',
    price: 'R$ 39,90',
    priceNote: '/mês',
    description: 'Para quem está começando',
    icon: <Zap className="w-7 h-7" />,
    buttonText: 'Assinar Essencial',
    features: [
      '200 mensagens/dia com IA',
      '3 agentes: Fiscal, Clientes e Cobranças',
      'Até 100 clientes e 100 fornecedores',
      'Notas fiscais ilimitadas',
      'Lembretes automáticos',
      'Suporte prioritário',
    ],
  },
  {
    id: 'profissional',
    name: 'Profissional',
    price: 'R$ 69,90',
    priceNote: '/mês',
    description: 'Para profissionais autônomos',
    icon: <Star className="w-7 h-7" />,
    popular: true,
    buttonText: 'Assinar Profissional',
    features: [
      '1.000 mensagens/dia com IA',
      'Todos os 5 agentes de IA',
      'Até 500 clientes e 500 fornecedores',
      'Tudo ilimitado',
      'Automação completa',
      'Relatórios avançados',
      'Suporte prioritário',
    ],
  },
  {
    id: 'completo',
    name: 'Completo',
    price: 'R$ 99,90',
    priceNote: '/mês',
    description: 'Para empresas em escala',
    icon: <Crown className="w-7 h-7" />,
    buttonText: 'Assinar Completo',
    features: [
      'Mensagens ilimitadas',
      'Todos os agentes + futuros',
      'Clientes e fornecedores ilimitados',
      'Integração com outros sistemas',
      'Notificações automáticas personalizadas',
      'Suporte 24/7 dedicado',
      'Gerente de conta',
      'Garantia de disponibilidade 99,9%',
    ],
  },
];

export default function Pricing() {
  const navigate = useNavigate();
  const { userPlan, userEmail } = useAuth();
  const [isLoading, setIsLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Usar plano do AuthContext (validado pelo backend) em vez de localStorage
  const currentPlan = (userPlan || 'free').toLowerCase();
  // Normalizar aliases legados
  const normalizedPlan = currentPlan === 'pro' ? 'essencial' : currentPlan === 'enterprise' ? 'completo' : currentPlan;

  const handleSelectPlan = async (planId: string) => {
    console.log('🎯 Plano selecionado:', planId);
    
    // Se for plano free, já é o plano atual — ir para dashboard
    if (planId === 'free') {
      console.log('✅ Plano gratuito — redirecionando para dashboard');
      localStorage.setItem('user_plan', 'free');
      navigate('/dashboard');
      return;
    }

    setIsLoading(planId);
    setError(null);

    try {
      const email = userEmail || localStorage.getItem('user_email');
      console.log('📧 Email:', email);
      
      if (!email) {
        console.log('❌ Sem email, redirecionando para login');
        navigate('/login');
        return;
      }

      console.log('💳 Criando checkout para:', planId);
      const response = await createCheckout(planId, email);
      
      if (response.checkout_url) {
        window.location.href = response.checkout_url;
      } else {
        setError('Erro ao criar sessão de pagamento');
        setIsLoading(null);
      }
    } catch (err) {
      console.error('Erro no checkout:', err);
      const detail = axios.isAxiosError(err) ? (err.response?.data?.detail || '') : '';
      const status = axios.isAxiosError(err) ? err.response?.status : undefined;
      if (detail === 'Stripe não configurado' || status === 503) {
        setError('Sistema de pagamento em manutenção. Use o plano gratuito por enquanto ou entre em contato pelo suporte.');
      } else {
        setError(detail || 'Não foi possível iniciar o pagamento. Tente novamente ou escolha o plano gratuito.');
      }
      setIsLoading(null);
    }
  };

  const handleBack = () => {
    navigate('/dashboard');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-900 to-slate-900 py-8 px-4">
      {/* Header */}
      <div className="max-w-6xl mx-auto mb-8">
        <button
          onClick={handleBack}
          className="flex items-center gap-2 text-indigo-300 hover:text-white transition-colors mb-4"
        >
          <ArrowLeft className="w-5 h-5" />
          Voltar
        </button>

        <div className="text-center">
          <div className="flex items-center justify-center gap-3 mb-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 via-purple-500 to-cyan-500 flex items-center justify-center shadow-lg">
              <span className="text-white font-black text-xl">N</span>
            </div>
            <h1 className="text-3xl font-black text-white">NEXUS</h1>
          </div>
          
          <h2 className="text-2xl md:text-3xl font-bold text-white mb-2">
            Escolha Seu Plano
          </h2>
          <p className="text-lg text-indigo-200">
            <span className="text-green-400 font-semibold">Plano Gratuito para Sempre</span> • Faça upgrade quando quiser
          </p>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="max-w-2xl mx-auto mb-6">
          <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-3 text-red-200 text-center text-sm">
            {error}
          </div>
        </div>
      )}

      {/* Plans Grid - 4 colunas */}
      <div className="max-w-6xl mx-auto grid md:grid-cols-2 lg:grid-cols-4 gap-5">
        {plans.map((plan) => (
          <div
            key={plan.id}
            className={`relative bg-white/10 backdrop-blur-sm rounded-2xl p-5 border flex flex-col ${
              plan.popular 
                ? 'border-blue-400 shadow-xl shadow-blue-500/20' 
                : plan.free
                ? 'border-green-400/50'
                : 'border-white/20'
            }`}
          >
            {/* Badge */}
            {plan.popular && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="bg-gradient-to-r from-blue-500 to-purple-500 text-white text-xs font-bold px-3 py-1 rounded-full">
                  Mais Popular
                </span>
              </div>
            )}
            {plan.free && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="bg-gradient-to-r from-green-500 to-emerald-500 text-white text-xs font-bold px-3 py-1 rounded-full">
                  Sem Cartão
                </span>
              </div>
            )}

            {/* Plan Header */}
            <div className="text-center mb-3 pt-2">
              <div className={`w-12 h-12 mx-auto mb-2 rounded-xl flex items-center justify-center ${
                plan.popular 
                  ? 'bg-gradient-to-br from-blue-500 to-purple-500 text-white' 
                  : plan.free
                  ? 'bg-gradient-to-br from-green-500 to-emerald-500 text-white'
                  : 'bg-gradient-to-br from-purple-500 to-indigo-500 text-white'
              }`}>
                {plan.icon}
              </div>
              <h3 className="text-lg font-bold text-white">{plan.name}</h3>
              <p className="text-indigo-200 text-xs">{plan.description}</p>
            </div>

            {/* Price */}
            <div className="text-center mb-3">
              <span className={`text-3xl font-black ${plan.free ? 'text-green-400' : 'text-white'}`}>
                {plan.price}
              </span>
              {plan.priceNote && (
                <span className="text-indigo-300 text-sm ml-1">{plan.priceNote}</span>
              )}
            </div>

            {/* Features */}
            <ul className="space-y-2 mb-4 flex-grow">
              {plan.features.map((feature, index) => {
                const isExpansionOption = feature.startsWith('Opção:');
                return (
                  <li key={index} className={`flex items-start gap-2 ${isExpansionOption ? 'mt-3 pt-3 border-t border-white/10' : ''}`}>
                    {isExpansionOption ? (
                      <Zap className="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-400" />
                    ) : (
                      <Check className="w-4 h-4 flex-shrink-0 mt-0.5 text-green-400" />
                    )}
                    <span className={`text-sm ${isExpansionOption ? 'text-amber-300 font-medium' : 'text-indigo-100'}`}>
                      {isExpansionOption ? feature.replace('Opção: ', '') : feature}
                    </span>
                  </li>
                );
              })}
            </ul>

            {/* CTA Button - Cores diferenciadas por plano */}
            <button
              onClick={() => handleSelectPlan(plan.id)}
              disabled={isLoading !== null}
              className={`w-full py-3 px-4 rounded-xl font-bold text-sm transition-all duration-200 
                flex items-center justify-center gap-2
                ${plan.free 
                  ? 'bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-400 hover:to-emerald-400 hover:shadow-green-500/30' 
                  : plan.popular 
                    ? 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 hover:shadow-blue-500/30'
                    : 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 hover:shadow-purple-500/30'
                }
                text-white hover:shadow-lg hover:scale-[1.02]
                ${isLoading === plan.id ? 'opacity-70 cursor-wait' : ''}
                disabled:opacity-50 disabled:cursor-not-allowed
              `}
            >
              {isLoading === plan.id ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Processando...
                </>
              ) : normalizedPlan === plan.id ? (
                <>
                  <Rocket className="w-4 h-4" />
                  ✓ Plano Atual
                </>
              ) : (
                <>
                  <Rocket className="w-4 h-4" />
                  {plan.buttonText}
                </>
              )}
            </button>
          </div>
        ))}
      </div>

      {/* Addon: Pacote Extra de Clientes */}
      {normalizedPlan === 'free' && (
        <div className="max-w-6xl mx-auto mt-6">
          <div className="bg-gradient-to-r from-amber-500/10 to-orange-500/10 backdrop-blur-sm border border-amber-400/30 rounded-2xl p-5">
            <div className="flex flex-col md:flex-row items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center flex-shrink-0">
                <Users className="w-6 h-6 text-white" />
              </div>
              <div className="flex-1 text-center md:text-left">
                <h3 className="text-white font-bold text-base">Precisa de Mais Clientes Sem Mudar de Plano?</h3>
                <p className="text-indigo-200 text-sm mt-1">
                  Adicione <span className="text-amber-300 font-semibold">+10 clientes e +10 fornecedores</span> ao seu plano gratuito por apenas{' '}
                  <span className="text-amber-300 font-semibold">R$ 12,90 (compra única)</span>. Mensagens proporcionais inclusas.
                </p>
              </div>
              <button
                onClick={async () => {
                  setIsLoading('addon');
                  setError(null);
                  try {
                    const email = userEmail || localStorage.getItem('user_email');
                    if (!email) { navigate('/login'); return; }
                    const response = await createAddonCheckout(email);
                    if (response.checkout_url) {
                      window.location.href = response.checkout_url;
                    } else {
                      setError('Erro ao criar sessão de pagamento');
                    }
                  } catch (err) {
                    const detail = axios.isAxiosError(err) ? (err.response?.data?.detail || '') : '';
                    const status = axios.isAxiosError(err) ? err.response?.status : undefined;
                    if (detail === 'Stripe não configurado' || status === 503) {
                      setError('Sistema de pagamento em manutenção. Tente novamente mais tarde.');
                    } else {
                      setError(detail || 'Não foi possível iniciar o pagamento. Tente novamente.');
                    }
                  } finally {
                    setIsLoading(null);
                  }
                }}
                disabled={isLoading !== null}
                className={`px-6 py-3 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 text-white font-bold text-sm transition-all whitespace-nowrap flex items-center gap-2 ${
                  isLoading === 'addon' ? 'opacity-70 cursor-wait' : ''
                }`}
              >
                {isLoading === 'addon' ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Processando...
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4" />
                    Adicionar +10 Clientes/Fornecedores
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Trust Badges */}
      <div className="max-w-4xl mx-auto mt-8 text-center">
        <div className="flex flex-wrap justify-center gap-4 text-indigo-300 text-xs">
          <div className="flex items-center gap-1">
            <Check className="w-4 h-4 text-green-400" />
            Pagamento Seguro via Stripe
          </div>
          <div className="flex items-center gap-1">
            <Check className="w-4 h-4 text-green-400" />
            Cancele Quando Quiser
          </div>
          <div className="flex items-center gap-1">
            <Check className="w-4 h-4 text-green-400" />
            Garantia de 7 Dias
          </div>
        </div>
      </div>
    </div>
  );
}
