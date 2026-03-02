// import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import LoginForm from '../components/LoginForm'
import SignUpForm from '../components/SignUpForm'
import AuthLayout from '../components/AuthLayout'

export default function AuthPage() {
  const [searchParams] = useSearchParams()
  const mode = searchParams.get('mode') || 'login'

  return (
    <AuthLayout title={mode === 'signup' ? 'Criar Conta' : 'Entrar'}>
      <motion.div
        key={mode}
        initial={{ opacity: 0, x: mode === 'signup' ? 20 : -20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: mode === 'signup' ? -20 : 20 }}
        transition={{ duration: 0.3 }}
      >
        {mode === 'signup' ? (
          <SignUpForm />
        ) : (
          <LoginForm />
        )}
      </motion.div>
    </AuthLayout>
  )
}
