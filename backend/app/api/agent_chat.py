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
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def get_openai_client():
    """Retorna cliente OpenAI configurado. Usado por agent_automation.py."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key)
    except Exception:
        return None


class SensitiveActionRequired(Exception):
    """Raised when a tool call requires password confirmation before execution.
    Supports batch: pending_actions is a list of {tool_name, arguments, description}
    for when multiple sensitive tools are requested at once (e.g. delete 3 clients).
    """
    def __init__(self, tool_name: str, arguments: dict, description: str,
                 pending_actions: list[dict] | None = None):
        self.tool_name = tool_name
        self.arguments = arguments
        self.description = description
        # For batch operations, all pending sensitive actions
        self.pending_actions = pending_actions or [
            {"tool_name": tool_name, "arguments": arguments, "description": description}
        ]
        super().__init__(description)


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
- Avisar sobre prazos fiscais (boleto mensal do MEI vence dia 20, declaração anual até 31/maio)
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
- Lembrete fiscal: 🚨 "Boleto mensal do MEI vence em X dias"
- Se não tem nada nos dados: "Dia livre! Quer marcar algo?"

CONTEXTO DE OUTROS AGENTES:
Você pode receber um bloco "CONTEXTO DE OUTROS AGENTES" com resumo das últimas conversas
do usuário em outros agentes (Clientes, Financeiro, Cobranças, Assistente). USE esse contexto para:
- Saber se um compromisso já foi mencionado em outro agente
- Ver clientes que precisam de follow-up mencionados no agente de Clientes
- Evitar pedir informações que o usuário já deu em outro agente

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
- Editar dados de clientes existentes (nome, telefone, email, segmento, notas)
- Excluir/apagar clientes (use a ferramenta delete_client — o sistema cuida da confirmação com senha)
- Buscar clientes por nome ou telefone
- Mostrar a lista de clientes
- Avisar quem precisa de contato (faz tempo que não fala)
- Lembrar aniversários
- **Cadastrar e listar FORNECEDORES** (use list_suppliers e create_supplier)
- **Consultar ESTOQUE** (use get_stock_summary e search_products)

PARA EXCLUIR OU EDITAR CLIENTES (REGRA CRÍTICA):
- Quando o usuário pedir para apagar/excluir/remover clientes, USE DIRETAMENTE a ferramenta delete_client
- Quando o usuário pedir para editar/alterar/atualizar dados de clientes, USE DIRETAMENTE a ferramenta update_client
- ⛔ NUNCA peça senha, PIN ou qualquer confirmação no chat — o sistema mostra automaticamente uma janela segura
- ⛔ NUNCA diga "digite sua senha", "informe sua senha", "preciso que confirme com senha" ou qualquer variação
- ⛔ NUNCA condicione a execução à digitação de senha pelo chat — simplesmente CHAME a ferramenta
- O sistema intercepta a chamada da ferramenta e exibe um popup seguro de senha ao usuário
- Apenas chame a ferramenta (delete_client ou update_client) com os parâmetros corretos
- Se o usuário pedir pra apagar TODOS os clientes, primeiro liste-os com search_clients, depois chame delete_client para CADA um

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

CONTEXTO DE OUTROS AGENTES:
Você pode receber um bloco "CONTEXTO DE OUTROS AGENTES" com resumo das últimas conversas
do usuário em outros agentes (Financeiro, Cobranças, Agenda, Assistente). USE esse contexto para:
- Saber se um cliente já foi mencionado em cobranças ou no financeiro
- Evitar pedir informações que o usuário já forneceu em outro agente
- Dar respostas mais completas e integradas

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
• Boleto mensal (DAS) Comércio/Indústria: R$ 82,05 por mês (INSS R$ 81,05 + ICMS R$ 1,00)
• Boleto mensal (DAS) Serviços: R$ 86,05 por mês (INSS R$ 81,05 + ISS R$ 5,00)
• Boleto mensal (DAS) Comércio+Serviços: R$ 87,05 por mês (INSS R$ 81,05 + ICMS R$ 1,00 + ISS R$ 5,00)
• Limite do MEI por ano: R$ 81.000 (~R$ 6.750/mês)
• Se passar até 20% (R$ 97.200): paga sobre o que passou, desenquadra em janeiro
• Se passar mais de 20%: desenquadra desde o começo do ano

O QUE VOCÊ FAZ:
1. Boleto mensal do MEI (DAS) — vence dia 20, quanto custa e como pagar
2. Declaração anual do MEI (DASN) — até 31/maio, como fazer
3. Nota Fiscal — como emitir (NFS-e padrão nacional, CRT 4)
4. Anotar entradas (vendas) e saídas (gastos) — SEMPRE pergunte a forma de pagamento
5. Ver quanto entrou e saiu no mês, na semana ou no dia
6. Avisar sobre limite MEI — quanto já usou e quanto falta
7. Mostrar vendas por FORMA DE PAGAMENTO (PIX, dinheiro, cartão débito/crédito, fiado, boleto, etc.)
8. Listar faturas e cobranças emitidas (use list_invoices)
9. Verificar plano e limite de clientes do NEXUS (use get_subscription_info)

FORMAS DE PAGAMENTO ACEITAS:
• PIX, Dinheiro, Cartão de Débito, Cartão de Crédito
• Crédito Próprio (crediário da loja), Fiado
• Boleto, Transferência Bancária, Parcelado
• Entrada + Parcelado, Cheque
REGRA: Ao anotar uma venda, SEMPRE pergunte como o cliente pagou se não foi informado.

MULTAS (informação real):
• Boleto atrasado (DAS): 0,33% por dia (máximo 20%) + juros
• Declaração anual atrasada (DASN): 2% ao mês (mínimo R$ 50)
• Se ficar 12 meses sem pagar o boleto mensal: CNPJ fica inapto

SEUS DADOS ATUAIS:
{crm_context}

REGRAS DE OURO:
1. NUNCA invente valores de receita, despesa ou saldo — use SOMENTE os DADOS ATUAIS acima
2. Se não tem movimentação nos dados acima, diga: "Ainda não tem movimentações registradas este mês. Quer registrar uma venda ou gasto?"
3. Os valores do boleto mensal (DAS) e limite MEI SÃO reais de 2026, pode mostrar
4. Se pedirem previsão e não tem dados, diga honestamente: "Preciso de mais dados pra prever"
5. NÃO invente nomes de clientes, valores de vendas ou transações fictícias
6. Se os dados acima mostram "Nenhum cliente" ou "0", responda com dados zerados — NÃO fabrique exemplos

COMO RESPONDER:
- Sempre em linguagem simples, como um contador amigo explicaria
- Use R$ com formato brasileiro (R$ 1.000,00)
- Evite jargão técnico — quando usar siglas como DAS ou DASN, explique entre parênteses (ex: "boleto mensal do MEI")
- Resumo do mês: "Entrou R$ X | Saiu R$ Y | Sobrou R$ Z"
- Boleto mensal: "Vence dia 20 | Valor: R$ X | Pague pelo app do banco ou site do Simples Nacional"

CONTEXTO DE OUTROS AGENTES:
Você pode receber um bloco "CONTEXTO DE OUTROS AGENTES" com resumo das últimas conversas
do usuário em outros agentes (Clientes, Cobranças, Agenda, Assistente). USE esse contexto para:
- Saber se uma transação ou cobrança já foi discutida em outro agente
- Evitar repetir informações que o usuário já recebeu
- Dar respostas mais completas quando o assunto envolve dados de outros agentes

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
- Listar faturas por status (use list_invoices: pendente, paga, vencida, todas)
- Ajudar a escrever mensagens de cobrança educadas
- Sugerir por onde cobrar (Telegram, email)

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
- Sugira canal (Telegram geralmente funciona melhor)
- Se não tem nada pendente nos dados: "Tudo em dia! 👍"

CONTEXTO DE OUTROS AGENTES:
Você pode receber um bloco "CONTEXTO DE OUTROS AGENTES" com resumo das últimas conversas
do usuário em outros agentes (Clientes, Financeiro, Agenda, Assistente). USE esse contexto para:
- Saber se um cliente devedor já foi contatado ou mencionado em outro agente
- Ver se o usuário já discutiu valores ou acordos em outro agente
- Dar respostas mais integradas sem pedir dados que já foram fornecidos

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
- Listar e buscar clientes (use a ferramenta search_clients)
- Cadastrar clientes novos (use a ferramenta create_client)
- Editar dados de clientes (use a ferramenta update_client — o sistema cuida da confirmação com senha)
- Excluir/apagar clientes (use a ferramenta delete_client — o sistema cuida da confirmação com senha)
- Ver agenda do dia ou da semana (use list_appointments)
- Listar faturas e cobranças (use list_invoices)
- Verificar plano e limite de clientes do NEXUS (use get_subscription_info)

REGRA CRÍTICA PARA EXCLUIR E EDITAR:
- Para excluir/editar clientes: CHAME DIRETAMENTE a ferramenta (delete_client ou update_client)
- ⛔ NUNCA peça senha, PIN ou confirmação no chat — o sistema exibe um popup seguro automaticamente
- ⛔ NUNCA diga "digite sua senha" ou "preciso da sua senha" — isso é proibido
- Simplesmente chame a ferramenta e o sistema cuida da autenticação

AUTOMAÇÃO WEB (IMPORTANTE — leia com atenção):
O sistema NEXUS possui automação web integrada com Playwright.
Quando o usuário pede automação web, o SISTEMA detecta e mostra um plano com
etapas numeradas. Após aprovação do usuário, o sistema executa automaticamente.
Você NÃO executa a automação — o sistema cuida disso.

SEUS DADOS ATUAIS:
{crm_context}

REGRAS DE OURO:
1. NUNCA invente dados — use SOMENTE os DADOS REAIS acima
2. Para qualquer operação de cliente, USE as ferramentas disponíveis
3. Se não tem dados, diga honestamente e sugira o próximo passo
4. Priorize sempre o que é mais urgente para o negócio

CONTEXTO DE OUTROS AGENTES:
Você pode receber um bloco "CONTEXTO DE OUTROS AGENTES" — use para dar respostas
mais completas e integradas sem repetir perguntas já respondidas em outros agentes.

Data de hoje: {date}
Responda SEMPRE em português brasileiro simples e objetivo.""",
}

