# -*- coding: utf-8 -*-
# [CHECK_EQUITY_PROMOTED_V1]
# Verifie si les 5 equity approuves (CAT, CSCO, TXN, AMD, PLD) ont bien ete
# promus dans instruments et target_universe.
import sqlite3
import os

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
EQUITY = ["CAT", "CSCO", "TXN", "AMD", "PLD"]


def header(t):
    print()
    print("=" * 72)
    print("  " + t)
    print("=" * 72)


def step1_instruments():
    header("1. instruments - les 5 equity sont-ils inseres ?")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    placeholders = ",".join("?" * len(EQUITY))
    rows = cur.execute(
        "SELECT id, ticker, name, sector, asset_class FROM instruments "
        "WHERE ticker IN ({}) ORDER BY ticker".format(placeholders),
        EQUITY,
    ).fetchall()
    if not rows:
        print("  AUCUN des 5 equity n'est dans instruments")
    for r in rows:
        print("  id={:4d} {:6s} {:35s} sector={:15s} class={}".format(
            r[0], r[1], (r[2] or "")[:35], r[3] or "", r[4]
        ))
    missing = [t for t in EQUITY if t not in [r[1] for r in rows]]
    if missing:
        print()
        print("  Manquants : " + ", ".join(missing))
    con.close()
    return [r[1] for r in rows]


def step2_target_universe():
    header("2. target_universe - is_active=1 pour les equity ?")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    # detecte le schema
    cols = [r[1] for r in cur.execute("PRAGMA table_info(target_universe)").fetchall()]
    if not cols:
        print("  table target_universe absente")
        con.close()
        return
    print("  colonnes target_universe : " + ", ".join(cols))
    placeholders = ",".join("?" * len(EQUITY))
    if "ticker" in cols:
        rows = cur.execute(
            "SELECT * FROM target_universe WHERE ticker IN ({})".format(placeholders),
            EQUITY,
        ).fetchall()
    elif "instrument_id" in cols:
        rows = cur.execute(
            "SELECT tu.* FROM target_universe tu "
            "JOIN instruments i ON i.id = tu.instrument_id "
            "WHERE i.ticker IN ({})".format(placeholders),
            EQUITY,
        ).fetchall()
    else:
        print("  schema inattendu - ni ticker ni instrument_id")
        con.close()
        return
    print()
    print("  Header :", " | ".join(cols))
    if not rows:
        print("  AUCUNE ligne target_universe pour ces 5 equity")
    for r in rows:
        print("  " + " | ".join(str(v)[:20] for v in r))
    con.close()


def step3_prices_history():
    header("3. prices - historique disponible pour les equity ?")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    placeholders = ",".join("?" * len(EQUITY))
    rows = cur.execute(
        "SELECT i.ticker, COUNT(p.id), MIN(p.date), MAX(p.date) "
        "FROM instruments i "
        "LEFT JOIN prices p ON p.instrument_id = i.id "
        "WHERE i.ticker IN ({}) GROUP BY i.ticker ORDER BY i.ticker".format(placeholders),
        EQUITY,
    ).fetchall()
    if not rows:
        print("  Aucun de ces tickers dans instruments (donc 0 prices)")
    for t, n, dmin, dmax in rows:
        if n == 0:
            print("  {:6s} 0 prix - PROBLEME, fetch_etf_history a echoue".format(t))
        else:
            print("  {:6s} {} prix de {} a {}".format(t, n, dmin, dmax))
    con.close()


def step4_positions():
    header("4. positions - les equity sont-ils deja en portefeuille ?")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    placeholders = ",".join("?" * len(EQUITY))
    cols = [r[1] for r in cur.execute("PRAGMA table_info(positions)").fetchall()]
    if "ticker" in cols:
        rows = cur.execute(
            "SELECT * FROM positions WHERE ticker IN ({})".format(placeholders),
            EQUITY,
        ).fetchall()
    elif "instrument_id" in cols:
        rows = cur.execute(
            "SELECT i.ticker, p.* FROM positions p "
            "JOIN instruments i ON i.id = p.instrument_id "
            "WHERE i.ticker IN ({})".format(placeholders),
            EQUITY,
        ).fetchall()
    else:
        print("  schema positions inattendu : " + ", ".join(cols))
        con.close()
        return
    if not rows:
        print("  Aucune position ouverte sur ces equity (normal apres simple approve)")
    for r in rows:
        print("  " + " | ".join(str(v)[:25] for v in r))
    con.close()


def main():
    print("NEXTONES check equity promoted - DB=" + DB)
    found = step1_instruments()
    step2_target_universe()
    step3_prices_history()
    step4_positions()
    print()
    print("=" * 72)
    print("  Lecture rapide :")
    print("  - Si step 1 vide : approve n'a PAS insere dans instruments -> bug pipeline")
    print("  - Si step 3 montre 0 prix : fetch_etf_history a echoue ou pas declenche")
    print("  - Si step 2 absente : target_universe pas mis a jour -> equity invisible")
    print("    pour la construction.")
    print("=" * 72)


if __name__ == "__main__":
    main()
