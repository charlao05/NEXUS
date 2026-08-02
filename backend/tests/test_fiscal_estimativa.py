# pyright: reportMissingImports=false
# -*- coding: utf-8 -*-
"""
Numero fiscal calculado por IA se apresenta como ESTIMATIVA (D-012)
====================================================================

O CONTEXTO

10 acoes fiscais sao interceptadas em agent_hub.py:986 e respondidas pelo LLM
antes de chegar ao codigo deterministico (E-036). Isso e divida arquitetural
declarada — o principio 3 de ARCH_PRINCIPLES.md — e NAO bloqueia o piloto.

Mas o risco nao e igual em todas elas. O dono separou em tres grupos:

  1. repetir constante   limite MEI, valor do DAS       risco baixo (ancorado)
  2. interpretacao       explicar regra, quando emitir  moderado, conferivel
  3. CALCULO             multa, juros, IRPF             🔴 o perigoso

O grupo 3 e perigoso por um motivo especifico:

    "pode parecer extremamente convincente e ainda assim estar errada.
     Nao por ma intencao do modelo, mas porque ele nao foi feito para ser
     um motor matematico deterministico."

A CONDICAO QUE ISSO IMPOE (D-012)

Nao bloquear o piloto — mas tambem nao deixar essas respostas parecerem
oficiais. Numero que a IA CALCULOU se apresenta como estimativa, com a fonte
oficial para conferir antes de pagar ou declarar.

Nao exige refatoracao. Muda como a resposta se apresenta.

O QUE ESTE ARQUIVO TRAVA

A instrucao no prompt. A REDACAO do modelo nao e testavel sem chamar a OpenAI —
e um teste que dependesse da rede seria pior que nenhum. O que se garante aqui
e que a instrucao esta la, e que o enquadramento perigoso nao voltou.

    cd backend && pytest tests/test_fiscal_estimativa.py -v
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

_PROMPTS = io.open(BACKEND / "app/api/agent_chat.py", encoding="utf-8").read()


def test_o_prompt_manda_apresentar_calculo_como_estimativa():
    """A instrucao central do D-012."""
    assert "ESTIMATIVA" in _PROMPTS, (
        "o prompt fiscal deixou de mandar apresentar calculo como estimativa. "
        "Multa, juros e IRPF calculados por LLM voltariam a parecer valor "
        "oficial (D-012).")
    assert "VALOR QUE VOCÊ CALCULOU" in _PROMPTS, (
        "sumiu a distincao entre valor FIXO (pode afirmar) e valor CALCULADO "
        "(estimativa). Sem ela a regra vira decoracao.")


def test_o_prompt_manda_conferir_na_fonte_oficial():
    """Estimativa sem para-onde-ir nao protege ninguem."""
    for fonte in ("Portal do Simples Nacional", "e-CAC"):
        assert fonte in _PROMPTS, (
            f"o prompt deixou de indicar '{fonte}' como fonte de conferencia. "
            "O usuario precisa saber ONDE confirmar antes de pagar.")
    assert "antes de emitir a guia" in _PROMPTS or "ANTES de pagar" in _PROMPTS


def test_o_prompt_nao_anuncia_multa_como_informacao_real():
    """REGRESSAO do enquadramento que causava o problema.

    O bloco se chamava `MULTAS (informação real)`. Chamar de "informacao real"
    o insumo de um CALCULO convida o modelo a apresentar o RESULTADO como fato.
    A regra e real; o valor calculado a partir dela nao e.
    """
    assert "MULTAS (informação real)" not in _PROMPTS, (
        "voltou o enquadramento `MULTAS (informação real)`. A REGRA e oficial; "
        "o VALOR calculado a partir dela e estimativa.")


def test_o_prompt_declara_que_o_agente_nao_executa_ato_fiscal():
    """O limite que mantem isto como limitacao declarada e nao como bloqueio.

    Enquanto o NEXUS so ORIENTA, erro de calculo e informacao imprecisa que o
    usuario confere no portal. No dia em que ele emitir DAS, gerar DARF ou
    declarar, o erro passa a ter consequencia financeira — e ai estas 10 acoes
    migram para deterministico (gatilho do D-012).
    """
    baixo = _PROMPTS.lower()
    assert "não emite guia" in baixo or "nao emite guia" in baixo, (
        "o prompt deixou de declarar que o agente NAO executa ato fiscal. "
        "Esse limite e o que sustenta a decisao de nao bloquear o piloto.")
    for proibido in ("não gera DARF", "não declara"):
        assert proibido.lower() in baixo, f"sumiu do prompt: {proibido}"


def test_os_valores_fixos_continuam_afirmaveis():
    """Contraprova: se a regra fosse "tudo e estimativa", o produto-joia
    perderia a razao de existir. Constante da lei se afirma."""
    assert "86,05" in _PROMPTS, "o DAS de servicos sumiu do prompt"
    assert "81.000" in _PROMPTS, "o limite MEI sumiu do prompt"
    assert "VALOR FIXO" in _PROMPTS, (
        "sumiu a autorizacao explicita de afirmar valor fixo — sem ela o "
        "modelo passa a hedgear ate o que e constante da lei")


def test_as_constantes_do_prompt_batem_com_as_do_codigo():
    """Duas fontes de verdade fiscal continuam existindo (E-036).

    Enquanto a divida nao for paga, pelo menos elas nao podem divergir em
    silencio: quando o salario minimo de 2027 sair, quem atualizar so uma das
    duas quebra aqui.
    """
    from agents.contabilidade_agent import DAS_VALORES_2026, LIMITE_ANUAL_MEI

    for atividade, valor in DAS_VALORES_2026.items():
        esperado = f"{valor:.2f}".replace(".", ",")
        assert esperado in _PROMPTS, (
            f"o DAS de {atividade} vale R$ {esperado} no codigo "
            f"(contabilidade_agent.py) e NAO aparece no prompt fiscal. "
            "As duas fontes divergiram.")

    limite = f"{LIMITE_ANUAL_MEI:,.0f}".replace(",", ".")
    assert limite in _PROMPTS, (
        f"o limite MEI e {limite} no codigo e nao aparece no prompt")
