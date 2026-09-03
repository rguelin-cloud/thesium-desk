# -*- coding: utf-8 -*-
"""
diag_sector.py
==============
Diagnostic ThesiumDesk : origine des rejets d'ordres et exposition sectorielle.

Lecture seule. Ne modifie jamais la base.

USAGE :
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 diag_sector.py

    py -3.13 diag_sector.py > diag_sector_output.txt
"""

import os
import sqlite3
import sys

DB = "thesium.db"
LINE = "=" * 78


def section(title):
    print()
    print(LINE)
    print(title)
    print(LINE)


def safe(fn, label):
    """Execute un bloc et continue meme si le schema differe."""
    try:
        fn()
    except Exception as exc:
        print("  [ERREUR] {} : {}".format(label, exc))


def main():
    if not os.path.exists(DB):
        print("ERREUR : base introuvable : {}".format(os.path.abspath(DB)))
        return 1

    c = sqlite3.connect("file:{}?mode=ro".format(DB), uri=True)
    c.row_factory = sqlite3.Row

    print(LINE)
    print("DIAGNOSTIC THESIUMDESK - rejets et exposition sectorielle")
    print("Base : {}".format(os.path.abspath(DB)))
    print(LINE)

    # ---------------------------------------------------------------- 1
    section("1. QUI REJETTE ?  (validated_by x rejection_reason)")

    def q1():
        rows = c.execute("""
            SELECT COALESCE(validated_by,'(null)') vb,
                   COALESCE(rejection_reason,'(null)') rr,
                   COUNT(*) n
            FROM orders WHERE status='rejected'
            GROUP BY vb, rr ORDER BY n DESC LIMIT 20
        """).fetchall()
        for r in rows:
            print("{:5d}  by={:22s} reason={}".format(
                r["n"], str(r["vb"])[:22], str(r["rr"])[:42]))
        tot = sum(r["n"] for r in rows)
        print("-" * 60)
        print("{:5d}  total affiche".format(tot))

    safe(q1, "validated_by")

    # ---------------------------------------------------------------- 2
    section("2. REPARTITION PAR validated_by SEUL")

    def q2():
        for r in c.execute("""
            SELECT COALESCE(validated_by,'(null)') vb,
                   status, COUNT(*) n
            FROM orders GROUP BY vb, status
            ORDER BY vb, n DESC
        """):
            print("{:22s} {:12s} {:5d}".format(
                str(r["vb"])[:22], str(r["status"])[:12], r["n"]))

    safe(q2, "repartition statut")

    # ---------------------------------------------------------------- 3
    section("3. ARM EN DETAIL  (87 rejets = 35% du total)")

    def q3():
        for r in c.execute("""
            SELECT o.id, o.created_at, o.quantity, o.validated_by,
                   o.rejection_reason, o.cycle_id, o.validated_at
            FROM orders o JOIN instruments i ON i.id = o.instrument_id
            WHERE i.ticker='ARM' AND o.status='rejected'
            ORDER BY o.created_at DESC LIMIT 12
        """):
            print("id={:5d} {} qty={:>9} by={:12s} reason={:12s} cyc={}".format(
                r["id"], str(r["created_at"])[:16], r["quantity"],
                str(r["validated_by"])[:12],
                str(r["rejection_reason"])[:12],
                str(r["cycle_id"])[:18]))

    safe(q3, "ARM detail")

    # ---------------------------------------------------------------- 4
    section("4. EXPOSITION SECTORIELLE ACTUELLE")

    nav = cash = 0.0

    def q4():
        nonlocal nav, cash
        row = c.execute(
            "SELECT total_value, cash FROM portfolio_state WHERE id=1"
        ).fetchone()
        nav = float(row["total_value"] or 0)
        cash = float(row["cash"] or 0)
        print("NAV  = {:>14,.0f}".format(nav))
        print("Cash = {:>14,.0f}   ({:.1f}% du NAV)".format(
            cash, 100.0 * cash / nav if nav else 0))
        print()
        print("{:26s} {:>14s} {:>8s} {:>8s}".format(
            "SECTEUR", "VALEUR", "% NAV", "LIGNES"))
        print("-" * 60)
        tot = 0.0
        for r in c.execute("""
            SELECT i.sector, SUM(pp.quantity*pp.current_price) mv, COUNT(*) n
            FROM portfolio_positions pp
            JOIN instruments i ON i.id = pp.instrument_id
            GROUP BY i.sector ORDER BY mv DESC
        """):
            mv = float(r["mv"] or 0)
            tot += mv
            pct = 100.0 * mv / nav if nav else 0
            flag = "  <-- SATURE" if mv >= 240000 else ""
            print("{:26s} {:>14,.0f} {:>7.1f}% {:>8d}{}".format(
                str(r["sector"] or "n/a")[:26], mv, pct, r["n"], flag))
        print("-" * 60)
        print("{:26s} {:>14,.0f} {:>7.1f}%".format(
            "TOTAL INVESTI", tot, 100.0 * tot / nav if nav else 0))
        print("{:26s} {:>14,.0f} {:>7.1f}%".format(
            "CASH", cash, 100.0 * cash / nav if nav else 0))

    safe(q4, "exposition")

    # ---------------------------------------------------------------- 5
    section("5. RISK CONFIG ACTIVE")

    def q5():
        for r in c.execute("SELECT * FROM risk_config WHERE id=1"):
            for k in r.keys():
                print("  {:30s} = {}".format(k, r[k]))
        if nav:
            print()
            print("  Traduction en USD sur NAV = {:,.0f} :".format(nav))
            row = c.execute("SELECT * FROM risk_config WHERE id=1").fetchone()
            for k in row.keys():
                if k.endswith("_pct") and row[k] is not None:
                    print("    {:28s} -> {:>12,.0f} USD".format(
                        k, nav * float(row[k]) / 100.0))

    safe(q5, "risk_config")

    # ---------------------------------------------------------------- 6
    section("6. TOP POSITIONS")

    def q6():
        print("{:8s} {:18s} {:>13s} {:>7s} {:>13s}".format(
            "TICKER", "SECTEUR", "VALEUR", "% NAV", "PNL"))
        print("-" * 66)
        for r in c.execute("""
            SELECT i.ticker, i.sector, pp.quantity,
                   pp.quantity*pp.current_price mv, pp.unrealized_pnl
            FROM portfolio_positions pp
            JOIN instruments i ON i.id = pp.instrument_id
            ORDER BY mv DESC LIMIT 20
        """):
            mv = float(r["mv"] or 0)
            print("{:8s} {:18s} {:>13,.0f} {:>6.2f}% {:>13,.0f}".format(
                str(r["ticker"])[:8], str(r["sector"] or "")[:18], mv,
                100.0 * mv / nav if nav else 0,
                float(r["unrealized_pnl"] or 0)))

    safe(q6, "positions")

    # ---------------------------------------------------------------- 7
    section("7. SECTEUR DES TICKERS LES PLUS REJETES")

    def q7():
        print("{:8s} {:20s} {:>6s} {:>6s} {:>7s}".format(
            "TICKER", "SECTEUR", "REJ", "TOT", "TAUX"))
        print("-" * 56)
        for r in c.execute("""
            SELECT i.ticker, i.sector,
                   SUM(o.status='rejected') rej, COUNT(*) tot
            FROM orders o JOIN instruments i ON i.id = o.instrument_id
            WHERE o.side='buy'
            GROUP BY i.ticker, i.sector
            HAVING rej > 0 ORDER BY rej DESC LIMIT 20
        """):
            pct = 100.0 * r["rej"] / r["tot"] if r["tot"] else 0
            print("{:8s} {:20s} {:>6d} {:>6d} {:>6.1f}%".format(
                str(r["ticker"])[:8], str(r["sector"] or "n/a")[:20],
                r["rej"], r["tot"], pct))

    safe(q7, "rejets par secteur")

    # ---------------------------------------------------------------- 8
    section("8. REGIME DE MARCHE RECENT")

    def q8():
        for r in c.execute("""
            SELECT * FROM market_regime_log
            ORDER BY rowid DESC LIMIT 3
        """):
            print("  ---")
            for k in r.keys():
                v = str(r[k])
                if len(v) > 100:
                    v = v[:100] + "..."
                print("  {:24s} = {}".format(k, v))

    safe(q8, "market_regime_log")

    print()
    print(LINE)
    print("FIN DU DIAGNOSTIC")
    print(LINE)

    c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
