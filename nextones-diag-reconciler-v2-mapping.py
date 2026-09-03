# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-RECONCILER-V2-MAPPING]
# Verifie pourquoi le reconciler V2 affiche encore "?" comme broker_symbol :
#   1) Le resolver est-il importable ?
#   2) La fonction resolve() repond-elle pour LINK, AAPL, BTC, NVDA ?
#   3) fetch_mappings(con, thesium_tickers=[...]) renvoie-t-il un dict peuple ?
#   4) Que contient la fonction reconcile() : ou est lu le broker_symbol ?
#
# Usage : py -3.13 nextones-diag-reconciler-v2-mapping.py

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


def load_mod(name, filename):
    p = os.path.join(PROD, filename)
    if not os.path.exists(p):
        print(f"  [FAIL] {filename} introuvable")
        return None
    spec = ilu.spec_from_file_location(name, p)
    m = ilu.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
        return m
    except Exception as e:
        print(f"  [FAIL] import {filename} : {e}")
        traceback.print_exc()
        return None


def main():
    banner("[1] Test import nextones-broker-resolver.py")
    res = load_mod("_nx_resolver_diag", "nextones-broker-resolver.py")
    if res is None:
        sys.exit(1)
    print(f"  OK importe : {res}")
    print(f"  attributs publics :", [a for a in dir(res) if not a.startswith("_")][:20])
    print(f"  resolve dispo : {hasattr(res, 'resolve')}")
    if hasattr(res, "resolve"):
        import inspect
        sig = inspect.signature(res.resolve)
        print(f"  signature resolve : {sig}")

    banner("[2] Appels resolve() sur tickers cles")
    con = sqlite3.connect(DB, timeout=10.0)
    con.execute("PRAGMA busy_timeout=10000")
    for t in ("LINK", "AAPL", "BTC", "NVDA", "GOOGL", "TSLA", "HYPE", "ZEC", "META"):
        for variant in ("conn", "noconn"):
            try:
                if variant == "conn":
                    r = res.resolve(t, conn=con)
                else:
                    r = res.resolve(t)
                print(f"  [{variant:6s}] {t:6s} -> {r!r}"[:200])
                break  # un succes suffit
            except TypeError as e:
                if variant == "noconn":
                    print(f"  [TypeError] {t:6s} : {e}")
            except Exception as e:
                print(f"  [EXC {variant}] {t:6s} : {e}")
                traceback.print_exc()
                break
    con.close()

    banner("[3] Test fetch_mappings() du reconciler V2")
    rec = load_mod("_nx_rec_diag", "nextones-broker-reconciler.py")
    if rec is None:
        sys.exit(1)
    print("  fetch_mappings dispo :", hasattr(rec, "fetch_mappings"))
    if hasattr(rec, "fetch_mappings"):
        import inspect
        sig = inspect.signature(rec.fetch_mappings)
        print(f"  signature fetch_mappings : {sig}")

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
            print(f"    {t:6s} -> {d}")
    except Exception as e:
        print(f"  [FAIL] fetch_mappings : {e}")
        traceback.print_exc()
    con.close()

    banner("[4] Inspecte reconcile() pour comprendre l'affichage '?'")
    if hasattr(rec, "reconcile"):
        import inspect
        try:
            src = inspect.getsource(rec.reconcile)
            print(src[:3500])
        except Exception as e:
            print("  [WARN] getsource KO :", e)
    else:
        print("  pas de reconcile()")

    banner("[5] Inspecte main() / verbose pour voir le print '?'")
    try:
        with open(os.path.join(PROD, "nextones-broker-reconciler.py"),
                  "r", encoding="utf-8-sig") as fh:
            txt = fh.read()
        lines = txt.splitlines()
        for i, ln in enumerate(lines, 1):
            if "'?'" in ln or '"?"' in ln or "<->" in ln:
                print(f"  L{i}: {ln.rstrip()}")
    except Exception as e:
        print("  [WARN]", e)


if __name__ == "__main__":
    main()
