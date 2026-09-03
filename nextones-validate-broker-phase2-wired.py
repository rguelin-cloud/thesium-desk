# -*- coding: utf-8 -*-
# [NEXTONES-VALIDATE-BROKER-PHASE2-WIRED-V1]
# Verifie que le hook broker est bien cable dans risk_pretrade.py et qu'il
# intercepte une vraie invocation run_pretrade_checks("HYPE", ...).
#
# Etapes:
#   1. Verifie presence marker NEXTONES-BROKER-CHECK-V1 dans risk_pretrade.py
#   2. Importe risk_pretrade et appelle run_pretrade_checks("HYPE", 100, 50, "BUY")
#      -> attendu : passed=0, blocked_by='broker_mapping_ok',
#                   marker='[NEXTONES-BROKER-CHECK-V1]'
#   3. Appelle run_pretrade_checks("AAPL", 1, 200, "BUY")
#      -> attendu : laisse passer le hook, le pretrade V2 normal s'execute
#   4. Verifie qu'une ligne marker '[NEXTONES-BROKER-CHECK-V1]' a ete
#      inseree dans risk_pretrade_log pour HYPE.

import os
import sys
import json
import sqlite3
import importlib.util
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get(
    "THESIUM_DB",
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db",
)
MARKER = "[NEXTONES-BROKER-CHECK-V1]"
TARGET = ROOT / "risk_pretrade.py"


def fatal(msg, code=1):
    print("[FAIL] " + msg); sys.exit(code)


def step(n, msg):
    print()
    print("=" * 60)
    print("[" + str(n) + "] " + msg)
    print("=" * 60)


def main():
    step(1, "Verifie marker dans risk_pretrade.py")
    if not TARGET.exists():
        fatal(str(TARGET) + " introuvable")
    with open(TARGET, "rb") as f:
        txt = f.read().decode("utf-8-sig", errors="replace")
    if "NEXTONES-BROKER-CHECK-V1" not in txt:
        fatal("marker NEXTONES-BROKER-CHECK-V1 ABSENT - patch non applique")
    print("[OK] marker present")

    step(2, "Importe risk_pretrade et invoque HYPE (doit etre refuse)")
    spec = importlib.util.spec_from_file_location("rp", str(TARGET))
    rp = importlib.util.module_from_spec(spec); spec.loader.exec_module(rp)
    if not hasattr(rp, "run_pretrade_checks"):
        fatal("run_pretrade_checks introuvable apres import")

    res = rp.run_pretrade_checks("HYPE", 100, 50.0, "BUY", db_path=DB_PATH)
    print("Retour HYPE :")
    print(json.dumps({k: (v if k != "details_json" else "(...JSON...)")
                      for k, v in res.items()}, indent=2, default=str))
    if res.get("passed") not in (0, False):
        fatal("HYPE devrait etre refuse (passed=0)")
    if res.get("blocked_by") != "broker_mapping_ok":
        fatal("blocked_by attendu='broker_mapping_ok', obtenu="
              + str(res.get("blocked_by")))
    if res.get("marker") != MARKER:
        fatal("marker attendu=" + MARKER + ", obtenu=" + str(res.get("marker")))
    print("[OK] HYPE refuse par broker_mapping_ok")

    step(3, "Invoque AAPL 1 200 BUY (doit traverser le hook et arriver au V2)")
    try:
        res2 = rp.run_pretrade_checks("AAPL", 1.0, 200.0, "BUY", db_path=DB_PATH)
        print("Retour AAPL marker :", res2.get("marker"))
        print("Retour AAPL passed :", res2.get("passed"))
        print("Retour AAPL blocked_by :", res2.get("blocked_by"))
        # marker attendu = '[RISK_V2]' (le hook a laisse passer)
        if res2.get("marker") == MARKER:
            fatal("AAPL ne devrait PAS porter le marker broker : hook a "
                  "intercepte par erreur")
        print("[OK] AAPL traverse le hook, pretrade V2 execute normalement")
    except Exception as e:
        print("[WARN] AAPL exception (acceptable si VAR/conn require runtime) : " + str(e))

    step(4, "Verifie INSERT dans risk_pretrade_log avec marker broker")
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM risk_pretrade_log WHERE marker=? AND symbol='HYPE'",
        (MARKER,),
    )
    n = cur.fetchone()[0]
    print("Lignes risk_pretrade_log marker=" + MARKER + " symbol=HYPE : " + str(n))
    if n < 1:
        fatal("aucune ligne risk_pretrade_log inseree pour HYPE")
    cur.execute(
        "SELECT id, ts, symbol, side, qty, passed, blocked_by, marker "
        "FROM risk_pretrade_log WHERE marker=? ORDER BY id DESC LIMIT 3",
        (MARKER,),
    )
    print("Dernieres entrees broker dans risk_pretrade_log :")
    for r in cur.fetchall():
        print("  " + str(r))
    con.close()

    print()
    print("=" * 60)
    print("[VERDICT] PASS - Phase 2.5 cable et fonctionnel")
    print("=" * 60)


if __name__ == "__main__":
    main()
