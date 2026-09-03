# -*- coding: utf-8 -*-
# nextones-validate-convergence-block-prod-v1.py
# Marker : [VALIDATE_CONVERGENCE_BLOCK_PROD_V1]
#
# But : verifier en prod que le garde-fou [CONVERGENCE_FORCED_EXIT_BLOCK_V1]
# bloque bien les BUY sur les tickers forced_exit=1 du dernier cycle.
#
# Lit :
#   - convergence_snapshots : derniers forced_exit=1 par cycle
#   - risk_check_result (ou table equivalente) : derniers verdicts
#   - orders : ce qui a ete inserre (pour confirmer aucun BUY sur forced_exit)

import os
import sys
import sqlite3
import json
from collections import defaultdict

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

print()
print("=" * 78)
print("VALIDATION PROD [CONVERGENCE_FORCED_EXIT_BLOCK_V1]")
print("-" * 78)

if not os.path.exists(DB):
    print("  [KO] DB introuvable : %s" % DB)
    sys.exit(1)

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
cur = c.cursor()

# --- 1) Dernier cycle_id dans convergence_snapshots
cur.execute("SELECT cycle_id, COUNT(*) AS n FROM convergence_snapshots GROUP BY cycle_id ORDER BY cycle_id DESC LIMIT 3")
rows = cur.fetchall()
if not rows:
    print("  [KO] convergence_snapshots vide")
    sys.exit(2)

print("  Derniers cycles dans convergence_snapshots :")
for r in rows:
    print("    %s : %d tickers" % (r["cycle_id"], r["n"]))

last_cycle = rows[0]["cycle_id"]
print()
print("  Cycle analyse : %s" % last_cycle)
print("-" * 78)

# --- 2) Tickers forced_exit=1 dans ce cycle
cur.execute(
    "SELECT ticker, direction_consensus, sizing_multiplier, forced_exit "
    "FROM convergence_snapshots WHERE cycle_id=? AND forced_exit=1 ORDER BY ticker",
    (last_cycle,)
)
forced = cur.fetchall()
forced_tickers = [r["ticker"] for r in forced]
print("  Tickers forced_exit=1 : %d" % len(forced))
for r in forced:
    print("    %-8s dir=%s mult=%s" % (r["ticker"], r["direction_consensus"], r["sizing_multiplier"]))

if not forced:
    print()
    print("  [INFO] Aucun ticker forced_exit=1 dans ce cycle.")
    print("  Garde-fou ne pouvait pas se declencher. Pas une preuve d'echec.")

# --- 3) Inspecter risk_check_result (ou risk_pretrade_log)
print()
print("-" * 78)
print("  Tables risk*/orders :")
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'risk%' OR name LIKE 'orders%')")
for r in cur.fetchall():
    print("    %s" % r["name"])

# Schema de risk_check_result
risk_table = None
for candidate in ("risk_check_result", "risk_pretrade_log", "risk_results"):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (candidate,))
    if cur.fetchone():
        risk_table = candidate
        break

if not risk_table:
    print("  [KO] Aucune table risk_check_result/risk_pretrade_log/risk_results")
    sys.exit(3)

print()
print("  Table risk utilisee : %s" % risk_table)
cur.execute("PRAGMA table_info(%s)" % risk_table)
cols = [r["name"] for r in cur.fetchall()]
print("  Colonnes : %s" % cols)

# --- 4) Derniers verdicts sur ce cycle
# On essaie plusieurs champs possibles
cycle_col = None
for cand in ("cycle_id", "cycle", "run_id"):
    if cand in cols:
        cycle_col = cand
        break

print()
print("-" * 78)
if cycle_col:
    cur.execute(
        "SELECT * FROM %s WHERE %s=? ORDER BY rowid DESC LIMIT 50" % (risk_table, cycle_col),
        (last_cycle,)
    )
else:
    print("  [WARN] Pas de colonne cycle_id dans %s, on prend les 30 derniers" % risk_table)
    cur.execute("SELECT * FROM %s ORDER BY rowid DESC LIMIT 30" % risk_table)

