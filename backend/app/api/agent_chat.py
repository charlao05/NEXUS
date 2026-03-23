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

REGRA CRÍTICA PARA EXCLUIR E EDITAR:
- Para excluir/editar clientes: CHAME DIRETAMENTE a ferramenta (delete_client ou update_client)
- ⛔ NUNCA peça senha, PIN ou confirmação no chat — o sistema exibe um popup seguro automaticamente
- ⛔ NUNCA diga "digite sua senha" ou "preciso da sua senha" — isso é proibido
- Simplesmente chame a ferramenta e o sistema cuida da autenticação

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

CONTEXTO DE OUTROS AGENTES:
Você pode receber um bloco extra chamado "CONTEXTO DE OUTROS AGENTES" com resumo das últimas
conversas em outros agentes (Clientes, Financeiro, Cobranças, Agenda). USE esse contexto para:
- Dar respostas integradas sem que o usuário precise repetir informações
- Saber o que já foi discutido e decidido em outro agente
- Evitar pedir dados que o usuário já forneceu em outro agente
Se esse contexto não aparecer, significa que não há conversas recentes em outros agentes.

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
            "description": "Registra transação financeira (receita ou despesa). Use quando o usuário pedir para anotar venda, pagamento, gasto, entrada ou saída. SEMPRE pergunte a forma de pagamento se o usuário não informar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["receita", "despesa"], "description": "receita=entrada, despesa=saída"},
                    "amount": {"type": "number", "description": "Valor em reais"},
                    "description": {"type": "string", "description": "Descrição da transação"},
                    "category": {"type": "string", "description": "Categoria (ex: vendas, material, aluguel)"},
                    "payment_method": {"type": "string", "enum": ["pix", "dinheiro", "cartao_debito", "cartao_credito", "credito_proprio", "fiado", "boleto", "transferencia", "parcelado", "entrada_parcelado", "cheque", "nao_informado"], "description": "Forma de pagamento: pix, dinheiro, cartao_debito, cartao_credito, credito_proprio (crediário próprio), fiado, boleto, transferencia, parcelado, entrada_parcelado (entrada + parcelas), cheque"},
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
            "description": "Atualiza dados de um cliente existente. Use quando pedir para alterar telefone, email, nome ou segmento. IMPORTANTE: esta ação requer confirmação com senha.",
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
    {
        "type": "function",
        "function": {
            "name": "delete_client",
            "description": "Exclui/desativa um cliente do CRM. Use quando o usuário pedir para apagar, excluir, remover ou deletar um cliente. IMPORTANTE: esta ação requer confirmação com senha.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "integer", "description": "ID do cliente a remover"},
                    "client_name": {"type": "string", "description": "Nome do cliente (para confirmação)"},
                    "hard_delete": {"type": "boolean", "description": "Se true, remove permanentemente. Se false (padrão), apenas desativa."},
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
    # ── Ferramenta de Breakdown por Forma de Pagamento ──
    {
        "type": "function",
        "function": {
            "name": "get_payment_breakdown",
            "description": "Retorna vendas agrupadas por forma de pagamento (PIX, dinheiro, cartão débito/crédito, fiado, boleto, etc). Use quando pedir vendas por forma de pagamento, breakdown de recebimentos, ou como recebeu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Data início ISO: YYYY-MM-DD (padrão: início do mês)"},
                    "end_date": {"type": "string", "description": "Data fim ISO: YYYY-MM-DD (padrão: hoje)"},
                },
                "required": [],
            },
        },
    },
    # ── Ferramenta de Listar Fornecedores ──
    {
        "type": "function",
        "function": {
            "name": "list_suppliers",
            "description": "Lista fornecedores cadastrados. Fornecedores são contatos com tipo 'supplier'. Use quando o usuário perguntar sobre fornecedores.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Texto para buscar (nome, telefone). Use '' para listar todos."},
                },
                "required": [],
            },
        },
    },
    # ── Ferramenta de Cadastrar Fornecedor ──
    {
        "type": "function",
        "function": {
            "name": "create_supplier",
            "description": "Cadastra um novo fornecedor. Use quando o usuário pedir para cadastrar, registrar ou adicionar um fornecedor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nome do fornecedor"},
                    "phone": {"type": "string", "description": "Telefone com DDD"},
                    "email": {"type": "string", "description": "Email do fornecedor"},
                    "cpf_cnpj": {"type": "string", "description": "CPF ou CNPJ"},
                    "notes": {"type": "string", "description": "Observações (produtos que fornece, condições, etc)"},
                    "address": {"type": "string", "description": "Endereço"},
                    "city": {"type": "string", "description": "Cidade"},
                    "state": {"type": "string", "description": "Estado (UF)"},
                },
                "required": ["name"],
            },
        },
    },
]

