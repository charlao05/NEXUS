# PROMPT DETALHADO PARA INTERFACE NEXUS
**Foco: Botões com Gradientes Psicológicos Únicos**

## PROBLEMA ATUAL
Todos os botões estão com a mesma cor roxa/lilás. Preciso que cada agente tenha seu próprio gradiente único.

## OBJETIVO
Cada botão deve ter um gradiente que reflita a PERSONALIDADE e FUNÇÃO do agente, baseado em psicologia das cores.

---

## ESPECIFICAÇÃO DETALHADA DOS BOTÕES

### REGRAS GERAIS PARA TODOS OS BOTÕES

**Dimensões:**
- Largura: 100% do card (w-full)
- Altura: py-3.5 (14px padding vertical)
- Border radius: rounded-lg (8px)
- Fonte: font-semibold text-base

**Estados de Hover:**
- Escala: scale-105
- Sombra: shadow-xl
- Transição: transition-all duration-300
- Brilho: brightness-110

**Estados de Focus:**
- Ring: focus:ring-4
- Ring color: Baseada no gradiente principal
- Outline: outline-none

**Estados de Active (clique):**
- Escala: scale-95
- Duração: 100ms

---

## BOTÃO 1: AUTOMAÇÃO WEB 🌐
**Psicologia:** Confiança técnica, estabilidade, profissionalismo

**Gradiente Normal:**
```css
background: linear-gradient(135deg, #2563EB 0%, #1E40AF 100%);
/* from-blue-600 to-blue-700 */
```

**Hover:**
```css
background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%);
/* from-blue-700 to-blue-800 */
box-shadow: 0 20px 25px -5px rgba(37, 99, 235, 0.4);
```

**Classes Tailwind Completas:**
```html
<button class="w-full bg-gradient-to-r from-blue-600 to-blue-700 
               text-white font-semibold py-3.5 rounded-lg
               hover:from-blue-700 hover:to-blue-800 
               hover:shadow-xl hover:scale-105
               active:scale-95
               focus:ring-4 focus:ring-blue-300 focus:outline-none
               transition-all duration-300">
  Executar
</button>
```

**Cores Hex Exatas:**
- Cor 1 (início): #2563EB (blue-600)
- Cor 2 (fim): #1E40AF (blue-700)
- Hover início: #1E40AF (blue-700)
- Hover fim: #1E3A8A (blue-800)
- Ring focus: #93C5FD (blue-300)

---

## BOTÃO 2: AGENDA COMPLETA 📅
**Psicologia:** Organização, inteligência, sofisticação

**Gradiente Normal:**
```css
background: linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%);
/* from-purple-600 to-purple-700 */
```

**Hover:**
```css
background: linear-gradient(135deg, #6D28D9 0%, #5B21B6 100%);
/* from-purple-700 to-purple-800 */
box-shadow: 0 20px 25px -5px rgba(124, 58, 237, 0.4);
```

**Classes Tailwind Completas:**
```html
<button class="w-full bg-gradient-to-r from-purple-600 to-purple-700 
               text-white font-semibold py-3.5 rounded-lg
               hover:from-purple-700 hover:to-purple-800 
               hover:shadow-xl hover:scale-105
               active:scale-95
               focus:ring-4 focus:ring-purple-300 focus:outline-none
               transition-all duration-300">
  Executar
</button>
```

**Cores Hex Exatas:**
- Cor 1: #7C3AED (purple-600)
- Cor 2: #6D28D9 (purple-700)
- Hover início: #6D28D9 (purple-700)
- Hover fim: #5B21B6 (purple-800)
- Ring focus: #D8B4FE (purple-300)

---

## BOTÃO 3: CLIENTES (CRM) 👥
**Psicologia:** Relacionamento, comunicação, confiança social

**Gradiente Normal:**
```css
background: linear-gradient(135deg, #0891B2 0%, #0E7490 100%);
/* from-cyan-600 to-cyan-700 */
```

**Hover:**
```css
background: linear-gradient(135deg, #0E7490 0%, #155E75 100%);
/* from-cyan-700 to-cyan-800 */
box-shadow: 0 20px 25px -5px rgba(8, 145, 178, 0.4);
```

**Classes Tailwind Completas:**
```html
<button class="w-full bg-gradient-to-r from-cyan-600 to-cyan-700 
               text-white font-semibold py-3.5 rounded-lg
               hover:from-cyan-700 hover:to-cyan-800 
               hover:shadow-xl hover:scale-105
               active:scale-95
               focus:ring-4 focus:ring-cyan-300 focus:outline-none
               transition-all duration-300">
  Executar
</button>
```

**Cores Hex Exatas:**
- Cor 1: #0891B2 (cyan-600)
- Cor 2: #0E7490 (cyan-700)
- Hover início: #0E7490 (cyan-700)
- Hover fim: #155E75 (cyan-800)
- Ring focus: #67E8F9 (cyan-300)

---

## BOTÃO 4: ANÁLISE FINANCEIRA 💰
**Psicologia:** Crescimento, dinheiro, segurança financeira

**Gradiente Normal:**
```css
background: linear-gradient(135deg, #059669 0%, #047857 100%);
/* from-green-600 to-green-700 */
```

**Hover:**
```css
background: linear-gradient(135deg, #047857 0%, #065F46 100%);
/* from-green-700 to-green-800 */
box-shadow: 0 20px 25px -5px rgba(5, 150, 105, 0.4);
```

