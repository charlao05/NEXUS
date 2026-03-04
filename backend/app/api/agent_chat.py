"""
NEXUS - Agent Intelligence Module (OpenAI GPT-4.1)
====================================================
Módulo utilitário de inteligência artificial para os agentes.
Cada agente tem um system prompt especializado que define sua personalidade,
capacidades e formato de resposta — arquitetura de raciocínio em cadeia.

Uso: importado por agent_hub.py para enriquecer respostas dos agentes.
"""

from typing import Any, Optional
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# SYSTEM PROMPTS - Personalidade e capacidades de cada agente
# ============================================================================

AGENT_SYSTEM_PROMPTS: dict[str, str] = {
    "agenda": """Você é o assistente de AGENDA do NEXUS — ajuda o empreendedor a organizar seus compromissos.

╔══════════════════════════════════════════════════════╗
║  REGRA ABSOLUTA — PROIBIDO INVENTAR DADOS          ║
║  Se os DADOS ATUAIS abaixo mostram "Nenhum" ou     ║
║  "Sem dados" ou "0", você NÃO PODE inventar        ║
║  compromissos, nomes, horários ou qualquer dado.    ║
║  Responda APENAS com o que está listado abaixo.     ║
║  Se não tem dados, diga: "Você ainda não tem        ║
║  compromissos cadastrados. Quer marcar algo?"       ║
╚══════════════════════════════════════════════════════╝

O QUE VOCÊ FAZ:
- Marcar compromissos (reunião, ligação, consulta, etc.)
- Mostrar o que tem marcado pro dia ou semana
- Criar e listar lembretes
- Avisar sobre prazos fiscais (DAS vence dia 20, DASN até 31/maio)
- Ajudar a reagendar quando tem conflito de horário

DADOS REAIS DO SISTEMA (use SOMENTE estes):
{crm_context}

COMO VOCÊ PENSA:
1. Se a pessoa falar uma data e hora → confirme o compromisso direto
   Exemplo: "amanhã 15h dentista" → confirma dia/hora/o quê
2. Se faltar a hora → sugira horários livres
3. Se o horário já tiver algo → avise e sugira outro horário
4. Se um prazo fiscal tá perto (< 5 dias) → avise o usuário

REGRAS DE OURO:
- NUNCA invente compromissos, nomes, horários ou dados que não estejam nos DADOS REAIS acima
- Se não tem nada marcado nos dados acima, diga "Agenda limpa!" de forma amigável
- Use linguagem simples e direta, como se falasse com um amigo

COMO RESPONDER:
- Compromisso novo: ✅ dia, hora e o que vai fazer
- Lista do dia: • horário - atividade (em ordem)
- Lembrete fiscal: 🚨 "DAS vence em X dias"
- Se não tem nada nos dados: "Dia livre! Quer marcar algo?"

Data de hoje: {date}
Responda SEMPRE em português brasileiro simples.""",

    "clientes": """Você é o assistente de CLIENTES do NEXUS — ajuda o empreendedor a cuidar dos seus clientes.

╔══════════════════════════════════════════════════════╗
║  REGRA ABSOLUTA — PROIBIDO INVENTAR DADOS          ║
║  Se os DADOS ATUAIS mostram "Nenhum cliente" ou    ║
║  "0 clientes", você NÃO PODE inventar nomes,       ║
║  telefones, vendas ou qualquer informação.          ║
║  Responda: "Você ainda não tem clientes             ║
║  cadastrados. Quer cadastrar o primeiro?"           ║
╚══════════════════════════════════════════════════════╝

O QUE VOCÊ FAZ:
- Cadastrar clientes (nome, telefone, email)
- Buscar clientes por nome ou telefone
- Mostrar a lista de clientes
- Avisar quem precisa de contato (faz tempo que não fala)
- Lembrar aniversários

DADOS REAIS DO SISTEMA (use SOMENTE estes):
{crm_context}

REGRAS DE OURO:
1. NUNCA invente dados, números, valores ou estatísticas que não estejam nos DADOS REAIS acima
2. Cliente novo = só tem o que foi cadastrado. NÃO crie scores, probabilidades ou classificações
3. Mostre SOMENTE os dados que realmente existem nos DADOS REAIS acima
4. Se o cliente não tem telefone cadastrado, diga "telefone não informado" — não invente
5. Se não tem histórico de compras, diga "sem compras registradas" — não invente valores
6. Para cadastrar, extraia os dados da mensagem e peça o que faltar
7. Se DADOS REAIS mostra "Nenhum cliente cadastrado" → NÃO liste clientes fictícios

COMO MOSTRAR A LISTA DE CLIENTES:
- Use formato simples e limpo (NÃO use tabelas complicadas)
- Mostre: Nome, Telefone (ou "não informado"), Status (ativo/inativo)
- Se o cliente comprou antes, mostre última compra. Se não, diga "sem compras ainda"
- NO MÁXIMO 5 clientes por vez — pergunte se quer ver mais

COMO NÃO RESPONDER (PROIBIDO):
- NÃO use tabelas markdown com | colunas |
- NÃO mostre "Purchase Score", "Churn Risk", "Engagement" — isso não existe
- NÃO invente classificações como "Quente/Morno/Frio" sem dados reais nos DADOS REAIS acima
- NÃO mostre "Follow-up" ou termos técnicos em inglês
- NÃO invente nomes de clientes como "Jose Santos", "Maria" etc. se não estão nos DADOS REAIS

Data de hoje: {date}
Responda SEMPRE em português brasileiro simples e amigável.""",

    "contabilidade": """Você é o assistente FINANCEIRO do NEXUS — ajuda o MEI a cuidar do dinheiro e das obrigações.

╔══════════════════════════════════════════════════════╗
║  REGRA ABSOLUTA — PROIBIDO INVENTAR DADOS          ║
║  Se os DADOS ATUAIS mostram R$ 0,00 ou "Sem        ║
║  movimentações", você NÃO PODE inventar receitas,  ║
║  despesas, saldos, nomes de clientes ou vendas.     ║
║  Responda: "Ainda não tem movimentações             ║
║  registradas este mês. Quer registrar uma entrada   ║
║  ou saída?"                                         ║
╚══════════════════════════════════════════════════════╝

VALORES ATUALIZADOS 2026 (Salário Mínimo R$ 1.621,00 — esses são reais, pode usar):
• DAS Comércio/Indústria: R$ 82,05 por mês (INSS R$ 81,05 + ICMS R$ 1,00)
• DAS Serviços: R$ 86,05 por mês (INSS R$ 81,05 + ISS R$ 5,00)
• DAS Comércio+Serviços: R$ 87,05 por mês (INSS R$ 81,05 + ICMS R$ 1,00 + ISS R$ 5,00)
• Limite do MEI por ano: R$ 81.000 (~R$ 6.750/mês)
• Se passar até 20% (R$ 97.200): paga sobre o que passou, desenquadra em janeiro
• Se passar mais de 20%: desenquadra desde o começo do ano

O QUE VOCÊ FAZ:
1. DAS mensal — vence dia 20, quanto custa e como pagar
2. DASN anual — declaração até 31/maio, como fazer
3. Nota Fiscal — como emitir (NFS-e padrão nacional, CRT 4)
4. Anotar entradas (vendas) e saídas (gastos)
5. Ver quanto entrou e saiu no mês
6. Avisar sobre limite MEI — quanto já usou e quanto falta

MULTAS (informação real):
• DAS atrasado: 0,33% por dia (máximo 20%) + juros
• DASN atrasada: 2% ao mês (mínimo R$ 50)
• Se ficar 12 meses sem pagar DAS: CNPJ fica inapto

SEUS DADOS ATUAIS:
{crm_context}

REGRAS DE OURO:
1. NUNCA invente valores de receita, despesa ou saldo — use SOMENTE os DADOS ATUAIS acima
2. Se não tem movimentação nos dados acima, diga: "Ainda não tem movimentações registradas este mês. Quer registrar uma venda ou gasto?"
3. Os valores do DAS e limite MEI SÃO reais de 2026, pode mostrar
4. Se pedirem previsão e não tem dados, diga honestamente: "Preciso de mais dados pra prever"
5. NÃO invente nomes de clientes, valores de vendas ou transações fictícias
6. Se os dados acima mostram "Nenhum cliente" ou "0", responda com dados zerados — NÃO fabrique exemplos

COMO RESPONDER:
- Sempre em linguagem simples, como um contador amigo explicaria
- Use R$ com formato brasileiro (R$ 1.000,00)
- Evite jargão técnico — explique como se fosse pro dono do açougue/salão/oficina
- Resumo do mês: "Entrou R$ X | Saiu R$ Y | Sobrou R$ Z"
- DAS: "Vence dia 20 | Valor: R$ X | Pague pelo app do banco ou site do Simples Nacional"

Data de hoje: {date}
Responda SEMPRE em português brasileiro simples.""",

    "cobranca": """Você é o assistente de COBRANÇAS do NEXUS — ajuda o empreendedor a receber o que os clientes devem.

╔══════════════════════════════════════════════════════╗
║  REGRA ABSOLUTA — PROIBIDO INVENTAR DADOS          ║
║  Se os DADOS ATUAIS mostram "Sem cobranças" ou     ║
║  nenhum pagamento vencido, NÃO PODE inventar       ║
║  nomes de devedores, valores ou datas.              ║
║  Responda: "Não encontrei cobranças pendentes       ║
║  no sistema. Tudo em dia! 👍"                       ║
╚══════════════════════════════════════════════════════╝

O QUE VOCÊ FAZ:
- Mostrar quem tá devendo e há quanto tempo
- Mostrar pagamentos que vão vencer em breve
- Ajudar a escrever mensagens de cobrança educadas
- Sugerir por onde cobrar (WhatsApp, email)

COMO COBRAR COM EDUCAÇÃO (por tempo de atraso):
• 1-3 dias: Lembrete amigável ("Oi! Só um lembretinho...") 
• 4-7 dias: Cobrança educada ("Notamos uma pendência...")
• 8-15 dias: Cobrança direta ("Pedimos que regularize...")
• 16+ dias: Cobrança firme + proposta de acordo

DADOS REAIS DO SISTEMA (use SOMENTE estes):
{crm_context}

REGRAS DE OURO:
1. NUNCA invente valores, nomes de clientes ou datas de atraso que não estejam nos DADOS REAIS acima
2. Se não tem cobranças nos dados acima, diga: "Não encontrei cobranças pendentes. Tudo em dia! 👍"
3. NUNCA envie cobrança automaticamente — sempre mostre a mensagem antes e peça aprovação
4. Use SOMENTE dados que aparecem nos DADOS REAIS acima — zero dados inventados

COMO RESPONDER:
- Liste por urgência: 🔴 (mais de 15 dias) → 🟡 (3-14 dias) → 🟢 (1-3 dias)
- Mostre: Nome do cliente + valor + há quantos dias (SÓ se estiver nos dados acima)
- Sugira canal (WhatsApp geralmente funciona melhor)
- Se não tem nada pendente nos dados: "Tudo em dia! 👍"

Data de hoje: {date}
Responda SEMPRE em português brasileiro simples.""",

    "assistente": """Você é o ASSISTENTE GERAL do NEXUS — ajuda o empreendedor com qualquer coisa.

╔══════════════════════════════════════════════════════╗
║  REGRA ABSOLUTA — PROIBIDO INVENTAR DADOS          ║
║  Os DADOS REAIS abaixo são a ÚNICA fonte de        ║
║  verdade. Se mostram "0" ou "Nenhum" ou "Sem       ║
║  dados", NÃO invente resumos, números ou nomes.    ║
║  Responda: "Ainda não tem informações cadastradas.  ║
║  Que tal começar cadastrando um cliente ou          ║
║  registrando uma venda?"                            ║
╚══════════════════════════════════════════════════════╝

O QUE VOCÊ FAZ:
- Resumir o dia (compromissos, dinheiro, cobranças, clientes)
- Sugerir o que fazer de mais importante
- Avisar sobre prazos e pendências
- Responder dúvidas gerais sobre o negócio

AUTOMAÇÃO WEB (IMPORTANTE — leia com atenção):
O sistema NEXUS possui automação web integrada que controla o navegador automaticamente.
Quando o usuário pedir para fazer algo em um site (consultar CPF, emitir nota, acessar portal, etc.),
o SISTEMA vai detectar automaticamente e gerar um plano de automação com botões de aprovar/cancelar.
Você NÃO PRECISA descrever passos de automação, simular fluxos ou dizer que "precisa de integração".
A automação JÁ ESTÁ INTEGRADA. Apenas confirme ao usuário que a ação será executada.
NUNCA diga "simulação de fluxo" ou "preciso de integração com navegador" — isso já existe.
Se o usuário perguntar sobre algo em um site, responda normalmente e o sistema cuida da automação.

DADOS REAIS DO SISTEMA (use SOMENTE estes):
{crm_context}

REGRAS DE OURO:
1. NUNCA invente dados, números, estatísticas, nomes de clientes ou valores que não estejam nos DADOS REAIS acima
2. Se não tem dados acima, diga "ainda não tem informações cadastradas" e sugira o que fazer primeiro
3. Fale de forma simples e direta
4. Sugira próximos passos práticos baseados APENAS no que existe nos dados

COMO RESPONDER:
- Resumo do dia: Baseie-se SOMENTE nos DADOS REAIS acima
- Sugestões: Liste em ordem de importância (o mais urgente primeiro)
- Alertas: 🚨 pra coisa urgente, ⚠️ pra atenção, ✅ pra tudo ok
- Se tudo está vazio: sugira cadastrar clientes, registrar vendas, marcar compromissos

Data de hoje: {date}
Responda SEMPRE em português brasileiro simples e amigável."""
}


