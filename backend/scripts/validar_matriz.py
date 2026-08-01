#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
validar_matriz.py — detector de deriva da Matriz de Funcionalidades
====================================================================

POR QUE ISTO EXISTE

A Matriz de Funcionalidades (AUDITORIA_NEXUS/21_MATRIZ_FUNCIONALIDADES.md) e a
fonte unica de verdade do produto: dela saem os modulos, os planos, o pricing, a
documentacao e a estrategia de degustacao.

Uma fonte unica de verdade que apodrece e pior que nenhuma, porque as decisoes
continuam sendo tomadas com ela. O dono nomeou esse risco antes de a matriz
existir. Este script e a resposta.

O QUE ELE FAZ

1. RE-MEDE do codigo o que e mensurvel (usa IA? · categoria implementada ·
   rota viva ou morta · endpoint existe? · tem teste?) e FALHA apontando a
   linha da matriz que divergiu do codigo.

2. GERA o bloco de resumo do Doc 21 a partir do CSV. Nenhuma contagem da matriz
   e digitada a mao — foi assim que o "34 das 39 acoes" sobreviveu meses num
   documento (E-037).

O QUE ELE NAO E

NAO e um teste vermelho de proposito. Ele fica VERDE enquanto matriz e codigo
concordam. Um vermelho aqui significa que alguem mudou o codigo sem atualizar a
matriz — ou que a matriz esta errada. Essa e a diferenca entre um alarme que se
olha e um que se ignora (o CI ficou 134 runs vermelho sendo ignorado — E-021).

USO

    python backend/scripts/validar_matriz.py                # valida
    python backend/scripts/validar_matriz.py --resumo       # so imprime o resumo
    python backend/scripts/validar_matriz.py --escrever DOC # injeta o resumo no md

Sai com codigo 1 se houver divergencia.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
CSV_PADRAO = BACKEND / "scripts" / "matriz_funcionalidades.csv"

MARCA_INICIO = "<!-- RESUMO:INICIO -->"
MARCA_FIM = "<!-- RESUMO:FIM -->"


# ==========================================================================
# Leitura do codigo — a fonte contra a qual a matriz e conferida
# ==========================================================================
def _ler(rel: str) -> str:
    p = BACKEND / rel
    if not p.exists():
        return ""
    return io.open(p, encoding="utf-8").read()


def acoes_interceptadas_por_llm() -> set[str]:
    """As acoes que NAO chegam ao codigo deterministico.

    agent_hub.py:986 desvia toda acao presente em ACTION_PROMPTS para o LLM;
    o instance.execute() so roda como fallback quando o LLM levanta excecao.
    Ver AUDITORIA_NEXUS/21B_ESPECIFICACOES.md.
    """
    txt = _ler("app/api/agent_chat.py")
    if "ACTION_PROMPTS" not in txt:
        return set()
    bloco = txt.split("ACTION_PROMPTS: dict[str, str] = {")[1].split("\n}")[0]
    todas = set(re.findall(r'^\s*"([a-z_]+)":', bloco, re.M))
    # list_clients tem leitura deterministica explicita em agent_hub.py:992
    return todas - {"list_clients"}


def routers_montados() -> set[str]:
    """Modulos cujo `router` e de fato incluido no app."""
    txt = _ler("main.py")
    return set(re.findall(r'_include\(\s*["\']([\w.]+)["\']', txt))


def routers_definidos() -> dict[str, list[str]]:
    """{modulo: [nomes de APIRouter definidos]} — para achar router orfao."""
    achados: dict[str, list[str]] = {}
    for p in sorted((BACKEND / "app" / "api").glob("*.py")):
        txt = io.open(p, encoding="utf-8").read()
        nomes = re.findall(r"^(\w+)\s*=\s*APIRouter\(", txt, re.M)
        if nomes:
            achados[f"app.api.{p.stem}"] = nomes
    return achados


def rotas_mortas() -> set[str]:
    """Paths declarados em routers que nunca sao montados."""
    montados = routers_montados()
    mortas: set[str] = set()
    for modulo, nomes in routers_definidos().items():
        txt = _ler(modulo.replace(".", "/") + ".py")
        for nome in nomes:
            if nome == "router" and modulo in montados:
                continue  # o router principal deste modulo esta vivo
            if nome == "router":
                continue  # modulo inteiro nao montado: tratado por _modulo_morto
            prefixo_m = re.search(
                rf'{nome}\s*=\s*APIRouter\([^)]*prefix\s*=\s*["\']([^"\']+)', txt)
            prefixo = prefixo_m.group(1) if prefixo_m else ""
            for m in re.finditer(rf'@{nome}\.(get|post|put|patch|delete)\("([^"]*)"', txt):
                mortas.add(prefixo + m.group(2))
    return mortas


