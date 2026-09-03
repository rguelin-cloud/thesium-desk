# -*- coding: utf-8 -*-
# nextones-test-risk-v2-direct.py
# Test direct du module risk_pretrade pour valider le fix [RISK_V2_DBLOCK_FIX_V2]
# Reproduit le scenario du lock : une conn ouverte par execution_engine + appel risk_pretrade
#
# Verdict :
#   - SANS conn : si le lock se reproduit -> fix necessaire (confirmation du bug)
#   - AVEC conn : doit passer sans lock -> fix valide

import os
import sys
import time
import json
import sqlite3
import traceback

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

if PROD not in sys.path:
    sys.path.insert(0, PROD)

print()
print("=" * 72)
print("[1] Import risk_pretrade et inspection signature")
print("-" * 72)
try:
    import risk_pretrade
    import inspect
    sig = inspect.signature(risk_pretrade.run_pretrade_checks)
    print("  Module : %s" % risk_pretrade.__file__)
    print("  Signature : run_pretrade_checks%s" % str(sig))
    has_conn_param = "conn" in sig.parameters
    print("  Param 'conn' present : %s" % has_conn_param)
    if not has_conn_param:
        print("  [KO] Le patch [RISK_V2_DBLOCK_FIX_V2] n'est PAS actif dans le module charge.")
        print("       Probablement : API non redemarree OU autre version de risk_pretrade en path.")
        sys.exit(2)
except Exception as e:
    print("  [KO] Import a echoue : %s" % e)
    traceback.print_exc()
    sys.exit(3)

print()
print("=" * 72)
print("[2] Trouver un ticker existant pour le test (SOL prioritaire)")
print("-" * 72)
conn_probe = sqlite3.connect(DB_PATH, timeout=5.0)
conn_probe.row_factory = sqlite3.Row
row = conn_probe.execute(
    "SELECT id, ticker FROM instruments WHERE ticker IN ('SOL','BTC','ETH','LINK','ZEC') ORDER BY CASE ticker WHEN 'SOL' THEN 1 WHEN 'BTC' THEN 2 WHEN 'ETH' THEN 3 ELSE 9 END LIMIT 1"
).fetchone()
if not row:
    print("  [KO] Aucun ticker test trouve.")
    conn_probe.close()
    sys.exit(4)
test_ticker = row["ticker"]
test_inst_id = row["id"]
print("  Ticker selectionne : %s (instrument_id=%s)" % (test_ticker, test_inst_id))

# Recuperer un prix recent pour le test
prow = conn_probe.execute(
    "SELECT close FROM prices WHERE instrument_id = ? ORDER BY date DESC LIMIT 1",
    (test_inst_id,)
).fetchone()
test_price = float(prow["close"]) if prow and prow["close"] else 100.0
print("  Prix test : %.4f" % test_price)
conn_probe.close()

test_qty = 1.0
test_side = "buy"

print()
print("=" * 72)
print("[3] Test SANS conn (mode legacy - ouvre 2e connexion)")
print("-" * 72)
print("  Appel : run_pretrade_checks('%s', %.2f, %.4f, '%s')" % (test_ticker, test_qty, test_price, test_side))
t0 = time.perf_counter()
try:
    res_no_conn = risk_pretrade.run_pretrade_checks(test_ticker, test_qty, test_price, test_side)
    dt = (time.perf_counter() - t0) * 1000
    print("  [OK] Duree : %.1f ms" % dt)
    print("  passed     : %s" % res_no_conn.get("passed"))
    print("  blocked_by : %s" % res_no_conn.get("blocked_by"))
    print("  reasons    : %s" % json.dumps(res_no_conn.get("reasons", []), ensure_ascii=False)[:200])
except sqlite3.OperationalError as e:
    dt = (time.perf_counter() - t0) * 1000
    if "locked" in str(e).lower():
        print("  [LOCK] Duree : %.1f ms - 'database is locked' (mode legacy reproduit le bug)" % dt)
    else:
        print("  [ERR ] OperationalError : %s" % e)
except Exception as e:
    dt = (time.perf_counter() - t0) * 1000
    print("  [ERR ] %s : %s" % (type(e).__name__, e))

print()
print("=" * 72)
print("[4] Test AVEC conn partagee (mode [RISK_V2_DBLOCK_FIX_V2])")
print("-" * 72)
print("  Simulation du scenario execution_engine : conn ouverte + transaction active")
shared = sqlite3.connect(DB_PATH, timeout=5.0)
shared.row_factory = sqlite3.Row
shared.execute("PRAGMA busy_timeout=30000")
# On simule une transaction en cours cote execution_engine
shared.execute("BEGIN IMMEDIATE")
print("  [SETUP] BEGIN IMMEDIATE acquired sur shared conn")

print("  Appel : run_pretrade_checks('%s', %.2f, %.4f, '%s', conn=shared)" % (test_ticker, test_qty, test_price, test_side))
t0 = time.perf_counter()
try:
    res_with_conn = risk_pretrade.run_pretrade_checks(test_ticker, test_qty, test_price, test_side, conn=shared)
    dt = (time.perf_counter() - t0) * 1000
    print("  [OK] Duree : %.1f ms" % dt)
    print("  passed     : %s" % res_with_conn.get("passed"))
    print("  blocked_by : %s" % res_with_conn.get("blocked_by"))
    print("  reasons    : %s" % json.dumps(res_with_conn.get("reasons", []), ensure_ascii=False)[:300])
    details = res_with_conn.get("details", {})
    if details:
        print("  details    : %s" % json.dumps(details, ensure_ascii=False, default=str)[:400])
except sqlite3.OperationalError as e:
    dt = (time.perf_counter() - t0) * 1000
    if "locked" in str(e).lower():
        print("  [LOCK] Duree : %.1f ms - 'database is locked' (FIX NE FONCTIONNE PAS)" % dt)
    else:
        print("  [ERR ] OperationalError : %s" % e)
except Exception as e:
    dt = (time.perf_counter() - t0) * 1000
    print("  [ERR ] %s : %s" % (type(e).__name__, e))
    traceback.print_exc()

# Cleanup
try:
    shared.rollback()
    shared.close()
    print("  [CLEAN] shared conn rollback + close")
except Exception:
    pass

print()
print("=" * 72)
print("VERDICT")
print("-" * 72)
print("  - Si [4] passe sans lock : fix [RISK_V2_DBLOCK_FIX_V2] OPERATIONNEL")
print("  - Si [4] echoue en lock  : fix incomplet, investiguer ouverture 2e conn dans run_pretrade_checks")
print("=" * 72)
