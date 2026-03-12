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
- Listar e buscar clientes (use a ferramenta search_clients)
- Cadastrar clientes novos (use a ferramenta create_client)

AUTOMAÇÃO WEB (IMPORTANTE — leia com atenção):
O sistema NEXUS possui automação web integrada com Playwright.
Quando o usuário pede automação web, o SISTEMA detecta e mostra um plano com botões de aprovar/cancelar.
Se você está recebendo esta mensagem, é porque a detecção de automação NÃO foi ativada para este pedido.
Por isso, NÃO diga que a página foi aberta, que a automação está em andamento ou que executou algo no navegador.
Se o usuário pedir para acessar um site ou portal, responda:
"Vou preparar a automação web para isso. Por favor, clique no botão 'Automação Web' nas Ações Rápidas
ou reformule seu pedido mencionando o site específico (ex: 'consultar CPF na Receita Federal')."
NUNCA invente que abriu uma página, que preencheu um formulário, ou que a automação foi concluída.
NUNCA diga "simulação de fluxo" — a automação existe mas precisa ser ativada pelo sistema, não por você.

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
# CRM TOOLS — Function Calling para ações reais no banco de dados
# ============================================================================

CRM_TOOLS_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "create_client",
            "description": "Cadastra um novo cliente no CRM. Use quando o usuário pedir para cadastrar, registrar ou adicionar um cliente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nome completo do cliente"},
                    "phone": {"type": "string", "description": "Telefone com DDD (ex: 27999887766)"},
                    "email": {"type": "string", "description": "Email do cliente"},
                    "cpf_cnpj": {"type": "string", "description": "CPF ou CNPJ"},
                    "segment": {"type": "string", "enum": ["lead", "prospect", "standard", "premium", "vip"], "description": "Segmento do cliente"},
                    "notes": {"type": "string", "description": "Observações"},
                    "address": {"type": "string", "description": "Endereço"},
                    "city": {"type": "string", "description": "Cidade"},
                    "state": {"type": "string", "description": "Estado (UF)"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_appointment",
            "description": "Cria um agendamento/compromisso. Use quando o usuário pedir para marcar, agendar ou criar reunião, consulta, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Título do compromisso"},
                    "scheduled_at": {"type": "string", "description": "Data e hora ISO 8601 (ex: 2026-03-20T15:00:00)"},
                    "description": {"type": "string", "description": "Detalhes do compromisso"},
                    "duration_minutes": {"type": "integer", "description": "Duração em minutos (padrão: 60)"},
                    "appointment_type": {"type": "string", "enum": ["reuniao", "ligacao", "consulta", "visita", "outro"], "description": "Tipo"},
                    "client_id": {"type": "integer", "description": "ID do cliente associado (se houver)"},
                },
                "required": ["title", "scheduled_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_transaction",
            "description": "Registra transação financeira (receita ou despesa). Use quando o usuário pedir para anotar venda, pagamento, gasto, entrada ou saída.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["receita", "despesa"], "description": "receita=entrada, despesa=saída"},
                    "amount": {"type": "number", "description": "Valor em reais"},
                    "description": {"type": "string", "description": "Descrição da transação"},
                    "category": {"type": "string", "description": "Categoria (ex: vendas, material, aluguel)"},
                    "client_id": {"type": "integer", "description": "ID do cliente associado"},
                    "notes": {"type": "string", "description": "Observações"},
                },
                "required": ["type", "amount", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_invoice",
            "description": "Cria fatura/cobrança para um cliente. Use quando pedir para criar cobrança ou conta a receber.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "integer", "description": "ID do cliente"},
                    "description": {"type": "string", "description": "Descrição do serviço/produto"},
                    "amount": {"type": "number", "description": "Valor em reais"},
                    "due_date": {"type": "string", "description": "Data de vencimento (YYYY-MM-DD)"},
                },
                "required": ["client_id", "description", "amount", "due_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_clients",
            "description": "Busca clientes pelo nome, telefone ou email. Use SEMPRE que o usuário perguntar sobre clientes: listar todos, buscar por nome, ver quem tem cadastrado. Para listar TODOS, use query vazio ('').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Texto para buscar (nome, telefone ou email). Use '' (vazio) para listar todos os clientes."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_client",
            "description": "Atualiza dados de um cliente existente. Use quando pedir para alterar telefone, email, nome ou segmento.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "integer", "description": "ID do cliente a atualizar"},
                    "name": {"type": "string", "description": "Novo nome"},
                    "phone": {"type": "string", "description": "Novo telefone"},
                    "email": {"type": "string", "description": "Novo email"},
                    "segment": {"type": "string", "description": "Novo segmento"},
                    "notes": {"type": "string", "description": "Novas observações"},
                },
                "required": ["client_id"],
            },
        },
    },
    # ── Ferramentas de Fluxo de Caixa ──
    {
        "type": "function",
        "function": {
            "name": "get_daily_cashflow",
            "description": "Use SEMPRE que o usuário perguntar sobre hoje: 'quanto entrou hoje', 'quanto saiu hoje', 'saldo do dia', 'como foi hoje'. Retorna entradas, saídas e saldo do dia atual.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weekly_cashflow",
            "description": "Use quando o usuário perguntar sobre a semana: 'como foi essa semana', 'total da semana', 'melhor dia da semana', 'quanto entrei essa semana'.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cashflow_by_range",
            "description": "Use quando o usuário especificar um período personalizado: 'últimos 15 dias', 'de segunda a sexta', 'entre dia X e Y'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Data início ISO: YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "Data fim ISO: YYYY-MM-DD"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    # ── Ferramentas de Estoque / Inventário ──
    {
        "type": "function",
        "function": {
            "name": "get_stock_summary",
            "description": "Retorna resumo do estoque: total de produtos, valor total, alertas de estoque baixo, movimentações do dia e da semana. Use quando o usuário perguntar sobre estoque, inventário, produtos em estoque.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Busca produtos no estoque por nome, SKU ou categoria. Use '' para listar todos. Use quando perguntar sobre produtos, estoque de itens, listar produtos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Texto para buscar (nome, SKU ou categoria). Use '' para listar todos."},
                    "low_stock": {"type": "boolean", "description": "Se true, retorna apenas produtos abaixo do estoque mínimo"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "register_stock_entry",
            "description": "Registra entrada de estoque (compra, produção, devolução). Use quando o usuário disser que comprou, recebeu ou entrou mercadoria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "description": "ID do produto"},
                    "quantity": {"type": "number", "description": "Quantidade que entrou"},
                    "unit_price": {"type": "number", "description": "Preço unitário de compra"},
                    "reason": {"type": "string", "description": "Motivo: compra, producao, devolucao, ajuste"},
                    "notes": {"type": "string", "description": "Observações"},
                },
                "required": ["product_id", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "register_stock_exit",
            "description": "Registra saída de estoque (venda, uso, perda). Use quando o usuário disser que vendeu, usou ou saiu mercadoria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "description": "ID do produto"},
                    "quantity": {"type": "number", "description": "Quantidade que saiu"},
                    "unit_price": {"type": "number", "description": "Preço de venda unitário"},
                    "reason": {"type": "string", "description": "Motivo: venda, uso, perda, ajuste"},
                    "notes": {"type": "string", "description": "Observações"},
                },
                "required": ["product_id", "quantity"],
            },
        },
    },
]