def _decoradores_vivos() -> list[tuple[str, str, str]]:
    """[(METODO, path, modulo)] dos routers montados."""
    achados: list[tuple[str, str, str]] = []
    for modulo in routers_montados():
        txt = _ler(modulo.replace(".", "/") + ".py")
        pm = re.search(r'^router\s*=\s*APIRouter\([^)]*prefix\s*=\s*["\']([^"\']+)',
                       txt, re.M | re.S)
        prefixo = pm.group(1) if pm else ""
        for m in re.finditer(r'@router\.(get|post|put|patch|delete)\("([^"]*)"', txt):
            achados.append((m.group(1).upper(), prefixo + m.group(2), modulo))
    return achados


def paths_vivos() -> set[str]:
    """Paths alcancaveis por HTTP.

    Menos que o numero de decoradores, e isso e correto: 12 paths tem mais de
    um metodo (GET+PUT em /api/auth/me, GET+PUT+DELETE em /api/crm/clients/{id}
    etc.). Medido em 01/08/2026: 144 decoradores -> 130 paths unicos.
    """
    return {p for _, p, _ in _decoradores_vivos()}


def rotas_sombreadas() -> list[str]:
    """(METODO, path) declarados em DOIS modulos — o 2o nunca executa.

    O FastAPI resolve para o primeiro router registrado em main.py. Um path
    duplicado entre modulos nao e erro de sintaxe nem quebra o boot: o codigo
    existe, importa e compila, e simplesmente nunca roda. Ver E-040 — metade do
    checkout de billing.py e inalcancavel por causa disto, e uma correcao de
    cobranca feita la nao teria efeito nenhum.
    """
    por_rota: dict[tuple[str, str], list[str]] = {}
    for metodo, path, modulo in _decoradores_vivos():
        por_rota.setdefault((metodo, path), []).append(modulo)
    ordem = list(routers_montados_em_ordem())
    saida = []
    for (metodo, path), modulos in sorted(por_rota.items()):
        distintos = sorted(set(modulos), key=lambda m: ordem.index(m) if m in ordem else 99)
        if len(distintos) > 1:
            vence, perdem = distintos[0], distintos[1:]
            saida.append(f"{metodo} {path}: executa {vence}; NUNCA executa {', '.join(perdem)}")
    return saida


def routers_montados_em_ordem() -> list[str]:
    """A ordem importa: o FastAPI resolve para o primeiro registrado."""
    return re.findall(r'_include\(\s*["\']([\w.]+)["\']', _ler("main.py"))


def arquivos_de_teste() -> str:
    """Concatena a suite, para conferir se um teste citado existe de fato."""
    partes = []
    for p in sorted((BACKEND / "tests").glob("test_*.py")):
        partes.append(p.name + "\n" + io.open(p, encoding="utf-8").read())
    return "\n".join(partes)