# ============================================================================
# ACTION_PROMPTS — Mapeia ações de botões rápidos para prompts naturais
# ============================================================================

ACTION_PROMPTS: dict[str, str] = {
    # Agenda
    "list_today":        "Liste todos os meus compromissos de hoje.",
    "list_week":         "Mostre minha agenda completa desta semana.",
    "add_appointment":   "Quero marcar um novo compromisso. Me pergunte os detalhes.",
    # Clientes
    "list_clients":      "Liste meus clientes cadastrados.",
    "add_client":        "Quero cadastrar um novo cliente. Me pergunte os dados.",
    "list_followup":     "Quais clientes precisam de atenção ou acompanhamento?",
    # Fornecedores / Estoque
    "list_suppliers":    "Liste meus fornecedores cadastrados.",
    "stock_summary":     "Mostre o resumo do meu estoque atual.",
    # Financeiro
    "pipeline_summary":  "Mostre o resumo do meu pipeline de vendas.",
    "monthly_summary":   "Mostre o resumo financeiro do mês atual.",
    "daily_summary_fin": "Mostre o resumo financeiro de hoje.",
    "weekly_summary_fin": "Mostre o resumo financeiro desta semana.",
    "payment_breakdown": "Mostre as vendas separadas por forma de pagamento.",
    "das_status":        "Qual é o status do próximo boleto MEI (DAS)?",
    "mei_status":        "Qual é o meu limite MEI e quanto já usei?",
    # Cobranças
    "list_overdue":      "Liste os clientes que estão devendo (faturas vencidas).",
    "list_pending":      "Liste as contas a vencer nos próximos dias.",
    "send_reminder":     "Quero enviar lembretes de cobrança para clientes com faturas em aberto.",
    "total_open":        "Qual é o total em aberto de cobranças pendentes?",
    # Contabilidade / NF
    "emit_nf":           "Quero emitir uma nota fiscal. Me pergunte os detalhes.",
    "list_nf":           "Liste as notas fiscais emitidas.",
    "generate_report":   "Gere um relatório contábil do período.",
    "generate_contract": "Quero gerar um contrato. Me pergunte os detalhes.",
    "checklist_mensal":  "O que ainda falta fazer este mês (obrigações fiscais e financeiras)?",
    # Assistente pessoal
    "daily_summary":     "Faça um resumo do meu dia: compromissos, cobranças e tarefas pendentes.",
    "suggest_tasks":     "O que devo fazer agora? Sugira as prioridades do dia.",
    "get_alerts":        "Quais são os alertas importantes que preciso saber?",
    "web_automation":    "Preciso executar uma tarefa automatizada no site. Me pergunte o que fazer.",
}