# Ferramentas disponíveis por agente
AGENT_AVAILABLE_TOOLS: dict[str, list[str]] = {
    "clientes": ["create_client", "search_clients", "update_client", "create_appointment", "search_products", "get_stock_summary"],
    "agenda": ["create_appointment", "create_client"],
    "contabilidade": ["record_transaction", "create_client", "create_invoice", "get_stock_summary", "get_daily_cashflow", "get_weekly_cashflow", "get_cashflow_by_range"],
    "financeiro": ["record_transaction", "get_daily_cashflow", "get_weekly_cashflow", "get_cashflow_by_range", "get_stock_summary"],
    "cobranca": ["search_clients", "create_invoice"],
    "assistente": ["create_client", "create_appointment", "record_transaction", "create_invoice", "search_clients", "update_client", "get_stock_summary", "search_products", "register_stock_entry", "register_stock_exit", "get_daily_cashflow", "get_weekly_cashflow", "get_cashflow_by_range"],
}

_TOOLS_ADDENDUM = """

FERRAMENTAS DISPONÍVEIS (IMPORTANTE):
Você tem ferramentas que executam ações REAIS no sistema.

Para CONSULTAR dados (listar, buscar, ver, mostrar clientes, procurar):
- USE a ferramenta search_clients para listar ou buscar clientes
- Com query="" (vazio) para listar TODOS os clientes
- Com query="nome" para buscar um específico
- SEMPRE use a ferramenta ao invés de responder com base apenas no resumo do sistema

Para AÇÕES (cadastrar, agendar, registrar, anotar, criar):
1. USE as ferramentas disponíveis para executar a ação de verdade
2. NUNCA diga que fez algo sem usar a ferramenta — as ferramentas são a ÚNICA forma de executar ações
3. Se a ferramenta retornar erro, informe o usuário
4. Se faltar informação obrigatória (como nome do cliente), PERGUNTE antes de usar a ferramenta
5. Após executar, confirme com os dados reais retornados pela ferramenta

REGRA: Quando o usuário perguntar sobre clientes (quem são, quantos, nomes, buscar), SEMPRE use search_clients.

Para ESTOQUE/INVENTÁRIO (produtos, mercadoria, material, quantidade):
- get_stock_summary: resumo geral do estoque (valor, alertas, movimentações)
- search_products: buscar ou listar produtos no estoque
- register_stock_entry: registrar compra/entrada de mercadoria
- register_stock_exit: registrar venda/saída de mercadoria
REGRA: Quando o usuário perguntar sobre estoque, produtos ou inventário, use as ferramentas de estoque.

Para FLUXO DE CAIXA (quanto entrou/saiu hoje, essa semana, período):
- get_daily_cashflow: entradas, saídas e saldo do dia atual
- get_weekly_cashflow: resumo da semana (segunda a hoje) + melhor dia
- get_cashflow_by_range: período personalizado com agrupamento diário
REGRA: Quando o usuário perguntar sobre entradas/saídas de dinheiro hoje ou na semana, use as ferramentas de cashflow."""


