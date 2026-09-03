# -*- coding: utf-8 -*-
# nextones-diag-sell-overshoot-v2.py
# Diag v2 :
#   - Trouver OU le side "SELL" / "BUY" est decide
#   - Trouver OU la quantite est calculee a partir de (target - current)
#   - Position ZEC reelle via instruments.symbol JOIN portfolio_positions
#   - SELL ZEC recents via instrument_id JOIN

import os
import sys
import sqlite3

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(PROD, "thesium.db")

print()
print("=" * 72)
print("DIAG v2 : ou les SELL sont generes + position ZEC reelle")
print("=" * 72)

# ----------------------------------------------------------------------
# [1] Position ZEC via JOIN instruments
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[1] Position ZEC reelle (JOIN instruments)")
print("-" * 72)

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Schema instruments
cur.execute("PRAGMA table_info(instruments)")
icols = [c[1] for c in cur.fetchall()]
print("  Colonnes instruments : %s" % ", ".join(icols))

# Chercher la colonne symbol/ticker dans instruments
sym_col = None
for c in ["symbol", "ticker", "code", "name"]:
    if c in icols:
        sym_col = c
        break
print("  Colonne symbole utilisee : %s" % sym_col)

# Position ZEC
sql = """
SELECT i.%s, pp.quantity, pp.avg_cost, pp.current_price, pp.weight_pct, pp.updated_at
FROM portfolio_positions pp
JOIN instruments i ON i.id = pp.instrument_id
WHERE i.%s = 'ZEC'
""" % (sym_col, sym_col)
cur.execute(sql)
rows = cur.fetchall()
print()
if rows:
    print("  ZEC dans portfolio_positions :")
    for r in rows:
        print("    symbol=%s qty=%s avg_cost=%s price=%s weight_pct=%s updated_at=%s" % r)
else:
    print("  [INFO] ZEC absent de portfolio_positions => position = 0")

# ----------------------------------------------------------------------
# [2] SELL ZEC recents (orders) via JOIN
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[2] Orders ZEC (10 plus recents) : qty vs position")
print("-" * 72)

sql = """
SELECT o.id, i.%s, o.side, o.quantity, o.status, o.rejection_reason, o.created_at
FROM orders o
JOIN instruments i ON i.id = o.instrument_id
WHERE i.%s = 'ZEC'
ORDER BY o.id DESC
LIMIT 10
""" % (sym_col, sym_col)
cur.execute(sql)
rows = cur.fetchall()
print()
print("  %-6s %-6s %-5s %-7s %-10s %-30s %-20s" % ("id", "tick", "side", "qty", "status", "rejection_reason", "created_at"))
for r in rows:
    safe = tuple(str(x)[:30] if x is not None else "None" for x in r)
    print("  %-6s %-6s %-5s %-7s %-10s %-30s %-20s" % safe)

# ----------------------------------------------------------------------
# [3] Chercher OU "SELL" est ecrit en code (tous les .py prod, pas diag)
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[3] Tous les .py prod (hors diag/patch) contenant 'SELL'")
print("-" * 72)

EXCLUDE_PREFIX = ("nextones-", "_show_", "test_")
hits = []
for fname in sorted(os.listdir(PROD)):
    if not fname.endswith(".py"):
        continue
    # On garde les fichiers prod (pas diag/patch one-shot)
    if any(fname.startswith(p) for p in EXCLUDE_PREFIX):
        continue
    full = os.path.join(PROD, fname)
    try:
        with open(full, "r", encoding="utf-8-sig") as fh:
            text = fh.read()
    except Exception as e:
        continue
    if '"SELL"' in text or "'SELL'" in text:
        # Compter occurrences
        n1 = text.count('"SELL"')
        n2 = text.count("'SELL'")
        hits.append((fname, n1 + n2))

if not hits:
    print("  [WARN] aucun fichier prod ne contient string SELL")
else:
    print("  Fichiers prod avec 'SELL' :")
    for fname, n in hits:
        print("    %s  (%d occurrences)" % (fname, n))

# ----------------------------------------------------------------------
# [4] Pour les 3 premiers candidats, dump des lignes SELL et contexte
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[4] Lignes SELL en contexte (top 3 fichiers)")
print("-" * 72)

for fname, _ in hits[:3]:
    full = os.path.join(PROD, fname)
    with open(full, "r", encoding="utf-8-sig") as fh:
        lines = fh.read().split("\n")
    print()
    print("  --- %s ---" % fname)
    for i, ln in enumerate(lines):
        if '"SELL"' in ln or "'SELL'" in ln:
            # Contexte +/- 3 lignes
            start = max(0, i - 3)
            end = min(len(lines), i + 4)
            print("  L%d (contexte) :" % (i + 1))
            for k in range(start, end):
                marker = " >>" if k == i else "   "
                print("  %s L%d: %s" % (marker, k + 1, lines[k][:160].rstrip()))
            print()

# ----------------------------------------------------------------------
# [5] Cherche la logique target - current = delta -> side
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[5] Logique de calcul du delta (target - current)")
print("-" * 72)

KEYWORDS = ["target_qty", "delta_qty", "qty_delta", "current_qty", "diff_qty", "target_weight", "current_weight"]

for fname in sorted(os.listdir(PROD)):
    if not fname.endswith(".py"):
        continue
    if any(fname.startswith(p) for p in EXCLUDE_PREFIX):
        continue
    full = os.path.join(PROD, fname)
    try:
        with open(full, "r", encoding="utf-8-sig") as fh:
            text = fh.read()
    except Exception:
        continue
    matches = [k for k in KEYWORDS if k in text]
    if matches:
        print("  %s : %s" % (fname, ", ".join(matches)))

conn.close()
print()
print("=" * 72)
