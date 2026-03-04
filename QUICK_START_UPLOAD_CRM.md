# 🎬 GUIA RÁPIDO: Como Testar Upload OCR + CRM Externo

## ⚡ TL;DR - Começar em 5 minutos

### **1. Verificar Status dos Serviços**
```bash
# Verificar se backend está rodando
curl http://localhost:8000/health

# Verificar se frontend está rodando
curl http://localhost:5176/
```

### **2. Abrir a Aplicação**
Navegue para: **http://localhost:5176/agents**

### **3. Testar Upload OCR**
- Clique em qualquer agente
- Procure pelo botão: **📄 Carregar Documento (OCR)**
- Selecione tipo: **"Obrigação (DAS, FGTS, etc)"**
- (Arquivo de exemplo abaixo)
- Veja os dados extraídos na pré-visualização JSON

### **4. Testar CRM Externo**
- Clique em qualquer agente
- Procure pelo botão: **🔗 Integrar CRM Externo**
- Preencha com dados de teste:
  - URL: `https://api.example.com`
  - Token: `test-token`
  - Endpoint: `/contacts`
- Clique em **"🧪 Testar Conexão"** → Vê badge ✓ Conectado
- Clique em **"🚀 Sincronizar"** → Importa clientes

---

## 📊 O Que Acontece Por Trás

### **Upload OCR Flow**
```
Frontend (UploadModal)
    ↓
Seleciona arquivo
    ↓
Converte para Base64
    ↓
Envia POST /api/upload/process
    ↓
Backend processa (OCR stub)
    ↓
Retorna JSON estruturado
    ↓
Frontend auto-preenche formulário
    ↓
Pré-visualização mostra dados extraídos
```

### **CRM Sync Flow**
```
Frontend (ExternalCrmModal)
    ↓
Preenche URL + Token + Endpoint
    ↓
Clica "Testar Conexão"
    ↓
POST /api/external-crm/test-connection
    ↓
Backend retorna status (stub)
    ↓
Se OK: POST /api/external-crm/sync
    ↓
Backend importa clientes (mock: 2 clientes)
    ↓
Frontend recarrega dropdown de clientes
    ↓
Clientes importados aparecem na lista
```

---

## 🧪 Dados de Teste

### **Tipos de Documento (OCR)**
| Tipo | Retorna |
|------|---------|
| `obligation` | DAS com due_date, estimated_value |
| `sale` | Venda com cliente, valor, descrição |
| `invoice` | NFS-e com série, número, cliente |
| `customer` | Cliente com CNPJ, email, phone |

**Exemplo de retorno (obligation):**
```json
{
  "id": "OBL-001",
  "name": "DAS - Janeiro",
  "type": "DAS",
  "due_date": "2026-01-20",
  "estimated_value": 80.50,
  "priority": "high"
}
```

### **CRM Externo (Stub)**
O stub retorna **sempre** estes dados:
```json
{
  "status": "ok",
  "synced_clients": 2,
  "synced_obligations": 4,
  "synced_sales": 2,
  "errors": []
}
```

**URLs testadas (funcionam):**
- `https://api.pipedrive.com`
- `https://api.zendesk.com`
- `https://api.hubspot.com`
- Qualquer URL (resposta é stub)

---

## 🔧 Endpoints Disponíveis

### **Upload**
```
POST /api/upload/process
Content-Type: application/json

{
  "document_type": "obligation|sale|invoice|customer",
  "file_base64": "base64-do-arquivo"
}

Resposta:
{
  "status": "ok",
  "extracted_data": {...},
  "confidence": 0.85,
  "message": "..."
}
```

### **CRM - Testar Conexão**
```
POST /api/external-crm/test-connection
Content-Type: application/json

{
  "url": "https://api.example.com",
  "api_token": "seu-token",
  "endpoint": "/persons"
}

Resposta:
{
  "status": "ok",
  "message": true
}
```

### **CRM - Sincronizar**
```
POST /api/external-crm/sync
Content-Type: application/json

{
  "url": "https://api.pipedrive.com",
  "api_token": "seu-token",
  "endpoint": "/persons",
  "field_mappings": {}
}

Resposta:
{
  "status": "ok",
  "synced_clients": 2,
  "synced_obligations": 4,
  "synced_sales": 2,
  "errors": []
}
```

---

## 🎨 Interface Visual

### **Botões de Integração**
Localizados na parte inferior do formulário de agente:

```
┌─────────────────────────────────────┐
│ 📄 Carregar Documento (OCR)         │
│ 🔗 Integrar CRM Externo             │
└─────────────────────────────────────┘
```

### **Modal de Upload**
```
┌─────────────────────────────────────┐
│ 📄 Carregar Documento (OCR)      [✕]│
├─────────────────────────────────────┤
│ Tipo de Documento:                  │
│ [Obrigação ▼]                       │
│                                     │
│ Arquivo (Foto/PDF):                 │
│ [Selecionar arquivo...]             │
│                                     │
│ [Cancelar] [✨ Extrair Dados]      │
└─────────────────────────────────────┘
```

### **Modal de CRM**
```
┌─────────────────────────────────────┐
│ 🔗 Integrar com CRM Externo     [✕]│
├─────────────────────────────────────┤
│ URL da API:                         │
│ [https://api.pipedrive.com...]      │
│                                     │
│ API Token / Bearer:                 │
│ [••••••••••••••••••]                │
│                                     │
│ Endpoint:                           │
│ [/persons]                          │
│                                     │
│ [🧪 Testar] [✓ Conectado]          │
│ [🚀 Sincronizar]                   │
└─────────────────────────────────────┘
```

---

## 🐛 Troubleshooting

### **"Conexão recusada" na porta 8000**
```bash
# Verificar se backend está rodando
netstat -ano | findstr :8000

# Matar processo se necessário
taskkill /PID <PID> /F

# Reiniciar
cd c:\Users\Charles\Desktop\NEXUS
& .\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### **"Conexão recusada" na porta 5176**
```bash
# Frontend pode estar em outra porta (5173, 5174, 5175...)
# Procure no console do npm a URL correta

# Se nada funciona, reiniciar:
cd c:\Users\Charles\Desktop\NEXUS\frontend
npm run dev
```

### **Modal não abre**
- Verifique console (F12 → Console)
- Procure por erros JavaScript
- Limpe cache: Ctrl+Shift+Delete

### **Dados não aparecem na pré-visualização**
- Verifique se arquivo foi carregado
- Procure por erro na rede (F12 → Network)
- Confirme que backend respondeu com 200

---

## 💡 Dicas

1. **Teste com dados simples:** Use valores curtos antes de testar com dados reais
2. **Console browser:** F12 → Console mostra erros em tempo real
3. **Network tab:** F12 → Network mostra requisições/respostas
4. **Dados testados:** Todos os endpoints retornam sucesso (stubs)
5. **Produção:** Substitua stubs por integrações reais (código comentado pronto)

---

## 📚 Documentação Completa

Veja também:
- `UPLOAD_OCR_IMPLEMENTATION.md` - Implementação técnica
- `UPLOAD_OCR_FINAL_REPORT.md` - Relatório executivo
- `UPLOAD_OCR_CRM_IMPLEMENTATION.md` - Descrição geral

---

## 🎉 Status

✅ **PRONTO PARA TESTAR**

- Backend rodando ✓
- Frontend rodando ✓
- Endpoints respondendo ✓
- UI bonita e responsiva ✓
- Dados fluindo corretamente ✓

**Começar:** Abra http://localhost:5176/agents e clique nos botões de integração!
