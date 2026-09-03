# -*- coding: utf-8 -*-
"""
Affiche le dernier cycle de regime_log + schema reel de la table
(complement a la section [4] qui a echoue avec 'no such column: ts').
"""
import os
import sqlite3

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(ROOT, "thesium.db")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

print("=" * 78)
print("SCHEMA regime_log")
print("=" * 78)
cols = conn.execute("PRAGMA table_info(regime_log)").fetchall()
for c in cols:
    print(f"  {c['cid']:3} {c['name']:30} {c['type']:15} pk={c['pk']}  notnull={c['notnull']}  default={c['dflt_value']}")

print()
print("=" * 78)
print("Dernier cycle (regime_log)")
print("=" * 78)
# On prend toutes les colonnes, sans hypothese sur les noms
last = conn.execute("SELECT * FROM regime_log ORDER BY id DESC LIMIT 1").fetchone()
if last:
    for k in last.keys():
        print(f"  {k:30} = {last[k]}")
else:
    print("  Aucun cycle")

print()
print("=" * 78)
print("Dernier cycle (market_regime_log)")
print("=" * 78)
cols2 = conn.execute("PRAGMA table_info(market_regime_log)").fetchall()
print(f"  {len(cols2)} colonnes")
last_m = conn.execute("SELECT * FROM market_regime_log ORDER BY id DESC LIMIT 5").fetchall()
if last_m:
    for row in last_m:
        print(f"  --- id={row['id']} cycle={row['cycle_id']} class={row['asset_class']} ---")
        for k in row.keys():
            print(f"      {k:25} = {row[k]}")
else:
    print("  Aucun log")

print()
print("=" * 78)
print("Distribution market_regime (asset_class x regime)")
print("=" * 78)
dist = conn.execute("""
    SELECT asset_class, regime, COUNT(*) AS n
    FROM market_regime_log
    GROUP BY asset_class, regime
    ORDER BY asset_class, regime
""").fetchall()
for r in dist:
    print(f"  {r['asset_class']:8} {r['regime']:8} n={r['n']}")

conn.close()
