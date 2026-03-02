import React from 'react';
import { motion } from 'framer-motion';
import { Zap, Brain, Link2, Shield, TrendingUp, Workflow } from 'lucide-react';

interface AuthLayoutProps {
  children: React.ReactNode;
  title: string;
}

export function AuthLayout({ children, title }: AuthLayoutProps) {
  const benefits = [
    {
      icon: Zap,
      title: 'Automatize em Minutos',
      description: 'Sem código, sem complexidade'
    },
    {
      icon: Brain,
      title: 'IA Inteligente',
      description: 'Entende seu negócio automaticamente'
    },
    {
      icon: Link2,
      title: '300+ Integrações',
      description: 'Conecte suas ferramentas favoritas'
    },
    {
      icon: Shield,
      title: 'Segurança Garantida',
      description: 'LGPD compliant e certificado SSL'
    },
    {
      icon: TrendingUp,
      title: 'ROI Comprovado',
      description: 'Economize horas por semana automatizando tarefas do seu negócio.'
    },
    {
      icon: Workflow,
      title: 'Fluxos Ilimitados',
      description: 'Crie quantos processos precisar'
    }
  ];

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.3
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.5 }
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
      {/* Background animated elements */}
      <div className="absolute top-0 left-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2 animate-pulse"></div>
      <div className="absolute bottom-0 right-0 w-96 h-96 bg-green-500/10 rounded-full blur-3xl translate-x-1/2 translate-y-1/2 animate-pulse" style={{ animationDelay: '1s' }}></div>

      <div className="w-full max-w-7xl grid grid-cols-1 lg:grid-cols-2 gap-8 items-center relative z-10">
        {/* LEFT SIDE - Benefits & Trust */}
        <motion.div
          className="hidden lg:flex flex-col space-y-8"
          initial={{ opacity: 0, x: -50 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        >
          <div className="space-y-4">
            <h1 className="text-5xl font-bold bg-gradient-to-r from-green-400 via-blue-400 to-purple-400 bg-clip-text text-transparent">
              Automatize Tudo.
              <br />
              Sem Código.
              <br />
              Com IA.
            </h1>
            <p className="text-xl text-slate-300">
              Junte-se a centenas de empresas que economizam tempo com NEXUS
            </p>
          </div>

          {/* Trust badges */}
          <div className="flex items-center gap-4">
            <div className="flex -space-x-3">
              {[1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  className="w-10 h-10 rounded-full bg-gradient-to-br from-green-400 to-blue-500 border-2 border-slate-800 flex items-center justify-center text-white text-sm font-bold"
                >
                  {i}
                </div>
              ))}
            </div>
            <div className="text-sm text-slate-300">
              <p className="font-semibold text-white">127 pessoas</p>
              <p>se cadastraram hoje</p>
            </div>
          </div>

          {/* Benefits Grid */}
          <motion.div
            className="grid grid-cols-1 gap-4"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            {benefits.map((benefit, idx) => {
              const Icon = benefit.icon;
              return (
                <motion.div
                  key={idx}
                  className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 hover:border-green-500/50 transition-all"
                  variants={itemVariants}
                  whileHover={{ x: 10 }}
                >
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-gradient-to-br from-green-400/20 to-blue-500/20 rounded-lg">
                      <Icon className="w-5 h-5 text-green-400" />
                    </div>
                    <div>
                      <p className="font-semibold text-white">{benefit.title}</p>
                      <p className="text-sm text-slate-400">{benefit.description}</p>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </motion.div>

          {/* Rating */}
          <div className="flex items-center gap-3 bg-slate-800/30 border border-slate-700 rounded-lg p-4 w-fit">
            <div className="flex gap-1">
              {[...Array(5)].map((_, i) => (
                <span key={i} className="text-lg">⭐</span>
              ))}
            </div>
            <div className="text-sm">
              <p className="font-semibold text-white">4.9/5.0</p>
              <p className="text-slate-400">2.000+ avaliações</p>
            </div>
          </div>
        </motion.div>

        {/* RIGHT SIDE - Form Card */}
        <motion.div
          className="w-full max-w-md"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2 }}
        >
          <div className="bg-slate-800/80 backdrop-blur border border-slate-700 rounded-2xl p-8 shadow-2xl">
            {/* Logo */}
            <div className="mb-8 text-center">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-gradient-to-br from-green-400 to-blue-500 mb-4">
                <Zap className="w-6 h-6 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">NEXUS</h2>
              <p className="text-slate-400">{title}</p>
            </div>

            {/* Form */}
            {children}

            {/* Footer */}
            <div className="mt-8 text-center text-sm text-slate-400">
              <p>
                Ao continuar, você concorda com nossos{' '}
                <a href="#" className="text-green-400 hover:text-green-300 transition">
                  Termos de Serviço
                </a>
                {' '}e{' '}
                <a href="#" className="text-green-400 hover:text-green-300 transition">
                  Política de Privacidade
                </a>
              </p>
            </div>

            {/* Security badge */}
            <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-400">
              <Shield className="w-4 h-4 text-green-400" />
              <span>Seus dados são criptografados e seguros</span>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
