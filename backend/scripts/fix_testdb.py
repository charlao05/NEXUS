# pyright: reportMissingImports=false
"""Fix test.db: add missing columns and create admin account."""
import sqlite3
import sys
import os

# Path absoluto para test.db (o banco que o backend realmente usa)
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test.db")
print(f"DB path: {db_path}")
print(f"Exists: {os.path.exists(db_path)}")

conn = sqlite3.connect(db_path)
c = conn.cursor()

# 1. Adicionar colunas faltantes
for col, default in [("role", "user"), ("communication_preference", "email")]:
    try:
        c.execute(f"ALTER TABLE users ADD COLUMN {col} VARCHAR(20) DEFAULT '{default}'")
        conn.commit()
        print(f"  + Added column: {col}")
    except Exception as e:
        if "duplicate" in str(e).lower():
            print(f"  = Column {col} already exists")
        else:
            print(f"  ! Column {col}: {e}")

# 2. Verificar/criar conta admin
row = c.execute(
    "SELECT id, email, plan, role, full_name FROM users WHERE email=?",
    ("charles.rsilva05@gmail.com",)
).fetchone()

if row:
    print(f"  Charles exists: id={row[0]}, plan={row[2]}, role={row[3]}, name={row[4]}")
    c.execute(
        "UPDATE users SET role='admin', plan='enterprise', full_name='Charles Silva' WHERE email=?",
        ("charles.rsilva05@gmail.com",)
    )
    conn.commit()
    print("  >> Updated to admin/enterprise/Charles Silva")
else:
    print("  Charles NOT found - creating...")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import bcrypt
    from datetime import datetime, timedelta, timezone
    pw = bcrypt.hashpw(b"Teste1234", bcrypt.gensalt(12)).decode("utf-8")
    now = datetime.now(timezone.utc).isoformat()
    trial = (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat()
    c.execute(
        """INSERT INTO users 
           (email, password_hash, full_name, plan, status, role, communication_preference,
            trial_ends_at, email_verified, lgpd_consent, created_at, updated_at, last_login)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("charles.rsilva05@gmail.com", pw, "Charles Silva", "enterprise", "active",
         "admin", "email", trial, 1, 1, now, now, now)
    )
    conn.commit()
    print(f"  >> Created admin (id={c.lastrowid})")

# 3. Verificar resultado final
cols = [i[1] for i in c.execute("PRAGMA table_info(users)").fetchall()]
total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
admin = c.execute(
    "SELECT id, email, plan, role, full_name FROM users WHERE email=?",
    ("charles.rsilva05@gmail.com",)
).fetchone()
print(f"\n  Total users: {total}")
print(f"  Columns: {cols}")
print(f"  Admin: {admin}")

conn.close()
print("\nDONE - test.db fixed!")
