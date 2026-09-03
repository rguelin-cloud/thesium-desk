import sqlite3, json
c = sqlite3.connect('thesium.db')
c.row_factory = sqlite3.Row

print('=== Toutes les theses META creees pendant le cycle 20:46:16 ===')
for r in c.execute("""
    SELECT id, agent_type, conviction_score, proposed_action, thesis_text, created_at
    FROM theses
    WHERE instrument_id = 7
      AND created_at LIKE '2026-05-24 20:46%'
    ORDER BY id
"""):
    d = dict(r)
    text = (d['thesis_text'] or '')[:90]
    print(f"  #{d['id']} {d['agent_type']:<25} conv={d['conviction_score']:.1f} action={d['proposed_action']} | {text}")

print()
print('=== Tous les orders META du cycle 20:46:16 ===')
for r in c.execute("""
    SELECT id, thesis_id, side, quantity, status, created_at
    FROM orders WHERE instrument_id=7
      AND created_at LIKE '2026-05-24 20:46%'
    ORDER BY id
"""):
    print(dict(r))

print()
print('=== Log decisions exit_decisions_log cycle 20260524-204616 META ===')
for r in c.execute("""
    SELECT * FROM exit_decisions_log
    WHERE ticker='META' AND cycle_id='20260524-204616'
"""):
    print(dict(r))
