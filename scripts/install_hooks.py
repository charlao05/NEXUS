"""
install_hooks.py — Instala Git hooks do NEXUS
================================================
Copia os hooks de scripts/hooks/ para .git/hooks/
e garante que são executáveis.

Uso:
    python scripts/install_hooks.py
"""

import shutil
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_SRC = ROOT / "scripts" / "hooks"
HOOKS_DST = ROOT / ".git" / "hooks"


def main():
    if not HOOKS_DST.exists():
        print(f"AVISO: {HOOKS_DST} não existe. Este diretório é um repositório Git?")
        return

    installed = 0
    for hook_file in HOOKS_SRC.iterdir():
        if hook_file.is_file() and not hook_file.name.startswith("."):
            dst = HOOKS_DST / hook_file.name
            shutil.copy2(hook_file, dst)
            # Garante permissão de execução (Unix)
            dst.chmod(dst.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            print(f"  Instalado: {hook_file.name} → .git/hooks/{hook_file.name}")
            installed += 1

    if installed:
        print(f"\n{installed} hook(s) instalado(s) com sucesso.")
        print("Os testes de segurança serão executados antes de cada push.")
    else:
        print("Nenhum hook encontrado em scripts/hooks/")


if __name__ == "__main__":
    main()
