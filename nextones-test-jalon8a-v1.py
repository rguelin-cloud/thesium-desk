# -*- coding: utf-8 -*-
# nextones-test-jalon8a-v1.py
# Jalon 8A - Tests unitaires : no look-ahead + slippage cap
#
# Tests :
#   1. test_market_data_no_lookahead    : aucune ligne avec date > day_t
#   2. test_fred_no_lookahead           : idem sur macro_history
#   3. test_fill_simulator_slippage_cap : slippage_bps <= 5
#   4. test_pplx_neutral_stub           : scores fixes 50/100
#   5. test_replay_schema_present       : 6 tables replay_* existent
#
# Usage : py -3.13 .\nextones-test-jalon8a-v1.py

import os
import sys
import sqlite3
import traceback
from datetime import datetime

# Force le mode replay pour eviter les warnings
os.environ["NEXTONES_REPLAY_MODE"] = "1"

# Import des modules jalon 8A (doivent etre dans le meme dossier)
try:
    from replay_adapters import MarketDataAdapter, FREDAdapter, PPLXNeutralAdapter
    from fill_simulator import simulate_fill, compute_slippage_bps, SLIPPAGE_CAP_BPS
except ImportError as e:
    print(f"[FAIL] Import jalon 8A modules: {e}")
    sys.exit(1)

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

REPLAY_TABLES = [
    "replay_runs",
    "replay_cycles",
    "replay_orders",
    "replay_positions",
    "replay_nav",
    "replay_regime_log",
]

# Date arbitraire au milieu de la fenetre 24 mois pour les tests
# Choix : lundi 16 juin 2025 (jour ouvre, pour que get_close_at retourne une valeur)
TEST_DAY = "2025-06-16"


def _result(name: str, ok: bool, msg: str = ""):
    tag = "PASS" if ok else "FAIL"
    bar = "OK  " if ok else "ERR "
    print(f"  [{bar}] {name:45s} {tag}  {msg}")
    return ok


def test_replay_schema_present():
    print("\n[TEST 1] Schema replay_* present")
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'replay_%'"
    )
    found = {r[0] for r in cur.fetchall()}
    conn.close()

    all_ok = True
    for t in REPLAY_TABLES:
        ok = t in found
        all_ok &= _result(f"table {t}", ok, "" if ok else "MANQUANTE")
    return all_ok


def test_market_data_no_lookahead():
    print("\n[TEST 2] MarketDataAdapter : no look-ahead")
    adapter = MarketDataAdapter(DB_PATH)
    rows = adapter.get_prices_up_to(TEST_DAY, ticker="SPY")
    if not rows:
        return _result("SPY rows <= TEST_DAY", False, "0 rows retournes")
    max_date = max(r["date"] for r in rows)
    ok = max_date <= TEST_DAY
    _result(
        f"max(date) <= {TEST_DAY}",
        ok,
        f"max_date={max_date} (n={len(rows)})",
    )
    # Verifie tous les tickers
    rows_all = adapter.get_prices_up_to(TEST_DAY)
    max_all = max(r["date"] for r in rows_all)
    ok2 = max_all <= TEST_DAY
    _result(
        "max(date) tous tickers <= TEST_DAY",
        ok2,
        f"max={max_all} n={len(rows_all)}",
    )
    # get_close_at
    px = adapter.get_close_at(TEST_DAY, "SPY")
    _result("get_close_at SPY", px is not None and px > 0, f"close={px}")
    # get_open_after (J+1)
    bar = adapter.get_open_after(TEST_DAY, "SPY")
    ok3 = bar is not None and bar["date"] > TEST_DAY
    _result(
        "get_open_after SPY > TEST_DAY",
        ok3,
        f"date={bar['date'] if bar else None}",
    )
    return ok and ok2 and ok3


def test_fred_no_lookahead():
    print("\n[TEST 3] FREDAdapter : no look-ahead")
    adapter = FREDAdapter(DB_PATH)
    rows = adapter.get_macro_up_to(TEST_DAY, series_id="VIX")
    if not rows:
        return _result("VIX rows <= TEST_DAY", False, "0 rows (FRED pas fetche ?)")
    max_date = max(r["date"] for r in rows)
    ok = max_date <= TEST_DAY
    _result(
        f"max(date) VIX <= {TEST_DAY}",
        ok,
        f"max={max_date} n={len(rows)}",
    )
    vix = adapter.get_value_at(TEST_DAY, "VIX")
    _result("get_value_at VIX", vix is not None and vix > 0, f"vix={vix}")
    return ok