**Classes Tailwind Completas:**
```html
<button class="w-full bg-gradient-to-r from-green-600 to-green-700 
               text-white font-semibold py-3.5 rounded-lg
               hover:from-green-700 hover:to-green-800 
               hover:shadow-xl hover:scale-105
               active:scale-95
               focus:ring-4 focus:ring-green-300 focus:outline-none
               transition-all duration-300">
  Executar
</button>
```

**Cores Hex Exatas:**
- Cor 1: #059669 (green-600)
- Cor 2: #047857 (green-700)
- Hover início: #047857 (green-700)
- Hover fim: #065F46 (green-800)
- Ring focus: #86EFAC (green-300)

---

## BOTÃO 5: NOTA FISCAL 📄
**Psicologia:** Profissionalismo, seriedade, documentação

**Gradiente Normal:**
```css
background: linear-gradient(135deg, #4F46E5 0%, #4338CA 100%);
/* from-indigo-600 to-indigo-700 */
```

**Hover:**
```css
background: linear-gradient(135deg, #4338CA 0%, #3730A3 100%);
/* from-indigo-700 to-indigo-800 */
box-shadow: 0 20px 25px -5px rgba(79, 70, 229, 0.4);
```

**Classes Tailwind Completas:**
```html
<button class="w-full bg-gradient-to-r from-indigo-600 to-indigo-700 
               text-white font-semibold py-3.5 rounded-lg
               hover:from-indigo-700 hover:to-indigo-800 
               hover:shadow-xl hover:scale-105
               active:scale-95
               focus:ring-4 focus:ring-indigo-300 focus:outline-none
               transition-all duration-300">
  Executar
</button>
```

**Cores Hex Exatas:**
- Cor 1: #4F46E5 (indigo-600)
- Cor 2: #4338CA (indigo-700)
- Hover início: #4338CA (indigo-700)
- Hover fim: #3730A3 (indigo-800)
- Ring focus: #A5B4FC (indigo-300)

---

## BOTÃO 6: COBRANÇAS 💳
**Psicologia:** Ação urgente (mas suave), importância, atenção

**Gradiente Normal:**
```css
background: linear-gradient(135deg, #DB2777 0%, #BE185D 100%);
/* from-pink-600 to-pink-700 */
```

**Hover:**
```css
background: linear-gradient(135deg, #BE185D 0%, #9F1239 100%);
/* from-pink-700 to-pink-800 */
box-shadow: 0 20px 25px -5px rgba(219, 39, 119, 0.4);
```

**Classes Tailwind Completas:**
```html
<button class="w-full bg-gradient-to-r from-pink-600 to-pink-700 
               text-white font-semibold py-3.5 rounded-lg
               hover:from-pink-700 hover:to-pink-800 
               hover:shadow-xl hover:scale-105
               active:scale-95
               focus:ring-4 focus:ring-pink-300 focus:outline-none
               transition-all duration-300">
  Executar
</button>
```

**Cores Hex Exatas:**
- Cor 1: #DB2777 (pink-600)
- Cor 2: #BE185D (pink-700)
- Hover início: #BE185D (pink-700)
- Hover fim: #9F1239 (pink-800)
- Ring focus: #F9A8D4 (pink-300)

---

## TABELA DE REFERÊNCIA RÁPIDA

| Agente              | Cor Base | Gradiente Normal          | Gradiente Hover           | Ring Focus | Psicologia               |
|---------------------|----------|---------------------------|---------------------------|------------|--------------------------|
| 🌐 Automação Web    | Azul     | blue-600 → blue-700       | blue-700 → blue-800       | blue-300   | Confiança técnica        |
| 📅 Agenda           | Roxo     | purple-600 → purple-700   | purple-700 → purple-800   | purple-300 | Organização              |
| 👥 Clientes         | Cyan     | cyan-600 → cyan-700       | cyan-700 → cyan-800       | cyan-300   | Relacionamento           |
| 💰 Financeiro       | Verde    | green-600 → green-700     | green-700 → green-800     | green-300  | Crescimento financeiro   |
| 📄 Nota Fiscal      | Indigo   | indigo-600 → indigo-700   | indigo-700 → indigo-800   | indigo-300 | Profissionalismo         |
| 💳 Cobranças        | Rosa     | pink-600 → pink-700       | pink-700 → pink-800       | pink-300   | Urgência suave           |

---

## CHECKLIST DE IMPLEMENTAÇÃO

✅ Cada botão tem gradiente único  
✅ Cores baseadas em psicologia (azul=confiança, verde=dinheiro, etc)  
✅ Hover com gradiente mais escuro  
✅ Sombra colorida no hover (mesma cor do botão)  
✅ Escala 105% no hover (micro-recompensa)  
✅ Escala 95% no clique (feedback tátil)  
✅ Ring colorido no focus (acessibilidade)  
✅ Transição suave 300ms  
✅ Texto branco em todos (contraste perfeito)  
✅ Border radius consistente (rounded-lg)  

---

## RESULTADO ESPERADO

Cada agente terá uma identidade visual única através de seu botão:
- 🌐 **Azul**: Técnico, confiável
- 📅 **Roxo**: Organizado, inteligente
- 👥 **Cyan**: Social, comunicativo
- 💰 **Verde**: Financeiro, crescimento
- 📄 **Indigo**: Profissional, sério
- 💳 **Rosa**: Urgente (suave), importante

✨ Usuário identificará cada agente pela cor instantaneamente.  
✨ Gradientes transmitem modernidade e sofisticação.  
✨ Hover recompensa com feedback visual imediato.