# ============================================================================
# FERRAMENTAS CRM — Definições para function calling (OpenAI)
# ============================================================================

CRM_TOOLS_DEFINITIONS: list[dict] = [
    # ── CLIENTES ──────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "search_clients",
            "description": "Busca e lista clientes do CRM. Use quando o usuário pedir para ver, buscar ou listar clientes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Nome, telefone ou email para buscar. Deixe vazio para listar todos.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de resultados. Padrão: 10.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_client",
            "description": "Cadastra um novo cliente no CRM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nome completo do cliente."},
                    "phone": {"type": "string", "description": "Telefone com DDD."},
                    "email": {"type": "string", "description": "Email do cliente."},
                    "notes": {"type": "string", "description": "Observações sobre o cliente."},
                    "segment": {
                        "type": "string",
                        "enum": ["lead", "prospect", "standard", "premium", "vip"],
                        "description": "Segmento do cliente. Padrão: standard.",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_client",
            "description": "Atualiza dados de um cliente existente. REQUER SENHA — o sistema exibe popup automático.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "integer", "description": "ID do cliente a atualizar."},
                    "name": {"type": "string", "description": "Novo nome."},
                    "phone": {"type": "string", "description": "Novo telefone."},
                    "email": {"type": "string", "description": "Novo email."},
                    "notes": {"type": "string", "description": "Novas observações."},
                    "segment": {
                        "type": "string",
                        "enum": ["lead", "prospect", "standard", "premium", "vip", "churned"],
                    },
                    "is_active": {"type": "boolean", "description": "Ativar ou desativar cliente."},
                },
                "required": ["client_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_client",
            "description": "Remove ou desativa um cliente do CRM. REQUER SENHA — o sistema exibe popup automático.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "integer", "description": "ID do cliente a remover."},
                    "soft": {
                        "type": "boolean",
                        "description": "True = desativa (padrão). False = apaga permanentemente.",
                    },
                },
                "required": ["client_id"],
            },
        },
    },
    # ── AGENDAMENTOS ──────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_appointment",
            "description": "Cria um novo agendamento/compromisso.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Título do compromisso."},
                    "scheduled_at": {
                        "type": "string",
                        "description": "Data e hora no formato ISO 8601 (ex: 2026-04-01T15:00:00).",
                    },
                    "client_id": {"type": "integer", "description": "ID do cliente relacionado (opcional)."},
                    "description": {"type": "string", "description": "Descrição ou notas do compromisso."},
                    "duration_minutes": {"type": "integer", "description": "Duração em minutos. Padrão: 60."},
                    "appointment_type": {
                        "type": "string",
                        "enum": ["reuniao", "ligacao", "consulta", "entrega", "visita", "outro"],
                        "description": "Tipo do compromisso.",
                    },
                },
                "required": ["title", "scheduled_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_appointments",
            "description": (
                "Lista compromissos agendados. Use quando o usuário perguntar 'o que tenho hoje', "
                "'minha agenda', 'compromissos da semana', 'o que tem marcado'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "enum": ["hoje", "semana", "todos"],
                        "description": "Filtro de período. Padrão: 'hoje'.",
                    },
                },
                "required": [],
            },
        },
    },
    # ── FINANCEIRO ────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "record_transaction",
            "description": "Registra uma receita (venda) ou despesa (gasto) no financeiro.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["receita", "despesa"],
                        "description": "Tipo da transação.",
                    },
                    "amount": {"type": "number", "description": "Valor em reais."},
                    "description": {"type": "string", "description": "Descrição da transação."},
                    "category": {"type": "string", "description": "Categoria (ex: venda, aluguel, fornecedor)."},
                    "payment_method": {
                        "type": "string",
                        "enum": [
                            "pix", "dinheiro", "cartao_debito", "cartao_credito",
                            "credito_proprio", "fiado", "boleto", "transferencia",
                            "parcelado", "entrada_parcelado", "cheque", "nao_informado",
                        ],
                        "description": "Forma de pagamento.",
                    },
                    "client_id": {"type": "integer", "description": "ID do cliente (opcional)."},
                },
                "required": ["type", "amount", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_cashflow",
            "description": "Retorna resumo financeiro do dia atual (entradas, saídas e saldo).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weekly_cashflow",
            "description": "Retorna resumo financeiro da semana atual (entradas, saídas e saldo).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_payment_breakdown",
            "description": "Mostra vendas agrupadas por forma de pagamento (PIX, dinheiro, cartão, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Data início YYYY-MM-DD (opcional)."},
                    "end_date": {"type": "string", "description": "Data fim YYYY-MM-DD (opcional)."},
                },
                "required": [],
            },
        },
    },
    # ── COBRANÇAS / FATURAS ───────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_invoice",
            "description": "Cria uma fatura/cobrança para um cliente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "integer", "description": "ID do cliente."},
                    "description": {"type": "string", "description": "Descrição da cobrança."},
                    "amount": {"type": "number", "description": "Valor em reais."},
                    "due_date": {"type": "string", "description": "Data de vencimento YYYY-MM-DD."},
                },
                "required": ["client_id", "description", "amount", "due_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_invoices",
            "description": (
                "Lista faturas e cobranças. Use quando o usuário perguntar sobre 'notas fiscais', "
                "'faturas emitidas', 'cobranças do mês', 'quem pagou', 'faturas vencidas', "
                "'contas a receber'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["todas", "pendente", "paga", "vencida"],
                        "description": "Filtro de status. Padrão: 'todas'.",
                    },
                    "start_date": {"type": "string", "description": "Data início YYYY-MM-DD (opcional)."},
                    "end_date": {"type": "string", "description": "Data fim YYYY-MM-DD (opcional)."},
                },
                "required": [],
            },
        },
    },
    # ── ASSINATURA / PLANO ────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_subscription_info",
            "description": (
                "Retorna informações sobre a assinatura e limite do plano do usuário no NEXUS: "
                "plano ativo, limite de clientes, uso atual, data de renovação, se é trial. "
                "Use quando o usuário perguntar sobre 'meu plano', 'limite de clientes', "
                "'quantos clientes posso ter', 'quando renova', 'assinar o NEXUS'."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    # ── FORNECEDORES ──────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "list_suppliers",
            "description": "Lista fornecedores cadastrados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Busca por nome ou categoria."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_supplier",
            "description": "Cadastra um novo fornecedor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nome do fornecedor."},
                    "phone": {"type": "string", "description": "Telefone."},
                    "email": {"type": "string", "description": "Email."},
                    "category": {"type": "string", "description": "Categoria/segmento do fornecedor."},
                    "notes": {"type": "string", "description": "Observações."},
                },
                "required": ["name"],
            },
        },
    },
    # ── ESTOQUE ───────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_stock_summary",
            "description": "Retorna resumo do estoque: total de produtos, valor em estoque, alertas de estoque baixo.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Busca produtos no estoque por nome ou categoria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Nome ou categoria do produto."},
                    "low_stock_only": {
                        "type": "boolean",
                        "description": "Se True, retorna apenas produtos com estoque baixo.",
                    },
                },
                "required": [],
            },
        },
    },
]

