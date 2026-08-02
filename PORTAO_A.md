# Portão A

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
- [ ] converter proposta
- [x] receber pagamento
- [x] ativar plano
- [x] cancelar assinatura
- [x] agenda
- [x] notificações
- [ ] backup

**10 de 12.**

---

## 3. Evidência

### cadastro
```
Teste:   test_auth.py · test_caminho_do_dinheiro.py::pagante
Commit:  604a207
Status:  PASS
```

### login
```
Teste:   test_auth.py · test_atribuicao_consumo.py
Commit:  604a207
Status:  PASS
```

### criar cliente
```
Teste:   test_isolamento_dashboard.py · test_fase6.py::TestCRMServiceMultiTenancy
Commit:  60f10de
Status:  PASS
```

### criar produto
```
Teste:   test_inventory.py
Commit:  60f10de
Status:  PASS
```

### criar proposta
```
Teste:   test_caminho_do_dinheiro.py::test_gerar_proposta_devolve_texto
         test_caminho_do_dinheiro.py::test_calcular_orcamento_nao_usa_ia
Commit:  604a207
Status:  PASS
```

### converter proposta
```
Teste:   nenhum
Commit:  —
Status:  PARCIAL
Motivo:  As peças existem; o elo não. `gerar_proposta` (vendas_agent.py) tem
         zero ligação com `Opportunity`. O pipeline sabe fechar
         (stage="fechado_ganho", crm_routes.py:272) e a venda sabe ser
         registrada (POST /api/crm/transactions) — mas são três passos
         manuais desconectados.
         O usuário CONSEGUE registrar a venda. Não impede trabalhar.
DECISÃO PENDENTE DO DONO: isto bloqueia o Portão A?
```

### receber pagamento
```
Teste:   test_caminho_do_dinheiro.py::test_pagamento_ativa_o_plano_do_cliente
         test_caminho_do_dinheiro.py::test_pagamento_repetido_nao_duplica
Commit:  604a207
Status:  PASS
Nota:    200 não é sucesso num webhook — o teste inspeciona o corpo.
```

### ativar plano
```
Teste:   test_caminho_do_dinheiro.py::test_pagamento_ativa_o_plano_do_cliente
         test_caminho_do_dinheiro.py::test_assinatura_foi_criada_no_banco
Commit:  604a207
Status:  PASS
```

### cancelar assinatura
```
Teste:   test_caminho_do_dinheiro.py::test_cancelar_assinatura_nao_explode
         test_caminho_do_dinheiro.py::test_ver_minha_assinatura_responde
Commit:  604a207
Status:  PASS
```

### agenda
```
Teste:   test_fase6.py · test_notificacoes_vivas.py
Commit:  c08a544
Status:  PASS
```

### notificações
```
Teste:   test_notificacoes_vivas.py (6 testes)
Commit:  c08a544
Status:  PASS
Nota:    Só as 6 regras determinísticas. Ação sugerida e priorização por
         contexto são a Central de Prioridades, e continuam em desenho.
```

### backup
```
Teste:   test_backup_exportacao.py (5 testes)   — metade do usuário
Commit:  c08a544
Status:  BLOQUEADO
Falta:   PITR do Neon — verificação de painel, do dono.
         Perguntas: o plano inclui? qual a retenção em dias?
         Nenhum código prova isso, e fingir que prova seria pior.
```

---

## Fora da engenharia — bloqueia tudo

- [ ] **Render pago** — produção suspensa por inadimplência (E-034).
      Sem isto o Portão A não fecha: nem o PITR se verifica, nem os cinco
      usuários entram.
- [ ] **Stripe live** — chaves `sk_live_` + webhook em modo live.

---

## Isolamento entre usuários

```
Mecanismo: app/core/tenant.py — 16 modelos protegidos, 2 camadas
Teste:     test_pia.py (23) · test_isolamento_{pia,midia,notificacoes,
           dashboard,analytics_morto}.py
Mutação:   6 mutações, 6 detecções
Commit:    60f10de
Status:    PASS
Exceção:   Interaction e Opportunity isolam por join com Client (D-004)
```

---

## Como este documento é atualizado

Item só muda para `PASS` com **teste que falha se o passo quebrar** — não com
smoke, não com "rodei e funcionou". Item sem teste é `BLOQUEADO` ou `PARCIAL`,
nunca `PASS`.

Suíte: **515 testes**. CI: `success`.