# Ferramentas disponíveis por agente
AGENT_AVAILABLE_TOOLS: dict[str, list[str]] = {
    "clientes": ["create_client", "search_clients", "update_client", "delete_client", "create_appointment", "search_products", "get_stock_summary", "list_suppliers", "create_supplier"],
    "agenda": ["create_appointment", "create_client", "list_suppliers", "create_supplier", "get_stock_summary"],
    "contabilidade": ["record_transaction", "create_client", "create_invoice", "get_stock_summary", "get_daily_cashflow", "get_weekly_cashflow", "get_cashflow_by_range", "get_payment_breakdown"],
    "financeiro": ["record_transaction", "get_daily_cashflow", "get_weekly_cashflow", "get_cashflow_by_range", "get_stock_summary", "get_payment_breakdown"],
    "cobranca": ["search_clients", "create_invoice"],
    "assistente": ["create_client", "create_appointment", "record_transaction", "create_invoice", "search_clients", "update_client", "delete_client", "get_stock_summary", "search_products", "register_stock_entry", "register_stock_exit", "get_daily_cashflow", "get_weekly_cashflow", "get_cashflow_by_range", "get_payment_breakdown", "list_suppliers", "create_supplier"],
}

# Ferramentas que requerem confirmação com senha do usuário
SENSITIVE_TOOLS: set[str] = {"delete_client", "update_client"}

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
- get_payment_breakdown: vendas agrupadas por forma de pagamento (PIX, dinheiro, cartão, fiado, etc.)
REGRA: Quando o usuário perguntar sobre entradas/saídas de dinheiro hoje ou na semana, use as ferramentas de cashflow.
REGRA: Quando perguntar sobre formas de pagamento, como recebeu, ou breakdown, use get_payment_breakdown.

Para FORNECEDORES (cadastrar, listar, buscar fornecedores):
- list_suppliers: lista fornecedores cadastrados (query="" para todos, ou buscar por nome/telefone)
- create_supplier: cadastra um novo fornecedor (nome obrigatório, outros opcionais)
REGRA: Fornecedores são separados dos clientes. Use essas ferramentas específicas.

FORMA DE PAGAMENTO (IMPORTANTE):
Ao registrar vendas/transações com record_transaction, SEMPRE pergunte a forma de pagamento ao usuário.
Formas aceitas: pix, dinheiro, cartao_debito, cartao_credito, credito_proprio (crediário próprio), fiado, boleto, transferencia, parcelado, entrada_parcelado (entrada + parcelas), cheque.

Para EDITAR clientes (mudar nome, telefone, email, segmento):
- USE a ferramenta update_client com o client_id e os campos a alterar
- Primeiro busque o cliente com search_clients se não souber o ID
- O sistema exibe um popup seguro de confirmação com senha automaticamente

Para EXCLUIR/APAGAR clientes:
- USE a ferramenta delete_client com o client_id
- O sistema exibe um popup seguro de confirmação com senha automaticamente
- Para apagar múltiplos clientes, chame delete_client para cada um