# ============================================================================
# FERRAMENTAS DISPONÍVEIS POR AGENTE
# ============================================================================

AGENT_AVAILABLE_TOOLS: dict[str, list[str]] = {
    "agenda": [
        "create_appointment",
        "list_appointments",
        "search_clients",
    ],
    "clientes": [
        "search_clients",
        "create_client",
        "update_client",
        "delete_client",
        "list_suppliers",
        "create_supplier",
        "get_stock_summary",
        "search_products",
    ],
    "contabilidade": [
        "record_transaction",
        "get_daily_cashflow",
        "get_weekly_cashflow",
        "get_payment_breakdown",
        "list_invoices",
        "get_subscription_info",
        "search_clients",
    ],
    "cobranca": [
        "create_invoice",
        "list_invoices",
        "search_clients",
    ],
    "assistente": [
        "search_clients",
        "create_client",
        "update_client",
        "delete_client",
        "create_appointment",
        "list_appointments",
        "record_transaction",
        "get_daily_cashflow",
        "get_weekly_cashflow",
        "get_payment_breakdown",
        "create_invoice",
        "list_invoices",
        "get_subscription_info",
        "list_suppliers",
        "get_stock_summary",
        "search_products",
    ],
}

# ============================================================================
# ADDENDUM DE INSTRUÇÕES DE FERRAMENTAS (anexado a todos os prompts)
# ============================================================================