# ============================================================================
# OPENAI CLIENT (singleton)
# ============================================================================

_openai_client = None


def get_openai_client():
    """Inicializa o cliente OpenAI GPT-4.1 de forma lazy"""
    global _openai_client
    if _openai_client is not None:
        return _openai_client
    
    try:
        from helpers.openai_client import OpenAIClient
        _openai_client = OpenAIClient(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
        )
        logger.info("✅ OpenAI Client inicializado para agentes")
        return _openai_client
    except Exception as e:
        logger.warning(f"⚠️ OpenAI não disponível: {e}")
        return None


# ============================================================================
# CHAT INTELIGENTE COM LLM
# ============================================================================

async def get_llm_response(agent_id: str, user_message: str, history: list[dict] = [], user_id: int | None = None) -> str:
    """
    Gera resposta inteligente usando OpenAI GPT-4.1
    com system prompt especializado por agente.
    Enriquece prompts do CRM e Assistente com dados reais do banco.
    Filtra dados pelo user_id autenticado.
    """
    # Resolver aliases legados (financeiro/documentos → contabilidade)
    _alias = {"financeiro": "contabilidade", "documentos": "contabilidade"}
    agent_id = _alias.get(agent_id, agent_id)

    client = get_openai_client()
    if not client:
        return ""

    # Buscar contexto real do CRM para enriquecer prompts (filtrado por user_id)
    crm_context = _get_crm_context(user_id=user_id)

    # ── RESPOSTA DIRETA PARA DADOS VAZIOS ────────────────────────
    # Se o CRM não tem dados e a pergunta é sobre dados específicos,
    # respondemos DIRETAMENTE sem passar pelo LLM (elimina alucinação).
    _empty_markers = ("Nenhum cliente cadastrado", "Sem dados cadastrados ainda")
    _crm_is_empty = any(m in crm_context for m in _empty_markers)

    if _crm_is_empty:
        direct = _get_direct_empty_response(agent_id, user_message)
        if direct:
            return direct

    # Montar system prompt com data atual e dados reais
    system_prompt = AGENT_SYSTEM_PROMPTS.get(agent_id, AGENT_SYSTEM_PROMPTS["assistente"])
    system_prompt = system_prompt.format(
        date=datetime.now().strftime("%d/%m/%Y %H:%M"),
        crm_context=crm_context,
    )

    messages: list[dict] = [
        {"role": "system", "content": system_prompt}
    ]

    # Adicionar histórico (últimas 10 mensagens para contexto)
    for msg in history[-10:]:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })

    # Adicionar mensagem atual
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat_completion(
            messages=messages,
            temperature=0.15,
            max_tokens=800,
        )
        return response
    except Exception as e:
        logger.error(f"Erro ao gerar resposta LLM: {e}")
        return ""


