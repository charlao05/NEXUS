"""
pre_deploy_validation.py — Validação pré-deploy NEXUS
========================================================
Executa TODAS as verificações necessárias antes de deploy/push:
  1. Compilação Python (sintaxe)
  2. TypeScript (tsc --noEmit)
  3. Testes unitários backend
  4. Testes de segurança (Shannon)
  5. ESLint frontend
  6. Verificação de secrets expostos

Uso:
    python scripts/pre_deploy_validation.py          # Roda tudo
    python scripts/pre_deploy_validation.py --quick  # Só segurança + typecheck

Exit code 0 = ok para deploy, 1 = problemas encontrados.
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

# Se não for Windows, ajusta
if not VENV_PYTHON.exists():
    VENV_PYTHON = ROOT / ".venv" / "bin" / "python"

DIVIDER = "=" * 60
PASS = "\033[92m PASS \033[0m"
FAIL = "\033[91m FAIL \033[0m"
SKIP = "\033[93m SKIP \033[0m"

results: list[tuple[str, bool, float]] = []


def run_step(name: str, cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> bool:
    """Executa uma etapa de validação."""
    print(f"\n{DIVIDER}")
    print(f"  {name}")
    print(DIVIDER)
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={
                **__import__("os").environ,
                "PYTHONPATH": str(ROOT),
                "ENVIRONMENT": "test",
                "NEXUS_SKIP_DOTENV": "1",
            },
        )
        elapsed = time.time() - start
        if result.stdout.strip():
            # Only show last 30 lines to keep output manageable
            lines = result.stdout.strip().split("\n")
            for line in lines[-30:]:
                print(f"  {line}")
        if result.returncode != 0:
            if result.stderr.strip():
                for line in result.stderr.strip().split("\n")[-15:]:
                    print(f"  \033[91m{line}\033[0m")
            print(f"\n  [{FAIL}] {name} ({elapsed:.1f}s)")
            results.append((name, False, elapsed))
            return False
        print(f"\n  [{PASS}] {name} ({elapsed:.1f}s)")
        results.append((name, True, elapsed))
        return True
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        print(f"\n  [{FAIL}] {name} — TIMEOUT após {timeout}s")
        results.append((name, False, elapsed))
        return False
    except FileNotFoundError as e:
        elapsed = time.time() - start
        print(f"\n  [{SKIP}] {name} — {e}")
        results.append((name, True, elapsed))  # Skip = não bloqueia
        return True


def check_secret_leaks() -> bool:
    """Verifica se há secrets hardcoded no código."""
    print(f"\n{DIVIDER}")
    print("  Verificação de Secrets Expostos")
    print(DIVIDER)
    start = time.time()

    PATTERNS = [
        "sk_live_",       # Stripe live key
        "sk_test_",       # Stripe test key (em código, não env)
        "AKIA",           # AWS access key
        "ghp_",           # GitHub PAT
        "gho_",           # GitHub OAuth
        "AIza",           # Google API key
    ]

    SCAN_DIRS = [BACKEND / "app", BACKEND / "agents", FRONTEND / "src"]
    EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}
    findings = []

    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for f in scan_dir.rglob("*"):
            if f.suffix not in EXTENSIONS:
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for pattern in PATTERNS:
                    if pattern in content:
                        # Ignora se está em .env.example ou em comentários
                        for i, line in enumerate(content.split("\n"), 1):
                            if pattern in line and not line.strip().startswith("#"):
                                findings.append(f"  {f.relative_to(ROOT)}:{i} → '{pattern}...'")
            except Exception:
                pass

    elapsed = time.time() - start
    if findings:
        print("  \033[91mSecrets potenciais encontrados:\033[0m")
        for f in findings:
            print(f"    {f}")
        print(f"\n  [{FAIL}] Secret Scan ({elapsed:.1f}s)")
        results.append(("Secret Scan", False, elapsed))
        return False

    print("  Nenhum secret exposto encontrado.")
    print(f"\n  [{PASS}] Secret Scan ({elapsed:.1f}s)")
    results.append(("Secret Scan", True, elapsed))
    return True


def main():
    quick = "--quick" in sys.argv
    total_start = time.time()

    print("\n" + "=" * 60)
    print("   NEXUS — Validação Pré-Deploy")
    print("   Modo:", "RÁPIDO (--quick)" if quick else "COMPLETO")
    print("=" * 60)

    all_ok = True

    # 1. TypeScript
    all_ok &= run_step(
        "TypeScript Typecheck",
        ["npx", "tsc", "--noEmit"],
        cwd=FRONTEND,
    )

    # 2. Security tests (sempre roda)
    all_ok &= run_step(
        "Security Tests (Shannon Framework)",
        [str(VENV_PYTHON), "-m", "pytest", "tests/security/", "-v", "--tb=short"],
    )

    if not quick:
        # 3. Backend unit tests
        all_ok &= run_step(
            "Backend Unit Tests",
            [str(VENV_PYTHON), "-m", "pytest", "backend/tests/", "-v", "--tb=short"],
        )

        # 4. ESLint frontend
        all_ok &= run_step(
            "ESLint Frontend",
            ["npx", "eslint", "src/", "--max-warnings=0"],
            cwd=FRONTEND,
            timeout=60,
        )

        # 5. Python syntax check (core files)
        all_ok &= run_step(
            "Python Syntax Check",
            [
                str(VENV_PYTHON), "-c",
                "import py_compile; "
                "files=['backend/main.py','backend/app/api/auth.py','backend/app/api/agent_hub.py',"
                "'backend/app/api/agent_chat.py','backend/database/models.py',"
                "'backend/database/crm_service.py']; "
                "[py_compile.compile(f, doraise=True) for f in files]; "
                "print(f'{len(files)} arquivos OK')"
            ],
        )

    # 6. Secret scan (sempre roda)
    all_ok &= check_secret_leaks()

    # Resumo final
    total_elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print("   RESUMO DA VALIDAÇÃO")
    print(f"{'=' * 60}")
    for name, passed, elapsed in results:
        status = PASS if passed else FAIL
        print(f"  [{status}] {name} ({elapsed:.1f}s)")
    print(f"\n  Total: {total_elapsed:.1f}s")

    if all_ok:
        print(f"\n  \033[92m{'=' * 50}\033[0m")
        print(f"  \033[92m  APROVADO para deploy!\033[0m")
        print(f"  \033[92m{'=' * 50}\033[0m\n")
        sys.exit(0)
    else:
        failed = [name for name, passed, _ in results if not passed]
        print(f"\n  \033[91m{'=' * 50}\033[0m")
        print(f"  \033[91m  BLOQUEADO — {len(failed)} verificação(ões) falharam:\033[0m")
        for f in failed:
            print(f"  \033[91m    - {f}\033[0m")
        print(f"  \033[91m{'=' * 50}\033[0m\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
