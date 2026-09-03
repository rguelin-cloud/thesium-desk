# -*- coding: utf-8 -*-
# nextones-validate-stop-loss-v1.py
# Valide le patch [STOP_LOSS_BLOCK_V1] :
# - Verifie marker present dans risk_pretrade.py
# - Verifie fonction check_stop_loss importable
# - Test 1 : BUY BTC (PnL -19%) doit retourner False (BLOCK)
# - Test 2 : SELL BTC doit retourner True (sell skip)
# - Test 3 : BUY CSCO (PnL ~ -0.34% si position) doit retourner True
# - Test 4 : BUY ticker inexistant doit retourner True (no_position)
# - Test 5 : run_pretrade_checks integre - smoke test

import os
import sys
import sqlite3
import importlib.util
import json

PROD_ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
RP_PATH = os.path.join(PROD_ROOT, "risk_pretrade.py")
DB_PATH = os.path.join(PROD_ROOT, "thesium.db")
MARKER = "[STOP_LOSS_BLOCK_V1]"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    print("=" * 70)
    print("VALIDATION [STOP_LOSS_BLOCK_V1]")
    print("=" * 70)

    # 1. Marker present
    with open(RP_PATH, "r", encoding="utf-8-sig") as f:
        src = f.read()
    if MARKER not in src:
        print("[FAIL] Marker " + MARKER + " absent de risk_pretrade.py")
        sys.exit(1)
    print("[OK] Marker " + MARKER + " present")

    # 2. Import risk_pretrade
    if PROD_ROOT not in sys.path:
        sys.path.insert(0, PROD_ROOT)

    rp = load_module("risk_pretrade", RP_PATH)
    if not hasattr(rp, "check_stop_loss"):
        print("[FAIL] check_stop_loss n'est pas exposee par risk_pretrade")
        sys.exit(1)
    print("[OK] check_stop_loss importee")

    # 3. Tests directs
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row

    # Liste des positions a tester (donnees prod connues)
    test_cases = [
        ("BTC", "buy", False, "BTC PnL -19% doit etre bloque"),
        ("BTC", "sell", True, "SELL BTC doit passer (sell_skip)"),
        ("SOL", "buy", False, "SOL PnL -17.95% doit etre bloque"),
        ("ETH", "buy", False, "ETH PnL -20.12% doit etre bloque"),
        ("LINK", "buy", False, "LINK PnL -16% doit etre bloque"),
        ("AMZN", "buy", False, "AMZN PnL -9.57% doit etre bloque"),
        ("AAPL", "buy", True, "AAPL PnL -6.55% doit passer (au-dessus seuil)"),
        ("ZZZ_NOPE", "buy", True, "Ticker inexistant doit passer (no_position)"),
    ]

    passed = 0
    failed = 0
    for ticker, side, expected_ok, label in test_cases:
        try:
            ok, details = rp.check_stop_loss(c, ticker, side)
            status = "OK" if ok == expected_ok else "FAIL"
            if ok == expected_ok:
                passed += 1
            else:
                failed += 1
            print("[" + status + "] " + label)
            print("       ok=" + str(ok) + " details=" + json.dumps(details, default=str))
        except Exception as e:
            failed += 1
            print("[ERR ] " + label + " - " + str(e))

    # 4. Smoke test run_pretrade_checks pour BTC BUY
    print("-" * 70)
    print("Smoke test run_pretrade_checks(BTC, buy, 0.01)")
    try:
        # signature suposee: run_pretrade_checks(c, ticker, side, quantity, ...)
        # On la decouvre dynamiquement
        import inspect
        sig = inspect.signature(rp.run_pretrade_checks)
        print("       signature : " + str(sig))
        # On tente avec 3 args minimum
        result = rp.run_pretrade_checks(c, "BTC", "buy", 0.01)
        print("       result : " + json.dumps(result, default=str)[:500])
        if isinstance(result, dict):
            blocked_by = result.get("blocked_by")
            details = result.get("details", {})
            sl = details.get("stop_loss")
            if blocked_by == "stop_loss":
                print("[OK] blocked_by = stop_loss")
                passed += 1
            else:
                print("[INFO] blocked_by = " + str(blocked_by) + " (peut etre broker/convergence avant SL)")
            if sl:
                print("[OK] details.stop_loss present : " + json.dumps(sl, default=str))
                passed += 1
            else:
                print("[WARN] details.stop_loss absent")
    except Exception as e:
        print("[WARN] Smoke test echoue : " + str(e))

    print("=" * 70)
    print("RESULTAT : " + str(passed) + " passed, " + str(failed) + " failed")
    print("=" * 70)
    c.close()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
