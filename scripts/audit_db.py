"""Audit read-only do banco SQLite — NÃO modifica nada."""
import sqlite3
import os

def audit_db(path, label):
    if not os.path.exists(path):
        print(f"\n{label}: arquivo não encontrado ({path})")
        return
    size_kb = os.path.getsize(path) / 1024
    print(f"\n{'=' * 70}")
    print(f"{label}: {path} ({size_kb:.0f} KB)")
    print("=" * 70)

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"\nTabelas ({len(tables)}):\n")

    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
        count = cursor.fetchone()[0]
        print(f"  {table:30s} {count:>6} registros")

    # Detalhe das tabelas com dados relevantes
    print("\n--- USERS ---")
    try:
        cursor.execute("SELECT id, email, full_name, plan, role, created_at FROM users ORDER BY id")
        for row in cursor.fetchall():
            print(f"  id={row[0]} | {row[1]} | {row[2]} | plan={row[3]} | role={row[4]} | created={row[5]}")
    except Exception as e:
        print(f"  Erro: {e}")

    print("\n--- TRANSACTIONS ---")
    try:
        cursor.execute("SELECT id, user_id, type, amount, description, category, date FROM transactions ORDER BY id LIMIT 30")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  id={row[0]} | user={row[1]} | {row[2]:8s} | R${row[3]:>10.2f} | {row[4]:<30s} | cat={row[5]} | {row[6]}")
        else:
            print("  (vazio)")
    except Exception as e:
        print(f"  Erro: {e}")

    print("\n--- INVOICES ---")
    try:
        cursor.execute("SELECT id, user_id, client_id, description, amount, status, due_date FROM invoices ORDER BY id LIMIT 20")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  id={row[0]} | user={row[1]} | client={row[2]} | {row[3]:<25s} | R${row[4]:>8.2f} | {row[5]} | due={row[6]}")
        else:
            print("  (vazio)")
    except Exception as e:
        print(f"  Erro: {e}")

    print("\n--- CLIENTS ---")
    try:
        cursor.execute("SELECT id, user_id, name, phone, email, segment, source, is_active FROM clients ORDER BY id LIMIT 20")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  id={row[0]} | user={row[1]} | {row[2]:<20s} | {row[3] or '-':<15s} | {row[4] or '-':<25s} | seg={row[5]} | src={row[6]} | active={row[7]}")
        else:
            print("  (vazio)")
    except Exception as e:
        print(f"  Erro: {e}")

    print("\n--- PRODUCTS ---")
    try:
        cursor.execute("SELECT id, user_id, name, sku, category, current_stock, cost_price, sale_price FROM products ORDER BY id LIMIT 20")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  id={row[0]} | user={row[1]} | {row[2]:<20s} | sku={row[3]} | cat={row[4]} | stock={row[5]} | custo={row[6]} | venda={row[7]}")
        else:
            print("  (vazio)")
    except Exception as e:
        print(f"  Tabela não existe")

    print("\n--- STOCK_MOVEMENTS ---")
    try:
        cursor.execute("SELECT id, user_id, product_id, type, quantity, unit_price, reason FROM stock_movements ORDER BY id LIMIT 20")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  id={row[0]} | user={row[1]} | prod={row[2]} | {row[3]} | qty={row[4]} | price={row[5]} | reason={row[6]}")
        else:
            print("  (vazio)")
    except Exception as e:
        print(f"  Tabela não existe")

    print("\n--- CHAT_MESSAGES (últimas 10) ---")
    try:
        cursor.execute("SELECT id, user_id, agent_id, role, substr(content, 1, 60), created_at FROM chat_messages ORDER BY id DESC LIMIT 10")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  id={row[0]} | user={row[1]} | agent={row[2]} | {row[3]} | '{row[4]}...' | {row[5]}")
        else:
            print("  (vazio)")
    except Exception as e:
        print(f"  Erro: {e}")

    print("\n--- APPOINTMENTS ---")
    try:
        cursor.execute("SELECT id, user_id, title, scheduled_at, status FROM appointments ORDER BY id LIMIT 10")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  id={row[0]} | user={row[1]} | {row[2]:<30s} | {row[3]} | {row[4]}")
        else:
            print("  (vazio)")
    except Exception as e:
        print(f"  Erro: {e}")

    print("\n--- ACTIVITY_LOGS (últimos 10) ---")
    try:
        cursor.execute("SELECT id, user_id, action, substr(details, 1, 60), created_at FROM activity_logs ORDER BY id DESC LIMIT 10")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  id={row[0]} | user={row[1]} | {row[2]:<20s} | '{row[3]}' | {row[4]}")
        else:
            print("  (vazio)")
    except Exception as e:
        print(f"  Erro: {e}")

    conn.close()


if __name__ == "__main__":
    audit_db("backend/test.db", "BANCO PRINCIPAL (test.db)")
    audit_db("backend/data/nexus.db", "BANCO SECUNDÁRIO (nexus.db)")
