# -*- coding: utf-8 -*-
"""
nextones-check-post-exec.py

Check d'etat post-execution des 8 ordres du cycle 10:25.

Verifications:
  1. orders : statut des 8 ordres (CAT/CSCO/TXN/AMD/PLD/XLK/AAPL BUY + MSFT SELL)
  2. positions : nouvelles positions et delta vs avant cycle
  3. portfolio_state : NAV, cash, invested%, daily_pnl
  4. portfolio_history : derniere snapshot
  5. Comparaison invested% avant (56.22%) vs apres
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")

# Tickers attendus dans le cycle 10:25
EXPECTED_TICKERS = ["CAT", "CSCO", "TXN", "AMD", "PLD", "XLK", "AAPL", "MSFT"]


def section(title):
    print(f"\n{'='*70}\n  {title}\n{'='*70}")


def main():
    if not DB.exists():
        print(f"FAIL: DB introuvable {DB}")
        return 1

    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # -- 1. Orders des 8 dernieres heures sur les tickers attendus
    section("1. ORDERS du cycle (dernieres 8h, tickers cibles)")
    rows = cur.execute(
        """
        SELECT o.id, i.ticker, o.side, o.quantity, o.order_type, o.limit_price,
               o.status, o.created_at, o.validated_at, o.validated_by,
               o.rejection_reason
        FROM orders o
        JOIN instruments i ON i.id = o.instrument_id
        WHERE i.ticker IN ({})
          AND o.created_at >= datetime('now', '-8 hours')
        ORDER BY o.created_at DESC, i.ticker
        """.format(",".join("?" * len(EXPECTED_TICKERS))),
        EXPECTED_TICKERS,
    ).fetchall()

    if not rows:
        print("  AUCUN ordre trouve sur les 8h - cycle peut-etre plus ancien")
    else:
        print(f"  {len(rows)} ordre(s) trouve(s)")
        print(f"  {'TICKER':<7} {'SIDE':<5} {'QTY':>6} {'TYPE':<8} {'STATUS':<22} {'CREATED':<20}")
        print(f"  {'-'*7} {'-'*5} {'-'*6} {'-'*8} {'-'*22} {'-'*20}")
        by_status = {}
        for r in rows:
            d = dict(r)
            st = d["status"] or "?"
            by_status[st] = by_status.get(st, 0) + 1
            print(f"  {d['ticker']:<7} {d['side']:<5} {d['quantity']:>6} "
                  f"{(d['order_type'] or ''):<8} {st:<22} {(d['created_at'] or '')[:19]:<20}")
        print(f"\n  Repartition par statut: {by_status}")

    # -- 2. Positions actuelles
    section("2. POSITIONS actuelles")
    try:
        rows = cur.execute(
            """
            SELECT i.ticker, p.quantity, p.avg_price, p.last_price,
                   (p.quantity * COALESCE(p.last_price, p.avg_price)) AS market_value,
                   ((COALESCE(p.last_price, p.avg_price) - p.avg_price) * p.quantity) AS unrealized_pnl
            FROM positions p
            JOIN instruments i ON i.id = p.instrument_id
            WHERE p.quantity != 0
            ORDER BY market_value DESC
            """
        ).fetchall()
    except sqlite3.OperationalError:
        # Schema differe
        rows = cur.execute(
            "SELECT * FROM positions WHERE quantity != 0 ORDER BY id"
        ).fetchall()

    if not rows:
        print("  AUCUNE position")
    else:
        print(f"  {len(rows)} position(s)")
        total_mv = 0
        for r in rows:
            d = dict(r)
            ticker = d.get("ticker", "?")
            qty = d.get("quantity", 0)
            avg = d.get("avg_price") or 0
            last = d.get("last_price") or avg
            mv = d.get("market_value")
            if mv is None:
                mv = qty * last
            pnl = d.get("unrealized_pnl")
            if pnl is None:
                pnl = (last - avg) * qty
            total_mv += mv or 0
            in_cycle = " *" if ticker in EXPECTED_TICKERS else ""
            print(f"  {ticker:<7}{in_cycle:<2} qty={qty:>7} avg={avg:>9.2f} "
                  f"last={last:>9.2f} mv={mv:>11.2f} upnl={pnl:>+10.2f}")
        print(f"\n  Total market value positions: {total_mv:.2f}")
        print(f"  (* = ticker du cycle 10:25)")

    # -- 3. Portfolio state
    section("3. PORTFOLIO STATE (snapshot actuel)")
    try:
        row = cur.execute(
            "SELECT * FROM portfolio_state ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            d = dict(row)
            nav = d.get("total_value") or d.get("nav") or d.get("equity") or 0
            cash = d.get("cash", 0)
            invested_pct = ((nav - cash) / nav * 100) if nav else 0
            print(f"  NAV          : {nav:,.2f}")
            print(f"  Cash         : {cash:,.2f}")
            print(f"  Invested     : {nav - cash:,.2f} ({invested_pct:.2f}%)")
            print(f"  PnL total    : {d.get('pnl', 0):+,.2f}")
            print(f"  Daily PnL    : {d.get('daily_pnl', 0):+,.2f}")
            print(f"  Updated      : {d.get('updated_at') or d.get('timestamp', '?')}")
            print(f"\n  REFERENCE (avant cycle 10:25) :")
            print(f"  - NAV ref    : 1,000,368   delta = {nav - 1000368:+,.2f}")
            print(f"  - invested%  : 56.22%      delta = {invested_pct - 56.22:+.2f} pp")
    except sqlite3.OperationalError as e:
        print(f"  table portfolio_state inaccessible: {e}")

    # -- 4. Portfolio history (3 derniers points)
    section("4. PORTFOLIO HISTORY (3 dernieres snapshots)")
    try:
        rows = cur.execute(
            """
            SELECT * FROM portfolio_history
            ORDER BY id DESC LIMIT 3
            """
        ).fetchall()
        for r in rows:
            d = dict(r)
            ts = d.get("timestamp") or d.get("date") or d.get("created_at", "?")
            nav = d.get("total_value") or d.get("nav") or 0
            cash = d.get("cash", 0)
            print(f"  {str(ts)[:19]:<20} NAV={nav:>12,.2f} Cash={cash:>11,.2f} "
                  f"PnL={d.get('pnl', 0):>+8.2f}")
    except sqlite3.OperationalError as e:
        print(f"  table portfolio_history inaccessible: {e}")

    # -- 5. Recap cycle 10:25 attendu
    section("5. RECAP CYCLE 10:25 (BUY attendu)")
    expected = [
        ("CAT", 22, "BUY"), ("CSCO", 166, "BUY"), ("TXN", 65, "BUY"),
        ("AMD", 38, "BUY"), ("PLD", 139, "BUY"), ("XLK", 108, "BUY"),
        ("AAPL", 13, "BUY"), ("MSFT", 22, "SELL"),
    ]
    print(f"  {'TICKER':<7} {'SIDE':<5} {'QTY_ATTENDU':>11} {'STATUT_REEL':<25}")
    print(f"  {'-'*7} {'-'*5} {'-'*11} {'-'*25}")
    for tk, qty, side in expected:
        order = cur.execute(
            """
            SELECT o.status, o.quantity FROM orders o
            JOIN instruments i ON i.id = o.instrument_id
            WHERE i.ticker = ? AND o.side = ?
              AND o.created_at >= datetime('now', '-8 hours')
            ORDER BY o.created_at DESC LIMIT 1
            """,
            (tk, side),
        ).fetchone()
        if order:
            d = dict(order)
            match = "OK" if d["quantity"] == qty else f"qty diff={d['quantity']}"
            print(f"  {tk:<7} {side:<5} {qty:>11} {d['status']:<15} {match}")
        else:
            print(f"  {tk:<7} {side:<5} {qty:>11} {'AUCUN ORDRE'}")

    conn.close()
    print("\n" + "=" * 70)
    print("  Check termine")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
