# [TARGETS_CAPS_SMOOTHING_V1]
#
# Objectif : accelerer la convergence du portefeuille vers le budget MAINTAIN=70%.
#
# Modifications :
#   1. target_universe : augmente max_weight_pct
#        - equity : 5.0 -> 7.0
#        - crypto store_value/smart_chain (BTC, ETH, SOL) : 3.0 -> 5.0
#        - crypto oracle (LINK) : 2.0 -> 3.0
#        - equity auto_tech (TSLA) : 3.0 -> 5.0
#
#   2. target_construction_config.params_json :
#        - smoothing_max_delta_pct : 0.5 -> 2.0
#
# Theorique post-patch :
#   Sum max caps = 7*6 (AAPL, AMZN, GOOGL, MSFT, META, NVDA) + 5 (TSLA) + 5+5 (BTC, ETH)
#                + 3 (LINK) = 42 + 5 + 10 + 3 = 60% (proche du budget 70%)
#   Convergence : +2.0%/cycle au lieu de +0.5%
#
# Idempotent : detecte un flag dans la table risk_config (pas dispo) - on utilise
# une heuristique : si max_weight_pct AAPL == 7.0 -> deja patche.
#
# Backup auto : copie thesium.db -> thesium.db.bak.YYYYMMDD-HHMMSS

import sqlite3
from pathlib import Path
import shutil
import time
import json

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
MARKER = "[TARGETS_CAPS_SMOOTHING_V1]"


def main():
    if not DB.exists():
        print(f"[ERR] {DB} introuvable")
        return

    # Backup
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = DB.with_suffix(f".db.bak.{ts}")
    shutil.copy2(DB, backup)
    print(f"[OK] Backup DB : {backup}")

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Idempotence : si AAPL deja a 7.0, on skip caps
    r = cur.execute("SELECT max_weight_pct FROM target_universe WHERE ticker='AAPL'").fetchone()
    aapl_max = r["max_weight_pct"] if r else None
    caps_done = (aapl_max is not None and aapl_max >= 7.0)
    print(f"[INFO] AAPL max_weight_pct actuel : {aapl_max}")
    if caps_done:
        print("[INFO] Caps deja patches (AAPL >= 7.0), skip section caps.")

    print()
    print("=" * 70)
    print("[1] Update target_universe.max_weight_pct")
    print("=" * 70)
    if not caps_done:
        updates = [
            # equity 5.0 -> 7.0
            ("AAPL",  7.0),
            ("AMZN",  7.0),
            ("GOOGL", 7.0),
            ("MSFT",  7.0),
            ("META",  7.0),
            ("NVDA",  7.0),
            # equity 3.0 -> 5.0 (TSLA)
            ("TSLA",  5.0),
            # crypto 3.0 -> 5.0 (BTC, ETH, SOL)
            ("BTC",   5.0),
            ("ETH",   5.0),
            ("SOL",   5.0),
            # crypto 2.0 -> 3.0 (LINK)
            ("LINK",  3.0),
        ]
        for ticker, new_max in updates:
            r = cur.execute("SELECT max_weight_pct FROM target_universe WHERE ticker=?",
                            (ticker,)).fetchone()
            old = r["max_weight_pct"] if r else None
            if old is None:
                print(f"  [SKIP] {ticker} : non trouve dans target_universe")
                continue
            cur.execute("UPDATE target_universe SET max_weight_pct=? WHERE ticker=?",
                        (new_max, ticker))
            print(f"  [OK] {ticker:<6} : {old:.2f} -> {new_max:.2f}")
    else:
        print("  (deja patche)")

    print()
    print("=" * 70)
    print("[2] Update target_construction_config.params_json.smoothing_max_delta_pct")
    print("=" * 70)
    r = cur.execute("SELECT params_json FROM target_construction_config WHERE id=1").fetchone()
    if r:
        cfg = json.loads(r["params_json"])
        old_sm = cfg.get("smoothing_max_delta_pct")
        print(f"  [INFO] smoothing_max_delta_pct actuel : {old_sm}")
        if old_sm == 2.0:
            print("  [INFO] Smoothing deja a 2.0, skip.")
        else:
            cfg["smoothing_max_delta_pct"] = 2.0
            cur.execute("UPDATE target_construction_config SET params_json=?, updated_at=? WHERE id=1",
                        (json.dumps(cfg), time.strftime("%Y-%m-%d %H:%M:%S")))
            print(f"  [OK] smoothing_max_delta_pct : {old_sm} -> 2.0")
    else:
        print("  [ERR] target_construction_config id=1 introuvable")

    con.commit()

    # Validation
    print()
    print("=" * 70)
    print("[VALIDATION]")
    print("=" * 70)
    rows = cur.execute("""SELECT ticker, max_weight_pct FROM target_universe
                          ORDER BY max_weight_pct DESC, ticker""").fetchall()
    total_cap = 0.0
    for r in rows:
        print(f"  {r['ticker']:<6} max_weight_pct = {r['max_weight_pct']:.2f}%")
        total_cap += r['max_weight_pct'] or 0
    print(f"\n  Sum max caps : {total_cap:.2f}% (theorique max)")

    r = cur.execute("SELECT params_json FROM target_construction_config WHERE id=1").fetchone()
    cfg = json.loads(r["params_json"])
    print(f"\n  smoothing_max_delta_pct = {cfg.get('smoothing_max_delta_pct')}")
    print(f"  budget_maintain         = {cfg.get('budget_maintain')}")

    con.close()

    print()
    print("=" * 70)
    print(f"[SUCCESS] {MARKER}")
    print("=" * 70)
    print("""
Prochaines etapes :
  1. Restart uvicorn (les caps sont lus a chaque cycle de construction)
  2. Run Decision Cycle 1 fois -> les targets monteront de +2%
     (ex: 2.5% -> 4.5% pour les equity, 2.5% -> 4.5% pour BTC/ETH)
  3. Run a nouveau -> +2% encore -> les ordres BUY se declencheront
     car delta_target_pct > DRIFT_TOLERANCE_PCT (0.3%)

Convergence attendue (4-5 cycles) :
  - equity AAPL/MSFT/META/NVDA/GOOGL/AMZN : 2.5% -> ~7% chacun (cap)
  - crypto BTC/ETH                        : 2.5% -> ~5% chacun (cap)
  - TSLA                                  : 2.5% -> ~5% (cap)
  - LINK                                  : 2.0% -> ~3% (cap)
  - Total                                 : ~60% NAV investi (sur cible 70%)
""")


if __name__ == "__main__":
    main()
