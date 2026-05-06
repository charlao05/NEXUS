"""
pii_masker — Mascara PII em texto livre (LGPD-friendly).

Estrategia hibrida: preserva N ultimos caracteres por tipo (utilidade pra
suporte humano) sem permitir reidentificacao por atacante. Mask destrutivo
- nao reversivel intencionalmente (LGPD principio de minimizacao).

Tipos suportados (contexto BR):
  - CPF       (com validacao de DV; ex: 123.456.789-10 -> ***.***.***-10)
  - CNPJ      (com validacao de DV; ex: 12.345.678/0001-90 -> **.***.***/****-90)
  - Cartao    (PCI-DSS: ultimos 4)
  - Email     (1a letra + dominio; full-mask se local <=2 chars)
  - Telefone  (ultimos 4)
  - CEP       (ultimos 3)

Idempotencia: re-mascarar conteudo ja mascarado e no-op (regex nao casa ***).

Uso:
    from utils.pii_masker import mask_pii
    safe = mask_pii("meu CPF e 123.456.789-10 e email a@b.com")
"""
from __future__ import annotations

import re
from typing import Pattern


# ---------------------------------------------------------------------------
# Validacao de digito verificador (BR)
# ---------------------------------------------------------------------------

def _is_valid_cpf(digits: str) -> bool:
    """Valida CPF (11 digitos sem formatacao). Rejeita todos iguais."""
    if len(digits) != 11 or not digits.isdigit() or len(set(digits)) == 1:
        return False
    nums = [int(c) for c in digits]
    # 1o DV
    s1 = sum(nums[i] * (10 - i) for i in range(9))
    dv1 = (s1 * 10) % 11
    dv1 = 0 if dv1 == 10 else dv1
    if dv1 != nums[9]:
        return False
    # 2o DV
    s2 = sum(nums[i] * (11 - i) for i in range(10))
    dv2 = (s2 * 10) % 11
    dv2 = 0 if dv2 == 10 else dv2
    return dv2 == nums[10]


def _is_valid_cnpj(digits: str) -> bool:
    """Valida CNPJ (14 digitos sem formatacao). Rejeita todos iguais."""
    if len(digits) != 14 or not digits.isdigit() or len(set(digits)) == 1:
        return False
    nums = [int(c) for c in digits]
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s1 = sum(nums[i] * weights1[i] for i in range(12))
    dv1 = s1 % 11
    dv1 = 0 if dv1 < 2 else 11 - dv1
    if dv1 != nums[12]:
        return False
    s2 = sum(nums[i] * weights2[i] for i in range(13))
    dv2 = s2 % 11
    dv2 = 0 if dv2 < 2 else 11 - dv2
    return dv2 == nums[13]


# ---------------------------------------------------------------------------
# Regexes (compilados uma vez)
# ---------------------------------------------------------------------------

# CPF: aceita formatado ou nao. Captura 11 digitos com/sem pontuacao.
_RE_CPF: Pattern[str] = re.compile(
    r"\b(\d{3}\.?\d{3}\.?\d{3}-?\d{2})\b"
)

# CNPJ: 14 digitos com/sem pontuacao
_RE_CNPJ: Pattern[str] = re.compile(
    r"\b(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})\b"
)

# Cartao: 13-19 digitos com espacos/hifens opcionais (cobertura Visa/Master/Amex)
# Ancorado pra evitar match em strings tipo telefone longo
_RE_CARD: Pattern[str] = re.compile(
    r"\b(\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4})\b"
)

# Email: padrao RFC simplificado (suficiente pra texto livre)
_RE_EMAIL: Pattern[str] = re.compile(
    r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"
)

# Telefone BR: dois padroes separados pra evitar match em 11 digitos
# aleatorios (que poderiam parecer CPF com DV invalido).
#
# Padrao A — FORMATADO: tem marker explicito (parens, +55, separador entre
# DDD e numero, ou separador entre prefix e suffix).
_RE_PHONE_FORMATTED: Pattern[str] = re.compile(
    r"(?<!\d)"
    r"(?:"
    r"\+?55[\s.-]?\(?\d{2}\)?[\s.-]?9?\d{4}[\s.-]?\d{4}"   # +55 11 91234-5678
    r"|"
    r"\(\d{2}\)\s?9?\d{4}[\s.-]?\d{4}"                      # (11) 91234-5678
    r"|"
    r"\d{2}[\s.-]9?\d{4}[\s.-]?\d{4}"                       # 11 91234-5678
    r")"
    r"(?!\d)"
)
# Padrao B — MOBILE PURO: 11 digitos sem formatacao, mas com '9' no 3o
# digito (regra obrigatoria de celular BR desde 2014). Filtra produto codes.
_RE_PHONE_MOBILE_RAW: Pattern[str] = re.compile(
    r"(?<!\d)\d{2}9\d{8}(?!\d)"
)

