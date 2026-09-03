#!/usr/bin/env python3
# nextones-validate-risk-v2-runtime-v2.py
# Version corrigee : cible explicitement risk_pretrade_log + decouvre schema orders

import sqlite3
from pathlib import Path

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 78)
print("RISK ENGINE V2 RUNTIME — Validation cycle 29/05/2026 (v2)")
print("=" * 78)

# === 1. Schema orders ===
print("\n[1] Schema orders")
print("-" * 78)
cur.execute("PRAGMA table_info(orders)")
order_cols = [c[1] for c in cur.fetchall()]
for c in order_cols:
    print(f"  {c}")

# Detection colonne symbole
sym_col = None
for cand in ("symbol", "ticker", "instrument", "asset", "instrument_id", "ticker_symbol"):
    if cand in order_cols:
        sym_col = cand
        break
print(f"\n  Colonne symbole detectee : {sym_col}")

# === 2. Schema risk_pretrade_log ===
print("\n[2] Schema risk_pretrade_log")
print("-" * 78)
cur.execute("PRAGMA table_info(risk_pretrade_log)")
rpl_cols_info = cur.fetchall()
rpl_cols = [c[1] for c in rpl_cols_info]
for c in rpl_cols_info:
    print(f"  {c[1]:30s} {c[2]}")

# === 3. Schema risk_config ===
print("\n[3] risk_config (config actuelle)")
print("-" * 78)
cur.execute("SELECT * FROM risk_config")
for r in cur.fetchall():
    d = dict(r)
    for k, v in d.items():
        s = str(v)
        if len(s) > 100:
            s = s[:100] + "..."
        print(f"  {k:30s} : {s}")

# === 4. Contenu integral risk_pretrade_log (4 rows seulement) ===
print("\n[4] Contenu integral risk_pretrade_log")
print("-" * 78)
cur.execute("SELECT * FROM risk_pretrade_log ORDER BY id DESC")
rows = cur.fetchall()
for i, r in enumerate(rows, 1):
    print(f"\n  --- Row {i} ---")
    d = dict(r)
    for k, v in d.items():
        s = str(v)
        if len(s) > 200:
            s = s[:200] + "..."
        print(f"    {k:30s} : {s}")

# === 5. Les 10 ordres du cycle avec colonne symbole correcte ===
print(f"\n[5] Les 10 ordres pending du cycle 29/05 (col sym={sym_col})")
print("-" * 78)
select_cols = ["id"]
if sym_col:
    select_cols.append(sym_col)
for c in ("side", "qty", "status", "source_thesis_id", "thesis_id", "created_at"):
    if c in order_cols:
        select_cols.append(c)
sql = f"SELECT {', '.join(select_cols)} FROM orders WHERE id BETWEEN 4895 AND 4907 ORDER BY id"
cur.execute(sql)
orders = cur.fetchall()
header = " ".join(f"{c:<12}" for c in select_cols)
print(f"  {header}")
order_ids = []
for o in orders:
    line = " ".join(f"{str(o[c])[:12]:<12}" for c in select_cols)
    print(f"  {line}")
    order_ids.append(o["id"])

# === 6. Correspondance ordres <-> risk_pretrade_log ===
print(f"\n[6] Correspondance ordres -> risk_pretrade_log")
print("-" * 78)
# Cherche la colonne de jointure
join_col = None
for cand in ("order_id", "order", "ref_order_id"):
    if cand in rpl_cols:
        join_col = cand
        break

if join_col:
    print(f"  Jointure via {join_col}")
    placeholders = ",".join("?" * len(order_ids))
    cur.execute(f"SELECT * FROM risk_pretrade_log WHERE {join_col} IN ({placeholders})", order_ids)
    matches = cur.fetchall()
    print(f"  Lignes risk_pretrade_log matchant les 10 ordres : {len(matches)}")
    for m in matches:
        print(f"  {dict(m)}")
else:
    print("  Pas de colonne order_id - jointure impossible")
    # essai par symbole + timestamp
    if sym_col and "symbol" in rpl_cols:
        print(f"  Tentative jointure par symbol + window time")
        cur.execute("""
            SELECT * FROM risk_pretrade_log
            WHERE created_at >= '2026-05-29 10:00:00'
               OR ts >= 1748506800
            ORDER BY id DESC
        """)
        for m in cur.fetchall():
            print(f"  {dict(m)}")

# === 7. Stats decisions sur risk_pretrade_log ===
print(f"\n[7] Stats decisions risk_pretrade_log")
print("-" * 78)
status_col = next((c for c in ("decision", "status", "result", "verdict", "outcome") if c in rpl_cols), None)
if status_col:
    cur.execute(f"SELECT {status_col} AS s, COUNT(*) AS n FROM risk_pretrade_log GROUP BY {status_col}")
    for r in cur.fetchall():
        print(f"  {r['s']:<15} {r['n']}")
else:
    print("  Pas de colonne status/decision identifiee")

conn.close()
print("\n" + "=" * 78)