⛔ REGRA ABSOLUTA PARA EDIÇÃO E EXCLUSÃO:
- NUNCA peça senha, PIN ou qualquer tipo de confirmação pelo chat
- NUNCA diga "digite sua senha", "informe sua senha de confirmação", "preciso que confirme com senha"
- NUNCA condicione a ação à digitação de senha — simplesmente CHAME a ferramenta
- O sistema intercepta automaticamente e mostra uma janela segura de senha ao usuário
- Se você pedir senha pelo chat, estará QUEBRANDO A SEGURANÇA do sistema"""


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


def _push_user_notification(user_id: int | None, type: str, title: str, message: str, severity: str = "info", data: dict | None = None) -> None:
    """Envia notificação em tempo real para o usuário (SSE/polling)."""
    if not user_id:
        return
    try:
        import asyncio
        from app.api.notifications import send_notification
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(send_notification(user_id, type, title, message, data=data, severity=severity))
        else:
            asyncio.run(send_notification(user_id, type, title, message, data=data, severity=severity))
    except RuntimeError:
        # No event loop — create one
        try:
            import asyncio as _aio
            from app.api.notifications import send_notification as _sn
            _aio.run(_sn(user_id, type, title, message, data=data, severity=severity))
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"User notification skipped: {e}")


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
                _log_activity(user_id, "create_client", f"Cadastrou o cliente '{arguments.get('name')}'")
                _push_user_notification(user_id, "client_created", "Novo Cliente", f"'{arguments.get('name')}' cadastrado com sucesso", severity="success")
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
                _log_activity(user_id, "create_appointment", f"Marcou o compromisso '{arguments.get('title')}'")
                _push_user_notification(user_id, "appointment_created", "Novo Compromisso", f"'{arguments.get('title')}' agendado", severity="info", data={"scheduled_at": str(scheduled)})
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
                payment_method=arguments.get("payment_method", "nao_informado"),
            )
            if result.get("status") == "created":
                _notify_hub_event("PAGAMENTO_RECEBIDO", result.get("transaction", {}))
                _log_activity(user_id, "record_transaction", f"Registrou {arguments.get('type', 'receita')} de R${arguments.get('amount', 0):.2f}")
                _tx_type = arguments.get('type', 'receita')
                _push_user_notification(user_id, "transaction_recorded", "Transação Registrada", f"{_tx_type.capitalize()} de R${arguments.get('amount', 0):.2f}", severity="success" if _tx_type == "receita" else "warning")
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
                _log_activity(user_id, "create_invoice", f"Criou fatura de R${arguments.get('amount', 0):.2f}")
                _push_user_notification(user_id, "invoice_created", "Nova Fatura", f"Fatura de R${arguments.get('amount', 0):.2f} criada", severity="info")
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
                _log_activity(user_id, "update_client", f"Atualizou dados do cliente #{cid}")
                _push_user_notification(user_id, "client_updated", "Cliente Atualizado", f"Dados do cliente #{cid} atualizados", severity="info")
            return result

        elif tool_name == "delete_client":
            cid = arguments.get("client_id")
            if not cid:
                return {"status": "error", "message": "client_id é obrigatório para excluir"}
            hard = arguments.get("hard_delete", False)
            client_name = arguments.get("client_name", f"#{cid}")
            result = CRMService.delete_client(client_id=cid, soft=not hard, user_id=user_id)
            if result.get("status") in ("deactivated", "deleted"):
                _log_activity(user_id, "delete_client", f"{'Removeu' if hard else 'Desativou'} o cliente '{client_name}'")
                _push_user_notification(user_id, "client_deleted", "Cliente Removido", f"'{client_name}' foi {'excluído' if hard else 'desativado'}", severity="warning")
            return result

        # ── Ferramentas de Fluxo de Caixa ──
        elif tool_name == "get_daily_cashflow":
            result = CRMService.get_daily_summary(user_id=user_id)
            _log_activity(user_id, "daily_cashflow", "Viu o resumo financeiro do dia")
            return result

        elif tool_name == "get_weekly_cashflow":
            result = CRMService.get_weekly_summary(user_id=user_id)
            _log_activity(user_id, "weekly_cashflow", "Viu o resumo financeiro da semana")
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
            _log_activity(user_id, "range_cashflow", f"Viu o resumo financeiro de {start_str} a {end_str}")
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
                _log_activity(user_id, "stock_entry", f"Registrou entrada de {arguments.get('quantity', 0)} unidades no estoque")
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
                _log_activity(user_id, "stock_exit", f"Registrou saída de {arguments.get('quantity', 0)} unidades do estoque")
            return result

        # ── Ferramenta de Breakdown por Forma de Pagamento ──
        elif tool_name == "get_payment_breakdown":
            from datetime import date as _date
            start_str = arguments.get("start_date", "")
            end_str = arguments.get("end_date", "")
            try:
                s = _date.fromisoformat(start_str) if start_str else None
            except (ValueError, TypeError):
                s = None
            try:
                e = _date.fromisoformat(end_str) if end_str else None
            except (ValueError, TypeError):
                e = None
            result = CRMService.get_payment_breakdown(start_date=s, end_date=e, user_id=user_id)
            _log_activity(user_id, "payment_breakdown", "Viu as vendas por forma de pagamento")
            return result

        # ── Ferramentas de Fornecedores ──
        elif tool_name == "list_suppliers":
            from database.models import Client as _ClientModel, get_session as _get_sess
            _session = _get_sess()
            try:
                q = _session.query(_ClientModel).filter(
                    _ClientModel.contact_type == "supplier",
                    _ClientModel.is_active == True,
                )
                if user_id:
                    q = q.filter(_ClientModel.user_id == user_id)
                search_q = arguments.get("query", "")
                if search_q:
                    term = f"%{search_q}%"
                    from sqlalchemy import or_
                    q = q.filter(or_(_ClientModel.name.ilike(term), _ClientModel.phone.ilike(term)))
                suppliers = q.order_by(_ClientModel.name).limit(50).all()
                return {
                    "total": len(suppliers),
                    "suppliers": [s.to_dict() for s in suppliers],
                }
            finally:
                _session.close()

        elif tool_name == "create_supplier":
            result = CRMService.create_client(
                name=arguments.get("name", ""),
                phone=arguments.get("phone"),
                email=arguments.get("email"),
                cpf_cnpj=arguments.get("cpf_cnpj"),
                notes=arguments.get("notes", ""),
                address=arguments.get("address"),
                city=arguments.get("city"),
                state=arguments.get("state"),
                contact_type="supplier",
                user_id=user_id,
            )
            if result.get("status") == "created":
                _log_activity(user_id, "create_supplier", f"Cadastrou o fornecedor '{arguments.get('name')}'")
                _push_user_notification(user_id, "supplier_created", "Novo Fornecedor", f"'{arguments.get('name')}' cadastrado", severity="success")
            return result

        return {"status": "error", "message": f"Ferramenta desconhecida: {tool_name}"}

    except Exception as e:
        logger.error(f"Erro ao executar tool {tool_name}: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


def _call_with_tools(messages: list[dict], agent_id: str, user_id: int | None, confirmed_action: str | None = None) -> str:
    """Chama OpenAI com function calling e executa as ferramentas CRM.
    Retorna a resposta final como string, ou string vazia se falhar.
    
    Args:
        confirmed_action: Se fornecido, nome da tool que já foi confirmada com senha.
                         Permite execução direta sem nova solicitação de confirmação.
    Raises:
        SensitiveActionRequired: Quando uma ação sensível precisa de confirmação com senha.
    """
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
        # Coletar TODAS as ações sensíveis antes de levantar exceção (batch)
        _sensitive_actions: list[dict] = []

        for tc in assistant_msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            # Interceptar ferramentas sensíveis que requerem confirmação com senha
            if tc.function.name in SENSITIVE_TOOLS and tc.function.name != confirmed_action:
                _desc = ""
                if tc.function.name == "delete_client":
                    cname = args.get("client_name", f"#{args.get('client_id', '?')}")
                    _desc = f"Excluir cliente {cname}"
                elif tc.function.name == "update_client":
                    cname = args.get("name", f"#{args.get('client_id', '?')}")
                    _fields = [k for k in args if k not in ("client_id",)]
                    _desc = f"Editar cliente {cname} (campos: {', '.join(_fields)})"
                else:
                    _desc = f"Ação sensível: {tc.function.name}"
                _sensitive_actions.append({
                    "tool_name": tc.function.name,
                    "arguments": args,
                    "description": _desc,
                })
                continue  # Não executa agora — será agrupado no raise abaixo

            logger.info(f"  🔧 Executando {tc.function.name}({json.dumps(args, ensure_ascii=False)[:200]})")
            result = _execute_crm_tool(tc.function.name, args, user_id)
            logger.info(f"  ✅ Resultado: {result.get('status', 'unknown')}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

        # Se houve ações sensíveis coletadas, levantar exceção com TODAS de uma vez
        if _sensitive_actions:
            combined_desc = " | ".join(a["description"] for a in _sensitive_actions)
            raise SensitiveActionRequired(
                tool_name=_sensitive_actions[0]["tool_name"],
                arguments=_sensitive_actions[0]["arguments"],
                description=combined_desc,
                pending_actions=_sensitive_actions,
            )

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

            _sensitive_actions_r2: list[dict] = []

            for tc in final_msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                # Interceptar ferramentas sensíveis no round 2 também (batch)
                if tc.function.name in SENSITIVE_TOOLS and tc.function.name != confirmed_action:
                    _desc = ""
                    if tc.function.name == "delete_client":
                        cname = args.get("client_name", f"#{args.get('client_id', '?')}")
                        _desc = f"Excluir cliente {cname}"
                    elif tc.function.name == "update_client":
                        cname = args.get("name", f"#{args.get('client_id', '?')}")
                        _fields = [k for k in args if k not in ("client_id",)]
                        _desc = f"Editar cliente {cname} (campos: {', '.join(_fields)})"
                    else:
                        _desc = f"Ação sensível: {tc.function.name}"
                    _sensitive_actions_r2.append({
                        "tool_name": tc.function.name,
                        "arguments": args,
                        "description": _desc,
                    })
                    continue

                logger.info(f"  🔧 Executando (round 2) {tc.function.name}")
                result = _execute_crm_tool(tc.function.name, args, user_id)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

            if _sensitive_actions_r2:
                combined_desc = " | ".join(a["description"] for a in _sensitive_actions_r2)
                raise SensitiveActionRequired(
                    tool_name=_sensitive_actions_r2[0]["tool_name"],
                    arguments=_sensitive_actions_r2[0]["arguments"],
                    description=combined_desc,
                    pending_actions=_sensitive_actions_r2,
                )

            response3 = raw_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.15,
                max_tokens=800,
            )
            return response3.choices[0].message.content or ""

        return final_msg.content or ""

    except SensitiveActionRequired:
        raise  # Propagar para o caller (agent_hub.py) tratar
    except Exception as e:
        logger.warning(f"⚠️ Function calling falhou para {agent_id}: {e}", exc_info=True)
        return ""  # Fallback para chamada sem ferramentas


# ============================================================================
# CHAT INTELIGENTE COM LLM
# ============================================================================

async def get_llm_response(agent_id: str, user_message: str, history: list[dict] | None = None, user_id: int | None = None, confirmed_action: str | None = None) -> str:
    """
    Gera resposta inteligente usando OpenAI GPT-4.1
    com system prompt especializado por agente.
    Suporta function calling para ações reais (cadastrar, agendar, etc.).
    Filtra dados pelo user_id autenticado.
    
    Args:
        confirmed_action: Nome da tool que foi confirmada com senha (bypass de confirmação).
    Raises:
        SensitiveActionRequired: Quando uma ação requer confirmação com senha.
    """
    # Mutable default fix
    if history is None:
        history = []

    # Resolver aliases legados (financeiro/documentos → contabilidade)
    from app.core.agent_aliases import resolve_agent_id as _resolve_alias
    agent_id = _resolve_alias(agent_id)

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

    # ── Contexto cross-agent (resumo de outros agentes) ──────────
    if user_id:
        try:
            from app.services.chat_context import load_cross_agent_summary
            cross_ctx = load_cross_agent_summary(user_id, agent_id, msgs_per_agent=4)
            if cross_ctx:
                system_prompt += cross_ctx
        except Exception:
            pass  # Não bloquear se falhar

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
        # Cópia da lista para que _call_with_tools não corrompa o original
        # (ela adiciona tool_calls/tool results que quebram o fallback sem tools)
        messages_for_tools = list(messages)
        tool_response = _call_with_tools(messages_for_tools, agent_id, user_id, confirmed_action=confirmed_action)
        if tool_response:
            return tool_response

    # ── Fallback: chamada sem ferramentas ─────────────────────────
    client = get_openai_client()
    if client:
        try:
            response = client.chat_completion(
                messages=messages,
                temperature=0.15,
                max_tokens=800,
            )
            if response:
                return response
        except Exception as e:
            logger.error(f"Erro ao gerar resposta LLM: {e}")

    # ── Último recurso: fallback por palavras-chave (LLM indisponível) ──
    keyword_fallback = _get_keyword_fallback(agent_id, user_message)
    if keyword_fallback:
        return keyword_fallback

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
    # Fornecedores e Estoque
    "list_suppliers": "Mostra meus fornecedores. Lista simples com nome, telefone e se tá ativo. Se não tenho nenhum, me explica como cadastrar.",
    "stock_summary": "Como tá meu estoque? Mostra quantos produtos tenho, valor total e se tem algum com estoque baixo.",
    # Financeiro (unifica contabilidade)
    "monthly_summary": "Como tá meu mês? Quanto entrou, quanto saiu e quanto sobrou. Separe por forma de pagamento se tiver (PIX, dinheiro, cartão débito, cartão crédito, fiado, boleto, transferência, etc).",
    "daily_summary_fin": "Como foi meu dia hoje? Quanto entrou e saiu HOJE, detalhando por forma de pagamento (PIX, dinheiro, cartão débito, crédito, fiado, etc).",
    "weekly_summary_fin": "Como foi minha semana? Quanto entrou e saiu ESSA SEMANA, mostrando o melhor dia e detalhando por forma de pagamento.",
    "payment_breakdown": "Me mostra as vendas separadas por forma de pagamento: à vista, a prazo, cartão de débito, cartão de crédito, crédito próprio, fiado, entrada + parcelado, parcelado, PIX, dinheiro, transferência, boleto. Mostra do mês e da semana.",
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
        "cadastrar cliente": "👤 **Novo Cliente**\n\nPra cadastrar, preciso de:\n1. **Nome completo**\n2. **Telefone** (com DDD)\n3. **Email** (opcional)\n\nMe passe as informações! 😊",
        "novo cliente": "👤 **Novo Cliente**\n\nPra cadastrar, preciso de:\n1. **Nome completo**\n2. **Telefone** (com DDD)\n3. **Email** (opcional)\n\nMe passe as informações! 😊",
        "cadastrar fornecedor": "🚚 **Novo Fornecedor**\n\nPra cadastrar, preciso de:\n1. **Nome** do fornecedor\n2. **Telefone** (com DDD)\n3. **Email** (opcional)\n\nMe passe as informações! 😊",
        "novo fornecedor": "🚚 **Novo Fornecedor**\n\nPra cadastrar, preciso de:\n1. **Nome** do fornecedor\n2. **Telefone** (com DDD)\n3. **Email** (opcional)\n\nMe passe as informações! 😊",
        "meu estoque": "📦 Você ainda não tem produtos cadastrados no estoque.\n\nPra começar a controlar, cadastre seus produtos primeiro!",
        "fornecedores": "🚚 Você ainda não tem fornecedores cadastrados.\n\nQuer cadastrar o primeiro? Me diz o **nome** e **telefone**! 😊",
    },
    "agenda": {
        "O que eu tenho marcado pra hoje": "📅 Dia livre! Você não tem nada marcado pra hoje.\n\nQuer agendar algo? Me diz o que, o dia e o horário! 😊",
        "Mostra minha agenda da semana": "📅 Semana livre! Nenhum compromisso agendado.\n\nQuer marcar algo? Me diz: \"reunião amanhã às 14h\" por exemplo.",
        "Quero marcar um compromisso": "📅 **Novo Compromisso**\n\nMe diz:\n1. **O que** vai fazer (reunião, consulta, ligação...)\n2. **Quando** (dia e hora)\n3. **Onde** (opcional)\n\n💡 Exemplo: \"dentista amanhã 15h\"",
        "cadastrar cliente": "👤 **Novo Cliente**\n\nPra cadastrar, preciso de:\n1. **Nome completo**\n2. **Telefone** (com DDD)\n3. **Email** (opcional)\n\nMe passe as informações! 😊",
        "novo cliente": "👤 **Novo Cliente**\n\nPra cadastrar, preciso de:\n1. **Nome completo**\n2. **Telefone** (com DDD)\n3. **Email** (opcional)\n\nMe passe as informações! 😊",
        "cadastrar fornecedor": "🚚 **Novo Fornecedor**\n\nPra cadastrar, preciso de:\n1. **Nome** do fornecedor\n2. **Telefone** (com DDD)\n3. **Email** (opcional)\n\nMe passe as informações! 😊",
        "novo fornecedor": "🚚 **Novo Fornecedor**\n\nPra cadastrar, preciso de:\n1. **Nome** do fornecedor\n2. **Telefone** (com DDD)\n3. **Email** (opcional)\n\nMe passe as informações! 😊",
        "meus clientes": "👥 Você ainda não tem clientes cadastrados.\n\nQuer cadastrar o primeiro? Me diz o **nome**, **telefone** e **email** que eu registro rapidinho! 😊",
        "meu estoque": "📦 Você ainda não tem produtos cadastrados no estoque.\n\nPra começar a controlar, cadastre seus produtos primeiro!",
        "fornecedores": "🚚 Você ainda não tem fornecedores cadastrados.\n\nQuer cadastrar o primeiro? Me diz o **nome** e **telefone**! 😊",
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
        "cadastrar cliente": "👤 **Novo Cliente**\n\nPra cadastrar, preciso de:\n1. **Nome completo**\n2. **Telefone** (com DDD)\n3. **Email** (opcional)\n\nMe passe as informações! 😊",
        "cadastrar fornecedor": "🚚 **Novo Fornecedor**\n\nPra cadastrar, preciso de:\n1. **Nome** do fornecedor\n2. **Telefone** (com DDD)\n3. **Email** (opcional)\n\nMe passe as informações! 😊",
        "novo fornecedor": "🚚 **Novo Fornecedor**\n\nPra cadastrar, preciso de:\n1. **Nome** do fornecedor\n2. **Telefone** (com DDD)\n3. **Email** (opcional)\n\nMe passe as informações! 😊",
        "meu estoque": "📦 Você ainda não tem produtos cadastrados no estoque.\n\nPra começar a controlar, cadastre seus produtos primeiro!",
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


def _get_keyword_fallback(agent_id: str, user_message: str) -> str:
    """Fallback de último recurso quando o LLM está indisponível.
    Detecta intenção por palavras-chave e retorna orientação útil.
    Retorna string vazia se não reconhecer a intenção.
    """
    msg = user_message.lower()

    if any(kw in msg for kw in ("cadastrar cliente", "novo cliente", "registrar cliente", "adicionar cliente")):
        return (
            "👤 **Novo Cliente**\n\n"
            "Pra cadastrar, preciso de:\n"
            "1. **Nome completo**\n"
            "2. **Telefone** (com DDD)\n"
            "3. **Email** (opcional)\n\n"
            "Me passe as informações! 😊"
        )

    if any(kw in msg for kw in ("cadastrar fornecedor", "novo fornecedor", "registrar fornecedor", "adicionar fornecedor")):
        return (
            "🚚 **Novo Fornecedor**\n\n"
            "Pra cadastrar, preciso de:\n"
            "1. **Nome** do fornecedor\n"
            "2. **Telefone** (com DDD)\n"
            "3. **Email** (opcional)\n\n"
            "Me passe as informações! 😊"
        )

    if any(kw in msg for kw in ("marcar compromisso", "agendar reunião", "agendar reuniao", "novo compromisso", "marcar reunião", "marcar reuniao")):
        return (
            "📅 **Novo Compromisso**\n\n"
            "Me diz:\n"
            "1. **O que** vai fazer (reunião, consulta, ligação...)\n"
            "2. **Quando** (dia e hora)\n"
            "3. **Onde** (opcional)\n\n"
            "💡 Exemplo: \"dentista amanhã 15h\""
        )

    if any(kw in msg for kw in ("anotar venda", "registrar venda", "recebi", "gastei", "paguei", "anotar gasto")):
        return (
            "💰 **Registrar Transação**\n\n"
            "Me diz:\n"
            "1. **Tipo**: entrada (venda) ou saída (gasto)\n"
            "2. **Valor**: quanto\n"
            "3. **Descrição**: o que foi\n"
            "4. **Forma de pagamento**: PIX, dinheiro, cartão, etc.\n\n"
            "💡 Exemplo: \"recebi R$ 500 do João por PIX\""
        )

    if any(kw in msg for kw in ("meus clientes", "listar clientes", "ver clientes", "quantos clientes")):
        return "👥 Use o botão **Meus Clientes** nas Ações Rápidas para ver a lista! Ou me diga o nome de quem procura."

    if any(kw in msg for kw in ("meus fornecedores", "listar fornecedores", "ver fornecedores")):
        return "🚚 Use o botão **Meus Fornecedores** nas Ações Rápidas para ver a lista! Ou me diga o nome de quem procura."

    if any(kw in msg for kw in ("meu estoque", "estoque", "inventário", "inventario", "produtos")):
        return "📦 Use o botão **Meu Estoque** nas Ações Rápidas para ver o resumo! Ou me pergunte sobre um produto específico."

    if any(kw in msg for kw in ("nota fiscal", "emitir nf", "emitir nota")):
        return (
            "📝 **Emissão de Nota Fiscal (NFS-e)**\n\n"
            "Pra emitir a nota, preciso de:\n"
            "1. **Nome/Razão Social** do cliente\n"
            "2. **CPF ou CNPJ** do cliente\n"
            "3. **Valor** do serviço/produto\n"
            "4. **Descrição** do que foi feito\n\n"
            "Me passe essas informações! 😊"
        )

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

        # ── Dados do perfil do proprietário (PF/PJ) ─────────────────
        # Disponibiliza para agentes: nome, CPF/CNPJ, endereço, telefone, etc.
        _profile_lines: list[str] = []
        if user_id:
            try:
                from database.models import SessionLocal, User as _UserModel
                _pdb = SessionLocal()
                try:
                    _usr = _pdb.query(_UserModel).filter(_UserModel.id == user_id).first()
                    if _usr:
                        _pf = []
                        if getattr(_usr, "full_name", None):
                            _pf.append(f"Nome: {_usr.full_name}")
                        _pt = getattr(_usr, "person_type", None)
                        if _pt:
                            _pf.append(f"Tipo: {'Pessoa Física' if _pt == 'PF' else 'Pessoa Jurídica'}")
                        if getattr(_usr, "cpf", None):
                            _pf.append(f"CPF: {_usr.cpf}")
                        if getattr(_usr, "cnpj", None):
                            _pf.append(f"CNPJ: {_usr.cnpj}")
                        if getattr(_usr, "company_name", None):
                            _pf.append(f"Razão Social: {_usr.company_name}")
                        if getattr(_usr, "trade_name", None):
                            _pf.append(f"Nome Fantasia: {_usr.trade_name}")
                        if getattr(_usr, "phone", None):
                            _pf.append(f"Telefone: {_usr.phone}")
                        if getattr(_usr, "state_registration", None):
                            _pf.append(f"IE: {_usr.state_registration}")
                        if getattr(_usr, "municipal_registration", None):
                            _pf.append(f"IM: {_usr.municipal_registration}")
                        # Endereço compacto
                        _addr_parts = []
                        for _af in ("address_street", "address_number", "address_complement", "address_neighborhood", "address_city", "address_state", "address_zip"):
                            _av = getattr(_usr, _af, None)
                            if _av:
                                _addr_parts.append(str(_av))
                        if _addr_parts:
                            _pf.append(f"Endereço: {', '.join(_addr_parts)}")
                        if getattr(_usr, "business_type", None):
                            _pf.append(f"Tipo de Negócio: {_usr.business_type}")
                        if _pf:
                            _profile_lines.append("🧑‍💼 DADOS DO PROPRIETÁRIO/EMPRESA:")
                            _profile_lines.extend(f"  {l}" for l in _pf)
                finally:
                    _pdb.close()
            except Exception:
                pass  # Não bloquear se perfil indisponível

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
        # dashboard.total já conta só os ativos; inactive é contagem separada
        active_cl = clients_info.get("total", 0)
        inactive_cl = clients_info.get("inactive", 0)
        total_cl = active_cl + inactive_cl

        if active_cl > 0:
            lines.append(f"👥 Você tem {active_cl} cliente(s) ativo(s)" + (f" (e {inactive_cl} inativo(s))" if inactive_cl else ""))
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
        elif inactive_cl > 0:
            lines.append(f"👥 Nenhum cliente ativo ({inactive_cl} inativo(s)/excluído(s))")
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

        # Fornecedores
        try:
            from database.models import Client as _SuppClient, get_session as _supp_gs
            _supp_s = _supp_gs()
            try:
                supp_q = _supp_s.query(_SuppClient).filter(
                    _SuppClient.contact_type == "supplier",
                    _SuppClient.is_active == True,
                )
                if user_id:
                    supp_q = supp_q.filter(_SuppClient.user_id == user_id)
                supp_count = supp_q.count()
                if supp_count > 0:
                    supps = supp_q.order_by(_SuppClient.name).limit(5).all()
                    supp_names = [f"  - {s.name} | {s.phone or 'sem tel'}" for s in supps]
                    lines.append(f"🚚 Fornecedores: {supp_count} cadastrado(s)")
                    lines.append("Lista:\n" + "\n".join(supp_names))
            finally:
                _supp_s.close()
        except Exception:
            pass

        # Resumo por forma de pagamento (mês atual)
        try:
            pb = CRMService.get_payment_breakdown(user_id=user_id)
            by_pm = pb.get("by_payment_method", {})
            if by_pm:
                pm_lines = [f"  - {k}: R$ {v['total']:,.2f} ({v['percent']}%)" for k, v in by_pm.items() if v['total'] > 0]
                if pm_lines:
                    lines.append("💳 Vendas por forma de pgto (mês):")
                    lines.extend(pm_lines)
        except Exception:
            pass

        return "\n".join(_profile_lines + lines) if (_profile_lines or lines) else "Sem dados cadastrados ainda."

    except Exception as e:
        logger.warning(f"CRM context indisponível: {e}")
        return "Dados não disponíveis no momento."