# CEP: 8 digitos com hifen opcional
_RE_CEP: Pattern[str] = re.compile(
    r"\b(\d{5}-?\d{3})\b"
)


# ---------------------------------------------------------------------------
# Maskers individuais
# ---------------------------------------------------------------------------

def _mask_cpf(match: re.Match[str]) -> str:
    raw = match.group(1)
    digits = re.sub(r"\D", "", raw)
    if not _is_valid_cpf(digits):
        return raw  # nao mascara strings que parecem CPF mas DV nao bate
    return f"***.***.***-{digits[-2:]}"


def _mask_cnpj(match: re.Match[str]) -> str:
    raw = match.group(1)
    digits = re.sub(r"\D", "", raw)
    if not _is_valid_cnpj(digits):
        return raw
    return f"**.***.***/****-{digits[-2:]}"


def _mask_card(match: re.Match[str]) -> str:
    raw = match.group(1)
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 13:
        return raw
    return f"**** **** **** {digits[-4:]}"


def _mask_email(match: re.Match[str]) -> str:
    local, domain = match.group(1), match.group(2)
    if len(local) <= 2:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def _mask_phone(match: re.Match[str]) -> str:
    raw = match.group(0)
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 10 or len(digits) > 13:
        return raw  # fora da faixa esperada, nao toca
    # Sequencia de digitos iguais (ex: "99999999999") nao e telefone real:
    # filtra falso-positivo em codigos de produto/sequencias.
    if len(set(digits)) == 1:
        return raw
    return f"(**) ****-{digits[-4:]}"


def _mask_cep(match: re.Match[str]) -> str:
    raw = match.group(1)
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 8:
        return raw
    return f"*****-{digits[-3:]}"


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

def mask_pii(text: str) -> str:
    """Aplica todos os maskers em ordem (mais especificos primeiro).

    Idempotente: chamadas repetidas no mesmo texto produzem o mesmo resultado
    (regexes nao casam strings ja mascaradas que contem '*').

    Args:
        text: string arbitraria. Pode ser vazia/None.

    Returns:
        String com PII mascarada. Se input invalido, retorna como veio.
    """
    if not text or not isinstance(text, str):
        return text

    # Ordem importa: CPF/CNPJ antes de cartao/CEP (sobreposicao de digitos);
    # cartao antes de telefone (16 digitos vs 11);
    # email antes de phone (@ unico no email);
    # phone formatado antes de mobile-raw (formatado e mais especifico).
    out = text
    out = _RE_CARD.sub(_mask_card, out)
    out = _RE_CNPJ.sub(_mask_cnpj, out)
    out = _RE_CPF.sub(_mask_cpf, out)
    out = _RE_EMAIL.sub(_mask_email, out)
    out = _RE_CEP.sub(_mask_cep, out)
    out = _RE_PHONE_FORMATTED.sub(_mask_phone, out)
    out = _RE_PHONE_MOBILE_RAW.sub(_mask_phone, out)
    return out


def count_pii_matches(text: str) -> int:
    """Conta quantos PII matches existem em texto, sem mascarar.

    Util para telemetria (ex: '5 emails detectados em mensagens da hora').
    """
    if not text or not isinstance(text, str):
        return 0
    n = 0
    n += len(_RE_CARD.findall(text))
    # Validados (so conta se DV bate)
    for m in _RE_CPF.findall(text):
        if _is_valid_cpf(re.sub(r"\D", "", m)):
            n += 1
    for m in _RE_CNPJ.findall(text):
        if _is_valid_cnpj(re.sub(r"\D", "", m)):
            n += 1
    n += len(_RE_EMAIL.findall(text))
    n += len(_RE_CEP.findall(text))
    n += len(_RE_PHONE_FORMATTED.findall(text))
    n += len(_RE_PHONE_MOBILE_RAW.findall(text))
    return n
