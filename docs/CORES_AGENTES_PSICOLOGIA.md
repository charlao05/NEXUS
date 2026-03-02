# 🎨 Cores dos Agentes - Psicologia das Cores

## Mapa de Cores por Agente

Cada agente possui um gradiente único baseado em psicologia das cores para transmitir sua função e criar identidade visual instantânea.

---

### 🌐 Automação Web (site_agent)
**Cor:** Azul  
**Gradiente:** `#2563EB → #1E40AF` (blue-600 → blue-700)  
**Psicologia:** Confiança técnica, estabilidade, profissionalismo  
**CSS Class:** `.btn-automation`

**Quando usar azul:**
- Tecnologia e inovação
- Confiança e segurança
- Profissionalismo
- Processos técnicos

---

### 📅 Agenda Completa (agenda_agent)
**Cor:** Roxo  
**Gradiente:** `#7C3AED → #6D28D9` (purple-600 → purple-700)  
**Psicologia:** Organização, inteligência, sofisticação  
**CSS Class:** `.btn-agenda`

**Quando usar roxo:**
- Organização e planejamento
- Inteligência e estratégia
- Criatividade organizada
- Gestão de tempo

---

### 👥 Clientes / CRM (clients_agent)
**Cor:** Cyan  
**Gradiente:** `#0891B2 → #0E7490` (cyan-600 → cyan-700)  
**Psicologia:** Relacionamento, comunicação, confiança social  
**CSS Class:** `.btn-clients`

**Quando usar cyan:**
- Relacionamentos
- Comunicação
- Networking
- Atendimento ao cliente

---

### 💰 Análise Financeira (finance_agent)
**Cor:** Verde  
**Gradiente:** `#059669 → #047857` (green-600 → green-700)  
**Psicologia:** Crescimento, dinheiro, segurança financeira  
**CSS Class:** `.btn-financial`

**Quando usar verde:**
- Dinheiro e finanças
- Crescimento
- Prosperidade
- Saúde financeira

---

### 📄 Nota Fiscal (nf_agent)
**Cor:** Indigo  
**Gradiente:** `#4F46E5 → #4338CA` (indigo-600 → indigo-700)  
**Psicologia:** Profissionalismo, seriedade, documentação  
**CSS Class:** `.btn-invoice`

**Quando usar indigo:**
- Documentação oficial
- Seriedade e formalidade
- Processos legais
- Conformidade

---

### 💳 Cobranças (collections_agent)
**Cor:** Rosa  
**Gradiente:** `#DB2777 → #BE185D` (pink-600 → pink-700)  
**Psicologia:** Ação urgente (mas suave), importância, atenção  
**CSS Class:** `.btn-billing`

**Quando usar rosa:**
- Urgência sem agressividade
- Importância delicada
- Atenção necessária
- Lembretes importantes

---

## Tabela Resumo

| Agente          | Emoji | Cor    | Hex Início | Hex Fim | CSS Class       | Psicologia Principal |
|-----------------|-------|--------|------------|---------|-----------------|----------------------|
| Automação Web   | 🌐    | Azul   | #2563EB    | #1E40AF | .btn-automation | Confiança técnica    |
| Agenda          | 📅    | Roxo   | #7C3AED    | #6D28D9 | .btn-agenda     | Organização          |
| Clientes        | 👥    | Cyan   | #0891B2    | #0E7490 | .btn-clients    | Relacionamento       |
| Financeiro      | 💰    | Verde  | #059669    | #047857 | .btn-financial  | Crescimento          |
| Nota Fiscal     | 📄    | Indigo | #4F46E5    | #4338CA | .btn-invoice    | Profissionalismo     |
| Cobranças       | 💳    | Rosa   | #DB2777    | #BE185D | .btn-billing    | Urgência suave       |

---

## Como Adicionar Novo Agente

1. **Escolha a cor baseada na função:**
   - Financeiro → Verde
   - Técnico → Azul
   - Social → Cyan/Laranja
   - Urgente → Vermelho/Rosa
   - Organização → Roxo
   - Formal → Indigo

2. **Use o padrão Tailwind 600→700:**
   ```css
   background: linear-gradient(135deg, {cor}-600 0%, {cor}-700 100%);
   ```

3. **Hover sempre usa 700→800:**
   ```css
   hover: linear-gradient(135deg, {cor}-700 0%, {cor}-800 100%);
   ```

4. **Adicione ao mapa em AgentsPage.tsx:**
   ```typescript
   const classMap: Record<string, string> = {
     'novo_agent': 'btn-novo'
   }
   ```

5. **Crie o CSS em AgentsPage.css:**
   ```css
   .btn-novo {
     background: linear-gradient(135deg, #... 0%, #... 100%);
     box-shadow: 0 12px 26px rgba(..., 0.24);
   }
   ```

---

## Benefícios da Abordagem

✅ **Identidade Visual Instantânea** - Usuário reconhece agente pela cor  
✅ **Psicologia Aplicada** - Cores reforçam a função do agente  
✅ **Acessibilidade** - Ring focus colorido para navegação por teclado  
✅ **Feedback Visual** - Hover e active states criam micro-recompensas  
✅ **Modernidade** - Gradientes transmitem sofisticação  
✅ **Consistência** - Padrão repetível para novos agentes  

---

## Referências

- [Psicologia das Cores em UX](https://uxdesign.cc/color-psychology-in-ux-ui-design)
- [Tailwind CSS Gradients](https://tailwindcss.com/docs/gradient-color-stops)
- [Material Design Color System](https://m3.material.io/styles/color/system/overview)