def _get_agent_tools(agent_id: str) -> list[dict]:
    """Retorna as definições de ferramentas disponíveis para o agente."""
    tool_names = AGENT_AVAILABLE_TOOLS.get(agent_id, [])
    if not tool_names:
        return []
    return [t for t in CRM_TOOLS_DEFINITIONS if t["function"]["name"] in tool_names]


def _get_raw_openai_client():
    """Retorna o cliente OpenAI SDK cru para function calling."""
    wrapper = get_openai_client()
    if wrapper and hasattr(wrapper, "client"):
        return wrapper.client
    return None


def _notify_hub_event(event_name: str, payload: dict) -> None:
    """Dispara evento no Agent Hub (fire-and-forget, não bloqueia).
    CRITICAL FIX #2: Pub/Sub agora é disparado automaticamente após ações CRM."""
    try:
        from agents.agent_hub import hub, EventType, AgentType, AgentMessage
        import asyncio

        _event_map = {
            "CLIENTE_CRIADO": (EventType.CLIENTE_CRIADO, AgentType.CLIENTES),
            "CLIENTE_ATUALIZADO": (EventType.CLIENTE_ATUALIZADO, AgentType.CLIENTES),
            "COMPROMISSO_CRIADO": (EventType.COMPROMISSO_CRIADO, AgentType.AGENDA),
            "PAGAMENTO_RECEBIDO": (EventType.PAGAMENTO_RECEBIDO, AgentType.CONTABILIDADE),
            "NF_EMITIDA": (EventType.NF_EMITIDA, AgentType.CONTABILIDADE),
        }
        if event_name not in _event_map:
            return
        event_type, from_agent = _event_map[event_name]
        msg = AgentMessage(
            from_agent=from_agent,
            to_agent=None,  # broadcast
            event_type=event_type,
            payload=payload,
            priority=5,
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(hub.publish(msg))
        except RuntimeError:
            pass  # No event loop — skip (non-critical)
        logger.debug(f"📡 Hub event {event_name} dispatched")
    except Exception as e:
        logger.debug(f"Hub notification skipped: {e}")


def _log_activity(user_id: int | None, action: str, details: str) -> None:
    """Registra ação no ActivityLog para audit trail (LOW #22)."""
    try:
        from database.models import ActivityLog, SessionLocal
        if not user_id:
            return
        db = SessionLocal()
        try:
            log = ActivityLog(
                user_id=user_id,
                action=action,
                details=details,
            )
            db.add(log)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"ActivityLog skipped: {e}")


