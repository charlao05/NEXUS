# pyright: reportMissingImports=false
"""Create admin account directly using SQLite + bcrypt, no ORM dependency."""
import sqlite3
import os
import sys

# Ensure bcrypt is available
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "nexus.db")
print(f"DB: {DB_PATH}")
print(f"Exists: {os.path.exists(DB_PATH)}")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

email = "appnexxus.app@gmail.com"
password = "Teste1234"

# Check if exists
c.execute("SELECT id, email, plan, role, full_name FROM users WHERE email = ?", (email,))
existing = c.fetchone()

if existing:
    print(f"User exists: id={existing[0]}, plan={existing[2]}, role={existing[3]}, name={existing[4]}")
    # Update to admin
    c.execute("""
        UPDATE users SET 
            role = 'admin',
            plan = 'enterprise',
            full_name = 'Charles Silva',
            status = 'active'
        WHERE email = ?
    """, (email,))
    conn.commit()
    print(">> Updated to admin/enterprise")
else:
    print("User NOT found — creating...")
    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
    trial_end = (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    
    # Get column names from users table
    c.execute("PRAGMA table_info(users)")
    cols = [row[1] for row in c.fetchall()]
    print(f"Table columns: {cols}")
    
    c.execute("""
        INSERT INTO users (email, password_hash, full_name, plan, status, role, 
                          trial_ends_at, last_login, email_verified, lgpd_consent,
                          communication_preference, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        email, pw_hash, "Charles Silva", "enterprise", "active", "admin",
        trial_end, now, 1, 1, "email", now
    ))
    conn.commit()
    print(f">> Created admin: {email} / {password}")

# Verify
c.execute("SELECT id, email, plan, role, full_name, status FROM users WHERE email = ?", (email,))
row = c.fetchone()
print(f"\nVerification: id={row[0]}, email={row[1]}, plan={row[2]}, role={row[3]}, name={row[4]}, status={row[5]}")

conn.close()
print("Done!")