# ==========================================================================
# Validacao — cada regra devolve as divergencias que encontrou
# ==========================================================================
def validar(linhas: list[dict]) -> list[str]:
    erros: list[str] = []
    interceptadas = acoes_interceptadas_por_llm()
    mortas = rotas_mortas()
    vivos = paths_vivos()
    suite = arquivos_de_teste()

    ids = [l["id"] for l in linhas]
    for dup, n in Counter(ids).items():
        if n > 1:
            erros.append(f"id duplicado: {dup} aparece {n}x")

    # --- 0. estrutural: rota declarada em dois modulos --------------------
    # Nao depende da matriz. E um defeito do codigo que a matriz nao deve
    # esconder: o segundo modulo tem codigo que existe e nunca roda.
    for sombra in rotas_sombreadas():
        erros.append(f"[codigo] rota sombreada — {sombra}")

    for l in linhas:
        lid = l["id"]
        acoes = _lista(l.get("acoes_agente"))
        endpoints = _lista(l.get("endpoints"))
        usa_ia = _bool(l.get("usa_ia_runtime"))

        # --- 1. acao interceptada por LLM tem de estar marcada como IA -----
        pegas = [a for a in acoes if a in interceptadas]
        if pegas and not usa_ia:
            erros.append(
                f"{lid}: usa_ia_runtime=false, mas {pegas} esta(o) em "
                f"ACTION_PROMPTS -> agent_hub.py:986 responde por LLM. "
                f"O caminho HTTP real usa IA.")
        if pegas and l.get("implementacao_atual") != "C":
            erros.append(
                f"{lid}: implementacao_atual={l.get('implementacao_atual')}, "
                f"mas {pegas} e interceptada por LLM -> deveria ser C.")

        # --- 2. defeito A->C tem de estar declarado -----------------------
        if l.get("categoria_ideal") == "A" and l.get("implementacao_atual") == "C":
            if not (l.get("defeito") or "").strip():
                erros.append(
                    f"{lid}: Categoria A implementada como C e o campo "
                    f"'defeito' esta vazio. Todo A->C e defeito declarado.")

        # --- 3. determinismo implica custo zero ---------------------------
        if not usa_ia and _float(l.get("custo_por_uso_brl")) != 0.0:
            erros.append(
                f"{lid}: usa_ia_runtime=false mas custo_por_uso_brl="
                f"{l.get('custo_por_uso_brl')}. Sem IA o custo marginal e 0.")
        if usa_ia and _float(l.get("custo_por_uso_brl")) == 0.0:
            erros.append(
                f"{lid}: usa_ia_runtime=true com custo 0. Se consome modelo, "
                f"tem custo — preencha ou corrija a marcacao.")

        # --- 4. endpoints citados precisam existir ------------------------
        for ep in endpoints:
            path = _path(ep)
            if not path:
                continue
            if path in mortas:
                if l.get("estado") not in ("morta", "implementada_nao_exposta"):
                    erros.append(
                        f"{lid}: estado={l.get('estado')} mas o endpoint {path} "
                        f"pertence a um router NUNCA montado. Rota morta nao e "
                        f"vendavel.")
            elif not _casa(path, vivos):
                erros.append(
                    f"{lid}: endpoint {path} nao foi encontrado entre os "
                    f"paths montados. Endpoint inventado ou renomeado.")

        # --- 5. testes citados precisam existir ---------------------------
        for t in _lista(l.get("testes")):
            arq = t.split("::")[0].strip()
            if arq and arq not in suite:
                erros.append(
                    f"{lid}: teste citado '{t}' nao existe na suite.")

        # --- 6. natureza x categoria coerentes ----------------------------
        nat = (l.get("natureza") or "").strip()
        if nat == "IA" and l.get("categoria_ideal") != "C":
            erros.append(
                f"{lid}: natureza=IA mas categoria_ideal="
                f"{l.get('categoria_ideal')}. Se e IA por natureza, o ideal e C.")
        if nat in ("Matematica", "Dados") and l.get("categoria_ideal") == "C":
            erros.append(
                f"{lid}: natureza={nat} com categoria_ideal=C. Se existe "
                f"algoritmo tradicional, IA nao e obrigatoria.")

    return erros


