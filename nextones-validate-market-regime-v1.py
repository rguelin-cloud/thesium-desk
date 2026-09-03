# -*- coding: utf-8 -*-
"""
[VALIDATE_MARKET_REGIME_V1]
Validation E2E du MVP market_regime_v1.

Verifie :
  1. Table market_regime_log existe avec bonnes colonnes
  2. Colonnes equity_regime/crypto_regime dans regime_log
  3. Module market_regime_v1.py importable et detect_market_regime() retourne un dict valide
  4. Patch d'injection present dans execution_engine.py
  5. Test runtime : appel direct de detect_market_regime sur la DB de prod
  6. Affiche caps qui seraient appliques sur le prochain cycle
"""
import os
import sys
import sqlite3
import json

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
EE_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"

print("=" * 80)
print("[VALIDATE_MARKET_REGIME_V1] DEBUT")
print("=" * 80)

# 1. Schema
print("\n1. Verification schema DB")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
if "market_regime_log" in tables:
    cols = [r["name"] for r in cur.execute("PRAGMA table_info(market_regime_log)").fetchall()]
    expected = {"id", "cycle_id", "asset_class", "regime", "vix_value",
                "realized_vol_pct", "drawdown_5d_pct", "score",
                "buy_mult", "sell_mult", "convergence_thresh",
                "details_json", "notes", "created_at"}
    missing = expected - set(cols)
    if missing:
        print(f"  [FAIL] market_regime_log : colonnes manquantes = {missing}")
    else:
        print(f"  [OK] market_regime_log : {len(cols)} colonnes")
else:
    print(f"  [FAIL] Table market_regime_log absente")

rl_cols = [r["name"] for r in cur.execute("PRAGMA table_info(regime_log)").fetchall()]
expected_new = {"equity_regime", "crypto_regime", "equity_buy_mult",
                "equity_sell_mult", "crypto_buy_mult", "crypto_sell_mult"}
missing = expected_new - set(rl_cols)
if missing:
    print(f"  [FAIL] regime_log : nouvelles colonnes manquantes = {missing}")
else:
    print(f"  [OK] regime_log : nouvelles colonnes presentes")

# 2. Module importable
print("\n2. Import module market_regime_v1")
sys.path.insert(0, r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
try:
    import market_regime_v1
    print(f"  [OK] market_regime_v1 importable")
    funcs = ["detect_market_regime", "log_market_regime", "get_caps_for_proposal"]
    for fn in funcs:
        if hasattr(market_regime_v1, fn):
            print(f"  [OK] fonction {fn} presente")
        else:
            print(f"  [FAIL] fonction {fn} absente")
except Exception as e:
    print(f"  [FAIL] Import a echoue : {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Patch present
print("\n3. Verification patch execution_engine.py")
if os.path.exists(EE_PATH):
    with open(EE_PATH, "r", encoding="utf-8-sig", errors="ignore") as f:
        ee_content = f.read()
    if "PATCH_MARKET_REGIME_INJECTION_V1" in ee_content:
        print(f"  [OK] Marker PATCH_MARKET_REGIME_INJECTION_V1 present")
    else:
        print(f"  [FAIL] Marker absent dans execution_engine.py")
    # Compter les occurrences pour s'assurer une seule injection
    n = ee_content.count("PATCH_MARKET_REGIME_INJECTION_V1")
    print(f"  Occurrences marker : {n}")
else:
    print(f"  [FAIL] {EE_PATH} introuvable")

# 4. Appel runtime
print("\n4. Test runtime detect_market_regime()")
try:
    info = market_regime_v1.detect_market_regime(con)
    print(f"  [OK] Appel reussi")
    print(f"\n  === EQUITY ===")
    eq = info.get("equity", {})
    print(f"    regime           : {eq.get('regime')}")
    print(f"    vix_value        : {eq.get('vix_value')}")
    print(f"    realized_vol_pct : {eq.get('realized_vol_pct')}")
    print(f"    drawdown_5d_pct  : {eq.get('drawdown_5d_pct')}")
    print(f"    score            : {eq.get('score')}")
    print(f"    buy_mult         : {eq.get('buy_mult')}")
    print(f"    sell_mult        : {eq.get('sell_mult')}")
    print(f"    convergence_th   : {eq.get('convergence_thresh')}")
    print(f"    fallback         : {eq.get('fallback')}")
    print(f"    details          : {eq.get('details')}")
    print(f"\n  === CRYPTO ===")
    cr = info.get("crypto", {})
    print(f"    regime           : {cr.get('regime')}")
    print(f"    realized_vol_pct : {cr.get('realized_vol_pct')}")
    print(f"    drawdown_5d_pct  : {cr.get('drawdown_5d_pct')}")
    print(f"    score            : {cr.get('score')}")
    print(f"    buy_mult         : {cr.get('buy_mult')}")
    print(f"    sell_mult        : {cr.get('sell_mult')}")
    print(f"    convergence_th   : {cr.get('convergence_thresh')}")
    print(f"    fallback         : {cr.get('fallback')}")
    print(f"    details          : {cr.get('details')}")
except Exception as e:
    print(f"  [FAIL] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. Test log
print("\n5. Test log_market_regime (insert puis cleanup)")
TEST_CYCLE = "TEST_VALIDATE_MR_V1"
try:
    market_regime_v1.log_market_regime(con, TEST_CYCLE, info)
    n_rows = cur.execute(
        "SELECT COUNT(*) FROM market_regime_log WHERE cycle_id = ?",
        (TEST_CYCLE,)
    ).fetchone()[0]
    print(f"  [OK] {n_rows} ligne(s) inseree(s) en test")
    # Lecture
    rows = cur.execute(
        "SELECT * FROM market_regime_log WHERE cycle_id = ?",
        (TEST_CYCLE,)
    ).fetchall()
    for r in rows:
        print(f"    {r['asset_class']:<8} {r['regime']:<8} "
              f"buy_x{r['buy_mult']} sell_x{r['sell_mult']} "
              f"score={r['score']}")
    # Cleanup
    con.execute("DELETE FROM market_regime_log WHERE cycle_id = ?", (TEST_CYCLE,))
    con.commit()
    print(f"  [OK] Cleanup test rows")
except Exception as e:
    print(f"  [FAIL] {e}")
    import traceback
    traceback.print_exc()

# 6. get_caps_for_proposal sur chaque asset_class
print("\n6. Test get_caps_for_proposal()")
for ac in ("equity", "crypto", "etf"):
    caps = market_regime_v1.get_caps_for_proposal(info, ac)
    print(f"  asset_class={ac:<8} regime={caps['regime']:<8} "
          f"buy_mult={caps['buy_mult']} sell_mult={caps['sell_mult']} "
          f"convergence_thresh={caps['convergence_thresh']}")

con.close()
print()
print("=" * 80)
print("[VALIDATE_MARKET_REGIME_V1] FIN")
print("=" * 80)
print("\nProchaine etape : redemarrer api_server et lancer un Run Cycle.")
print("Les logs devraient afficher [market_regime] et la table market_regime_log")
print("doit etre remplie.")
