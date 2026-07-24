/**
 * Perfil de atendimento — regras de ambiente
 * ==========================================
 * O NEXUS adapta a experiência ao perfil escolhido no onboarding
 * (User.profile_type). Perfis FORA do modelo de assinatura não devem ver
 * NENHUMA superfície de cobrança (Pricing, upsell, banner de upgrade, aviso
 * de trial):
 *
 *  - cliente_servico: cliente final de uma empresa/profissional. Quem paga o
 *    consumo é a empresa contratante (rateio via contrato).
 *  - agencia_cooperativa: parceira que usa a infraestrutura do NEXUS para
 *    atender os clientes dela; a remuneração é contrato comercial medido por
 *    consumo, não plano de assinatura.
 *
 * MEI, autônomo, pequeno negócio e profissional liberal seguem o freemium
 * normal (planos + addon).
 */

export const BILLING_EXEMPT_PROFILES = ['cliente_servico', 'agencia_cooperativa'] as const

/** True se o perfil NÃO participa de plano/upsell/addon. */
export function isBillingExempt(profile: string | null | undefined): boolean {
  return !!profile && (BILLING_EXEMPT_PROFILES as readonly string[]).includes(profile)
}