_TOOLS_ADDENDUM = """
FERRAMENTAS DISPONÍVEIS — USE-AS PROATIVAMENTE:

Para CLIENTES (buscar, cadastrar, editar, excluir):
- search_clients: lista/busca clientes por nome, telefone ou email
- create_client: cadastra novo cliente
- update_client: atualiza dados (REQUER SENHA — popup automático)
- delete_client: remove/desativa (REQUER SENHA — popup automático)
REGRA: Para excluir ou editar, CHAME a ferramenta diretamente. NÃO peça senha no chat.

Para FINANCEIRO (registrar e consultar movimentações):
- record_transaction: registra venda (receita) ou gasto (despesa) — SEMPRE pergunte a forma de pagamento
- get_daily_cashflow: resumo financeiro do dia
- get_weekly_cashflow: resumo financeiro da semana
- get_payment_breakdown: vendas por forma de pagamento

Para COBRANÇAS (criar e listar faturas):
- create_invoice: cria fatura/cobrança para um cliente
- list_invoices: lista faturas com filtro de status (todas/pendente/paga/vencida) e período
REGRA: Use list_invoices quando o usuário perguntar sobre notas fiscais, faturas emitidas,
cobranças do mês, contas a receber ou faturas vencidas.

Para AGENDAMENTOS (marcar e consultar compromissos):
- create_appointment: marca novo compromisso
- list_appointments: lista compromissos com filtro 'hoje', 'semana' ou 'todos'
REGRA: Use list_appointments quando o usuário perguntar 'o que tenho hoje',
'minha agenda', 'compromissos da semana', 'o que tem marcado'.

Para ASSINATURA E PLANO NEXUS:
- get_subscription_info: retorna plano ativo, limite de clientes, uso atual e data de renovação
REGRA: Use quando o usuário perguntar sobre 'meu plano', 'limite de clientes',
'quantos clientes posso ter', 'quando renova' ou 'assinar o NEXUS'.

Para FORNECEDORES:
- list_suppliers: lista fornecedores
- create_supplier: cadastra fornecedor

Para ESTOQUE:
- get_stock_summary: resumo do estoque
- search_products: busca produtos por nome ou categoria
"""


# ============================================================================
# EXECUÇÃO DE FERRAMENTAS CRM
# ============================================================================

def _log_activity(user_id: int, action: str, detail: str) -> None:
    """Registra atividade do agente no log."""
    logger.info(f"[AGENT] user={user_id} action={action} | {detail}")


