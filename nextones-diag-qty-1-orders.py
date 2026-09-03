# -*- coding: utf-8 -*-
"""
Diag : pourquoi les ordres equity sortent a 1 unite apres un run cycle.
v2 : liste d'abord les tables dispo.
"""
import sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"

cx = sqlite3.connect(str(DB))
cx.row_factory = sqlite3.Row

# 1. Liste toutes les tables
print("=== Tables de la DB ===")
tables = cx.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
all_tables = [t['name'] for t in tables]
for t in all_tables:
    print(f"  {t}")

# 2. Cherche celles qui contiennent 'cycle', 'order', 'proposal', 'target'
print("\n=== Tables pertinentes ===")
for t in all_tables:
    if any(k in t.lower() for k in ('cycle', 'order', 'proposal', 'target', 'snapshot')):
        n = cx.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()['n']
        print(f"  {t} : {n} lignes")
        # Schema
        cols = cx.execute(f"PRAGMA table_info({t})").fetchall()
        for c in cols:
            print(f"     {c['name']:30s} {c['type']}")

# 3. Pour orders (probablement existe), dernier cycle_id et 20 derniers ordres
print("\n=== 20 derniers ordres ===")
try:
    cols = cx.execute("PRAGMA table_info(orders)").fetchall()
    col_names = [c['name'] for c in cols]
    if not col_names:
        print("  Table orders inexistante")
    else:
        # Ordre par id desc
        rows = cx.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 20").fetchall()
        for r in rows:
            d = dict(r)
            # Affiche les champs principaux
            print(" | ".join(f"{k}={v}" for k, v in d.items() if v is not None and k not in ('id',)))
            print("  ---")
except sqlite3.OperationalError as e:
    print(f"  ERREUR: {e}")

cx.close()