def _execute_crm_tool(tool_name: str, arguments: dict, user_id: int | None) -> dict:
    """Executa uma ferramenta CRM e retorna o resultado.
    Após cada operação bem-sucedida, dispara evento Pub/Sub e registra no ActivityLog."""
    try:
        from database.crm_service import CRMService

        if tool_name == "create_client":
            result = CRMService.create_client(
                name=arguments.get("name", ""),
                user_id=user_id,
                phone=arguments.get("phone"),
                email=arguments.get("email"),
                cpf_cnpj=arguments.get("cpf_cnpj"),
                segment=arguments.get("segment", "standard"),
                notes=arguments.get("notes", ""),
                address=arguments.get("address"),
                city=arguments.get("city"),
                state=arguments.get("state"),
            )
            if result.get("status") == "created":
                _notify_hub_event("CLIENTE_CRIADO", result.get("client", {}))
                _log_activity(user_id, "create_client", f"Cliente '{arguments.get('name')}' cadastrado via chat")
            return result

        elif tool_name == "create_appointment":
            scheduled_str = arguments.get("scheduled_at", "")
            try:
                scheduled = datetime.fromisoformat(scheduled_str)
            except (ValueError, TypeError):
                scheduled = datetime.now()
            result = CRMService.create_appointment(
                title=arguments.get("title", "Compromisso"),
                scheduled_at=scheduled,
                client_id=arguments.get("client_id"),
                description=arguments.get("description", ""),
                duration_minutes=arguments.get("duration_minutes", 60),
                appointment_type=arguments.get("appointment_type", "reuniao"),
                user_id=user_id,
            )
            if result.get("status") == "created":
                _notify_hub_event("COMPROMISSO_CRIADO", result.get("appointment", {}))
                _log_activity(user_id, "create_appointment", f"Compromisso '{arguments.get('title')}' criado via chat")
            return result

        elif tool_name == "record_transaction":
            result = CRMService.record_transaction(
                type=arguments.get("type", "receita"),
                amount=arguments.get("amount", 0),
                description=arguments.get("description", ""),
                category=arguments.get("category", "geral"),
                client_id=arguments.get("client_id"),
                notes=arguments.get("notes", ""),
                user_id=user_id,
            )
            if result.get("status") == "created":
                _notify_hub_event("PAGAMENTO_RECEBIDO", result.get("transaction", {}))
                _log_activity(user_id, "record_transaction", f"{arguments.get('type', 'receita')} R${arguments.get('amount', 0):.2f} via chat")
            return result

        elif tool_name == "create_invoice":
            from datetime import date as _date
            due_str = arguments.get("due_date", "")
            try:
                due = _date.fromisoformat(due_str)
            except (ValueError, TypeError):
                due = _date.today()
            result = CRMService.create_invoice(
                client_id=arguments.get("client_id", 0),
                description=arguments.get("description", ""),
                amount=arguments.get("amount", 0),
                due_date=due,
                user_id=user_id,
            )
            if result.get("status") == "created":
                _notify_hub_event("NF_EMITIDA", result.get("invoice", {}))
                _log_activity(user_id, "create_invoice", f"Fatura R${arguments.get('amount', 0):.2f} criada via chat")
            return result

        elif tool_name == "search_clients":
            return CRMService.search_clients(
                query=arguments.get("query", ""),
                user_id=user_id,
            )

        elif tool_name == "update_client":
            cid = arguments.get("client_id")
            if not cid:
                return {"status": "error", "message": "client_id é obrigatório para atualizar"}
            allowed = {k: v for k, v in arguments.items() if k != "client_id" and v is not None}
            result = CRMService.update_client(cid, user_id=user_id, **allowed)
            if result.get("status") == "updated":
                _notify_hub_event("CLIENTE_ATUALIZADO", {"client_id": cid, **allowed})
                _log_activity(user_id, "update_client", f"Cliente #{cid} atualizado via chat")
            return result

        # ── Ferramentas de Fluxo de Caixa ──
        elif tool_name == "get_daily_cashflow":
            result = CRMService.get_daily_summary(user_id=user_id)
            _log_activity(user_id, "daily_cashflow", "Consultou fluxo de caixa do dia via chat")
            return result

        elif tool_name == "get_weekly_cashflow":
            result = CRMService.get_weekly_summary(user_id=user_id)
            _log_activity(user_id, "weekly_cashflow", "Consultou fluxo de caixa da semana via chat")
            return result

        elif tool_name == "get_cashflow_by_range":
            from datetime import date as _date
            start_str = arguments.get("start_date", "")
            end_str = arguments.get("end_date", "")
            try:
                s = _date.fromisoformat(start_str)
                e = _date.fromisoformat(end_str)
            except (ValueError, TypeError):
                return {"status": "error", "message": "Datas inválidas. Use formato YYYY-MM-DD"}
            result = CRMService.get_financial_summary_by_range(s, e, user_id=user_id)
            _log_activity(user_id, "range_cashflow", f"Consultou fluxo de caixa {start_str} a {end_str} via chat")
            return result

        # ── Ferramentas de Estoque / Inventário ──
        elif tool_name == "get_stock_summary":
            from database.inventory_service import InventoryService
            return InventoryService.get_stock_summary(user_id)

        elif tool_name == "search_products":
            from database.inventory_service import InventoryService
            return InventoryService.get_products(
                user_id=user_id,
                search=arguments.get("query", ""),
                low_stock_only=arguments.get("low_stock", False),
            )

        elif tool_name == "register_stock_entry":
            from database.inventory_service import InventoryService
            result = InventoryService.register_entry(
                user_id=user_id,
                product_id=arguments.get("product_id", 0),
                quantity=arguments.get("quantity", 0),
                unit_price=arguments.get("unit_price"),
                reason=arguments.get("reason", "compra"),
                notes=arguments.get("notes"),
            )
            if result.get("status") == "created":
                _log_activity(user_id, "stock_entry", f"Entrada de {arguments.get('quantity', 0)} unidades do produto #{arguments.get('product_id')} via chat")
            return result

        elif tool_name == "register_stock_exit":
            from database.inventory_service import InventoryService
            result = InventoryService.register_exit(
                user_id=user_id,
                product_id=arguments.get("product_id", 0),
                quantity=arguments.get("quantity", 0),
                unit_price=arguments.get("unit_price"),
                reason=arguments.get("reason", "venda"),
                notes=arguments.get("notes"),
            )
            if result.get("status") == "created":
                _log_activity(user_id, "stock_exit", f"Saída de {arguments.get('quantity', 0)} unidades do produto #{arguments.get('product_id')} via chat")
            return result

        return {"status": "error", "message": f"Ferramenta desconhecida: {tool_name}"}

    except Exception as e:
        logger.error(f"Erro ao executar tool {tool_name}: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


def _call_with_tools(messages: list[dict], agent_id: str, user_id: int | None) -> str:
    """Chama OpenAI com function calling e executa as ferramentas CRM.
    Retorna a resposta final como string, ou string vazia se falhar."""
    raw_client = _get_raw_openai_client()
    if not raw_client:
        return ""

    agent_tools = _get_agent_tools(agent_id)
    if not agent_tools:
        return ""

    model = os.getenv("OPENAI_MODEL", "gpt-4.1")

    try:
        # Primeira chamada com ferramentas
        response = raw_client.chat.completions.create(
            model=model,
            messages=messages,
            tools=agent_tools,
            tool_choice="auto",
            temperature=0.15,
            max_tokens=800,
        )

        assistant_msg = response.choices[0].message

        # Se não há tool calls, retorna conteúdo direto
        if not assistant_msg.tool_calls:
            return assistant_msg.content or ""

        # Executar cada tool call
        logger.info(f"🔧 Agent {agent_id}: {len(assistant_msg.tool_calls)} tool call(s)")

        # Adicionar mensagem do assistente com tool_calls ao contexto
        tool_calls_dicts = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in assistant_msg.tool_calls
        ]
        messages.append({
            "role": "assistant",
            "content": assistant_msg.content,
            "tool_calls": tool_calls_dicts,
        })

        # Executar ferramentas e adicionar resultados
        for tc in assistant_msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            logger.info(f"  🔧 Executando {tc.function.name}({json.dumps(args, ensure_ascii=False)[:200]})")
            result = _execute_crm_tool(tc.function.name, args, user_id)
            logger.info(f"  ✅ Resultado: {result.get('status', 'unknown')}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

        # Segunda chamada para resposta natural baseada nos resultados
        response2 = raw_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.15,
            max_tokens=800,
        )

        final_msg = response2.choices[0].message

        # Tratar caso raro de tool calls encadeados (máximo 1 rodada extra)
        if final_msg.tool_calls:
            tc_dicts2 = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in final_msg.tool_calls
            ]
            messages.append({"role": "assistant", "content": final_msg.content, "tool_calls": tc_dicts2})

            for tc in final_msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                logger.info(f"  🔧 Executando (round 2) {tc.function.name}")
                result = _execute_crm_tool(tc.function.name, args, user_id)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

            response3 = raw_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.15,
                max_tokens=800,
            )
            return response3.choices[0].message.content or ""

        return final_msg.content or ""

    except Exception as e:
        logger.warning(f"⚠️ Function calling falhou para {agent_id}: {e}", exc_info=True)
        return ""  # Fallback para chamada sem ferramentas