def _execute_crm_tool(tool_name: str, arguments: dict, user_id: int) -> Any:
    """
    Executa uma ferramenta CRM e retorna o resultado.
    Cada tool_name corresponde a um método de CRMService ou InventoryService.
    """
    from database.crm_service import CRMService

    # ── CLIENTES ──────────────────────────────────────────────────────────────
    if tool_name == "search_clients":
        query = arguments.get("query", "")
        limit = arguments.get("limit", 10)
        contact_type = arguments.get("contact_type", "client")
        result = CRMService.search_clients(
            query=query, limit=limit, user_id=user_id,
            segment=arguments.get("segment"),
        )
        _log_activity(user_id, "search_clients", f"query='{query}' limit={limit}")
        return result

    elif tool_name == "create_client":
        result = CRMService.create_client(
            name=arguments["name"],
            user_id=user_id,
            phone=arguments.get("phone"),
            email=arguments.get("email"),
            notes=arguments.get("notes", ""),
            segment=arguments.get("segment", "standard"),
        )
        _log_activity(user_id, "create_client", f"name={arguments['name']}")
        return result

    elif tool_name == "update_client":
        client_id = arguments.get("client_id")
        if not client_id:
            return {"status": "error", "message": "client_id é obrigatório"}
        # Ação sensível — requer senha
        raise SensitiveActionRequired(
            tool_name="update_client",
            arguments=arguments,
            description=f"Atualizar dados do cliente ID {client_id}",
        )

    elif tool_name == "delete_client":
        client_id = arguments.get("client_id")
        if not client_id:
            return {"status": "error", "message": "client_id é obrigatório"}
        # Ação sensível — requer senha
        raise SensitiveActionRequired(
            tool_name="delete_client",
            arguments=arguments,
            description=f"Excluir cliente ID {client_id}",
        )

    # ── AGENDAMENTOS ──────────────────────────────────────────────────────────
    elif tool_name == "create_appointment":
        from datetime import datetime as dt
        scheduled_at_raw = arguments.get("scheduled_at")
        try:
            scheduled_at = dt.fromisoformat(scheduled_at_raw)
        except (TypeError, ValueError):
            return {"status": "error", "message": f"Data inválida: {scheduled_at_raw}. Use formato ISO 8601."}
        result = CRMService.create_appointment(
            title=arguments["title"],
            scheduled_at=scheduled_at,
            client_id=arguments.get("client_id"),
            description=arguments.get("description", ""),
            duration_minutes=arguments.get("duration_minutes", 60),
            appointment_type=arguments.get("appointment_type", "reuniao"),
            user_id=user_id,
        )
        _log_activity(user_id, "create_appointment", f"title={arguments['title']} at={scheduled_at_raw}")
        return result

    elif tool_name == "list_appointments":
        filtro = arguments.get("filter", "hoje")
        result = CRMService.list_appointments(filter=filtro, user_id=user_id)
        _log_activity(user_id, "list_appointments", f"filter={filtro}")
        return result

    # ── FINANCEIRO ────────────────────────────────────────────────────────────
    elif tool_name == "record_transaction":
        from datetime import date
        result = CRMService.record_transaction(
            type=arguments["type"],
            amount=float(arguments["amount"]),
            description=arguments["description"],
            category=arguments.get("category", "geral"),
            payment_method=arguments.get("payment_method", "nao_informado"),
            client_id=arguments.get("client_id"),
            transaction_date=date.today(),
            user_id=user_id,
        )
        _log_activity(
            user_id, "record_transaction",
            f"type={arguments['type']} amount={arguments['amount']} method={arguments.get('payment_method','nao_informado')}"
        )
        return result

    elif tool_name == "get_daily_cashflow":
        result = CRMService.get_daily_summary(user_id=user_id)
        _log_activity(user_id, "get_daily_cashflow", "consultou fluxo do dia")
        return result

    elif tool_name == "get_weekly_cashflow":
        result = CRMService.get_weekly_summary(user_id=user_id)
        _log_activity(user_id, "get_weekly_cashflow", "consultou fluxo da semana")
        return result

    elif tool_name == "get_payment_breakdown":
        result = CRMService.get_payment_breakdown(
            start_date=arguments.get("start_date"),
            end_date=arguments.get("end_date"),
            user_id=user_id,
        )
        _log_activity(user_id, "get_payment_breakdown", "consultou breakdown por pagamento")
        return result

    # ── COBRANÇAS / FATURAS ───────────────────────────────────────────────────
    elif tool_name == "create_invoice":
        from datetime import date
        due_date_raw = arguments.get("due_date")
        try:
            due_date = date.fromisoformat(due_date_raw)
        except (TypeError, ValueError):
            return {"status": "error", "message": f"Data de vencimento inválida: {due_date_raw}. Use YYYY-MM-DD."}
        result = CRMService.create_invoice(
            client_id=arguments["client_id"],
            description=arguments["description"],
            amount=float(arguments["amount"]),
            due_date=due_date,
            user_id=user_id,
        )
        _log_activity(user_id, "create_invoice", f"client_id={arguments['client_id']} amount={arguments['amount']}")
        return result

    elif tool_name == "list_invoices":
        status = arguments.get("status", "todas")
        result = CRMService.list_invoices(
            status=status,
            start=arguments.get("start_date"),
            end=arguments.get("end_date"),
            user_id=user_id,
        )
        _log_activity(user_id, "list_invoices", f"status={status}")
        return result

    # ── ASSINATURA / PLANO ────────────────────────────────────────────────────
    elif tool_name == "get_subscription_info":
        try:
            from database.models import SessionLocal
            from sqlalchemy import text
            db = SessionLocal()
            try:
                # Tenta buscar via tabela user_subscriptions se existir
                result_row = db.execute(
                    text(
                        "SELECT plan_name, client_limit, clients_used, renewal_date, is_trial, is_active "
                        "FROM user_subscriptions WHERE user_id = :uid AND is_active = TRUE LIMIT 1"
                    ),
                    {"uid": user_id},
                ).fetchone()
                if result_row:
                    row = dict(result_row._mapping)
                    _log_activity(user_id, "get_subscription_info", f"plano={row.get('plan_name')}")
                    return {
                        "status": "ok",
                        "plan": row.get("plan_name", "Desconhecido"),
                        "client_limit": row.get("client_limit", 0),
                        "clients_used": row.get("clients_used", 0),
                        "renewal_date": str(row.get("renewal_date", "")),
                        "is_trial": bool(row.get("is_trial", False)),
                    }
                else:
                    # Sem assinatura ativa — retorna status informativo
                    _log_activity(user_id, "get_subscription_info", "sem assinatura ativa")
                    return {
                        "status": "no_subscription",
                        "message": "Nenhuma assinatura ativa encontrada para este usuário.",
                    }
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"get_subscription_info: tabela não encontrada ou erro — {e}")
            return {
                "status": "unavailable",
                "message": "Informações de assinatura não disponíveis no momento.",
            }

    # ── FORNECEDORES ──────────────────────────────────────────────────────────
    elif tool_name == "list_suppliers":
        query = arguments.get("query", "")
        result = CRMService.search_clients(
            query=query, limit=20, user_id=user_id,
            segment="supplier",
        )
        _log_activity(user_id, "list_suppliers", f"query='{query}'")
        return result

    elif tool_name == "create_supplier":
        result = CRMService.create_client(
            name=arguments["name"],
            user_id=user_id,
            phone=arguments.get("phone"),
            email=arguments.get("email"),
            notes=arguments.get("notes", ""),
            segment=arguments.get("category", "supplier"),
            contact_type="supplier",
        )
        _log_activity(user_id, "create_supplier", f"name={arguments['name']}")
        return result

    # ── ESTOQUE ───────────────────────────────────────────────────────────────
    elif tool_name == "get_stock_summary":
        try:
            from database.inventory_service import InventoryService
            result = InventoryService.get_stock_summary(user_id=user_id)
        except ImportError:
            result = {"status": "unavailable", "message": "Módulo de estoque não instalado."}
        _log_activity(user_id, "get_stock_summary", "consultou resumo do estoque")
        return result

    elif tool_name == "search_products":
        try:
            from database.inventory_service import InventoryService
            result = InventoryService.search_products(
                query=arguments.get("query", ""),
                low_stock_only=arguments.get("low_stock_only", False),
                user_id=user_id,
            )
        except ImportError:
            result = {"status": "unavailable", "message": "Módulo de estoque não instalado."}
        _log_activity(user_id, "search_products", f"query={arguments.get('query','')}")
        return result

    # ── FERRAMENTA DESCONHECIDA ───────────────────────────────────────────────
    else:
        logger.warning(f"Ferramenta desconhecida solicitada: {tool_name}")
        return {"status": "error", "message": f"Ferramenta '{tool_name}' não reconhecida."}


