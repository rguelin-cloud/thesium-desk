import sqlite3
c = sqlite3.connect('thesium.db')
c.row_factory = sqlite3.Row

# Recup l'ordre META rejeté pour voir sa thesis source
oid = 164
row = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
if row:
    print('=== Order #164 ===')
    for k in row.keys():
        print(f'  {k} = {row[k]}')
    tid = row['thesis_id']
    print()
    print(f'=== Thesis source #{tid} ===')
    t = c.execute("SELECT * FROM theses WHERE id=?", (tid,)).fetchone()
    if t:
        for k in t.keys():
            print(f'  {k} = {t[k]}')

# Voir le contexte : les 9 fills META d'avant
print()
print('=== Historique META orders (filled+rejected) ===')
for r in c.execute("""
    SELECT o.id, o.side, o.quantity, o.status, o.created_at, t.agent_type, t.thesis_text
    FROM orders o
    JOIN instruments i ON o.instrument_id=i.id
    LEFT JOIN theses t ON o.thesis_id=t.id
    WHERE i.ticker='META' AND o.status IN ('filled','rejected','executed')
    ORDER BY o.id DESC LIMIT 5
"""):
    d = dict(r)
    text = (d['thesis_text'] or '')[:80]
    print(f"  #{d['id']} {d['side']} qty={d['quantity']} st={d['status']} agent={d['agent_type']} | {text}")

# Voir le cycle_reconciliation_log pour ce cycle
print()
print('=== Cycle reconciliation log (last 3 rows) ===')
for r in c.execute("PRAGMA table_info(cycle_reconciliation_log)"):
    print(r)
print()
for r in c.execute("SELECT * FROM cycle_reconciliation_log ORDER BY id DESC LIMIT 3"):
    print(dict(r))
