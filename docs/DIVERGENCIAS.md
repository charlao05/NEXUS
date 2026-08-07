# Divergências abertas — fila operacional

Promessa do produto × implementação. **Fila, não arquivo histórico:** só itens
abertos, uma linha cada, ponteiro em vez de conteúdo.

⏳ **Transitório.** Morre quando a Matriz de Funcionalidades existir — ali
divergência vira *estado de uma funcionalidade* — ou quando esta fila zerar.

| Divergência | Estado | Decisão necessária | Destino |
|---|---|---|---|
| PIX prometido no addon — `Pricing.tsx:365` × `auth.py:1524` | aberta | cumprir ou corrigir a copy; depende de 2 leituras de painel (`Country`, Pix ativo) | **E-046** · **D-017** |
| Agente promete "gera propostas comerciais" e o pipeline não recebe — `agent_hub.py:435`, zero refs a `Opportunity` | aberta | ligar ao pipeline ou corrigir a descrição | — |

**Ao resolver:** o item **vira evidência, vira decisão, ou desaparece** — e sai
daqui. Item encerrado não mora nesta fila.

**Ao registrar:** promessa com `arquivo:linha`, e uma decisão necessária que
tenha dois lados — *cumprir* ou *corrigir a comunicação*. Escolher é decisão de
produto.

🔴 Item que passe a ser exigido por obrigação legal ou de auditoria **deixa de ser
transitório** e migra para registro permanente (D-018) — foi o caso da exportação
LGPD, hoje **E-047**.
