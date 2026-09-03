# -*- coding: utf-8 -*-
# nextones-diag-stop-loss-wiring.py
# Verifie comment check_stop_loss est branche dans run_pretrade_checks
# - Affiche le bloc autour de l'appel
# - Verifie que 'c' (ou autre nom de connexion) est defini dans le scope
# - Lance un vrai appel via run_pretrade_checks avec la bonne signature

import os
import sys
import sqlite3
import importlib.util

PROD_ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
RP_PATH = os.path.join(PROD_ROOT, "risk_pretrade.py")
DB_PATH = os.path.join(PROD_ROOT, "thesium.db")


def main():
    print("=" * 70)
    print("DIAG STOP_LOSS WIRING dans run_pretrade_checks")
    print("=" * 70)

    with open(RP_PATH, "r", encoding="utf-8-sig") as f:
        src = f.read()
    lines = src.split("\n")

    # 1. Trouver appel check_stop_loss
    print("\n--- 1. Appels check_stop_loss ---")
    for i, ln in enumerate(lines, 1):
        if "check_stop_loss" in ln and "def check_stop_loss" not in ln:
            print("L" + str(i) + ": " + ln.rstrip())

    # 2. Trouver run_pretrade_checks et afficher 30 lignes
    print("\n--- 2. Debut de run_pretrade_checks (40 lignes) ---")
    for i, ln in enumerate(lines, 1):
        if "def run_pretrade_checks" in ln:
            for j in range(i - 1, min(len(lines), i + 80)):
                marker = " >>> " if "check_stop_loss" in lines[j] or "sl_ok" in lines[j] else "     "
                print(marker + "L" + str(j + 1) + ": " + lines[j].rstrip())
            break

    # 3. Test runtime avec la VRAIE signature
    print("\n--- 3. Test runtime run_pretrade_checks(ticker, qty, price, side) ---")
    if PROD_ROOT not in sys.path:
        sys.path.insert(0, PROD_ROOT)

    spec = importlib.util.spec_from_file_location("risk_pretrade", RP_PATH)
    rp = importlib.util.module_from_spec(spec)
    sys.modules["risk_pretrade"] = rp
    spec.loader.exec_module(rp)

    # BTC -19% : doit etre bloque par stop_loss (ou par autre check avant)
    try:
        result = rp.run_pretrade_checks(
            ticker="BTC",
            qty=0.01,
            price=60935.71,
            side="buy",
            db_path=DB_PATH,
        )
        print("Result BTC BUY 0.01 @ 60935 :")
        import json
        print(json.dumps(result, default=str, indent=2)[:2000])
    except Exception as e:
        import traceback
        print("[ERR] " + str(e))
        traceback.print_exc()

    # SELL BTC : doit passer
    print("\n--- BTC SELL 0.01 ---")
    try:
        result = rp.run_pretrade_checks(
            ticker="BTC",
            qty=0.01,
            price=60935.71,
            side="sell",
            db_path=DB_PATH,
        )
        import json
        print(json.dumps(result, default=str, indent=2)[:1500])
    except Exception as e:
        print("[ERR] " + str(e))

    # CSCO BUY : pas en perte -8%, doit passer le SL (peut etre bloque ailleurs)
    print("\n--- CSCO BUY 1 ---")
    try:
        result = rp.run_pretrade_checks(
            ticker="CSCO",
            qty=1.0,
            price=70.0,
            side="buy",
            db_path=DB_PATH,
        )
        import json
        print(json.dumps(result, default=str, indent=2)[:1500])
    except Exception as e:
        print("[ERR] " + str(e))


if __name__ == "__main__":
    main()
