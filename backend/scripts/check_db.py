# pyright: reportMissingImports=false
import sqlite3
conn = sqlite3.connect('data/nexus.db')
c = conn.cursor()

# Search for Charles
c.execute("SELECT email, plan, role, full_name FROM users WHERE email LIKE '%charles%' OR email LIKE '%rsilva%'")
rows = c.fetchall()
print(f"Charles search: {len(rows)} results")
for r in rows:
    print(f"  {r}")

# Total count
c.execute("SELECT COUNT(*) FROM users")
print(f"Total users: {c.fetchone()[0]}")

# List all emails
c.execute("SELECT email FROM users ORDER BY rowid DESC LIMIT 5")
print("Last 5 users:")
for r in c.fetchall():
    print(f"  {r[0]}")

conn.close()
