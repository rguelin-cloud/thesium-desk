# -*- coding: utf-8 -*-
# nextones-diag-sol-bypass-v2.py
# v2 : sans colonne 'action' (qui n'existe pas dans orders)

import os
import sqlite3

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

con = sqlite3.connect(DB, timeout=5.0)
con.row_factory = sqlite3.Row

print()
print("=" * 72)
print("[1] Schema orders")
print("-" * 72)
cols = con.execute("PRAGMA table_info(orders)").fetchall()
order_cols = [c[1] for c in cols]
print("  colonnes orders : %s" % order_cols)

print()
print("=" * 72)
print("[2] Ordres SOL recents (5 derniers)")
print("-" * 72)
rows = con.execute(
    "SELECT id, created_at, side, quantity, status, thesis_id FROM orders "
    "WHERE instrument_id = (SELECT id FROM instruments WHERE ticker='SOL') "
    "ORDER BY id DESC LIMIT 5"
).fetchall()
for r in rows:
    print("  order #%d %s side=%s qty=%s status=%s thesis=%s" % (
        r["id"], r["created_at"], r["side"], r["quantity"], r["status"], r["thesis_id"]))

print()
print("=" * 72)
print("[3] portfolio_targets_history pour SOL")
print("-" * 72)
try:
    cols_h = [c[1] for c in con.execute("PRAGMA table_info(portfolio_targets_history)").fetchall()]
    print("  colonnes : %s" % cols_h)
    rows = con.execute(
        "SELECT * FROM portfolio_targets_history WHERE ticker='SOL' "
        "ORDER BY rowid DESC LIMIT 5"
    ).fetchall()
    for row in rows:
        print("  --- row ---")
        for k in row.keys():
            v = row[k]
            if isinstance(v, str) and len(v) > 200:
                v = v[:200] + "..."
            print("    %-25s = %s" % (k, v))
except Exception as e:
    print("  [WARN] %s" % e)

print()
print("=" * 72)
print("[4] portfolio_targets : tous les tickers en forced_exit selon snapshot J-1")
print("-" * 72)
# Croiser portfolio_targets et convergence_snapshots
rows = con.execute(
    "SELECT pt.ticker, pt.target_weight_pct, pt.snapshot_id, pt.updated_at, "
    "       cs.forced_exit, cs.sizing_multiplier, cs.direction_consensus "
    "FROM portfolio_targets pt "
    "LEFT JOIN convergence_snapshots cs "
    "  ON cs.ticker = pt.ticker AND cs.cycle_id = '20260609-091332' "
    "WHERE pt.active = 1 "
    "ORDER BY pt.ticker"
).fetchall()
print("  ticker   target%  fe  mult   dir          updated_at")
for r in rows:
    fe = r["forced_exit"] if r["forced_exit"] is not None else "-"
    mult = r["sizing_multiplier"] if r["sizing_multiplier"] is not None else "-"
    direc = r["direction_consensus"] or "-"
    print("  %-8s %7s  %2s  %5s  %-12s %s" % (
        r["ticker"], r["target_weight_pct"], fe, mult, direc, r["updated_at"]))

print()
print("=" * 72)
print("[5] thesis 7413 (origine de order #266 SOL)")
print("-" * 72)
try:
    cols_th = [c[1] for c in con.execute("PRAGMA table_info(theses)").fetchall()]
    print("  colonnes theses : %s" % cols_th[:20])
    th = con.execute("SELECT * FROM theses WHERE id = 7413").fetchone()
    if th:
        for k in th.keys():
            v = th[k]
            if isinstance(v, str) and len(v) > 200:
                v = v[:200] + "..."
            print("    %-25s = %s" % (k, v))
    else:
        print("  ABSENT")
except Exception as e:
    print("  [WARN] %s" % e)

print()
print("=" * 72)
print("[6] portfolio_construction_agent_jalon2.py : appels apply_convergence_sizing")
print("-" * 72)
pca = os.path.join(PROD, "portfolio_construction_agent_jalon2.py")
if os.path.exists(pca):
    with open(pca, "r", encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.readlines()
    for i, l in enumerate(lines, 1):
        s = l.strip()
        if "apply_convergence_sizing" in s:
            print("    L%4d %s" % (i, s[:160]))
        elif s.startswith("def ") and "construction" in s.lower():
            print("    L%4d %s" % (i, s[:160]))

print()
print("=" * 72)
print("[7] Recherche : par ou passent les BUY crypto qui creent #266 ?")
print("-" * 72)
# 1. Trouver tous les fichiers avec 'INSERT INTO orders'
hits = []
for root, dirs, files in os.walk(PROD):
    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "__pycache__", "node_modules", "backups", ".git")]
    for f in files:
        if f.endswith(".py") and not f.startswith("nextones-diag") and not f.startswith("nextones-test") and not f.startswith("nextones-fix"):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                    t = fh.read()
                if "INSERT INTO orders" in t or 'INSERT INTO "orders"' in t:
                    n = t.count("INSERT INTO orders") + t.count('INSERT INTO "orders"')
                    hits.append((os.path.relpath(path, PROD), n))
            except Exception:
                pass

print("  Fichiers avec INSERT INTO orders :")
for rel, n in sorted(hits):
    print("    - %s (%d insert)" % (rel, n))

print()
print("=" * 72)
print("[8] reconciler / reconciliation : insertion d'ordres ?")
print("-" * 72)
for fname in ("reconciler.py", "portfolio_reconciler.py", "cycle_reconciler.py"):
    p = os.path.join(PROD, fname)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8-sig", errors="replace") as fh:
            t = fh.read()
        has_insert = "INSERT INTO orders" in t
        has_conv = "convergence_snapshots" in t or "forced_exit" in t or "apply_convergence_sizing" in t
        print("  %s : INSERT orders=%s, lit convergence=%s" % (fname, has_insert, has_conv))

print()
print("=" * 72)
print("FIN DIAG")
print("=" * 72)
con.close()
