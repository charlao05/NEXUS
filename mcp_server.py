"""
NEXUS — MCP Server de Ferramentas Internas
============================================
Expõe tools atômicas e read-only para o agente Copilot operar o projeto
com autonomia total: rodar testes, checar saúde, consultar DB, lint, etc.

Protocolo: stdio (JSON-RPC via stdin/stdout)
Registrado em: .vscode/mcp.json → "nexus-dev"

Importante:
  - NÃO escrever em stdout (corrompe JSON-RPC). Usar stderr/logging.
  - Tools devem ser focadas e retornar strings descritivas.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

# Configurar logging em stderr (stdout é reservado para JSON-RPC)
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[nexus-mcp] %(levelname)s %(message)s",
)
logger = logging.getLogger("nexus-mcp")

# ── Paths ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.resolve()
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DB_PATH = PROJECT_ROOT / "backend" / "test.db"
LOG_FILE = PROJECT_ROOT / "logs" / "automation.log"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"

# Fallback Python
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

# ── Importar FastMCP ─────────────────────────────────────────────────
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    logger.error(
        "Pacote 'mcp' não encontrado. Instale com: pip install mcp[cli]\n"
        "O servidor MCP não pode iniciar sem essa dependência."
    )
    sys.exit(1)

mcp = FastMCP("NEXUS Dev Tools")


# ══════════════════════════════════════════════════════════════════════
# TOOLS — Cada @mcp.tool() vira uma ferramenta disponível no Chat
# ══════════════════════════════════════════════════════════════════════


@mcp.tool()
def health_check() -> str:
    """Verifica se o backend NEXUS está rodando e o banco está conectado.
    Faz GET http://127.0.0.1:8000/health e retorna o resultado."""
    try:
        import urllib.request

        req = urllib.request.Request("http://127.0.0.1:8000/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            status = data.get("status", "unknown")
            db = data.get("database", "unknown")
            redis = data.get("redis", "unknown")
            return f"Backend: {status} | Database: {db} | Redis: {redis}"
    except Exception as e:
        return f"Backend OFFLINE ou inacessível: {e}"


@mcp.tool()
def run_tests(filter: str = "", verbose: bool = False) -> str:
    """Executa pytest no projeto NEXUS e retorna o resultado.

    Args:
        filter: Filtro de testes (ex: 'test_auth', 'test_freemium', '-k login').
                Vazio = roda todos os testes.
        verbose: Se True, usa -v para output detalhado.
    """
    cmd = [PYTHON, "-m", "pytest"]
    if verbose:
        cmd.append("-v")
    if filter:
        if filter.startswith("-"):
            cmd.extend(filter.split())
        else:
            cmd.extend(["-k", filter])
    cmd.append("--tb=short")
    cmd.append("--no-header")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        output = result.stdout + result.stderr
        # Truncar se muito longo
        if len(output) > 8000:
            output = output[:4000] + "\n\n... [truncado] ...\n\n" + output[-3000:]
        return output or "(sem output)"
    except subprocess.TimeoutExpired:
        return "TIMEOUT: testes excederam 120s"
    except Exception as e:
        return f"Erro ao rodar pytest: {e}"


@mcp.tool()
def lint_backend(fix: bool = False) -> str:
    """Roda Ruff (linter/formatter) no código Python do backend.

    Args:
        fix: Se True, aplica correções automáticas (--fix).
    """
    cmd = [PYTHON, "-m", "ruff", "check", "backend/"]
    if fix:
        cmd.append("--fix")
    cmd.append("--output-format=concise")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = (result.stdout + result.stderr).strip()
        if not output:
            return "✅ Nenhum problema encontrado pelo Ruff"
        if len(output) > 5000:
            output = output[:5000] + "\n... [truncado]"
        return output
    except FileNotFoundError:
        return "Ruff não instalado. Instale com: pip install ruff"
    except Exception as e:
        return f"Erro ao rodar ruff: {e}"


@mcp.tool()
def typecheck_frontend() -> str:
    """Roda tsc --noEmit no frontend para verificar erros TypeScript."""
    cmd = ["npx", "tsc", "--noEmit", "--pretty"]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(FRONTEND_DIR),
            capture_output=True,
            text=True,
            timeout=60,
            shell=True,
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode == 0:
            return "✅ TypeScript: zero erros"
        if len(output) > 5000:
            output = output[:5000] + "\n... [truncado]"
        return output or "Erros de TypeScript (sem output detalhado)"
    except Exception as e:
        return f"Erro ao rodar tsc: {e}"


@mcp.tool()
def db_stats() -> str:
    """Retorna estatísticas do banco SQLite do NEXUS (read-only).
    Contagem de users, clients, invoices, chat_messages, subscriptions."""
    if not DB_PATH.exists():
        return f"Banco não encontrado em {DB_PATH}"

    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cursor = conn.cursor()

        tables = {
            "users": "SELECT count(*) FROM users",
            "clients": "SELECT count(*) FROM clients",
            "invoices": "SELECT count(*) FROM invoices",
            "chat_messages": "SELECT count(*) FROM chat_messages",
            "subscriptions": "SELECT count(*) FROM subscriptions",
        }

        lines = [f"📊 DB: {DB_PATH.name} ({DB_PATH.stat().st_size // 1024}KB)"]
        for name, query in tables.items():
            try:
                cursor.execute(query)
                count = cursor.fetchone()[0]
                lines.append(f"  {name}: {count}")
            except sqlite3.OperationalError:
                lines.append(f"  {name}: (tabela não existe)")

        # Último usuário criado
        try:
            cursor.execute(
                "SELECT email, plan, role, created_at FROM users ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                lines.append(f"\n  Último user: {row[0]} (plan={row[1]}, role={row[2]})")
        except sqlite3.OperationalError:
            pass

        conn.close()
        return "\n".join(lines)
    except Exception as e:
        return f"Erro ao consultar DB: {e}"


@mcp.tool()
def db_query(sql: str) -> str:
    """Executa uma query SQL read-only no banco SQLite do NEXUS.
    Apenas SELECT é permitido — qualquer tentativa de escrita é bloqueada.

    Args:
        sql: Query SQL (apenas SELECT).
    """
    # Segurança: bloquear escrita
    normalized = sql.strip().upper()
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "ATTACH"]
    for word in forbidden:
        if word in normalized:
            return f"❌ Bloqueado: queries de escrita não são permitidas ({word})"

    if not DB_PATH.exists():
        return f"Banco não encontrado em {DB_PATH}"

    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(50)  # Limitar a 50 rows
        conn.close()

        if not rows:
            return "Nenhum resultado"

        # Formatar como tabela
        lines = [" | ".join(columns)]
        lines.append("-" * len(lines[0]))
        for row in rows:
            lines.append(" | ".join(str(v) for v in row))

        result = "\n".join(lines)
        if len(result) > 5000:
            result = result[:5000] + "\n... [truncado, 50 rows max]"
        return result
    except Exception as e:
        return f"Erro SQL: {e}"


@mcp.tool()
def tail_logs(lines: int = 50) -> str:
    """Retorna as últimas N linhas do log de automação do NEXUS.

    Args:
        lines: Número de linhas a retornar (padrão: 50, máximo: 200).
    """
    lines = min(max(lines, 1), 200)

    if not LOG_FILE.exists():
        return f"Arquivo de log não encontrado: {LOG_FILE}"

    try:
        content = LOG_FILE.read_text(encoding="utf-8", errors="replace")
        all_lines = content.splitlines()
        tail = all_lines[-lines:]
        return "\n".join(tail) or "(log vazio)"
    except Exception as e:
        return f"Erro ao ler logs: {e}"


@mcp.tool()
def list_agents() -> str:
    """Lista todos os agentes IA disponíveis no NEXUS com seus arquivos."""
    agents_dir = BACKEND_DIR / "agents"
    if not agents_dir.exists():
        return "Diretório de agentes não encontrado"

    lines = ["🤖 Agentes NEXUS:"]
    for f in sorted(agents_dir.glob("*.py")):
        if f.name.startswith("_"):
            continue
        # Extrair primeira docstring ou class name
        content = f.read_text(encoding="utf-8", errors="replace")
        desc = ""
        for line in content.splitlines():
            if '"""' in line or "'''" in line:
                desc = line.strip().strip("\"'").strip()
                break
            if "class " in line:
                desc = line.strip()
                break
        lines.append(f"  📁 {f.name} — {desc[:80]}")

    return "\n".join(lines)


@mcp.tool()
def list_routes() -> str:
    """Lista todas as rotas/endpoints registrados na API FastAPI do NEXUS."""
    try:
        import urllib.request

        req = urllib.request.Request("http://127.0.0.1:8000/openapi.json", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            spec = json.loads(resp.read().decode())
            paths = spec.get("paths", {})

            lines = [f"🌐 {len(paths)} rotas registradas:"]
            for path, methods in sorted(paths.items()):
                method_list = ", ".join(m.upper() for m in methods if m != "options")
                summary = ""
                for m in methods.values():
                    if isinstance(m, dict):
                        summary = m.get("summary", "")
                        break
                lines.append(f"  {method_list:8s} {path}  {summary}")

            return "\n".join(lines)
    except Exception as e:
        return f"Erro ao listar rotas (backend rodando?): {e}"


@mcp.tool()
def project_overview() -> str:
    """Retorna uma visão geral do projeto NEXUS: estrutura, stack, agentes, páginas."""
    overview = []

    # Backend agents
    agents_dir = BACKEND_DIR / "agents"
    agents = [f.stem for f in agents_dir.glob("*.py") if not f.name.startswith("_")] if agents_dir.exists() else []

    # Backend API routes
    api_dir = BACKEND_DIR / "app" / "api"
    apis = [f.stem for f in api_dir.glob("*.py") if not f.name.startswith("_")] if api_dir.exists() else []

    # Frontend pages
    pages_dir = FRONTEND_DIR / "src" / "pages"
    pages = [f.stem for f in pages_dir.glob("*.tsx")] if pages_dir.exists() else []

    # Frontend components
    comps_dir = FRONTEND_DIR / "src" / "components"
    components = [f.stem for f in comps_dir.glob("*.tsx")] if comps_dir.exists() else []

    overview.append("═══ NEXUS — Visão Geral ═══\n")
    overview.append("Stack:")
    overview.append("  Backend: FastAPI + SQLAlchemy + SQLite/PostgreSQL + OpenAI")
    overview.append("  Frontend: React 18 + TypeScript + Vite + Tailwind CSS")
    overview.append("  Auth: JWT (bcrypt) + Google OAuth")
    overview.append("  Payments: Stripe")
    overview.append("  Browser: Playwright")
    overview.append(f"\n🤖 Agentes ({len(agents)}):")
    for a in sorted(agents):
        overview.append(f"   {a}")
    overview.append(f"\n🌐 API Routers ({len(apis)}):")
    for a in sorted(apis):
        overview.append(f"   {a}")
    overview.append(f"\n📄 Páginas ({len(pages)}):")
    for p in sorted(pages):
        overview.append(f"   {p}")
    overview.append(f"\n🧩 Componentes ({len(components)}):")
    for c in sorted(components):
        overview.append(f"   {c}")

    # DB status
    if DB_PATH.exists():
        overview.append(f"\n💾 DB: {DB_PATH} ({DB_PATH.stat().st_size // 1024}KB)")

    return "\n".join(overview)


@mcp.tool()
def test_login(email: str = "charles.rsilva05@gmail.com", password: str = "Admin@123") -> str:
    """Testa login no backend NEXUS e retorna resultado (plan, uid, token status).

    Args:
        email: Email para login.
        password: Senha para login.
    """
    try:
        import urllib.request

        body = json.dumps({"email": email, "password": password}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/auth/login",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            token = data.get("access_token", "")
            return (
                f"✅ Login OK\n"
                f"  plan: {data.get('plan')}\n"
                f"  user_id: {data.get('user_id')}\n"
                f"  email: {data.get('email')}\n"
                f"  token: {token[:30]}... ({len(token)} chars)"
            )
    except Exception as e:
        return f"❌ Login falhou: {e}"


@mcp.tool()
def frontend_lint() -> str:
    """Roda ESLint no código frontend do NEXUS."""
    cmd = ["npx", "eslint", "src", "--ext", "ts,tsx", "--max-warnings", "0", "--format", "compact"]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(FRONTEND_DIR),
            capture_output=True,
            text=True,
            timeout=60,
            shell=True,
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode == 0:
            return "✅ ESLint: zero warnings/erros"
        if len(output) > 5000:
            output = output[:5000] + "\n... [truncado]"
        return output or "ESLint encontrou problemas"
    except Exception as e:
        return f"Erro ao rodar ESLint: {e}"


# ══════════════════════════════════════════════════════════════════════
# RESOURCES — Contexto estático disponível para o agente
# ══════════════════════════════════════════════════════════════════════


@mcp.resource("nexus://env-config")
def get_env_config() -> str:
    """Retorna variáveis de ambiente do NEXUS (sem valores sensíveis)."""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return ".env não encontrado"

    lines = ["═══ NEXUS .env (keys only) ═══"]
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key = line.split("=", 1)[0]
            # Mascarar valor
            lines.append(f"  {key}=***")
    return "\n".join(lines)


@mcp.resource("nexus://db-schema")
def get_db_schema() -> str:
    """Retorna o schema completo do banco SQLite do NEXUS."""
    if not DB_PATH.exists():
        return "DB não encontrado"

    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        conn.close()

        lines = ["═══ NEXUS DB Schema ═══"]
        for (sql,) in tables:
            if sql:
                lines.append(f"\n{sql};")
        return "\n".join(lines)
    except Exception as e:
        return f"Erro: {e}"


# ══════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("Iniciando NEXUS MCP Server (stdio)...")
    mcp.run()