verdicts = cur.fetchall()
print("  Verdicts trouves : %d" % len(verdicts))

# --- 5) Regrouper par ticker + verifier blocked_by
by_ticker = defaultdict(list)
for v in verdicts:
    d = dict(v)
    tk = d.get("ticker") or d.get("symbol") or "?"
    by_ticker[tk].append(d)

print()
print("  Verdicts par ticker forced_exit=1 :")
print("  " + "-" * 76)
found_block = 0
missing = []
for tk in forced_tickers:
    rows_t = by_ticker.get(tk, [])
    if not rows_t:
        missing.append(tk)
        print("    %-8s : aucun verdict (pas propose ce cycle)" % tk)
        continue
    last_v = rows_t[0]
    # Champs interessants
    side = last_v.get("side") or last_v.get("action") or "?"
    verdict = last_v.get("verdict") or last_v.get("decision") or last_v.get("status") or "?"
    blocked_by = last_v.get("blocked_by") or last_v.get("reason") or ""
    details = last_v.get("details") or last_v.get("reason_detail") or ""
    if "convergence_forced_exit" in (blocked_by or "") or "convergence_forced_exit" in (details or ""):
        found_block += 1
        marker = "[OK]"
    elif str(verdict).upper() in ("BLOCK", "BLOCKED", "REJECT", "REJECTED"):
        marker = "[BLOCKED autre cause]"
    else:
        marker = "[PASS - BUG possible]"
    print("    %-8s %s | side=%-5s verdict=%-10s blocked_by=%s" % (tk, marker, str(side), str(verdict)[:10], str(blocked_by)[:40]))

print()
print("-" * 78)
print("  BUY bloques par convergence_forced_exit : %d / %d" % (found_block, len(forced_tickers)))
if missing:
    print("  Tickers forced_exit=1 sans verdict : %s" % ", ".join(missing))

# --- 6) Verifier orders : aucun BUY sur ticker forced_exit
print()
print("-" * 78)
print("  Verif orders (aucun BUY sur ticker forced_exit) :")
cur.execute("PRAGMA table_info(orders)")
ocols = [r["name"] for r in cur.fetchall()]
ts_col = "created_at" if "created_at" in ocols else ("ts" if "ts" in ocols else None)
cycle_col_o = "cycle_id" if "cycle_id" in ocols else None
side_col = "side" if "side" in ocols else ("action" if "action" in ocols else None)

if forced_tickers and side_col:
    placeholders = ",".join(["?"] * len(forced_tickers))
    where_cycle = ""
    params = list(forced_tickers)
    if cycle_col_o:
        where_cycle = " AND %s=?" % cycle_col_o
        params.append(last_cycle)
    sql = "SELECT * FROM orders WHERE ticker IN (%s) AND UPPER(%s)='BUY'%s ORDER BY rowid DESC LIMIT 20" % (placeholders, side_col, where_cycle)
    cur.execute(sql, params)
    bad = cur.fetchall()
    print("    Ordres BUY sur tickers forced_exit dans ce cycle : %d" % len(bad))
    if bad:
        print("    [KO] Le garde-fou n'a pas empeche ces BUY :")
        for b in bad:
            d = dict(b)
            print("      id=%s ticker=%s qty=%s status=%s" % (d.get("id"), d.get("ticker"), d.get("qty") or d.get("quantity"), d.get("status")))
    else:
        print("    [OK] Aucun BUY passe sur forced_exit=1")
else:
    print("    [SKIP] forced_tickers vide ou pas de colonne side")

c.close()
print()
print("=" * 78)
if found_block > 0 and not missing:
    print("VERDICT : GARDE-FOU OPERATIONNEL EN PROD")
elif not forced_tickers:
    print("VERDICT : INDETERMINE (cycle sans forced_exit, refaire un cycle)")
else:
    print("VERDICT : A INVESTIGUER (blocks manquants ou pas marques convergence_forced_exit)")
print("=" * 78)
