"""
Fix completo do banco de dados:
1. Detecta qual DB o backend usa (via .env / DATABASE_URL)
2. Adiciona colunas faltantes (role, communication_preference)
3. Cria/promove conta admin
"""
import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Simular o que o main.py faz: carregar .env
backend_dir = Path(__file__).parent.parent
root_dir = backend_dir.parent

# Carregar .env na mesma ordem que main.py
try:
    from dotenv import load_dotenv
    for p in [
        root_dir / '.env.local',
        root_dir / '.env',
        backend_dir / '.env.local',
        backend_dir / '.env',
    ]:
        if p.exists():
            load_dotenv(p, override=True)
            print(f"  Loaded: {p}")
except ImportError:
    print("  dotenv not available, using os.getenv only")

db_url = os.getenv("DATABASE_URL", "")
print(f"\nDATABASE_URL = {db_url!r}")

# Determinar path do DB
if db_url.startswith("sqlite"):
    # Extrair path do sqlite URL
    # sqlite:///./test.db -> ./test.db (relativo ao CWD do backend)
    db_path_str = db_url.replace("sqlite:///", "")
    # Resolver relativo ao backend dir (onde uvicorn roda)
    db_path = (backend_dir / db_path_str).resolve()
elif not db_url:
    db_path = (backend_dir / "data" / "nexus.db").resolve()
else:
    print(f"ERROR: PostgreSQL URL detectada, este script so funciona com SQLite")
    sys.exit(1)

print(f"DB Path: {db_path}")
print(f"Exists: {db_path.exists()}")

if not db_path.exists():
    print(f"\nDB file not found! Creating it...")
    db_path.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# 1. Verificar se a tabela users existe
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
if not cursor.fetchone():
    print("\nTabela 'users' NAO existe! O init_db() precisa rodar primeiro.")
    print("Vou criar a tabela manualmente...")
    # Importar e rodar init_db
    sys.path.insert(0, str(backend_dir))
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    # Reimportar para usar o DB correto
    import importlib
    if 'database.models' in sys.modules:
        del sys.modules['database.models']
    from database.models import init_db
    init_db()
    print("  init_db() executado!")
    # Reconectar
    conn.close()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

# 2. Verificar colunas existentes
cursor.execute("PRAGMA table_info(users)")
columns = {row[1] for row in cursor.fetchall()}
print(f"\nColunas existentes: {sorted(columns)}")

# 3. Adicionar colunas faltantes
missing = []
if 'role' not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'")
    missing.append('role')
if 'communication_preference' not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN communication_preference VARCHAR(20) DEFAULT 'email'")
    missing.append('communication_preference')

if missing:
    conn.commit()
    print(f"Colunas adicionadas: {missing}")
else:
    print("Todas as colunas necessarias ja existem.")

# 4. Contar usuarios
cursor.execute("SELECT COUNT(*) FROM users")
total = cursor.fetchone()[0]
print(f"\nTotal usuarios: {total}")

# 5. Verificar/criar conta admin
email = "charles.rsilva05@gmail.com"
cursor.execute("SELECT id, full_name, role, plan, status FROM users WHERE email = ?", (email,))
row = cursor.fetchone()

if row:
    uid, name, role, plan, status = row
    print(f"\nUsuario encontrado (ID={uid}): name={name}, role={role}, plan={plan}")
    # Promover para admin se necessario
    if role != 'admin' or plan != 'enterprise':
        cursor.execute(
            "UPDATE users SET role='admin', plan='enterprise', status='active' WHERE id=?",
            (uid,)
        )
        conn.commit()
        print("  -> Promovido para admin/enterprise!")
    else:
        print("  -> Ja e admin/enterprise.")
else:
    print(f"\nUsuario {email} NAO encontrado. Criando...")
    try:
        import bcrypt
        pw_hash = bcrypt.hashpw("Teste1234".encode(), bcrypt.gensalt(12)).decode()
    except ImportError:
        # Fallback: usar passlib ou hashlib
        import hashlib
        pw_hash = "$2b$12$" + hashlib.sha256("Teste1234".encode()).hexdigest()[:53]
    
    trial_end = (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("""
        INSERT INTO users (email, password_hash, full_name, plan, status, role, 
                          communication_preference, trial_ends_at, created_at, 
                          updated_at, last_login, email_verified, lgpd_consent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        email, pw_hash, "Charles Silva", "enterprise", "active", "admin",
        "email", trial_end, now, now, now, 1, 1
    ))
    conn.commit()
    new_id = cursor.lastrowid
    print(f"  -> Criado com ID={new_id}, role=admin, plan=enterprise")

# 6. Verificar resultado final
cursor.execute("SELECT id, email, full_name, role, plan FROM users WHERE email = ?", (email,))
final = cursor.fetchone()
print(f"\nResultado final: {final}")

# 7. Listar todos os usuarios (primeiros 5)
cursor.execute("SELECT id, email, plan, role FROM users ORDER BY id LIMIT 5")
print("\nPrimeiros 5 usuarios:")
for r in cursor.fetchall():
    print(f"  ID={r[0]} | {r[1]} | plan={r[2]} | role={r[3]}")

cursor.execute("SELECT COUNT(*) FROM users")
print(f"\nTotal: {cursor.fetchone()[0]} usuarios")

conn.close()
print("\nDone!")
