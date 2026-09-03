# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-RECONCILER-RUNTIME]
# Verifie en runtime :
#  1) Ce que retourne resolve_via_resolver() pour LINK et AAPL
#  2) Ce que retourne fetch_mappings(con, thesium_tickers=[20 tickers]) APRES fix
#  3) Comment main() appelle fetch_mappings (avec ou sans thesium_tickers=)
#  4) La nouvelle taille du fichier + presence des trois marqueurs cles
#
# Usage : py -3.13 nextones-diag-reconciler-runtime.py

import importlib.util as ilu
import os
import sqlite3
import sys
import traceback

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(PROD, "thesium.db")
sys.path.insert(0, PROD)


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


def main():
    banner("[1] Inspecte le source du reconciler")
    target = os.path.join(PROD, "nextones-broker-reconciler.py")
    with open(target, "r", encoding="utf-8-sig") as fh:
        src = fh.read()
    print(f"  taille : {len(src)} octets")
    markers = [
        "[NEXTONES-BROKER-RECONCILER-V2]",
        "[NEXTONES-BROKER-RECONCILER-V2] helper resolver",
        "Cas 1 : dataclass BrokerMatch",
        "_load_resolver",
        "resolve_via_resolver",
        "thesium_tickers=None",
        "thesium_tickers=[p",
        "fetch_mappings(con)",
        "fetch_mappings(con, ",
    ]
    for m in markers:
        n = src.count(m)
        print(f"  '{m[:55]:55s}' x {n}")

    banner("[2] Trouve l'appel fetch_mappings dans main()")
    lines = src.splitlines()
    for i, ln in enumerate(lines, 1):
        if "fetch_mappings(" in ln:
            print(f"  L{i}: {ln.strip()}")

    banner("[3] Import + appel resolve_via_resolver()")
    spec = ilu.spec_from_file_location("_nx_rec", target)
    rec = ilu.module_from_spec(spec)
    try:
        spec.loader.exec_module(rec)
        print("  import OK")
    except Exception as e:
        print(f"  [FAIL] import : {e}")
        traceback.print_exc()
        sys.exit(1)

    print("  resolve_via_resolver dispo :", hasattr(rec, "resolve_via_resolver"))
    if hasattr(rec, "resolve_via_resolver"):
        con = sqlite3.connect(DB, timeout=10.0)
        con.execute("PRAGMA busy_timeout=10000")
        for t in ("LINK", "AAPL", "BTC", "NVDA", "HYPE", "ZEC"):
            try:
                r = rec.resolve_via_resolver(t, con)
                print(f"  resolve_via_resolver({t:5s}) -> {r}")
            except Exception as e:
                print(f"  [EXC] {t}: {e}")
                traceback.print_exc()
        con.close()

    banner("[4] Test fetch_mappings(con, thesium_tickers=[20])")
    con = sqlite3.connect(DB, timeout=10.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=10000")
    tickers = ["AAPL", "AMD", "AMZN", "BTC", "CAT", "CSCO", "ETH", "GOOGL",
               "HYPE", "LINK", "META", "MSFT", "NVDA", "PLD", "SOL", "TSLA",
               "TXN", "XLE", "XLK", "ZEC"]
    try:
        by_broker, by_thesium = rec.fetch_mappings(con, thesium_tickers=tickers)
        print(f"  by_broker  : {len(by_broker)} entrees")
        print(f"  by_thesium : {len(by_thesium)} entrees")
        for t in tickers:
            d = by_thesium.get(t)
            if d is None:
                print(f"    {t:6s} -> None")
            else:
                print(f"    {t:6s} -> bs={d.get('broker_symbol'):10s} "
                      f"cs={d.get('contract_size')} ls={d.get('lot_step')}")
    except Exception as e:
        print(f"  [FAIL] : {e}")
        traceback.print_exc()
    con.close()

    banner("[5] Dump du bloc resolve_via_resolver dans le fichier")
    idx = src.find("def resolve_via_resolver")
    if idx >= 0:
        end = src.find("\n# [/NEXTONES-BROKER-RECONCILER-V2]", idx)
        if end < 0:
            end = idx + 2000
        print(src[idx:end + 50])
    else:
        print("  introuvable")


if __name__ == "__main__":
    main()
