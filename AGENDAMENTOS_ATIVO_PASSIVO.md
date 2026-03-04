# 📆 Agendamentos no NEXUS: Ativo vs Passivo

## 🎯 Visão Geral

O NEXUS possui **dois sistemas de agendamento distintos** para atender diferentes necessidades:

### 1. **📆 Agenda Ativa** (Você → Compromissos)
**Agente:** `schedule_agent`  
**Conceito:** Você agenda compromissos que **VOCÊ precisa cumprir**  
**IA:** Monitora e **LEMBRA você automaticamente**

### 2. **📞 Agendamento Passivo** (Clientes → Você)
**Agente:** `attendance_agent`  
**Conceito:** Clientes agendam atendimentos **COM você**  
**IA:** Confirma e notifica **o cliente automaticamente**

---

## 📆 Agenda Ativa (schedule_agent)

### **O que é?**
Sistema para gerenciar **seus próprios compromissos e obrigações**. A IA monitora prazos e envia lembretes automáticos.

### **Tipos de Compromisso**

| Tipo | Descrição | Exemplo |
|------|-----------|---------|
| 💰 **Payment** | Pagamentos que você precisa fazer | DAS, fornecedores, salários, contas |
| ⏰ **Deadline** | Prazos e deadlines gerais | Entrega de projeto, envio de documentos |
| 📄 **Invoice** | Emissão/entrega de notas fiscais | Emitir NF para cliente, enviar NFS-e |
| 🏢 **Supplier** | Reuniões com fornecedores | Reunião com fornecedor, confirmar pedido |
| 🛒 **Purchase** | Compras e pedidos | Comprar estoque, fazer pedido |

### **Como Funciona**

```
Você cria compromisso
    ↓
Define: tipo, descrição, vencimento, prioridade
    ↓
IA calcula urgência automaticamente
    ↓
IA envia lembretes X dias antes
    ↓
IA sugere ações recomendadas
    ↓
Notificações via WhatsApp/Email/SMS
```

### **Exemplo de Uso**

```json
{
  "commitment_type": "payment",
  "description": "Pagamento DAS Janeiro 2026",
  "due_date": "2026-01-20",
  "priority": "high",
  "reminder_days": 3
}
```

**Resposta da IA:**
```json
{
  "status": "ok",
  "commitment": {
    "type": "payment",
    "description": "Pagamento DAS Janeiro 2026",
    "due_date": "2026-01-20",
    "priority": "high",
    "days_remaining": 14,
    "urgency": "soon"
  },
  "reminder": "🟡 Em breve: 💰 Pagamento DAS Janeiro 2026 - Vence em 14 dias (20/01/2026)",
  "reminder_date": "2026-01-17",
  "actions": [
    "💳 Separar valor para pagamento",
    "📋 Confirmar dados bancários"
  ],
  "auto_notify": true,
  "notification_channels": ["email", "whatsapp", "sms"]
}
```

### **Níveis de Urgência**

| Urgência | Critério | Emoji | Ação |
|----------|----------|-------|------|
| **Overdue** | Já passou do prazo | 🚨 | ATRASADO! Ação imediata |
| **Today** | Vence hoje | ⚠️ | HOJE! Executar agora |
| **Critical** | Vence amanhã (≤1 dia) | 🔴 | URGENTE! Priorizar |
| **Urgent** | Vence em 2-3 dias | 🟠 | ATENÇÃO! Em breve |
| **Soon** | Vence em 4-7 dias | 🟡 | Em breve |
| **Normal** | Vence em >7 dias | 📅 | Normal |

### **Ações Automáticas da IA**

**Para Pagamentos:**
- Vence ≤1 dia: "🚨 Efetuar pagamento HOJE para evitar multa"
- Vence ≤3 dias: "💳 Separar valor para pagamento"
- Vence >3 dias: "📅 Marcar data no calendário"

**Para Notas Fiscais:**
- Vence ≤1 dia: "📄 Emitir nota fiscal URGENTE"
- Demais: "📝 Preparar dados para emissão"

**Para Fornecedores:**
- "📞 Confirmar reunião/entrega com fornecedor"
- "📋 Preparar lista de pedidos"

---

## 📞 Agendamento Passivo (attendance_agent)

### **O que é?**
Sistema para quando **clientes agendam atendimentos COM você**. A IA automatiza confirmações e lembretes para o cliente.

### **Como Funciona**

```
Cliente solicita agendamento
    ↓
Você (ou IA) registra no sistema
    ↓
Sistema confirma automaticamente
    ↓
Envia confirmação para o cliente (WhatsApp/SMS/Email)
    ↓
Envia lembretes antes do horário
    ↓
Você atende o cliente
```

### **Exemplo de Uso**

```json
{
  "client_name": "Maria Silva",
  "phone": "11987654321",
  "datetime": "2026-01-10T14:30"
}
```

