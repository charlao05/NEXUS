/**
 * TrialExpired — DEPRECATED
 * ===========================
 * No modelo freemium permanente, o plano gratuito nunca expira.
 * Este componente redireciona para /pricing caso seja acessado.
 */

import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { isBillingExempt } from '../utils/profile';

export default function TrialExpired() {
  const { userProfile } = useAuth();
  // Perfis fora do modelo de assinatura nunca devem cair em tela de plano.
  if (isBillingExempt(userProfile)) return <Navigate to="/dashboard" replace />;
  return <Navigate to="/pricing" replace />;
}
