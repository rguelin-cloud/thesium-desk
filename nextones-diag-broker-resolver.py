# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-BROKER-RESOLVER-V1]
# Comprendre :
#  1) Le vrai schema de broker_universe_activtrades
#  2) Quels symboles sont presents (sample + recherche LINKUSD/AAPL.US/etc.)
#  3) Le contenu de broker_shadow_orders (notamment LINK -> LINKUSD)
#  4) La logique de mapping reelle : est-ce que nextones-broker-resolver.py
#     ecrit dans instrument_broker_mapping ou pas ?
#  5) Le contenu de broker_mapping_audit
#  6) Liste des fichiers nextones-broker-* presents
#
# Usage : py -3.13 nextones-diag-broker-resolver.py

import os
import sqlite3
import sys

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"


def banner(t):
    print("=" * 60)
    print(t)
    print("=" * 60)


def main():
    con = sqlite3.connect(DB, timeout=10.0)
    con.execute("PRAGMA busy_timeout=10000")
    cur = con.cursor()

    banner("[1] Schema broker_universe_activtrades")
    cols = cur.execute(
        "PRAGMA table_info(broker_universe_activtrades)"
    ).fetchall()
    for c in cols:
        print(f"  cid={c[0]} name={c[1]:25s} type={c[2]:15s} "
              f"notnull={c[3]} pk={c[5]}")
    col_names = [c[1] for c in cols]

    banner("[2] Sample 5 broker_universe_activtrades")
    rows = cur.execute(
        "SELECT * FROM broker_universe_activtrades LIMIT 5"
    ).fetchall()
    print("  cols:", " | ".join(col_names))
    for r in rows:
        print("  ", r)

    banner("[3] Recherche tickers cles dans broker_universe_activtrades")
    # detecte la colonne probable
    sym_col = None
    for cand in ("broker_symbol", "symbol", "ticker", "name"):
        if cand in col_names:
            sym_col = cand
            break
    if sym_col is None:
        print("  [WARN] aucune colonne symbole reconnue. cols=", col_names)
    else:
        print(f"  colonne symbole presumee = {sym_col}")
        for sym in ("LINKUSD", "AAPL.US", "BTCUSD", "ETHUSD", "SOLUSD",
                    "NVDA.US", "META.US", "MSFT.US", "TSLA.US", "XLE.US",
                    "XLK.US", "HYPEUSD", "ZECUSD", "PLD.US", "TXN.US",
                    "AMD.US", "GOOGL.US", "AMZN.US", "CAT.US", "CSCO.US"):
            r = cur.execute(
                f"SELECT * FROM broker_universe_activtrades "
                f"WHERE {sym_col}=?",
                (sym,)
            ).fetchone()
            mark = "OK " if r else "ABS"
            print(f"  [{mark}] {sym:10s} -> {r}")

    banner("[4] Contenu broker_shadow_orders (10 dernieres)")
    rows = cur.execute(
        "SELECT id, ts, cycle_id, thesium_ticker, broker_symbol, side, "
        "qty_requested, volume_lots, status, notes "
        "FROM broker_shadow_orders ORDER BY id DESC LIMIT 10"
    ).fetchall()
    if not rows:
        print("  (vide)")
    else:
        for r in rows:
            print("  ", r)

    banner("[5] broker_mapping_audit")
    try:
        cols2 = [c[1] for c in cur.execute(
            "PRAGMA table_info(broker_mapping_audit)"
        ).fetchall()]
        n = cur.execute(
            "SELECT COUNT(*) FROM broker_mapping_audit"
        ).fetchone()[0]
        print(f"  cols : {cols2}")
        print(f"  count: {n}")
        rows = cur.execute(
            "SELECT * FROM broker_mapping_audit ORDER BY rowid DESC LIMIT 10"
        ).fetchall()
        for r in rows:
            print("  ", r)
    except sqlite3.Error as e:
        print("  [ERR]", e)

    banner("[6] Liste fichiers nextones-broker-* en prod")
    try:
        files = sorted([
            f for f in os.listdir(PROD)
            if f.startswith("nextones-broker") or f == "broker_resolver.py"
            or f == "order_translator.py" or f == "risk_broker_check.py"
            or f == "broker_shadow_executor.py"
        ])
        for f in files:
            full = os.path.join(PROD, f)
            sz = os.path.getsize(full)
            print(f"  {sz:8d}  {f}")
    except Exception as e:
        print("  [ERR]", e)

    banner("[7] Grep dans broker_resolver.py pour comprendre la logique")
    candidates = [
        os.path.join(PROD, "broker_resolver.py"),
        os.path.join(PROD, "nextones-broker-resolver.py"),
    ]
    found = None
    for c in candidates:
        if os.path.exists(c):
            found = c
            break
    if found is None:
        print("  [WARN] broker_resolver.py introuvable")
    else:
        print(f"  fichier = {found}")
        with open(found, "r", encoding="utf-8-sig") as fh:
            txt = fh.read()
        # cherche : INSERT INTO instrument_broker_mapping, ou un dict
        # de fallback, ou un appel a broker_universe_activtrades
        keywords = [
            "instrument_broker_mapping",
            "broker_universe_activtrades",
            "LINKUSD",
            "LINK",
            "INSERT INTO",
            "INSERT OR",
            "def resolve",
            "FALLBACK",
            "fallback",
            "_MAPPING",
        ]
        for kw in keywords:
            lines = [(i + 1, ln) for i, ln in enumerate(txt.splitlines())
                     if kw in ln]
            print(f"  --- keyword '{kw}' : {len(lines)} matches")
            for ln_num, ln in lines[:5]:
                print(f"    L{ln_num}: {ln.strip()[:100]}")

    banner("[8] Pragmas DB")
    for p in ("journal_mode", "busy_timeout"):
        v = cur.execute(f"PRAGMA {p}").fetchone()
        print(f"  {p} = {v}")

    con.close()


if __name__ == "__main__":
    main()
