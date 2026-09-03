# -*- coding: utf-8 -*-
# nextones-test-convergence-block-suite.py
# Suite de tests pour valider [CONVERGENCE_FORCED_EXIT_BLOCK_V1]
# Verifie : SELL passe, BUY sur forced_exit=0 passe, BUY sur ticker absent passe, BUY sur forced_exit=1 bloque

import os
import sys
import sqlite3
import json

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(PROD, "thesium.db")
if PROD not in sys.path:
    sys.path.insert(0, PROD)

import risk_pretrade  # noqa

CASES = [
    # (label, ticker, side, expected_blocked)
    ("SOL BUY (forced_exit=1)",  "SOL",  "buy",  True),
    ("SOL SELL (forced_exit=1)", "SOL",  "sell", False),
    ("HYPE BUY (forced_exit=0)", "HYPE", "buy",  False),
    ("HYPE SELL",                "HYPE", "sell", False),
    ("BTC BUY (forced_exit=1)",  "BTC",  "buy",  True),
    ("ETH BUY (forced_exit=1)",  "ETH",  "buy",  True),
    ("ZEC BUY (forced_exit=0)",  "ZEC",  "buy",  False),
    ("AAPL BUY (forced_exit=0)", "AAPL", "buy",  False),
]

# Recup prix de chaque ticker
con_prices = sqlite3.connect(DB, timeout=5.0)
con_prices.row_factory = sqlite3.Row
prices = {}
for label, tk, side, exp in CASES:
    if tk in prices:
        continue
    r = con_prices.execute(
        "SELECT close FROM prices WHERE instrument_id = "
        "(SELECT id FROM instruments WHERE ticker = ?) "
        "ORDER BY date DESC LIMIT 1",
        (tk,)
    ).fetchone()
    prices[tk] = float(r["close"]) if r and r["close"] else 100.0
con_prices.close()

print()
print("=" * 76)
print("SUITE TESTS [CONVERGENCE_FORCED_EXIT_BLOCK_V1]")
print("-" * 76)
print()
print("  %-30s | %-6s | %-9s | %-9s | %s" % (
    "Cas", "side", "expected", "got", "verdict"))
print("  " + "-" * 74)

all_ok = True
for label, tk, side, expected_blocked in CASES:
    price = prices.get(tk, 100.0)
    try:
        res = risk_pretrade.run_pretrade_checks(tk, 1.0, price, side)
        blocked_by = res.get("blocked_by") or ""
        # Convergence block UNIQUEMENT
        is_conv_block = (blocked_by == "convergence_forced_exit")
        # On compare a expected_blocked
        if expected_blocked:
            ok = is_conv_block
        else:
            ok = (blocked_by != "convergence_forced_exit")
        status = "OK " if ok else "KO!"
        if not ok:
            all_ok = False
        got = "blocked" if is_conv_block else "pass"
        exp = "blocked" if expected_blocked else "pass"
        print("  %-30s | %-6s | %-9s | %-9s | %s" % (label, side, exp, got, status))
        if not ok:
            print("    details : passed=%s blocked_by=%s" % (
                res.get("passed"), blocked_by))
    except Exception as e:
        all_ok = False
        print("  %-30s | %-6s | ERREUR : %s" % (label, side, str(e)[:80]))

print()
print("=" * 76)
print("VERDICT GLOBAL : %s" % ("TOUS OK" if all_ok else "ECHEC SUR AU MOINS UN CAS"))
print("=" * 76)