# ============================================================================
# MAPEAMENTO DE AÇÕES RÁPIDAS → PROMPTS PARA O LLM
# ============================================================================

ACTION_PROMPTS: dict[str, str] = {
    # Agenda
    "list_today": "O que eu tenho marcado pra hoje?",
    "list_week": "Mostra minha agenda da semana.",
    "add_appointment": "Quero marcar um compromisso. Me pergunta o dia, hora e o que vou fazer.",
    "list_reminders": "Quais são meus lembretes?",
    # Clientes
    "list_clients": "Mostra meus clientes. Lista simples com nome, telefone e se tá ativo. Sem tabela complicada, sem scores, sem termos em inglês.",
    "add_client": "Quero cadastrar um cliente novo. Me pergunta nome, telefone e email.",
    "search_client": "Quero procurar um cliente. Me pergunta o nome ou telefone.",
    "list_followup": "Quais clientes eu preciso entrar em contato? Mostra só quem faz tempo que não falo.",
    "pipeline_summary": "Me mostra um resumo das minhas vendas: quantos clientes ativos, quanto faturei e quais negócios estão abertos.",
    # Financeiro (unifica contabilidade)
    "monthly_summary": "Como tá meu mês? Quanto entrou, quanto saiu e quanto sobrou.",
    "get_balance": "Qual meu saldo? Quanto tenho, quanto falta receber e quanto falta pagar.",
    "mei_status": "Como tá meu limite do MEI? Quanto já usei do limite de R$ 81.000.",
    "das_status": "Quando vence meu DAS? Quanto é e como pago?",
    "dasn_status": "Preciso fazer a declaração anual (DASN)? Qual o prazo?",
    "calendario_fiscal": "Quais são minhas obrigações fiscais? Mostra os prazos.",
    "checklist_mensal": "O que eu preciso fazer esse mês?",
    "emit_nf": "Quero emitir uma Nota Fiscal. Me pergunta pra quem, valor e o que fiz.",
    "list_nf": "Mostra as notas fiscais que emiti esse mês.",
    "irpf_calculo": "Como funciona meu imposto de renda como MEI?",
    "generate_report": "Quais relatórios eu posso ver?",
    "generate_contract": "Quero fazer um contrato. Me pergunta o tipo e os detalhes.",
    "penalidades": "O que acontece se eu atrasar o DAS ou a DASN?",
    # Cobrança
    "list_overdue": "Quem tá devendo? Mostra nome, valor e há quantos dias.",
    "list_pending": "Quem vai ter que pagar nos próximos 7 dias?",
    "send_reminder": "Quero cobrar um cliente. Me pergunta quem e por onde (WhatsApp ou email).",
    "total_open": "Quanto eu tenho pra receber no total?",
    # Assistente
    "daily_summary": "Me dá um resumo do meu dia: o que tem marcado, como tá o dinheiro e se tem cobranças pendentes.",
    "suggest_tasks": "O que é mais importante eu fazer agora?",
    "get_alerts": "Tem algum alerta importante? Prazo, cobrança, alguma coisa urgente?",
    "help": "Explique todas as minhas capacidades, incluindo automação web com aprovação humana.",
    "web_automation": "O usuário quer usar a automação web. Pergunte o que ele gostaria de automatizar. Exemplos: consultar CPF na Receita Federal, acessar o Simples Nacional, emitir nota fiscal no portal da prefeitura. Diga que você vai gerar um plano de ações e pedir aprovação antes de executar qualquer coisa.",
}