# ============================================================================
# LOOP DE FUNCTION CALLING — OpenAI GPT-4.1
# ============================================================================

def _call_with_tools(
    client,
    model: str,
    messages: list[dict],
    tools: list[dict],
    user_id: int,
    max_rounds: int = 5,
) -> str:
    """
    Executa o loop de function calling com o modelo OpenAI.
    Retorna o texto final da resposta após todas as tool calls serem resolvidas.
    """
    current_messages = messages.copy()

    for round_num in range(max_rounds):
        response = client.chat.completions.create(
            model=model,
            messages=current_messages,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
            temperature=0.3,
            max_tokens=1500,
        )

        choice = response.choices[0]

        # Sem tool call → resposta final
        if choice.finish_reason == "stop" or not choice.message.tool_calls:
            return choice.message.content or ""

        # Processar tool calls
        tool_calls = choice.message.tool_calls
        current_messages.append(choice.message)

        # Verificar se há ações sensíveis em lote
        sensitive_actions = []
        for tc in tool_calls:
            tool_name = tc.function.name
            if tool_name in ("delete_client", "update_client"):
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                sensitive_actions.append({
                    "tool_call_id": tc.id,
                    "tool_name": tool_name,
                    "arguments": args,
                    "description": f"{'Excluir' if tool_name == 'delete_client' else 'Atualizar'} cliente ID {args.get('client_id', '?')}",
                })

        if sensitive_actions:
            first = sensitive_actions[0]
            raise SensitiveActionRequired(
                tool_name=first["tool_name"],
                arguments=first["arguments"],
                description=first["description"],
                pending_actions=sensitive_actions,
            )

        # Executar ferramentas normais
        for tc in tool_calls:
            tool_name = tc.function.name
            try:
                arguments = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            try:
                tool_result = _execute_crm_tool(tool_name, arguments, user_id)
                result_content = json.dumps(tool_result, ensure_ascii=False, default=str)
            except SensitiveActionRequired:
                raise
            except Exception as e:
                logger.error(f"Erro ao executar ferramenta {tool_name}: {e}")
                result_content = json.dumps({"status": "error", "message": str(e)})

            current_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_content,
            })

    # Fallback: última resposta disponível
    logger.warning(f"Loop de tools atingiu max_rounds={max_rounds}")
    last = current_messages[-1]
    if isinstance(last, dict) and last.get("role") == "tool":
        return "Processamento concluído. Verifique os dados acima."
    return last.get("content", "") if isinstance(last, dict) else ""


