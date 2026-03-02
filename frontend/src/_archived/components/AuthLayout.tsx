import { motion } from 'framer-motion'
import { Zap, Shield, Lock } from 'lucide-react'

interface AuthLayoutProps {
  children: React.ReactNode
  title: string
}

const benefits = [
  {
    icon: Zap,
    title: 'Acesso Rápido',
    description: 'Login simples e seguro'
  },
  {
    icon: Shield,
    title: 'Protegido',
    description: 'Seus dados em segurança'
  },
  {
    icon: Lock,
    title: 'Privacidade',
    description: 'Controle total da sua conta'
  }
]

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.2
    }
  }
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5 }
  }
}

export default function AuthLayout({ children, title }: AuthLayoutProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white overflow-hidden">
      {/* Animated Background Blurs */}
      <motion.div
        className="absolute inset-0 overflow-hidden pointer-events-none"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1 }}
      >
        <motion.div
          className="absolute -top-40 -right-40 w-80 h-80 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20"
          animate={{
            x: [0, 30, 0],
            y: [0, 30, 0]
          }}
          transition={{ duration: 8, repeat: Infinity }}
        />
        <motion.div
          className="absolute -bottom-40 -left-40 w-80 h-80 bg-green-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20"
          animate={{
            x: [0, -30, 0],
            y: [0, -30, 0]
          }}
          transition={{ duration: 10, repeat: Infinity }}
        />
        <motion.div
          className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-10"
          animate={{
            scale: [1, 1.1, 1]
          }}
          transition={{ duration: 7, repeat: Infinity }}
        />
      </motion.div>

      {/* Main Content */}
      <div className="relative z-10 min-h-screen flex items-center justify-center p-4 sm:p-6 lg:p-8">
        <div className="w-full max-w-7xl grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 items-center">
          {/* Left Side - Benefits (Hidden on mobile) */}
          <motion.div
            className="hidden lg:flex flex-col justify-center"
            initial={{ opacity: 0, x: -50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            {/* Header */}
            <div className="mb-12">
              <motion.h1
                className="text-5xl lg:text-6xl font-bold mb-4 bg-gradient-to-r from-green-400 to-blue-500 bg-clip-text text-transparent"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.4 }}
              >
                NEXUS
              </motion.h1>
              <motion.p
                className="text-lg text-slate-300 leading-relaxed"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.5 }}
              >
                Plataforma de gestão e automação
              </motion.p>
            </div>

            {/* Benefits Grid */}
            <motion.div
              className="grid grid-cols-1 gap-6"
              variants={containerVariants}
              initial="hidden"
              animate="visible"
            >
              {benefits.map((benefit, idx) => {
                const Icon = benefit.icon
                return (
                  <motion.div
                    key={idx}
                    variants={itemVariants}
                    whileHover={{ x: 10 }}
                    className="group"
                  >
                    <div className="flex items-start gap-4 p-4 rounded-xl bg-slate-800/50 hover:bg-slate-700/50 border border-slate-700/50 hover:border-green-400/30 transition-all duration-300">
                      <div className="flex-shrink-0 mt-1">
                        <Icon className="w-6 h-6 text-green-400 group-hover:text-green-300 transition-colors" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-base text-white group-hover:text-green-400 transition-colors">
                          {benefit.title}
                        </h3>
                        <p className="text-sm text-slate-400 mt-1">
                          {benefit.description}
                        </p>
                      </div>
                    </div>
                  </motion.div>
                )
              })}
            </motion.div>

            {/* Trust Badges */}
            <motion.div
              className="mt-12 space-y-4"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.8 }}
            >
              {/* Security Badge */}
              <div className="flex items-center gap-2 text-sm text-slate-300">
                <Lock className="w-4 h-4 text-green-400" />
                <span>Conexão segura</span>
              </div>
            </motion.div>
          </motion.div>

          {/* Right Side - Form Card */}
          <motion.div
            className="flex items-center justify-center"
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            <div className="w-full max-w-md">
              {/* Form Container */}
              <motion.div
                className="bg-slate-800/80 backdrop-blur-xl border border-slate-700/50 rounded-2xl p-8 shadow-2xl hover:border-green-400/30 transition-colors duration-300"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.4 }}
              >
                {/* Form Header */}
                <div className="mb-8">
                  <h2 className="text-3xl font-bold text-white mb-2">
                    {title}
                  </h2>
                  <p className="text-sm text-slate-400">
                    {title === 'Criar Conta'
                      ? 'Preencha os dados para criar sua conta'
                      : 'Bem-vindo de volta'}
                  </p>
                </div>

                {/* Form Content */}
                {children}

                {/* Footer Links */}
                <motion.div
                  className="mt-8 pt-6 border-t border-slate-700/50"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.6, delay: 1 }}
                >
                  <p className="text-xs text-slate-400 text-center">
                    Ao continuar, você concorda com nossos{' '}
                    <a href="#" className="text-green-400 hover:text-green-300 transition-colors">
                      Termos
                    </a>
                    {' '}e{' '}
                    <a href="#" className="text-green-400 hover:text-green-300 transition-colors">
                      Privacidade
                    </a>
                  </p>
                </motion.div>
              </motion.div>

              {/* Security Info - Mobile Only */}
              {/* <motion.div
                className="lg:hidden mt-6 flex items-center justify-center gap-2 text-xs text-slate-400"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.6, delay: 0.6 }}
              >
                <Award className="w-4 h-4 text-green-400" />
                <span>Acesso seguro</span>
              </motion.div> */}
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
