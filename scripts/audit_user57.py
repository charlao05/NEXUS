"""Audit: dados do user 57 (admin real) — READ-ONLY"""
import sqlite3

conn = sqlite3.connect("file:backend/test.db?mode=ro", uri=True)
c = conn.cursor()

print("=== CLIENTS DO USER 57 (admin) ===")
for r in c.execute("SELECT id, name, phone, email, segment, source FROM clients WHERE user_id=57"):
    print(f"  id={r[0]} | {r[1]} | {r[2]} | {r[3]} | seg={r[4]} | src={r[5]}")

print("\n=== TRANSACTIONS DO USER 57 ===")
for r in c.execute("SELECT id, type, amount, description, category, date FROM transactions WHERE user_id=57"):
    print(f"  id={r[0]} | {r[1]} | R${r[2]:.2f} | {r[3]} | cat={r[4]} | {r[5]}")

print("\n=== INTERACTIONS DO USER 57 ===")
c.execute("PRAGMA table_info(interactions)")
cols = [col[1] for col in c.fetchall()]
print(f"  Colunas: {cols}")
# interactions linked via client_id, not user_id
for r in c.execute("SELECT * FROM interactions WHERE client_id IN (SELECT id FROM clients WHERE user_id=57)"):
    print(f"  {r}")

print("\n=== CHAT_MESSAGES DO USER 57 (total) ===")
c.execute("SELECT COUNT(*) FROM chat_messages WHERE user_id=57")
print(f"  Total: {c.fetchone()[0]} mensagens")

print("\n=== CLIENTS RESTANTES (id > 20) ===")
for r in c.execute("SELECT id, user_id, name, email, segment FROM clients WHERE id > 20"):
    print(f"  id={r[0]} | user={r[1]} | {r[2]} | {r[3]} | seg={r[4]}")

print("\n=== RESUMO POR CLASSIFICAÇÃO ===")
# Users reais vs teste
c.execute("SELECT COUNT(*) FROM users WHERE email NOT LIKE '%@test.com' AND email NOT LIKE '%@nexus.com' AND email NOT LIKE '%@nexus-test.com' AND email NOT LIKE '%@nexus.dev' AND email NOT LIKE '%@anonimizado.nexus' AND email NOT LIKE '%@example.com'")
real_users = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM users")
total_users = c.fetchone()[0]
print(f"  Users REAIS: {real_users} / {total_users}")

print("\n  Users que parecem reais:")
for r in c.execute("""SELECT id, email, full_name, plan, role FROM users 
    WHERE email NOT LIKE '%@test.com' 
    AND email NOT LIKE '%@nexus.com' 
    AND email NOT LIKE '%@nexus-test.com'
    AND email NOT LIKE '%@nexus.dev'
    AND email NOT LIKE '%@anonimizado.nexus'
    AND email NOT LIKE '%@example.com'
    AND email NOT LIKE '%@t.com'"""):
    print(f"    id={r[0]} | {r[1]} | {r[2]} | plan={r[3]} | role={r[4]}")

# Dashboard simula admin vendo tudo ou só user_id?
print("\n=== VERIFICAR: O DASHBOARD FILTRA POR USER_ID? ===")
c.execute("SELECT user_id, COUNT(*) as cnt FROM transactions GROUP BY user_id")
for r in c.fetchall():
    print(f"  user_id={r[0]}: {r[1]} transações")

c.execute("SELECT user_id, COUNT(*) as cnt FROM clients GROUP BY user_id ORDER BY cnt DESC LIMIT 10")
print("\n  Top 10 user_id com mais clientes:")
for r in c.fetchall():
    print(f"    user_id={r[0]}: {r[1]} clientes")

conn.close()
