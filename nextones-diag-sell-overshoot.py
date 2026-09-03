# -*- coding: utf-8 -*-
# nextones-diag-sell-overshoot.py
# Diag pour Etape D : Cap qty SELL <= position detenue
#
# Objectif :
#   1. Trouver le fichier construction_agent.py (et/ou portfolio_construction_agent.py)
#   2. Reperer ou les SELL sont generes
#   3. Verifier si une logique de cap existe deja
#   4. Identifier la source de "position detenue" (table portfolio_positions ? holdings ?)
#   5. Verifier les SELL recents (ZEC #263 SELL 55, #265 SELL 10) vs position reelle ZEC

import os
import sys
import sqlite3
import re

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(PROD, "thesium.db")

print()
print("=" * 72)
print("DIAG : SELL overshoot - cap qty <= position detenue")
print("=" * 72)

# ----------------------------------------------------------------------
# [1] Trouver les fichiers construction_agent / portfolio_construction
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[1] Fichiers construction agent")
print("-" * 72)

candidates = []
for fname in os.listdir(PROD):
    low = fname.lower()
    if fname.endswith(".py") and ("construction" in low or "portfolio_agent" in low):
        full = os.path.join(PROD, fname)
        size = os.path.getsize(full)
        candidates.append((fname, full, size))

for fname, full, size in candidates:
    print("  %s  (%d bytes)" % (fname, size))

if not candidates:
    print("  [WARN] Aucun fichier construction_agent trouve")
    sys.exit(2)

# ----------------------------------------------------------------------
# [2] Chercher la generation de SELL dans ces fichiers
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[2] Generation de SELL : grep 'SELL' et 'side' dans chaque fichier")
print("-" * 72)

for fname, full, _ in candidates:
    print()
    print("  --- %s ---" % fname)
    with open(full, "r", encoding="utf-8-sig") as fh:
        text = fh.read()
    lines = text.split("\n")

    # Cherche les occurrences de 'SELL' (string literal)
    sell_lines = []
    for i, ln in enumerate(lines):
        if '"SELL"' in ln or "'SELL'" in ln:
            sell_lines.append((i + 1, ln.strip()))

    if not sell_lines:
        print("    [INFO] aucune string SELL trouvee")
    else:
        print("    %d lignes contiennent string SELL :" % len(sell_lines))
        for ln_no, txt in sell_lines[:15]:
            print("      L%d: %s" % (ln_no, txt[:160]))

    # Cherche des indices de cap / clip / min / position
    for kw in ["cap_qty", "max_sell", "clip", "current_position", "held_qty", "qty_held", "available_qty"]:
        if kw in text:
            for i, ln in enumerate(lines):
                if kw in ln:
                    print("    [HINT '%s'] L%d: %s" % (kw, i + 1, ln.strip()[:160]))
                    break

# ----------------------------------------------------------------------
# [3] Table portfolio_positions / holdings : positions reelles
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[3] Tables positions / holdings")
print("-" * 72)

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = sorted([r[0] for r in cur.fetchall()])

pos_tables = []
for t in tables:
    low = t.lower()
    if "position" in low or "holding" in low or "portfolio" in low:
        pos_tables.append(t)

print("  Tables candidates :")
for t in pos_tables:
    cur.execute("SELECT COUNT(*) FROM %s" % t)
    cnt = cur.fetchone()[0]
    print("    %s  (%d lignes)" % (t, cnt))

# ----------------------------------------------------------------------
# [4] Schema portfolio_positions et position ZEC reelle
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[4] Schema portfolio_positions + qty ZEC reelle")
print("-" * 72)

if "portfolio_positions" in pos_tables:
    cur.execute("PRAGMA table_info(portfolio_positions)")
    cols = cur.fetchall()
    print("  Schema portfolio_positions :")
    col_names = []
    for c in cols:
        print("    %s : %s" % (c[1], c[2]))
        col_names.append(c[1])
    print()
    # Position ZEC reelle
    if "ticker" in col_names and "qty" in col_names:
        cur.execute("SELECT * FROM portfolio_positions WHERE ticker = 'ZEC'")
        rows = cur.fetchall()
        if rows:
            print("  ZEC dans portfolio_positions :")
            for r in rows:
                d = dict(zip(col_names, r))
                print("    %s" % d)
        else:
            print("  [INFO] ZEC absent de portfolio_positions")
else:
    print("  [WARN] portfolio_positions absent, on cherche ailleurs")

# ----------------------------------------------------------------------
# [5] Les ordres SELL ZEC recents et leur qty vs position reelle
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[5] SELL ZEC recents (orders) vs position detenue")
print("-" * 72)

cur.execute("PRAGMA table_info(orders)")
ocols = [c[1] for c in cur.fetchall()]
print("  Colonnes orders : %s" % ", ".join(ocols[:25]))

# Filtrer SELL ZEC
sql = "SELECT id, ticker, side, qty, status, blocked_by, created_at FROM orders WHERE ticker='ZEC' AND side='SELL' ORDER BY id DESC LIMIT 10"
try:
    cur.execute(sql)
    rows = cur.fetchall()
    print()
    print("  SELL ZEC (10 plus recents) :")
    print("  %-6s %-6s %-5s %-7s %-10s %-30s %-20s" % ("id", "tick", "side", "qty", "status", "blocked_by", "created_at"))
    for r in rows:
        print("  %-6s %-6s %-5s %-7s %-10s %-30s %-20s" % tuple(str(x)[:30] for x in r))
except sqlite3.OperationalError as e:
    print("  [ERR] %s" % e)

conn.close()

print()
print("=" * 72)
print("RECAP")
print("=" * 72)
print("  -> noter les fichiers a patcher (etape D)")
print("  -> noter la table + colonne de qty detenue")
print("  -> noter les SELL en overshoot")