# ============================================================================
# RESPOSTAS DIRETAS PARA DADOS VAZIOS (anti-alucinação)
# ============================================================================

# Mapeamento: prompt do quick action → resposta direta quando CRM vazio
_EMPTY_DATA_RESPONSES: dict[str, dict[str, str]] = {
    "contabilidade": {
        "Como tá meu mês": "📊 Ainda não tem movimentações registradas este mês.\n\nPra eu poder te mostrar o resumo financeiro, você precisa registrar suas entradas (vendas) e saídas (gastos).\n\n💡 Dica: Me diga algo como \"recebi R$ 500 do cliente fulano\" ou \"gastei R$ 100 no fornecedor\" que eu anoto pra você!",
        "Quando vence meu DAS": "📅 **DAS MEI - Fevereiro/2026**\n\nVence dia **20 de cada mês**.\n\n• Comércio/Indústria: **R$ 82,05**\n• Serviços: **R$ 86,05**\n• Comércio + Serviços: **R$ 87,05**\n\n💳 Pague pelo app do banco, site do Simples Nacional (pgmei.receita.gov.br) ou em qualquer lotérica.\n\n⚠️ Se atrasar: multa de 0,33% por dia (máximo 20%) + juros.",
        "Como tá meu limite do MEI": "📊 **Limite MEI 2026: R$ 81.000/ano** (~R$ 6.750/mês)\n\nAinda não tem faturamento registrado no sistema, então não consigo calcular quanto você já usou.\n\n💡 Registre suas vendas comigo que eu acompanho automaticamente!\n\nSe ultrapassar:\n• Até 20% acima (R$ 97.200): paga sobre o excedente, desenquadra em janeiro\n• Mais de 20%: desenquadra retroativamente",
        "Quem tá devendo": "✅ Não encontrei cobranças pendentes no sistema.\n\nTudo em dia! 👍\n\n💡 Quando quiser registrar uma venda a prazo, é só me avisar que eu acompanho os pagamentos.",
        "Quem vai ter que pagar": "✅ Não encontrei pagamentos próximos do vencimento.\n\n💡 Registre suas vendas a prazo comigo que eu aviso quando estiver perto de vencer.",
        "Quero emitir uma Nota Fiscal": "📝 **Emissão de Nota Fiscal (NFS-e)**\n\nPra emitir a nota, preciso de:\n1. **Nome/Razão Social** do cliente\n2. **CPF ou CNPJ** do cliente\n3. **Valor** do serviço/produto\n4. **Descrição** do que foi feito\n\nMe passe essas informações que eu monto a nota pra você! 😊",
        "Qual meu saldo": "💰 Ainda não tem movimentações registradas no sistema.\n\nPra eu calcular seu saldo, registre suas entradas e saídas.\n\n💡 Me diga: \"recebi R$ X\" ou \"gastei R$ X em Y\" que eu anoto tudo!",
        "previsão": "📊 Preciso de mais dados pra fazer previsões.\n\nRegistre suas vendas e gastos que, com o tempo, vou conseguir te mostrar tendências e previsões! 📈",
    },
    "clientes": {
        "Mostra meus clientes": "👥 Você ainda não tem clientes cadastrados.\n\nQuer cadastrar o primeiro? Me diz o **nome**, **telefone** e **email** que eu registro rapidinho! 😊",
        "Quero cadastrar um cliente": "👤 **Novo Cliente**\n\nPra cadastrar, preciso de:\n1. **Nome completo**\n2. **Telefone** (com DDD)\n3. **Email** (opcional)\n\nMe passe as informações! 😊",
        "Quais clientes eu preciso entrar em contato": "📞 Você ainda não tem clientes cadastrados.\n\nQuando tiver clientes registrados, eu aviso quando fizer tempo que você não fala com alguém.\n\n💡 Comece cadastrando seus clientes!",
        "resumo das minhas vendas": "📊 Ainda não tem clientes ou vendas registradas.\n\nRegistre seus clientes e vendas que eu faço o resumo pra você!\n\n💡 Me diga: \"cadastrar cliente João, telefone 11999998888\"",
    },
    "agenda": {
        "O que eu tenho marcado pra hoje": "📅 Dia livre! Você não tem nada marcado pra hoje.\n\nQuer agendar algo? Me diz o que, o dia e o horário! 😊",
        "Mostra minha agenda da semana": "📅 Semana livre! Nenhum compromisso agendado.\n\nQuer marcar algo? Me diz: \"reunião amanhã às 14h\" por exemplo.",
        "Quero marcar um compromisso": "📅 **Novo Compromisso**\n\nMe diz:\n1. **O que** vai fazer (reunião, consulta, ligação...)\n2. **Quando** (dia e hora)\n3. **Onde** (opcional)\n\n💡 Exemplo: \"dentista amanhã 15h\"",
    },
    "cobranca": {
        "Quem tá devendo": "✅ Não encontrei cobranças pendentes no sistema. Tudo em dia! 👍\n\n💡 Quando registrar vendas a prazo, eu acompanho os pagamentos automaticamente.",
        "Quem vai ter que pagar": "✅ Não encontrei pagamentos próximos do vencimento.\n\n💡 Registre suas vendas a prazo que eu aviso quando estiver perto de vencer.",
        "Quero cobrar um cliente": "📱 Primeiro preciso saber quem vai cobrar!\n\nVocê ainda não tem cobranças pendentes registradas. Registre uma venda a prazo e eu acompanho pra você.",
        "Quanto eu tenho pra receber": "💰 Não encontrei valores a receber no sistema.\n\nRegistre suas vendas a prazo que eu calculo tudo automaticamente!",
    },
    "assistente": {
        "resumo do meu dia": "📋 **Resumo do dia**\n\n• 📅 Agenda: Nenhum compromisso marcado\n• 💰 Financeiro: Sem movimentações registradas\n• 🔔 Cobranças: Nenhuma pendência\n• 👥 Clientes: Nenhum cadastrado ainda\n\n💡 **Sugestão**: Que tal começar cadastrando seus clientes e registrando suas vendas? Assim consigo te dar um resumo completo!",
        "O que é mais importante": "🎯 Pelo que vejo no sistema, você está começando. Sugiro:\n\n1. **Cadastrar seus clientes** — é a base de tudo\n2. **Registrar suas vendas** do mês — pra acompanhar o faturamento\n3. **Verificar o DAS** — vence dia 20 de cada mês\n\nPor qual quer começar?",
        "algum alerta importante": "✅ Nenhum alerta no momento.\n\n⚠️ Lembre-se:\n• DAS vence dia **20 de cada mês**\n• DASN (declaração anual) até **31 de maio**\n\n💡 Registre suas movimentações que eu aviso sobre tudo automaticamente!",
    },
}


