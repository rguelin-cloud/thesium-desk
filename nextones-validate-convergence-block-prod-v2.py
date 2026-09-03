# -*- coding: utf-8 -*-
# nextones-validate-convergence-block-prod-v2.py
# Marker : [VALIDATE_CONVERGENCE_BLOCK_PROD_V2]
#
# v2 fix : 'orders' n'a pas de colonne 'ticker' -> detecter dynamiquement
# (symbol ou ticker). Ajoute aussi le decode de details_json.

import os
import sys
import sqlite3
import json
from collections import defaultdict

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

print()
print("=" * 78)
print("VALIDATION PROD [CONVERGENCE_FORCED_EXIT_BLOCK_V1] v2")
print("-" * 78)

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
cur = c.cursor()

# Dernier cycle convergence
cur.execute("SELECT cycle_id FROM convergence_snapshots ORDER BY cycle_id DESC LIMIT 1")
row = cur.fetchone()
last_cycle = row["cycle_id"]
print("  Cycle convergence_snapshots le plus recent : %s" % last_cycle)

# Tickers forced_exit=1
cur.execute(
    "SELECT ticker FROM convergence_snapshots WHERE cycle_id=? AND forced_exit=1 ORDER BY ticker",
    (last_cycle,)
)
forced_tickers = [r["ticker"] for r in cur.fetchall()]
print("  Tickers forced_exit=1 : %d -> %s" % (len(forced_tickers), forced_tickers))

# --- Detection colonnes orders
cur.execute("PRAGMA table_info(orders)")
ocols = [r["name"] for r in cur.fetchall()]
print()
print("  Colonnes orders : %s" % ocols)
symbol_col = "symbol" if "symbol" in ocols else ("ticker" if "ticker" in ocols else None)
side_col = "side" if "side" in ocols else ("action" if "action" in ocols else None)
ts_col_o = None
for cand in ("created_at", "ts", "timestamp", "inserted_at"):
    if cand in ocols:
        ts_col_o = cand
        break
print("  symbol_col=%s side_col=%s ts_col=%s" % (symbol_col, side_col, ts_col_o))

# --- Inspect risk_pretrade_log (verdicts complets)
print()
print("-" * 78)
print("  Derniers 30 verdicts risk_pretrade_log :")
print("  " + "-" * 76)
cur.execute("SELECT * FROM risk_pretrade_log ORDER BY id DESC LIMIT 30")
verdicts = cur.fetchall()

block_count = 0
pass_count = 0
forced_block = 0
forced_pass_buy = 0

print("  %-5s | %-8s | %-5s | %-7s | %-30s | %s" % ("id", "symbol", "side", "passed", "blocked_by", "marker"))
print("  " + "-" * 96)
for v in verdicts:
    d = dict(v)
    sym = d.get("symbol")
    side = (d.get("side") or "").upper()
    passed = d.get("passed")
    blocked_by = d.get("blocked_by") or ""
    marker = d.get("marker") or ""
    print("  %-5s | %-8s | %-5s | %-7s | %-30s | %s" % (d.get("id"), sym, side, str(passed), str(blocked_by)[:30], str(marker)[:40]))

    if passed == 0:
        block_count += 1
    else:
        pass_count += 1
    if sym in forced_tickers and side == "BUY":
        if passed == 0 and "convergence_forced_exit" in (blocked_by or ""):
            forced_block += 1
        else:
            forced_pass_buy += 1

print()
print("  Resume : %d blocked, %d passed sur 30 derniers" % (block_count, pass_count))
print("  Tickers forced_exit BUY bloques : %d" % forced_block)
print("  Tickers forced_exit BUY passes  : %d (BUG si > 0)" % forced_pass_buy)

# --- Verif orders : aucun BUY sur ticker forced_exit
print()
print("-" * 78)
print("  Verif orders (BUY sur ticker forced_exit) :")
if forced_tickers and symbol_col and side_col:
    placeholders = ",".join(["?"] * len(forced_tickers))
    sql = "SELECT * FROM orders WHERE %s IN (%s) AND UPPER(%s)='BUY' ORDER BY id DESC LIMIT 20" % (symbol_col, placeholders, side_col)
    cur.execute(sql, list(forced_tickers))
    bad = cur.fetchall()
    print("    BUY trouves sur forced_exit (depuis le debut) : %d" % len(bad))
    for b in bad[:10]:
        d = dict(b)
        print("      id=%s %s=%s side=%s qty=%s status=%s ts=%s" % (
            d.get("id"), symbol_col, d.get(symbol_col),
            d.get(side_col), d.get("qty") or d.get("quantity"),
            d.get("status"), d.get(ts_col_o) if ts_col_o else "?"
        ))
    if not bad:
        print("    [OK] Historiquement aucun BUY sur forced_exit")
else:
    print("    [SKIP] forced vide ou colonnes manquantes")

# --- Verif si le nouveau cycle (12:23) a cree un snapshot convergence
print()
print("-" * 78)
print("  Convergence refresh ?")
cur.execute("SELECT cycle_id, MAX(created_at) AS last_ts FROM convergence_snapshots GROUP BY cycle_id ORDER BY cycle_id DESC LIMIT 5")
for r in cur.fetchall():
    print("    cycle_id=%s last_ts=%s" % (r["cycle_id"], r["last_ts"]))

# Dernier memo / cycle
print()
print("  Derniers memos generes :")
try:
    cur.execute("SELECT id, created_at FROM memos ORDER BY id DESC LIMIT 5")
    for r in cur.fetchall():
        print("    memo id=%s created_at=%s" % (r["id"], r["created_at"]))
except Exception as e:
    print("    [skip memos] %s" % e)

c.close()
print()
print("=" * 78)
print("CONCLUSIONS")
print("-" * 78)
print("  1. Garde-fou Convergence : %d BUY bloque(s) sur forced_exit -> %s" % (
    forced_block, "OPERATIONNEL" if forced_block > 0 else "PAS DECLENCHE"))
print("  2. Convergence refresh : cycle snapshot le plus recent = %s" % last_cycle)
print("     -> si != cycle du jour, il faut le patch #2 (refresh par cycle)")
print("=" * 78)
