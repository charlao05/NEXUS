/**
 * TrialExpired — DEPRECATED
 * ===========================
 * No modelo freemium permanente, o plano gratuito nunca expira.
 * Este componente redireciona para /pricing caso seja acessado.
 */

import { Navigate } from 'react-router-dom';

export default function TrialExpired() {
  return <Navigate to="/pricing" replace />;
}
