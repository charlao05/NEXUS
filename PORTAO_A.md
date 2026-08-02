# Portão A — Engenharia

## Resultado

# ✅ PASSOU

**Data:** 02/08/2026 · **Commit:** `898e2a2` · **Suíte:** 515 testes, 0 falhas

Tudo que se prova pelo repositório. O que depende de infraestrutura está em
[`PORTAO_O.md`](PORTAO_O.md) — **este portão não depende de conta paga.**

---

## 1. Objetivo

**Cinco usuários conseguem trabalhar durante sete dias sem perder dados,
dinheiro ou confiança.**

---

## 2. Critérios de saída

- [x] cadastro
- [x] login
- [x] criar cliente
- [x] criar produto
- [x] criar proposta
- [x] converter proposta *(manual — ver limitação 2)*
- [x] receber pagamento
- [x] ativar plano
- [x] cancelar assinatura
- [x] agenda
- [x] notificações
- [x] exportar meus dados
- [x] isolamento entre usuários

**13 de 13.**

---

## 3. Evidência

### cadastro
```
Teste:   test_auth.py · test_caminho_do_dinheiro.py::pagante
Commit:  604a207            Status: PASS
```

### login
```
Teste:   test_auth.py · test_atribuicao_consumo.py
Commit:  604a207            Status: PASS
```

### criar cliente
```
Teste:   test_isolamento_dashboard.py · test_fase6.py::TestCRMServiceMultiTenancy
Commit:  60f10de            Status: PASS
```

### criar produto
```
Teste:   test_inventory.py
Commit:  60f10de            Status: PASS
```

### criar proposta
```
Teste:   test_caminho_do_dinheiro.py::test_gerar_proposta_devolve_texto
         test_caminho_do_dinheiro.py::test_calcular_orcamento_nao_usa_ia
Commit:  604a207            Status: PASS
```

### converter proposta
```
Teste:   test_caminho_do_dinheiro.py (proposta) · test_fase6.py (oportunidade)
Commit:  604a207            Status: PASS com limitação 2
```

### receber pagamento
```
Teste:   test_caminho_do_dinheiro.py::test_pagamento_ativa_o_plano_do_cliente
         test_caminho_do_dinheiro.py::test_pagamento_repetido_nao_duplica
Commit:  604a207            Status: PASS
Nota:    200 não é sucesso num webhook — o teste inspeciona o corpo.
```

### ativar plano
```
Teste:   test_caminho_do_dinheiro.py::test_pagamento_ativa_o_plano_do_cliente
         test_caminho_do_dinheiro.py::test_assinatura_foi_criada_no_banco
Commit:  604a207            Status: PASS
```

### cancelar assinatura
```
Teste:   test_caminho_do_dinheiro.py::test_cancelar_assinatura_nao_explode
         test_caminho_do_dinheiro.py::test_ver_minha_assinatura_responde
Commit:  604a207            Status: PASS
```

### agenda
```
Teste:   test_fase6.py · test_notificacoes_vivas.py
Commit:  c08a544            Status: PASS
```

### notificações
```
Teste:   test_notificacoes_vivas.py (6)
Commit:  c08a544            Status: PASS
```

### exportar meus dados
```
Teste:   test_backup_exportacao.py (5)
Commit:  c08a544            Status: PASS
Nota:    É o backup do lado do USUÁRIO. O do banco é Portão O.
```

### isolamento entre usuários
```
Mecanismo: app/core/tenant.py — 16 modelos, 2 camadas
Teste:     test_pia.py (23) · test_isolamento_{midia,notificacoes,
           dashboard,analytics_morto}.py
Mutação:   6 mutações, 6 detecções
Commit:    60f10de            Status: PASS
```

---

## 4. Limitações declaradas

Conhecidas, medidas, e nenhuma delas perde dado, dinheiro ou impede trabalhar.

### 1 · Ações fiscais assistidas por IA

> **Aprovado com limitação declarada.** As ações fiscais suportadas por LLM
> permanecem classificadas como **assistivas**. Não são utilizadas para
> executar operações financeiras nem para gerar documentos oficiais. As
> respostas que envolvam cálculos ou valores devem ser explicitamente
> apresentadas como estimativas ou orientações, com indicação para conferência
> na fonte oficial antes de qualquer pagamento ou obrigação legal.

10 ações são respondidas por LLM antes de chegar ao cálculo determinístico
(`agent_hub.py:986`). O risco não é uniforme:

| Grupo | Exemplo | Risco |
|---|---|---|
| repetir constante | DAS R$ 86,05, limite R$ 81.000 | baixo — ancorado no prompt |
| interpretação | explicar regra, quando emitir nota | moderado, conferível |
| **cálculo** | **multa, juros, IRPF** | apresentado como **estimativa** |

```
Mitigação: prompt exige "estimativa" + fonte oficial (D-012)
Teste:     test_fiscal_estimativa.py (6)
Spec:      AUDITORIA_NEXUS/21B_ESPECIFICACOES.md
```

**Reabre quando** o NEXUS emitir DAS, gerar DARF, calcular imposto
automaticamente, preencher declaração ou enviar informação a órgão público.
Aí o erro deixa de ser informação imprecisa e passa a ter consequência
financeira — e as 10 migram para determinístico.

### 2 · Proposta não vira venda sozinha
As peças existem; o elo não. `gerar_proposta` não se liga a `Opportunity`.

O usuário **consegue** fechar a venda: gera a proposta, envia, move a
oportunidade para `fechado_ganho` e registra a transação. Três passos manuais.

**Não bloqueia** porque o piloto mede **valor**, não automação — e pode revelar
que a integração imaginada não é a que o usuário espera.

### 3 · Automação web indisponível
Chromium ausente em produção. A rota responde **503 explícito**
(`AUTOMACAO_WEB_INDISPONIVEL`), não erro obscuro. Não está na jornada dos 12
passos. **Não prometer na oferta.**

### 4 · Duas tabelas isolam por join
`Interaction` e `Opportunity` não têm `user_id` próprio (D-004). Funciona hoje;
é a única exceção à regra de isolamento, declarada em
`test_pia.py::EXCECOES_DECLARADAS`.

---

## Como este documento é atualizado

Item só vira `PASS` com **teste que falha se o passo quebrar** — não com smoke,
não com "rodei e funcionou".

**Nada operacional entra aqui.** Se a resposta for "falta pagar", "falta
configurar" ou "falta a chave", é [`PORTAO_O.md`](PORTAO_O.md).
