# -*- coding: utf-8 -*-
# Diag schemas tables critiques pour wrapper 8B.2
import sqlite3, json, os

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

TABLES = [
    "theses", "crypto_context", "convergence_snapshots",
    "portfolio_positions", "portfolio_targets", "portfolio_targets_history",
    "target_universe", "target_construction_config", "regime_log",
    "portfolio_history", "portfolio_state",
]

for t in TABLES:
    print("=" * 70)
    print(f"TABLE : {t}")
    print("=" * 70)
    # Existe ?
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name=?", (t,))
    row = cur.fetchone()
    if not row:
        print("  (TABLE INEXISTANTE)")
        continue
    # DDL
    print(f"  DDL: {row[1]}")
    # Colonnes
    cur.execute(f"PRAGMA table_info({t})")
    cols = cur.fetchall()
    print(f"  Colonnes ({len(cols)}):")
    for c in cols:
        # cid, name, type, notnull, dflt, pk
        print(f"    {c[1]:35s} {c[2]:15s} notnull={c[3]} pk={c[5]}")
    # Count + max date si col date
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    cnt = cur.fetchone()[0]
    print(f"  Count: {cnt}")
    # Cherche col 'created_at', 'date', 'day_t', 'timestamp' pour info no-lookahead
    date_cols = [c[1] for c in cols if c[1].lower() in ("created_at", "date", "day_t", "timestamp", "ts", "updated_at")]
    for dc in date_cols:
        try:
            cur.execute(f"SELECT MIN({dc}), MAX({dc}) FROM {t} WHERE {dc} IS NOT NULL")
            r = cur.fetchone()
            print(f"  {dc} range: {r[0]} -> {r[1]}")
        except sqlite3.OperationalError as e:
            print(f"  {dc} range: ERR {e}")
    # Sample 2 lignes
    try:
        cur.execute(f"SELECT * FROM {t} LIMIT 2")
        rows = cur.fetchall()
        if rows:
            col_names = [c[1] for c in cols]
            for i, r in enumerate(rows, 1):
                snippet = dict(zip(col_names, r))
                # Tronque les valeurs longues
                snippet = {k: (str(v)[:60] + "..." if v and len(str(v)) > 60 else v) for k, v in snippet.items()}
                print(f"  Sample {i}: {json.dumps(snippet, default=str)[:200]}")
    except Exception as e:
        print(f"  Sample: ERR {e}")
    print()

conn.close()
