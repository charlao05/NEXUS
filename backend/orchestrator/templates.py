"""
Templates de Tarefas MEI — PT-BR.
==================================
Templates pré-definidos para automações de sites governamentais
e tarefas comuns de MEI (Microempreendedor Individual).

Cada template segue o padrão do Blueprint Comet:
- goal: Objetivo da tarefa
- constraints: Restrições e regras de segurança
- steps: Passos esperados (guia para o planner LLM)
- safety_rules: Regras de segurança obrigatórias
- site_config: Configuração do site alvo
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Templates MEI
# ---------------------------------------------------------------------------

TASK_TEMPLATES: dict[str, dict[str, Any]] = {
    # ── Receita Federal — Consulta CPF ───────────────────────────────
    "receita_federal_cpf": {
        "goal": "Consultar situação cadastral do CPF na Receita Federal",
        "site_config": {
            "name": "Receita Federal — CPF",
            "url": "https://servicos.receita.fazenda.gov.br/Servicos/CPF/ConsultaSituacao/ConsultaPublica.asp",
            "domain": "receita.fazenda.gov.br",
        },
        "constraints": [
            "Não inserir dados de cartão de crédito",
            "Parar se aparecer CAPTCHA e avisar o usuário",
            "Apenas consultar, não alterar dados cadastrais",
        ],
        "steps_hint": [
            "Navegar para a URL do serviço de consulta CPF",
            "Capturar estado da página para identificar campos",
            "Preencher campo de CPF com o número fornecido",
            "Preencher campo de data de nascimento se solicitado",
            "Resolver CAPTCHA se possível ou solicitar ajuda",
            "Clicar em Consultar",
            "Ler resultado da consulta (situação cadastral)",
            "Reportar resultado ao usuário",
        ],
        "safety_rules": [
            "NUNCA preencher campos de senha",
            "Se pedir login gov.br, PARAR e informar o usuário",
            "Capturar screenshot como evidência",
        ],
        "risk_level": "low",
    },

    # ── Receita Federal — Consulta CNPJ ──────────────────────────────
    "receita_federal_cnpj": {
        "goal": "Consultar situação cadastral do CNPJ na Receita Federal",
        "site_config": {
            "name": "Receita Federal — CNPJ",
            "url": "https://servicos.receita.fazenda.gov.br/servicos/cnpjreva/cnpjreva_solicitacao.asp",
            "domain": "receita.fazenda.gov.br",
        },
        "constraints": [
            "Apenas consultar, não alterar dados",
            "Parar em CAPTCHA",
        ],
        "steps_hint": [
            "Navegar para a URL do serviço de consulta CNPJ",
            "Capturar estado da página",
            "Inserir CNPJ no campo apropriado",
            "Resolver CAPTCHA ou solicitar ajuda",
            "Clicar em Consultar",
            "Ler e reportar resultado (razão social, situação, etc.)",
        ],
        "safety_rules": [
            "Não inserir dados além do CNPJ",
            "Screenshot de resultado obrigatório",
        ],
        "risk_level": "low",
    },

    # ── Simples Nacional — Portal ────────────────────────────────────
    "simples_nacional": {
        "goal": "Acessar Portal do Simples Nacional para consulta ou emissão de DAS",
        "site_config": {
            "name": "Portal do Simples Nacional",
            "url": "https://www8.receita.fazenda.gov.br/SimplesNacional/",
            "domain": "receita.fazenda.gov.br",
        },
        "constraints": [
            "Requer certificado digital ou login gov.br",
            "Se tela de login aparecer, PARAR para o usuário fazer login manualmente",
            "Não preencher credenciais automaticamente",
        ],
        "steps_hint": [
            "Navegar para o Portal do Simples Nacional",
            "Capturar estado da página e identificar opções disponíveis",
            "Identificar se é necessário login",
            "Se sim: PARAR e informar que o usuário precisa fazer login manualmente",
            "Se não: navegar até a seção de DAS/PGMEI",
            "Capturar informações disponíveis",
            "Reportar ao usuário",
        ],
        "safety_rules": [
            "NUNCA preencher login/senha",
            "Parar em tela de certificado digital",
            "Não clicar em links de pagamento sem aprovação",
        ],
        "risk_level": "medium",
    },

    # ── PGMEI — Emissão de DAS ──────────────────────────────────────
    "pgmei_das": {
        "goal": "Acessar o PGMEI para emissão de DAS (Documento de Arrecadação do Simples Nacional)",
        "site_config": {
            "name": "PGMEI — DAS",
            "url": "https://www8.receita.fazenda.gov.br/SimplesNacional/Aplicacoes/ATSPO/pgmei.app/Identificacao",
            "domain": "receita.fazenda.gov.br",
        },
        "constraints": [
            "Requer CNPJ do MEI",
            "Pode requerer validação adicional (CAPTCHA, código de acesso)",
        ],
        "steps_hint": [
            "Navegar para o PGMEI",
            "Capturar estado da página",
            "Inserir CNPJ do MEI",
            "Resolver validações ou solicitar ajuda",
            "Navegar até geração de DAS",
            "Selecionar período de apuração",
            "Gerar DAS e capturar link/PDF",
            "Reportar ao usuário com link para download",
        ],
        "safety_rules": [
            "Não preencher código de acesso — pedir ao usuário",
            "Screenshot de cada etapa importante",
            "Não clicar em pagamento automático",
        ],
        "risk_level": "medium",
    },

    # ── Prefeitura — NFS-e (genérica) ───────────────────────────────
    "prefeitura_nfse": {
        "goal": "Acessar sistema de NFS-e da Prefeitura para emissão de nota fiscal de serviço",
        "site_config": {
            "name": "Prefeitura — NFS-e",
            "url": "",  # Varia por cidade — será preenchido via dados do usuário
            "domain": "",
        },
        "constraints": [
            "URL varia conforme cidade do MEI",
            "Requer login na prefeitura (usuário/senha ou certificado)",
            "PARAR na tela de login para o usuário fazer manualmente",
        ],
        "steps_hint": [
            "Navegar para o sistema de NFS-e da prefeitura indicada",
            "Capturar estado da página",
            "Identificar se há tela de login",
            "Se sim: PARAR e informar o usuário",
            "Se autenticado: navegar até emissão de NFS-e",
            "Preencher dados da NFS-e conforme fornecidos",
            "Revisar dados antes de emitir",
            "Emitir nota ou PARAR para aprovação do usuário",
        ],
        "safety_rules": [
            "NUNCA preencher login/senha da prefeitura",
            "Aguardar aprovação do usuário antes de emitir a nota",
            "Não alterar valores ou alíquotas automaticamente",
        ],
        "risk_level": "high",
    },

    # ── gov.br — Portal genérico ────────────────────────────────────
    "gov_br": {
        "goal": "Acessar serviço no portal gov.br",
        "site_config": {
            "name": "gov.br",
            "url": "https://www.gov.br/pt-br",
            "domain": "gov.br",
        },
        "constraints": [
            "Portal gov.br requer login com conta gov.br",
            "PARAR na tela de login — o usuário faz manualmente",
        ],
        "steps_hint": [
            "Navegar para o portal gov.br ou serviço específico",
            "Capturar estado da página",
            "Se tela de login: PARAR e informar o usuário",
            "Se autenticado: navegar até o serviço solicitado",
            "Capturar informações e reportar",
        ],
        "safety_rules": [
            "NUNCA preencher credenciais gov.br",
            "Não autorizar aplicações terceiras automaticamente",
        ],
        "risk_level": "medium",
    },

    # ── E-CAC — Centro de Atendimento Virtual ────────────────────────
    "ecac": {
        "goal": "Acessar o e-CAC (Centro Virtual de Atendimento ao Contribuinte)",
        "site_config": {
            "name": "e-CAC",
            "url": "https://cav.receita.fazenda.gov.br/autenticacao/login",
            "domain": "receita.fazenda.gov.br",
        },
        "constraints": [
            "Requer login gov.br ou certificado digital",
            "SEMPRE parar na tela de login",
        ],
        "steps_hint": [
            "Navegar para o e-CAC",
            "PARAR na tela de login e informar o usuário",
            "Após login manual do usuário: continuar navegação",
            "Buscar serviço solicitado",
            "Capturar informações e reportar",
        ],
        "safety_rules": [
            "NUNCA preencher credenciais",
            "Não alterar dados cadastrais",
            "Não assinar documentos digitalmente",
        ],
        "risk_level": "high",
    },

    # ── Consulta genérica de site ────────────────────────────────────
    "generico": {
        "goal": "Acessar e interagir com um site conforme solicitação do usuário",
        "site_config": {
            "name": "Site genérico",
            "url": "",
            "domain": "",
        },
        "constraints": [
            "Seguir apenas domínios permitidos",
            "Não preencher dados sensíveis sem aprovação",
        ],
        "steps_hint": [
            "Navegar para o site solicitado",
            "Capturar estado da página com browser_get_page_state",
            "Identificar elementos relevantes para a tarefa",
            "Executar ações conforme o objetivo",
            "Capturar screenshot como evidência",
            "Reportar resultado ao usuário",
        ],
        "safety_rules": [
            "Não inserir senhas, CPF, dados bancários ou de cartão",
            "Se encontrar tela de login, PARAR e informar o usuário",
            "Não fazer transações financeiras sem aprovação explícita",
        ],
        "risk_level": "medium",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_template(site_hint: str) -> dict[str, Any]:
    """Retorna template para o site_hint informado, ou genérico."""
    return TASK_TEMPLATES.get(site_hint, TASK_TEMPLATES["generico"])


def get_template_names() -> list[str]:
    """Retorna nomes de todos os templates disponíveis."""
    return list(TASK_TEMPLATES.keys())


def format_template_for_llm(template: dict[str, Any], user_goal: str = "") -> str:
    """Formata template como contexto para o LLM planner.
    
    Retorna string com objetivo, restrições, passos sugeridos e regras.
    """
    lines = [
        f"TEMPLATE DE TAREFA: {template['goal']}",
        f"URL ALVO: {template['site_config'].get('url', 'N/A')}",
        f"RISCO: {template.get('risk_level', 'medium').upper()}",
        "",
        "RESTRIÇÕES:",
    ]
    for c in template.get("constraints", []):
        lines.append(f"  - {c}")
    
    lines.append("\nPASSOS SUGERIDOS:")
    for i, step in enumerate(template.get("steps_hint", []), 1):
        lines.append(f"  {i}. {step}")
    
    lines.append("\nREGRAS DE SEGURANÇA (OBRIGATÓRIAS):")
    for rule in template.get("safety_rules", []):
        lines.append(f"  ⚠️ {rule}")

    if user_goal:
        lines.append(f"\nOBJETIVO ESPECÍFICO DO USUÁRIO: {user_goal}")

    return "\n".join(lines)
