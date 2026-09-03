# -*- coding: utf-8 -*-
"""
Diag : pourquoi les cycles recents produisent peu d'ordres ?

On regarde :
  1. Les cycles recents (10 derniers) : nb propositions vs nb orders
  2. Pour chaque cycle : details des propositions (instrument, side, gap, threshold, status)
  3. Le regime actuel (calme/agite) et les thresholds appliques
  4. Les targets vs actuel : ecarts et pourquoi sub-threshold
  5. Convergence snapshots : combien sont en bloc/refused/forced_exit
"""
import sqlite3
import os
import json
from collections import defaultdict

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

def list_tables():
    return [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]

def cols(tbl):
    try:
        return [r["name"] for r in cur.execute(f"PRAGMA table_info({tbl})").fetchall()]
    except Exception:
        return []

ALL_TABLES = list_tables()
print(f"Tables disponibles : {len(ALL_TABLES)}")
for t in ALL_TABLES:
    if any(k in t.lower() for k in ("cycle", "propos", "target", "construct", "converg", "decision", "order", "regime", "snapshot")):
        print(f"  - {t}  cols={cols(t)}")

print()
print("=" * 80)
print("1. CYCLES RECENTS (depuis 10 jours) : nb propositions vs nb orders")
print("=" * 80)

# Lister cycles distincts dans orders
cycles_orders = cur.execute("""
    SELECT cycle_id, COUNT(*) AS n_orders, MIN(created_at) AS started
    FROM orders
    WHERE cycle_id IS NOT NULL
    GROUP BY cycle_id
    ORDER BY started DESC
    LIMIT 15
""").fetchall()

print(f"Cycles distincts (depuis orders) : {len(cycles_orders)}")
for r in cycles_orders:
    print(f"  cycle={r['cycle_id']:<25} n_orders={r['n_orders']:<3} started={r['started']}")

print()
print("=" * 80)
print("2. RECHERCHE D'UNE TABLE 'proposed_changes' ou similaire")
print("=" * 80)

candidates = [t for t in ALL_TABLES if any(k in t.lower() for k in ("propos", "target", "construct"))]
print(f"Candidats : {candidates}")

# Identifier la table de propositions par cycle
prop_table = None
for c in candidates:
    cc = cols(c)
    if any("cycle" in col.lower() for col in cc):
        prop_table = c
        print(f"  -> {c} a une colonne cycle, cols={cc}")
        break

if prop_table:
    print()
    print(f"Contenu de {prop_table} pour les cycles recents :")
    cycle_ids = [r["cycle_id"] for r in cycles_orders[:5]]
    ph = ",".join("?" * len(cycle_ids))
    cycle_col = "cycle_id" if "cycle_id" in cols(prop_table) else "cycle"
    try:
        rows = cur.execute(f"""
            SELECT * FROM {prop_table}
            WHERE {cycle_col} IN ({ph})
            ORDER BY {cycle_col} DESC
            LIMIT 100
        """, cycle_ids).fetchall()
        print(f"  {len(rows)} lignes trouvees")
        # Distribution par cycle
        dist = defaultdict(int)
        for r in rows:
            dist[r[cycle_col]] += 1
        for cid, n in sorted(dist.items(), reverse=True):
            print(f"    cycle={cid} : {n} propositions")
        # Dump 10 dernieres
        if rows:
            print(f"\n  Echantillon (premieres 10 lignes) :")
            for r in rows[:10]:
                d = dict(r)
                # Court
                short = {k: v for k, v in d.items() if v is not None and k not in ("notes", "details")}
                print(f"    {short}")
    except Exception as e:
        print(f"  ERREUR : {e}")

print()
print("=" * 80)
print("3. TABLE construction_snapshots si elle existe")
print("=" * 80)

if "construction_snapshots" in ALL_TABLES:
    cs_cols = cols("construction_snapshots")
    print(f"  cols : {cs_cols}")
    rows = cur.execute("""
        SELECT * FROM construction_snapshots
        ORDER BY rowid DESC LIMIT 5
    """).fetchall()
    for r in rows:
        d = dict(r)
        # Print sans details lourds
        for k, v in d.items():
            if v is not None:
                vs = str(v)
                if len(vs) > 200:
                    vs = vs[:200] + "...[TRUNC]"
                print(f"    {k} = {vs}")
        print("    ---")

print()
print("=" * 80)
print("4. TABLE convergence_snapshots si elle existe")
print("=" * 80)

if "convergence_snapshots" in ALL_TABLES:
    conv_cols = cols("convergence_snapshots")
    print(f"  cols : {conv_cols}")
    rows = cur.execute("""
        SELECT * FROM convergence_snapshots
        ORDER BY rowid DESC LIMIT 20
    """).fetchall()
    print(f"  {len(rows)} dernieres lignes :")
    for r in rows:
        d = dict(r)
        short = {k: v for k, v in d.items() if k in ("cycle_id", "ticker", "instrument_id", "verdict", "status", "score", "reason", "block_reason", "created_at")}
        print(f"    {short}")

print()
print("=" * 80)
print("5. TABLE targets si elle existe (ecart actuel vs target)")
print("=" * 80)

if "targets" in ALL_TABLES:
    t_cols = cols("targets")
    print(f"  cols : {t_cols}")
    # Derniere version
    rows = cur.execute("""
        SELECT * FROM targets ORDER BY rowid DESC LIMIT 20
    """).fetchall()
    for r in rows:
        d = dict(r)
        short = {k: v for k, v in d.items() if v is not None}
        print(f"    {short}")

print()
print("=" * 80)
print("6. REGIME ACTUEL")
print("=" * 80)

regime_tables = [t for t in ALL_TABLES if "regime" in t.lower()]
print(f"  Tables regime : {regime_tables}")
for t in regime_tables:
    rows = cur.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 3").fetchall()
    for r in rows:
        print(f"    {dict(r)}")

print()
print("=" * 80)
print("7. POSITIONS ACTUELLES + targets ratio")
print("=" * 80)

if "positions" in ALL_TABLES:
    p_cols = cols("positions")
    print(f"  cols positions : {p_cols}")
    rows = cur.execute("""
        SELECT * FROM positions ORDER BY rowid DESC LIMIT 25
    """).fetchall()
    print(f"  {len(rows)} positions :")
    for r in rows:
        d = dict(r)
        short = {k: v for k, v in d.items() if k in ("ticker", "instrument_id", "quantity", "qty", "market_value", "mv", "weight", "weight_pct", "target_weight", "updated_at")}
        if not short:
            short = d
        print(f"    {short}")

con.close()
print()
print("=" * 80)
print("FIN DU DIAG")
print("=" * 80)
