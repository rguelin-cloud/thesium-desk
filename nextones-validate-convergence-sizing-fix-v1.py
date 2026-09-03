# -*- coding: utf-8 -*-
# nextones-validate-convergence-sizing-fix-v1.py
# Verifie patch [APPLY_CONVERGENCE_SIZING_FIX_V1] :
# - Marker present dans portfolio_construction_agent.py
# - apply_convergence_sizing lit correctement sizing_multiplier (sans regime)
# - Les 8 forced_exit du dernier cycle ressortent avec scaled=0

import os
import sys
import sqlite3
import importlib.util

PROD_ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
PCA_PATH = os.path.join(PROD_ROOT, "portfolio_construction_agent.py")
DB_PATH = os.path.join(PROD_ROOT, "thesium.db")
MARKER = "[APPLY_CONVERGENCE_SIZING_FIX_V1]"


def main():
    print("=" * 70)
    print("VALIDATION " + MARKER)
    print("=" * 70)

    # 1. Marker present
    with open(PCA_PATH, "r", encoding="utf-8-sig") as f:
        src = f.read()
    if MARKER not in src:
        print("[FAIL] Marker absent")
        sys.exit(1)
    print("[OK] Marker present")

    # 2. Import module
    if PROD_ROOT not in sys.path:
        sys.path.insert(0, PROD_ROOT)
    spec = importlib.util.spec_from_file_location("pca", PCA_PATH)
    pca = importlib.util.module_from_spec(spec)
    sys.modules["pca"] = pca
    spec.loader.exec_module(pca)
    print("[OK] Module importe")

    # 3. Dernier cycle_id avec forced_exit
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    row = c.execute(
        """SELECT cycle_id, MAX(created_at) as ts,
                  SUM(CASE WHEN forced_exit=1 THEN 1 ELSE 0 END) as n_forced,
                  COUNT(*) as n
           FROM convergence_snapshots
           GROUP BY cycle_id ORDER BY ts DESC LIMIT 1"""
    ).fetchone()
    if not row:
        print("[FAIL] Pas de cycle dans convergence_snapshots")
        sys.exit(1)
    cycle_id = row["cycle_id"]
    print("[OK] cycle_id=" + cycle_id + " n_tickers=" + str(row["n"]) + " n_forced=" + str(row["n_forced"]))

    # 4. Liste des forced_exit attendus
    forced_rows = c.execute(
        "SELECT ticker FROM convergence_snapshots WHERE cycle_id=? AND forced_exit=1",
        (cycle_id,),
    ).fetchall()
    forced_tickers = sorted([r["ticker"] for r in forced_rows])
    print("[OK] forced_exit attendus : " + str(forced_tickers))

    # 5. Allocations factices avec tous les tickers du cycle
    all_rows = c.execute(
        "SELECT ticker FROM convergence_snapshots WHERE cycle_id=?",
        (cycle_id,),
    ).fetchall()
    all_tickers = [r["ticker"] for r in all_rows]
    # weight uniforme arbitraire
    allocations = {t: 5.0 for t in all_tickers}

    # 6. Appel apply_convergence_sizing
    try:
        scaled, log = pca.apply_convergence_sizing(c, cycle_id, allocations)
    except Exception as e:
        print("[FAIL] apply_convergence_sizing exception : " + str(e))
        sys.exit(1)

    print("[OK] apply_convergence_sizing OK, log size=" + str(len(log)))

    # 7. Verifier que tous les forced_exit ont scaled=0
    passed = 0
    failed = 0
    for t in forced_tickers:
        s = scaled.get(t, "MISSING")
        meta = log.get(t, ("?", "?", "?", "?"))
        if s == 0 or s == 0.0:
            print("[OK]   " + t + " scaled=" + str(s) + " meta=" + str(meta))
            passed += 1
        else:
            print("[FAIL] " + t + " scaled=" + str(s) + " (attendu 0) meta=" + str(meta))
            failed += 1

    # 8. Sample non-forced
    print("\nNon-forced (sample 5) :")
    non_forced = [t for t in all_tickers if t not in forced_tickers]
    for t in non_forced[:5]:
        s = scaled.get(t, "MISSING")
        meta = log.get(t, ("?", "?", "?", "?"))
        print("       " + t + " scaled=" + str(s) + " meta=" + str(meta))

    print("\n" + "=" * 70)
    print("RESULTAT : " + str(passed) + "/" + str(len(forced_tickers)) + " forced_exit -> scaled=0")
    print("=" * 70)
    c.close()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
