# -*- coding: utf-8 -*-
# nextones-diag-convergence-schema.py
# Diag du schema + contenu convergence_snapshots pour cabler le garde-fou forced_exit

import os
import sys
import sqlite3
import json

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

con = sqlite3.connect(DB, timeout=5.0)
con.row_factory = sqlite3.Row

print()
print("=" * 72)
print("[1] Tables liees a Convergence")
print("-" * 72)
tables = [r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%converg%' ORDER BY name"
).fetchall()]
for t in tables:
    print("  - %s" % t)

print()
print("=" * 72)
print("[2] Schema convergence_snapshots")
print("-" * 72)
if "convergence_snapshots" in tables:
    for r in con.execute("PRAGMA table_info(convergence_snapshots)").fetchall():
        print("  col %2d  %-25s  %-10s  pk=%d  notnull=%d  default=%s" % (
            r["cid"], r["name"], r["type"], r["pk"], r["notnull"], r["dflt_value"]))
    # Index
    print()
    print("  Indexes :")
    for r in con.execute("PRAGMA index_list(convergence_snapshots)").fetchall():
        print("    - %s (unique=%d)" % (r["name"], r["unique"]))
        for c in con.execute("PRAGMA index_info(%s)" % r["name"]).fetchall():
            print("        col : %s" % c["name"])

print()
print("=" * 72)
print("[3] Cycles snapshots distincts (5 derniers)")
print("-" * 72)
try:
    rows = con.execute(
        "SELECT cycle_id, COUNT(*) AS n, MIN(ts) AS first_ts, MAX(ts) AS last_ts "
        "FROM convergence_snapshots GROUP BY cycle_id ORDER BY MAX(ts) DESC LIMIT 5"
    ).fetchall()
    for r in rows:
        print("  cycle=%s  rows=%d  first=%s  last=%s" % (r["cycle_id"], r["n"], r["first_ts"], r["last_ts"]))
except Exception as e:
    print("  [WARN] %s -- essai sans cycle_id" % e)
    try:
        rows = con.execute(
            "SELECT DISTINCT cycle_id FROM convergence_snapshots ORDER BY cycle_id DESC LIMIT 10"
        ).fetchall()
        for r in rows:
            print("  cycle=%s" % r[0])
    except Exception as e2:
        print("  [KO] %s" % e2)

print()
print("=" * 72)
print("[4] Dernier snapshot SOL / ZEC / BTC")
print("-" * 72)
try:
    # Trouver dernier cycle
    last_cycle = con.execute(
        "SELECT cycle_id FROM convergence_snapshots ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    if last_cycle:
        cid = last_cycle["cycle_id"]
        print("  Dernier cycle : %s" % cid)
        for tk in ("SOL", "ZEC", "BTC", "ETH", "LINK"):
            r = con.execute(
                "SELECT * FROM convergence_snapshots WHERE cycle_id = ? AND ticker = ? LIMIT 1",
                (cid, tk)
            ).fetchone()
            if r:
                print()
                print("  --- %s ---" % tk)
                for k in r.keys():
                    v = r[k]
                    if isinstance(v, str) and len(v) > 200:
                        v = v[:200] + "..."
                    print("    %-25s = %s" % (k, v))
            else:
                print("  %s : ABSENT du cycle %s" % (tk, cid))
except Exception as e:
    print("  [KO] %s" % e)

print()
print("=" * 72)
print("[5] Patterns forced_exit / verdict dans convergence_engine.py")
print("-" * 72)
ce = os.path.join(PROD, "convergence_engine.py")
if os.path.exists(ce):
    with open(ce, "r", encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.readlines()
    print("  Taille : %d lignes" % len(lines))
    for i, l in enumerate(lines, 1):
        s = l.strip()
        if any(k in s for k in ("forced_exit", "FORCED_EXIT", "verdict", "VERDICT", "def run")):
            if not s.startswith("#"):
                print("    L%4d %s" % (i, s[:160]))
else:
    print("  ABSENT : %s" % ce)

print()
print("=" * 72)
print("[6] Patterns convergence dans portfolio_construction_agent_jalon2.py")
print("-" * 72)
pca = os.path.join(PROD, "portfolio_construction_agent_jalon2.py")
if os.path.exists(pca):
    with open(pca, "r", encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.readlines()
    for i, l in enumerate(lines, 1):
        s = l.strip()
        if any(k in s for k in ("forced_exit", "convergence", "CONVERGENCE")):
            if not s.startswith("#"):
                print("    L%4d %s" % (i, s[:160]))

print()
print("=" * 72)
print("FIN DIAG")
print("=" * 72)
con.close()