def test_pplx_neutral_stub():
    print("\n[TEST 4] PPLXNeutralAdapter : scores fixes 50")
    pplx = PPLXNeutralAdapter()
    a = pplx.get_crypto_context(TEST_DAY, "BTC")
    b = pplx.get_factor_quality(TEST_DAY, "SPY")
    c = pplx.get_geo_context(TEST_DAY)
    d = pplx.get_memo_summary(TEST_DAY, "SPY")
    e = pplx.get_thesis_challenge(TEST_DAY, "SPY")
    checks = [
        ("crypto.score=50", a["score"] == 50.0),
        ("factor.score=50", b["score"] == 50.0),
        ("geo.score=50", c["score"] == 50.0),
        ("memo.verdict=neutral", d["verdict"] == "neutral"),
        ("thesis.score=50", e["score"] == 50.0),
        ("crypto.stub=True", a["stub"] is True),
    ]
    all_ok = True
    for name, ok in checks:
        all_ok &= _result(name, ok)
    return all_ok


def test_fill_simulator_slippage_cap():
    print("\n[TEST 5] fill_simulator : slippage cape a 5 bps")
    # Test pur math
    slip = compute_slippage_bps(qty=1e12, volume=1.0)  # volontairement enorme
    ok1 = slip <= SLIPPAGE_CAP_BPS + 1e-9
    _result(f"slip enorme cape (slip={slip:.4f})", ok1, f"cap={SLIPPAGE_CAP_BPS}")

    slip2 = compute_slippage_bps(qty=10, volume=1e9)
    ok2 = 0 <= slip2 < 1.0
    _result(f"slip petit (slip={slip2:.6f})", ok2)

    # Test integration avec adapter
    adapter = MarketDataAdapter(DB_PATH)
    res_buy = simulate_fill(adapter, "SPY", "BUY", qty=100, day_decision=TEST_DAY)
    ok3 = res_buy.status == "filled" and res_buy.price_filled > res_buy.open_j1
    _result(
        "BUY SPY filled (price_filled > open_j1)",
        ok3,
        f"open={res_buy.open_j1:.2f} fill={res_buy.price_filled:.2f} slip={res_buy.slippage_bps:.4f}bps",
    )

    res_sell = simulate_fill(adapter, "SPY", "SELL", qty=100, day_decision=TEST_DAY)
    ok4 = res_sell.status == "filled" and res_sell.price_filled < res_sell.open_j1
    _result(
        "SELL SPY filled (price_filled < open_j1)",
        ok4,
        f"open={res_sell.open_j1:.2f} fill={res_sell.price_filled:.2f}",
    )

    # Reject path
    res_bad = simulate_fill(adapter, "SPY", "INVALID", qty=10, day_decision=TEST_DAY)
    ok5 = res_bad.status == "rejected"
    _result("side invalide rejete", ok5, f"reason={res_bad.reason}")

    res_zero = simulate_fill(adapter, "SPY", "BUY", qty=0, day_decision=TEST_DAY)
    ok6 = res_zero.status == "rejected"
    _result("qty=0 rejete", ok6, f"reason={res_zero.reason}")

    return ok1 and ok2 and ok3 and ok4 and ok5 and ok6


def main():
    print("=" * 70)
    print("JALON 8A - TESTS UNITAIRES V1")
    print("=" * 70)
    print(f"DB         : {DB_PATH}")
    print(f"TEST_DAY   : {TEST_DAY}")
    print(f"REPLAY MODE: {os.environ.get('NEXTONES_REPLAY_MODE')}")

    tests = [
        ("schema_present", test_replay_schema_present),
        ("market_no_lookahead", test_market_data_no_lookahead),
        ("fred_no_lookahead", test_fred_no_lookahead),
        ("pplx_neutral_stub", test_pplx_neutral_stub),
        ("fill_slippage_cap", test_fill_simulator_slippage_cap),
    ]

    results = {}
    for name, fn in tests:
        try:
            results[name] = fn()
        except Exception as e:
            print(f"\n[EXC] {name}: {e}")
            traceback.print_exc()
            results[name] = False

    print()
    print("=" * 70)
    print("RESUME")
    print("=" * 70)
    n_ok = sum(1 for v in results.values() if v)
    n_total = len(results)
    for name, ok in results.items():
        tag = "PASS" if ok else "FAIL"
        print(f"  {tag}  {name}")
    print(f"\n  {n_ok}/{n_total} tests OK")

    if n_ok == n_total:
        print("\n[DONE] Jalon 8A valide. Prochaine etape : jalon 8B (orchestrator).")
        sys.exit(0)
    else:
        print("\n[KO] Jalon 8A incomplet.")
        sys.exit(2)


if __name__ == "__main__":
    main()
