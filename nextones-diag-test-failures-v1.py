# -*- coding: utf-8 -*-
# nextones-diag-test-failures-v1.py
# Diag des 2 echecs du test jalon 8A :
#   1. get_close_at SPY 2025-06-15 = None (alors que get_open_after 2025-06-16 OK)
#   2. FREDAdapter VIX = 0 rows (mais fetch a insere 515 lignes !)

import sqlite3

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

conn = sqlite3.connect(DB, timeout=10.0)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 70)
print("DIAG 1 : SPY autour de 2025-06-15")
print("=" * 70)
cur.execute("""
    SELECT p.date, p.open, p.close, p.volume
    FROM prices p JOIN instruments i ON i.id = p.instrument_id
    WHERE i.ticker='SPY' AND p.date BETWEEN '2025-06-10' AND '2025-06-20'
    ORDER BY p.date
""")
for r in cur.fetchall():
    print(f"  {r['date']}  open={r['open']}  close={r['close']}  vol={r['volume']}")

print()
print("=" * 70)
print("DIAG 2 : macro_history - structure et contenu")
print("=" * 70)
cur.execute("PRAGMA table_info(macro_history)")
cols = cur.fetchall()
print("Colonnes:")
for c in cols:
    print(f"  {c['name']:15s} {c['cid']}  {c['type']}")

print()
cur.execute("SELECT COUNT(*) AS n FROM macro_history")
print(f"Total rows: {cur.fetchone()['n']}")

print()
cur.execute("SELECT * FROM macro_history LIMIT 3")
print("Echantillon (3 lignes):")
for r in cur.fetchall():
    print(f"  {dict(r)}")

print()
# Identifie le nom de colonne series
col_names = [c['name'] for c in cols]
print(f"col_names: {col_names}")
sid_col = None
for cand in ("series_id", "series", "ticker", "name"):
    if cand in col_names:
        sid_col = cand
        break
print(f"sid_col detecte: {sid_col}")

if sid_col:
    cur.execute(f"SELECT DISTINCT {sid_col} FROM macro_history")
    print(f"Series distinctes:")
    for r in cur.fetchall():
        print(f"  {dict(r)}")

# Test direct du filtre VIX <= 2025-06-15
if sid_col:
    cur.execute(f"SELECT COUNT(*) AS n FROM macro_history WHERE {sid_col}='VIX' AND date <= '2025-06-15'")
    print(f"\nFiltre VIX <= 2025-06-15 (col={sid_col}): n={cur.fetchone()['n']}")

conn.close()