# ============================================================================
# ENTRADA PRINCIPAL — get_llm_response
# ============================================================================

def get_llm_response(
    agent_type: str,
    user_message: str,
    crm_context: str = "",
    conversation_history: list[dict] = None,
    user_id: int = None,
    confirmed_actions: list[dict] = None,
) -> str:
    """
    Gera resposta do LLM para o agente especificado.

    Args:
        agent_type: Tipo do agente (agenda, clientes, contabilidade, cobranca, assistente)
        user_message: Mensagem do usuário
        crm_context: Contexto CRM pré-formatado para injetar no prompt
        conversation_history: Histórico de mensagens anteriores
        user_id: ID do usuário autenticado
        confirmed_actions: Ações sensíveis confirmadas com senha (ex: delete_client)

    Returns:
        Texto da resposta do agente
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY não configurada")
        return "Serviço de IA temporariamente indisponível. Verifique a configuração."

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except ImportError:
        return "Biblioteca OpenAI não instalada. Execute: pip install openai"

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    # Obter prompt base do agente
    base_prompt = AGENT_SYSTEM_PROMPTS.get(
        agent_type,
        AGENT_SYSTEM_PROMPTS["assistente"]
    )

    # Formatar prompt com contexto
    today_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    system_prompt = base_prompt.format(
        crm_context=crm_context or "Nenhum dado disponível no momento.",
        date=today_str,
    ) + _TOOLS_ADDENDUM

    # Montar mensagens
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    if conversation_history:
        messages.extend(conversation_history[-10:])  # Últimas 10 mensagens

    messages.append({"role": "user", "content": user_message})

    # Filtrar ferramentas disponíveis para este agente
    allowed_tool_names = set(AGENT_AVAILABLE_TOOLS.get(agent_type, []))
    tools = [
        t for t in CRM_TOOLS_DEFINITIONS
        if t["function"]["name"] in allowed_tool_names
    ]

    # Processar ações confirmadas (sensitive actions com senha validada)
    if confirmed_actions:
        for action in confirmed_actions:
            tool_name = action.get("tool_name")
            arguments = action.get("arguments", {})
            tool_call_id = action.get("tool_call_id", f"confirmed_{tool_name}")

            try:
                from database.crm_service import CRMService
                if tool_name == "delete_client":
                    result = CRMService.delete_client(
                        client_id=arguments["client_id"],
                        soft=arguments.get("soft", True),
                        user_id=user_id,
                    )
                elif tool_name == "update_client":
                    client_id = arguments.pop("client_id")
                    result = CRMService.update_client(
                        client_id=client_id,
                        user_id=user_id,
                        **arguments,
                    )
                else:
                    result = {"status": "error", "message": f"Ação '{tool_name}' não suportada em confirmed_actions"}

                _log_activity(user_id, f"confirmed_{tool_name}", f"args={arguments}")

                # Injetar resultado no contexto
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(action.get("arguments", {})),
                        },
                    }],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })
                messages.append({
                    "role": "user",
                    "content": "A ação foi confirmada e executada. Por favor, confirme o resultado ao usuário.",
                })

            except Exception as e:
                logger.error(f"Erro ao executar ação confirmada {tool_name}: {e}")
                return f"Erro ao executar a operação: {str(e)}"

    # Executar chamada ao modelo com tools
    try:
        return _call_with_tools(
            client=client,
            model=model,
            messages=messages,
            tools=tools,
            user_id=user_id or 0,
        )
    except SensitiveActionRequired:
        raise
    except Exception as e:
        logger.error(f"Erro na chamada ao modelo {model}: {e}", exc_info=True)
        return f"Desculpe, ocorreu um erro ao processar sua solicitação. Tente novamente em instantes."
