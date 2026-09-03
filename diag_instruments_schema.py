# -*- coding: utf-8 -*-
"""Verifie le schema de la table instruments pour le JOIN avec theses."""
import sqlite3
from pathlib import Path

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")

conn = sqlite3.connect(str(DB), timeout=10)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 80)
print("TABLE instruments")
print("=" * 80)
cur.execute("PRAGMA table_info(instruments)")
cols = cur.fetchall()
for c in cols:
    print(f"  {c['name']:<25} {c['type']:<15} default={c['dflt_value']}")

print("\nEchantillon (10 premiers):")
cur.execute("SELECT * FROM instruments LIMIT 10")
for r in cur.fetchall():
    print(" ", dict(r))

print("\nCount total:")
cur.execute("SELECT COUNT(*) FROM instruments")
print(" ", cur.fetchone()[0])

# Test JOIN reel pour top-5 theses recentes
print("\n" + "=" * 80)
print("TEST JOIN theses + instruments (top-5 conviction recentes)")
print("=" * 80)
try:
    cur.execute("""
        SELECT t.id, t.agent_type, t.conviction_score, t.proposed_action,
               t.thesis_text, t.status, t.created_at, i.*
        FROM theses t
        JOIN instruments i ON i.id = t.instrument_id
        WHERE t.status = 'active'
          AND datetime(t.created_at) >= datetime('now', '-1 day')
        ORDER BY t.conviction_score DESC
        LIMIT 5
    """)
    rows = cur.fetchall()
    print(f"  -> {len(rows)} lignes")
    for r in rows:
        d = dict(r)
        print(f"  id={d['id']} agent={d['agent_type']} conv={d['conviction_score']}")
        print(f"    instrument keys: {list(d.keys())}")
        # affiche seulement les cles potentielles ticker
        for k in ['ticker', 'symbol', 'name', 'asset_class', 'category']:
            if k in d:
                print(f"    {k}={d[k]}")
        print(f"    action: {d['proposed_action'][:100] if d['proposed_action'] else None}")
        break  # juste un exemple complet
except Exception as e:
    print(f"  ERREUR: {e}")

conn.close()