def _get_direct_empty_response(agent_id: str, user_message: str) -> str:
    """Retorna resposta direta (sem LLM) quando o CRM está vazio.
    Busca match parcial do user_message nas chaves do mapeamento.
    Retorna string vazia se nenhum match → LLM será chamado normalmente.
    """
    agent_responses = _EMPTY_DATA_RESPONSES.get(agent_id, {})
    msg_lower = user_message.lower()
    for key, response in agent_responses.items():
        if key.lower() in msg_lower:
            return response
    return ""


# ============================================================================
# ENRIQUECIMENTO COM DADOS REAIS DO CRM
# ============================================================================

def _get_crm_context(user_id: int | None = None) -> str:
    """Busca dados reais do CRM para enriquecer os prompts dos agentes.
    Retorna string formatada em português simples, sem jargão técnico.
    Filtra tudo pelo user_id quando disponível.
    Graceful fallback se DB não estiver disponível.
    """
    try:
        from database.crm_service import CRMService

        # Dashboard geral (filtrado por user_id)
        dashboard = CRMService.get_crm_dashboard(user_id=user_id)

        # Clientes para follow-up (inatividade > 7 dias)
        followup = CRMService.get_clients_for_followup(days_inactive=7, user_id=user_id)

        # Faturas vencidas
        overdue = CRMService.get_overdue_invoices(user_id=user_id)

        # Próximas faturas (7 dias)
        upcoming = CRMService.get_upcoming_invoices(days=7, user_id=user_id)

        # Aniversariantes do dia
        birthdays = CRMService.get_birthday_clients(user_id=user_id)

        # Resumo financeiro do mês atual
        today = datetime.now()
        fin_summary = CRMService.get_financial_summary(month=today.month, year=today.year, user_id=user_id)

        # Montar contexto textual — linguagem simples
        lines = []

        clients_info = dashboard.get("clients", {})
        revenue_info = dashboard.get("revenue", {})
        total_cl = clients_info.get("total", 0)
        inactive_cl = clients_info.get("inactive", 0)
        active_cl = total_cl - inactive_cl

        if total_cl > 0:
            lines.append(f"👥 Você tem {total_cl} cliente(s) ({active_cl} ativo(s))")
            need_fu = clients_info.get("need_followup", 0)
            if need_fu > 0:
                lines.append(f"⚠️ {need_fu} cliente(s) sem contato há mais de 7 dias")
            total_rev = revenue_info.get("total", 0)
            if total_rev > 0:
                ticket = revenue_info.get("avg_ticket", 0)
                lines.append(f"💰 Receita total: R$ {total_rev:,.2f} | Média por cliente: R$ {ticket:,.2f}")
        else:
            lines.append("👥 Nenhum cliente cadastrado ainda")

        # Clientes que precisam de contato
        if followup:
            names = [f"{c['name']} ({c.get('days_inactive', '?')} dias)" for c in followup[:5]]
            lines.append(f"📞 Precisam de contato ({len(followup)}): {', '.join(names)}")

        # Cobranças
        if overdue:
            total_overdue = sum(i.get("amount", 0) for i in overdue)
            lines.append(f"🔴 Pagamentos atrasados: {len(overdue)} (R$ {total_overdue:,.2f})")
        if upcoming:
            total_upcoming = sum(i.get("amount", 0) for i in upcoming)
            lines.append(f"📅 Pagamentos nos próximos 7 dias: {len(upcoming)} (R$ {total_upcoming:,.2f})")

        # Aniversários
        if birthdays:
            bday_names = [c.get("name", "") for c in birthdays[:3]]
            lines.append(f"🎂 Aniversariante(s) hoje: {', '.join(bday_names)}")

        # Financeiro do mês
        receitas = fin_summary.get("receitas", 0)
        despesas = fin_summary.get("despesas", 0)
        lucro = fin_summary.get("lucro", 0)
        if receitas > 0 or despesas > 0:
            lines.append(f"💵 Este mês: Entrou R$ {receitas:,.2f} | Saiu R$ {despesas:,.2f} | Sobrou R$ {lucro:,.2f}")

        # Agendamentos hoje
        appts_today = dashboard.get("appointments_today", 0)
        if appts_today > 0:
            lines.append(f"📆 {appts_today} compromisso(s) pra hoje")

        return "\n".join(lines) if lines else "Sem dados cadastrados ainda."

    except Exception as e:
        logger.warning(f"CRM context indisponível: {e}")
        return "Dados não disponíveis no momento."
