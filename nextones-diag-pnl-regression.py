#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diag : pourquoi le P&L est revenu a -$17,601 ?
1. Etat du marker [TOTAL_PNL_NAV_BASED_V1] dans api_server.py
2. Etat de la formule total_pnl = ... a L241 (et autour)
3. Lignes recentes de portfolio_history
4. portfolio_state actuel
5. positions actuelles + somme unrealized_pnl
6. test manuel : NAV - 1M = ?
"""
import os
import sqlite3
import sys

API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
MARKER = "[TOTAL_PNL_NAV_BASED_V1]"


def main():
    # 1) marker check
    with open(API, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    text = data.decode("utf-8", errors="replace")
    print("MARKER " + MARKER + " in api_server.py : " + str(MARKER in text))

    # 2) all 'total_pnl =' lines in api_server.py
    print()
    print("=" * 70)
    print("All 'total_pnl' assignments in api_server.py")
    print("=" * 70)
    lines = text.split("\n")
    for i, line in enumerate(lines, 1):
        if "total_pnl" in line and "=" in line:
            print("L" + str(i).rjust(4) + " | " + line.rstrip()[:140])

    # 3) portfolio_history last 5
    print()
    print("=" * 70)
    print("portfolio_history last 5 rows")
    print("=" * 70)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    for r in conn.execute(
        "SELECT date, total_value, cash, total_pnl FROM portfolio_history ORDER BY date DESC LIMIT 5"
    ).fetchall():
        d = dict(r)
        nav_minus_1m = round(d["total_value"] - 1_000_000, 2)
        print("  " + str(d) + "  | NAV-1M=" + str(nav_minus_1m))

    # 4) portfolio_state
    print()
    print("=" * 70)
    print("portfolio_state row")
    print("=" * 70)
    r = conn.execute("SELECT * FROM portfolio_state WHERE id=1").fetchone()
    if r:
        print("  " + str(dict(r)))
        nav = r["total_value"] or 0
        print("  NAV - 1,000,000 = " + str(round(nav - 1_000_000, 2)))

    # 5) positions snapshot
    print()
    print("=" * 70)
    print("positions: sum(quantity*avg_cost), sum(market_value), sum(unrealized)")
    print("=" * 70)
    rows = conn.execute(
        "SELECT quantity, avg_cost, current_price, unrealized_pnl FROM portfolio_positions WHERE quantity > 0"
    ).fetchall()
    sum_cost = 0
    sum_mv = 0
    sum_unr = 0
    for r in rows:
        d = dict(r)
        c = (d["quantity"] or 0) * (d["avg_cost"] or 0)
        m = (d["quantity"] or 0) * (d["current_price"] or 0)
        u = d["unrealized_pnl"] or 0
        sum_cost += c
        sum_mv += m
        sum_unr += u
    print("  sum(qty*avg_cost)      = " + str(round(sum_cost, 2)))
    print("  sum(qty*current_price) = " + str(round(sum_mv, 2)))
    print("  sum(unrealized_pnl)    = " + str(round(sum_unr, 2)))
    print("  unrealized only        = " + str(round(sum_mv - sum_cost, 2)))

    # 6) cash + nav
    cash_row = conn.execute("SELECT cash FROM portfolio_state WHERE id=1").fetchone()
    cash = cash_row["cash"] if cash_row else 0
    print()
    print("  cash                   = " + str(cash))
    print("  nav (cash + mv)        = " + str(round(cash + sum_mv, 2)))
    print("  nav - 1,000,000        = " + str(round(cash + sum_mv - 1_000_000, 2)))

    conn.close()


if __name__ == "__main__":
    main()