# ============================================================================
# CHAT INTELIGENTE COM LLM
# ============================================================================

async def get_llm_response(agent_id: str, user_message: str, history: list[dict] = [], user_id: int | None = None) -> str:
    """
    Gera resposta inteligente usando OpenAI GPT-4.1
    com system prompt especializado por agente.
    Suporta function calling para ações reais (cadastrar, agendar, etc.).
    Filtra dados pelo user_id autenticado.
    """
    # Resolver aliases legados (financeiro/documentos → contabilidade)
    _alias = {"financeiro": "contabilidade", "documentos": "contabilidade"}
    agent_id = _alias.get(agent_id, agent_id)

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

    # Adicionar instruções de ferramentas se o agente tem tools
    agent_tool_names = AGENT_AVAILABLE_TOOLS.get(agent_id, [])
    if agent_tool_names:
        system_prompt += _TOOLS_ADDENDUM

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

    # ── Tentar com function calling (permite ações reais) ─────────
    if agent_tool_names:
        tool_response = _call_with_tools(messages, agent_id, user_id)
        if tool_response:
            return tool_response

    # ── Fallback: chamada sem ferramentas ─────────────────────────
    client = get_openai_client()
    if not client:
        return ""

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
            # Incluir nomes dos clientes no contexto para o LLM
            try:
                from database.crm_service import CRMService as _CRM2
                _search = _CRM2.search_clients(query="", user_id=user_id, limit=10)
                _cl_list = _search.get("clients", [])
                if _cl_list:
                    _cl_names = [f"  - {c.get('name', '?')} | {c.get('phone', 'sem tel')} | {'Ativo' if c.get('is_active') else 'Inativo'}" for c in _cl_list[:10]]
                    lines.append("Lista de clientes:\n" + "\n".join(_cl_names))
            except Exception:
                pass
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

        # Fluxo de caixa do dia
        try:
            daily = CRMService.get_daily_summary(user_id=user_id)
            if daily["transactions_count"] > 0:
                lines.append(
                    f"💵 Hoje: Entrou R$ {daily['receitas']:,.2f} | "
                    f"Saiu R$ {daily['despesas']:,.2f} | "
                    f"Saldo R$ {daily['saldo']:,.2f}"
                )
            else:
                lines.append("💵 Hoje: nenhuma transação registrada ainda")
        except Exception:
            pass

        # Fluxo de caixa da semana
        try:
            weekly = CRMService.get_weekly_summary(user_id=user_id)
            if weekly["transactions_count"] > 0:
                lines.append(
                    f"📅 Esta semana: Entrou R$ {weekly['receitas']:,.2f} | "
                    f"Saiu R$ {weekly['despesas']:,.2f}"
                )
                if weekly["best_day"]:
                    lines.append(
                        f"🏆 Melhor dia: {weekly['best_day']['date']} "
                        f"(R$ {weekly['best_day']['receitas']:,.2f})"
                    )
        except Exception:
            pass

        # Agendamentos hoje
        appts_today = dashboard.get("appointments_today", 0)
        if appts_today > 0:
            lines.append(f"📆 {appts_today} compromisso(s) pra hoje")

        # Estoque / Inventário
        try:
            from database.inventory_service import InventoryService
            stock = InventoryService.get_stock_summary(user_id)
            total_prods = stock.get("total_products", 0)
            if total_prods > 0:
                stock_val = stock.get("total_stock_value", 0)
                lines.append(f"📦 Estoque: {total_prods} produto(s) | Valor total: R$ {stock_val:,.2f}")
                alerts = stock.get("low_stock_alerts", [])
                if alerts:
                    alert_names = [a.get("name", "?") for a in alerts[:3]]
                    lines.append(f"⚠️ Estoque baixo ({len(alerts)}): {', '.join(alert_names)}")
                mov_today = stock.get("movements_today", {})
                if mov_today.get("total", 0) > 0:
                    lines.append(f"📊 Movimentações hoje: {mov_today.get('entradas', 0)} entrada(s), {mov_today.get('saidas', 0)} saída(s)")
        except Exception:
            pass

        return "\n".join(lines) if lines else "Sem dados cadastrados ainda."

    except Exception as e:
        logger.warning(f"CRM context indisponível: {e}")
        return "Dados não disponíveis no momento."