**Resposta da IA:**
```json
{
  "status": "scheduled",
  "appointment": {
    "client_name": "Maria Silva",
    "phone": "11987654321",
    "datetime": "2026-01-10T14:30",
    "type": "attendance"
  },
  "notification": "Agendamento confirmado para Maria Silva em 2026-01-10T14:30",
  "channels": ["whatsapp", "sms", "email"]
}
```

### **Tipos de Atendimento**

- 📞 Consultas
- 🤝 Reuniões com clientes
- 💼 Atendimentos presenciais
- 🎓 Consultorias
- 🛠️ Serviços agendados

### **Notificações Automáticas**

**Para o Cliente:**
- Confirmação imediata após agendamento
- Lembrete 24h antes
- Lembrete 1h antes (opcional)

**Para Você (opcional):**
- Resumo diário de atendimentos
- Alerta 15min antes do horário

---

## 🔀 Comparação Direta

| Aspecto | 📆 Agenda Ativa | 📞 Agendamento Passivo |
|---------|----------------|----------------------|
| **Quem agenda?** | Você | Cliente |
| **Quem executa?** | Você | Você atende |
| **Notificação para** | Você | Cliente |
| **Objetivo** | Lembrar VOCÊ de compromissos | Confirmar com CLIENTE |
| **Exemplos** | Pagar DAS, emitir NF, reunião fornecedor | Atendimento, consulta, reunião |
| **Agente** | `schedule_agent` | `attendance_agent` |
| **Campos** | commitment_type, due_date, priority | client_name, phone, datetime |

---

## 🎨 Interface no Frontend

### **Agenda Ativa** (card roxo)
```
┌─────────────────────────────────────────────────┐
│ 📆 Agenda Ativa (Seus Compromissos)            │
├─────────────────────────────────────────────────┤
│ Gerencie SEUS compromissos: pagamentos, NFs,   │
│ reuniões com fornecedores. A IA monitora e     │
│ lembra você.                                    │
│                                                 │
│ [Executar]                                      │
└─────────────────────────────────────────────────┘
```

**Formulário:**
- Tipo de Compromisso: [Dropdown: payment, deadline, invoice...]
- Descrição: [Input text]
- Data de Vencimento: [Date picker]
- Prioridade: [Dropdown: critical, high, normal, low]
- Dias de Antecedência: [Number: 3]

### **Agendamento Passivo** (card verde)
```
┌─────────────────────────────────────────────────┐
│ 📞 Agendamento Passivo (Clientes)              │
├─────────────────────────────────────────────────┤
│ Clientes agendam ATENDIMENTOS com você.        │
│ Automatiza confirmações via WhatsApp.          │
│                                                 │
│ [Executar]                                      │
└─────────────────────────────────────────────────┘
```

**Formulário:**
- Nome do Cliente: [Input text]
- Telefone: [Input tel]
- Data e Hora: [Datetime picker]

---

## 💡 Casos de Uso Práticos

### **Cenário 1: MEI com vários clientes**

**Agenda Ativa:**
- Pagar DAS todo dia 20 (lembrete 3 dias antes)
- Emitir NF para Cliente A até dia 15
- Reunião com fornecedor dia 12

**Agendamento Passivo:**
- Cliente João agendou atendimento dia 8 às 14h
- Cliente Maria agendou consulta dia 10 às 10h
- Cliente Pedro agendou reunião dia 12 às 16h

### **Cenário 2: Contador**

**Agenda Ativa:**
- Enviar declaração IRPF até 30/04
- Pagar guia INSS dia 15
- Emitir NF serviços prestados dia 10

**Agendamento Passivo:**
- Cliente A agendou consulta fiscal dia 5 às 9h
- Cliente B agendou entrega de documentos dia 7 às 14h

---

## 🚀 Próximos Passos (Roadmap)

### **Agenda Ativa**
- [ ] Integração com Google Calendar
- [ ] Notificações push (mobile)
- [ ] Sincronização com sistemas bancários (pagamentos automáticos)
- [ ] Dashboard de compromissos pendentes

### **Agendamento Passivo**
- [ ] Calendário visual para clientes escolherem horários
- [ ] Integração com Calendly/Google Calendar
- [ ] Link de agendamento público
- [ ] Confirmação de presença automática (cliente responde SMS)

---

## 📝 Resumo Executivo

✅ **Dois agentes distintos** para dois propósitos diferentes  
✅ **Agenda Ativa:** Você gerencia seus compromissos (IA lembra você)  
✅ **Agendamento Passivo:** Clientes agendam com você (IA notifica eles)  
✅ **UI diferenciada:** Cards e formulários específicos para cada tipo  
✅ **Notificações inteligentes:** WhatsApp, SMS, Email  
✅ **Priorização automática:** IA calcula urgência baseado em prazos  

**Use os dois juntos** para ter controle total da sua agenda profissional! 🎯
