# -*- coding: utf-8 -*-
# nextones-diag-sol-bypass-convergence.py
# Trouver pourquoi SOL #266 a passe malgre forced_exit=1
# Hypotheses :
# A. apply_convergence_sizing pas appele pour crypto
# B. snapshot trop vieux -> cycle_id mismatch -> fallback no-op
# C. BUY 51 vient d'un autre chemin (reconciler, exit_agent)

import os
import re
import sqlite3
import json

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

con = sqlite3.connect(DB, timeout=5.0)
con.row_factory = sqlite3.Row

print()
print("=" * 72)
print("[1] Order #266 SOL - details complets")
print("-" * 72)
r = con.execute("SELECT * FROM orders WHERE id = 266").fetchone()
if r:
    for k in r.keys():
        v = r[k]
        if isinstance(v, str) and len(v) > 300:
            v = v[:300] + "..."
        print("    %-25s = %s" % (k, v))
else:
    print("  ABSENT")

print()
print("=" * 72)
print("[2] Cycle id associe a #266 - et son construction_snapshot")
print("-" * 72)
# Trouver toutes les tables avec cycle_id
tables = [r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()]
print("  Tables avec colonne cycle_id :")
for t in tables:
    try:
        cols = [c[1] for c in con.execute("PRAGMA table_info(%s)" % t).fetchall()]
        if "cycle_id" in cols:
            print("    - %s" % t)
    except Exception:
        pass

print()
print("=" * 72)
print("[3] construction_snapshots / portfolio_targets pour SOL aujourd'hui")
print("-" * 72)
# Chercher dans construction_snapshots (ou nom equivalent)
for tbl in ("construction_snapshots", "portfolio_targets", "targets", "allocation_snapshots"):
    if tbl in tables:
        print("  Table %s :" % tbl)
        try:
            cols = [c[1] for c in con.execute("PRAGMA table_info(%s)" % tbl).fetchall()]
            print("    colonnes : %s" % cols)
            # SOL aujourd'hui
            rows = con.execute(
                "SELECT * FROM %s WHERE %s = 'SOL' ORDER BY rowid DESC LIMIT 3" % (
                    tbl, "ticker" if "ticker" in cols else cols[1])
            ).fetchall()
            for row in rows:
                print("    --- row ---")
                for k in row.keys():
                    v = row[k]
                    if isinstance(v, str) and len(v) > 200:
                        v = v[:200] + "..."
                    print("      %-25s = %s" % (k, v))
        except Exception as e:
            print("    [WARN] %s" % e)

print()
print("=" * 72)
print("[4] Tous les ordres SOL aujourd'hui + chaine (thesis -> cycle)")
print("-" * 72)
rows = con.execute(
    "SELECT id, created_at, side, quantity, status, action, thesis_id, instrument_id FROM orders "
    "WHERE instrument_id = (SELECT id FROM instruments WHERE ticker='SOL') "
    "AND created_at >= '2026-06-10' ORDER BY id DESC LIMIT 5"
).fetchall()
for r in rows:
    print("  order #%d %s side=%s qty=%s status=%s action=%s thesis=%s" % (
        r["id"], r["created_at"], r["side"], r["quantity"], r["status"], r["action"], r["thesis_id"]))

print()
print("=" * 72)
print("[5] portfolio_construction_agent_jalon2.py - flow crypto vs equity")
print("-" * 72)
pca = os.path.join(PROD, "portfolio_construction_agent_jalon2.py")
if os.path.exists(pca):
    with open(pca, "r", encoding="utf-8-sig", errors="replace") as fh:
        txt = fh.read()
    lines = txt.splitlines()
    # Chercher si apply_convergence_sizing est appele dans tous les chemins
    print("  Appels apply_convergence_sizing :")
    for i, l in enumerate(lines, 1):
        if "apply_convergence_sizing" in l and "def " not in l:
            print("    L%4d %s" % (i, l.rstrip()[:160]))
    # Chercher mots-clefs crypto/equity
    print()
    print("  Branches asset_class (crypto / equity) :")
    for i, l in enumerate(lines, 1):
        s = l.strip()
        if any(k in s for k in ("asset_class", "is_crypto", "crypto_orders", "if crypto", "elif crypto")):
            if not s.startswith("#") and len(s) < 200:
                print("    L%4d %s" % (i, s[:160]))

print()
print("=" * 72)
print("[6] Recherche : qui INSERT dans orders pour crypto + SOL")
print("-" * 72)
patterns_files = []
for root, dirs, files in os.walk(PROD):
    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "__pycache__", "node_modules", "backups", ".git")]
    for f in files:
        if f.endswith(".py") and not f.startswith("nextones-diag") and not f.startswith("nextones-test"):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                    t = fh.read()
                # Pattern d'insertion orders + crypto
                if "INSERT INTO orders" in t or 'INSERT INTO "orders"' in t:
                    patterns_files.append((path, t))
            except Exception:
                pass

print("  Fichiers avec INSERT INTO orders :")
for path, t in patterns_files:
    rel = os.path.relpath(path, PROD)
    n = t.count("INSERT INTO orders") + t.count('INSERT INTO "orders"')
    print("    - %s (%d insert)" % (rel, n))

print()
print("=" * 72)
print("[7] CryptoAgent : emission directe d'ordres ou via construction ?")
print("-" * 72)
ca = os.path.join(PROD, "crypto_agent.py")
if not os.path.exists(ca):
    # Chercher
    for root, dirs, files in os.walk(PROD):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "__pycache__", "node_modules", "backups", ".git")]
        for f in files:
            if "crypto" in f.lower() and f.endswith(".py") and "diag" not in f and "test" not in f:
                ca = os.path.join(root, f)
                break
        if os.path.exists(ca):
            break

if os.path.exists(ca):
    print("  Fichier : %s" % os.path.relpath(ca, PROD))
    with open(ca, "r", encoding="utf-8-sig", errors="replace") as fh:
        txt = fh.read()
    has_insert = "INSERT INTO orders" in txt
    has_convergence = "convergence_snapshots" in txt or "apply_convergence_sizing" in txt or "forced_exit" in txt
    print("  - INSERT INTO orders : %s" % has_insert)
    print("  - lit convergence    : %s" % has_convergence)

print()
print("=" * 72)
print("FIN DIAG")
print("=" * 72)
con.close()