# ==========================================================================
# Resumo — gerado, nunca digitado
# ==========================================================================
def gerar_resumo(linhas: list[dict]) -> str:
    nat = Counter(l.get("natureza", "?") for l in linhas)
    est = Counter(l.get("estado", "?") for l in linhas)

    defeitos_ac = [l for l in linhas
                   if l.get("categoria_ideal") == "A"
                   and l.get("implementacao_atual") == "C"]
    sem_teste = [l for l in linhas
                 if not _lista(l.get("testes"))
                 and l.get("estado") != "morta"]
    vendida_sem_gate = [
        l for l in linhas
        if (l.get("gate_de_plano") or "").strip().lower() in ("nenhum", "")
        and (l.get("pricing_atual") or "").strip().lower()
        not in ("", "nao mencionado", "não mencionado")
        and l.get("estado") != "morta"
    ]
    custo_ia = sum(_float(l.get("custo_por_uso_brl")) for l in linhas
                   if _bool(l.get("usa_ia_runtime")))

    L = []
    A = L.append
    A(f"RESUMO DA MATRIZ — gerado por scripts/validar_matriz.py · nao editar a mao")
    A("")
    A(f"Total de funcionalidades ................ {len(linhas)}")
    A("")
    A("POR NATUREZA          O que isso significa comercialmente")
    for chave, nota in (
        ("Matematica", "diferencial defensavel, custo marginal R$ 0,00"),
        ("Dados", "custo de banco; escala com volume, nao com uso"),
        ("IA", "UNICO grupo que justifica cota por plano"),
        ("Mista", "candidatas naturais a degustacao"),
        ("Integracao externa", "dependem de terceiro — nao prometer sem ressalva"),
    ):
        A(f"  {chave:<20} {nat.get(chave, 0):>3}    {nota}")
    A("")
    A("POR ESTADO")
    for chave, rotulo, nota in (
        ("pronta_vendavel", "Prontas e vendaveis hoje", ""),
        ("implementada_nao_exposta", "Implementadas e NAO expostas", "<- receita parada"),
        ("parcial", "Parciais", ""),
        ("bloqueada", "Bloqueadas", ""),
        ("prometida_nao_implementada", "Prometidas e NAO implementadas", "<- exposicao contratual"),
        ("morta", "Codigo morto", ""),
    ):
        pontos = "." * max(1, 44 - len(rotulo))
        A(f"  {rotulo} {pontos} {est.get(chave, 0):>3}   {nota}")
    A("")
    A("DEFEITOS DERIVADOS DO CRUZAMENTO (ninguem digita estes numeros)")
    A(f"  Categoria A implementada como C ............. {len(defeitos_ac):>3}"
      f"   <- deveria ser calculo, e geracao")
    A(f"  Sem nenhum teste que as valide ............... {len(sem_teste):>3}")
    A(f"  Vendidas no Pricing e sem gate de plano ...... {len(vendida_sem_gate):>3}")
    A("")
    A(f"Custo de IA somando UM uso de cada funcionalidade: R$ {custo_ia:.4f}")
    if defeitos_ac:
        A("")
        A("As A->C, por id: " + ", ".join(sorted(l["id"] for l in defeitos_ac)))
    return "\n".join(L)


# ==========================================================================
# helpers
# ==========================================================================
def _lista(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v).split(";") if x.strip()]


def _bool(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "sim", "yes")


def _float(v) -> float:
    try:
        return float(str(v).replace(",", ".").strip() or 0)
    except ValueError:
        return 0.0


def _path(ep: str) -> str:
    """De 'POST /api/crm/clients (crm_routes.py:156)' extrai '/api/crm/clients'."""
    m = re.search(r"(/[\w/{}.-]*)", ep.split("(")[0])
    return m.group(1).rstrip("/") if m else ""


def _casa(path: str, vivos: set[str]) -> bool:
    """Compara ignorando o nome do parametro: /x/{id} == /x/{user_id}."""
    norm = lambda p: re.sub(r"\{[^}]+\}", "{}", p.rstrip("/"))
    alvo = norm(path)
    return any(norm(v) == alvo for v in vivos)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(CSV_PADRAO))
    ap.add_argument("--resumo", action="store_true", help="so imprime o resumo")
    ap.add_argument("--escrever", metavar="DOC",
                    help="injeta o resumo entre as marcas no markdown")
    args = ap.parse_args()

    caminho = Path(args.csv)
    if not caminho.exists():
        print(f"CSV nao encontrado: {caminho}", file=sys.stderr)
        return 2

    with io.open(caminho, encoding="utf-8", newline="") as fh:
        linhas = list(csv.DictReader(fh))

    resumo = gerar_resumo(linhas)

    if args.escrever:
        doc = Path(args.escrever)
        txt = io.open(doc, encoding="utf-8").read()
        novo = f"{MARCA_INICIO}\n```\n{resumo}\n```\n{MARCA_FIM}"
        if MARCA_INICIO in txt and MARCA_FIM in txt:
            txt = re.sub(re.escape(MARCA_INICIO) + r".*?" + re.escape(MARCA_FIM),
                         novo.replace("\\", "\\\\"), txt, flags=re.S)
            io.open(doc, "w", encoding="utf-8").write(txt)
            print(f"resumo injetado em {doc}")
        else:
            print(f"marcas {MARCA_INICIO}/{MARCA_FIM} ausentes em {doc}",
                  file=sys.stderr)
            return 2

    if args.resumo:
        print(resumo)
        return 0

    print(resumo)
    print()
    erros = validar(linhas)
    if erros:
        print(f"DIVERGENCIAS ENTRE A MATRIZ E O CODIGO: {len(erros)}\n")
        for e in erros:
            print("  x " + e)
        print("\nA matriz e a fonte unica de verdade do produto. Se ela e o "
              "codigo discordam,\numa das duas esta errada — e decidir qual e "
              "trabalho humano, nao deste script.")
        return 1

    print(f"OK — {len(linhas)} funcionalidades conferem com o codigo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
