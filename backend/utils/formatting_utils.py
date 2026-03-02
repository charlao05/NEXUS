"""Utilitários para formatação de mensagens em canais de comunicação."""

import re


def clean_markdown(text: str) -> str:
    """Remove formatação Markdown para texto puro legível.

    Remove: **negrito**, *itálico*, __sublinhado__, `código`, # títulos, etc.
    Mantém a estrutura e quebras de linha para melhor apresentação.

    Exemplos:
        "Olá **Charles**!" → "Olá Charles!"
        "**Login**: Faça *login*" → "Login: Faça login"
        "# Título" → "Título:"
    """
    if not text:
        return text

    # Remove **negrito** → texto
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)

    # Remove *itálico* → texto
    text = re.sub(r"\*(.+?)\*", r"\1", text)

    # Remove __sublinhado__ → texto
    text = re.sub(r"__(.+?)__", r"\1", text)

    # Remove _itálico_ → texto
    text = re.sub(r"_(.+?)_", r"\1", text)

    # Remove `código` → texto
    text = re.sub(r"`(.+?)`", r"\1", text)

    # Remove # títulos → Título:
    text = re.sub(r"^#{1,6}\s+(.+?)$", r"\1:", text, flags=re.MULTILINE)

    # Remove > citações mantendo texto
    text = re.sub(r"^>\s+(.+?)$", r"\1", text, flags=re.MULTILINE)

    # Remove [link](url) → link
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", text)

    return text
