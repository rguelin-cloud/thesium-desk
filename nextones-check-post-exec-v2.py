# -*- coding: utf-8 -*-
"""
nextones-check-post-exec-v2.py

v2 : decouverte automatique du schema (pas d'hypothese sur le nom de la table
positions). Re-utilise les sections 1/3/4/5 qui ont marche en v1 et adapte
la section 2.
"""

import sqlite3
import sys
from pathlib import Path

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
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

    # -- 0. Decouverte schema
    section("0. SCHEMA (tables pertinentes)")
    all_tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    print(f"  {len(all_tables)} tables au total")
    keywords = ("portfolio", "position", "holding", "order", "instrument", "thesis", "target")
    relevant = [t for t in all_tables if any(k in t.lower() for k in keywords)]
    print(f"  Tables pertinentes:")
    for t in relevant:
        try:
            cnt = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})").fetchall()]
            print(f"    {t:<35} rows={cnt:>6}  cols={cols}")
        except Exception as e:
            print(f"    {t:<35} ERROR {e}")

    # Detection table positions/holdings
    pos_table = None
    for name in ("positions", "holdings", "portfolio_positions", "portfolio_holdings", "current_positions"):
        if name in all_tables:
            pos_table = name
            break

    # -- 1. Orders cycle
    section("1. ORDERS du cycle (dernieres 8h, tickers cibles)")
    rows = cur.execute(
        """
        SELECT o.id, i.ticker, o.side, o.quantity, o.order_type,
               o.status, o.created_at
        FROM orders o
        JOIN instruments i ON i.id = o.instrument_id
        WHERE i.ticker IN ({})
          AND o.created_at >= datetime('now', '-8 hours')
        ORDER BY o.created_at DESC, i.ticker
        """.format(",".join("?" * len(EXPECTED_TICKERS))),
        EXPECTED_TICKERS,
    ).fetchall()
    print(f"  {len(rows)} ordre(s)")
    by_status = {}
    for r in rows:
        d = dict(r)
        by_status[d["status"]] = by_status.get(d["status"], 0) + 1
    print(f"  Repartition statut: {by_status}")

    # -- 2. Positions (dynamique)
    section("2. POSITIONS (table detectee)")
    if pos_table:
        print(f"  Table detectee: {pos_table}")
        cols = [c[1] for c in cur.execute(f"PRAGMA table_info({pos_table})").fetchall()]
        print(f"  Colonnes: {cols}")
        # Detecter qty column
        qty_col = next((c for c in ("quantity", "qty", "shares", "size") if c in cols), None)
        if qty_col:
            rows = cur.execute(
                f"SELECT * FROM {pos_table} WHERE {qty_col} != 0 ORDER BY {qty_col} DESC LIMIT 30"
            ).fetchall()
        else:
            rows = cur.execute(f"SELECT * FROM {pos_table} LIMIT 30").fetchall()
        print(f"  {len(rows)} position(s) non nulles")
        for r in rows:
            d = dict(r)
            tk_id = d.get("instrument_id")
            ticker = "?"
            if tk_id:
                t = cur.execute("SELECT ticker FROM instruments WHERE id=?", (tk_id,)).fetchone()
                if t:
                    ticker = t[0]
            in_cycle = " *" if ticker in EXPECTED_TICKERS else ""
            # Print colonnes principales
            key_fields = {k: d.get(k) for k in ("instrument_id", qty_col, "avg_price",
                                                 "average_price", "last_price",
                                                 "market_value", "unrealized_pnl")
                          if k in d}
            print(f"  {ticker:<7}{in_cycle:<2} {key_fields}")
    else:
        print("  AUCUNE table positions/holdings detectee.")
        print("  -> Reconstruction depuis orders (somme buy - sell par instrument)")
        rows = cur.execute(
            """
            SELECT i.ticker,
                   SUM(CASE WHEN o.side='buy' THEN o.quantity ELSE -o.quantity END) AS net_qty,
                   COUNT(*) AS n_orders,
                   MAX(o.created_at) AS last_order
            FROM orders o
            JOIN instruments i ON i.id = o.instrument_id
            WHERE o.status IN ('filled', 'executed')
            GROUP BY i.ticker
            HAVING net_qty != 0
            ORDER BY ABS(net_qty) DESC
            """
        ).fetchall()
        print(f"  {len(rows)} ticker(s) avec position nette non-nulle")
        for r in rows:
            d = dict(r)
            in_cycle = " *" if d["ticker"] in EXPECTED_TICKERS else ""
            print(f"  {d['ticker']:<7}{in_cycle:<2} net_qty={d['net_qty']:>+10.2f} "
                  f"orders={d['n_orders']:>3} last={d['last_order'][:19]}")

    # -- 3. Portfolio state
    section("3. PORTFOLIO STATE (snapshot actuel)")
    try:
        cols = [c[1] for c in cur.execute("PRAGMA table_info(portfolio_state)").fetchall()]
        if not cols:
            raise sqlite3.OperationalError("table portfolio_state vide ou inexistante")
        # Trouve l'ID col
        order_col = "id" if "id" in cols else cols[0]
        row = cur.execute(
            f"SELECT * FROM portfolio_state ORDER BY {order_col} DESC LIMIT 1"
        ).fetchone()
        if row:
            d = dict(row)
            nav = d.get("total_value") or d.get("nav") or d.get("equity") or 0
            cash = d.get("cash", 0) or 0
            invested_pct = ((nav - cash) / nav * 100) if nav else 0
            print(f"  NAV          : {nav:>15,.2f}")
            print(f"  Cash         : {cash:>15,.2f}")
            print(f"  Invested     : {nav - cash:>15,.2f}  ({invested_pct:.2f}%)")
            print(f"  PnL total    : {(d.get('pnl') or 0):>+15,.2f}")
            print(f"  Daily PnL    : {(d.get('daily_pnl') or 0):>+15,.2f}")
            print(f"  Updated      : {d.get('updated_at') or d.get('timestamp', '?')}")
            print(f"\n  Reference avant cycle 10:25: NAV 1,000,368  invested 56.22%")
            print(f"  Delta NAV       : {nav - 1000368:>+15,.2f}")
            print(f"  Delta invested  : {invested_pct - 56.22:>+15.2f} pp")
    except sqlite3.OperationalError as e:
        print(f"  ERREUR: {e}")

    # -- 4. Portfolio history (5 derniers)
    section("4. PORTFOLIO HISTORY (5 derniers points)")
    try:
        cols = [c[1] for c in cur.execute("PRAGMA table_info(portfolio_history)").fetchall()]
        order_col = "id" if "id" in cols else (cols[0] if cols else "rowid")
        rows = cur.execute(
            f"SELECT * FROM portfolio_history ORDER BY {order_col} DESC LIMIT 5"
        ).fetchall()
        for r in rows:
            d = dict(r)
            ts = d.get("timestamp") or d.get("date") or d.get("created_at") or d.get("updated_at", "?")
            nav = d.get("total_value") or d.get("nav") or 0
            cash = d.get("cash") or 0
            pnl = d.get("pnl") or 0
            print(f"  {str(ts)[:19]:<20} NAV={nav:>12,.2f} Cash={cash:>11,.2f} PnL={pnl:>+8.2f}")
    except sqlite3.OperationalError as e:
        print(f"  ERREUR: {e}")

    # -- 5. Recap cycle vs attendu
    section("5. RECAP CYCLE 10:25 (qty attendue vs reelle)")
    expected = [
        ("CAT", 22, "buy"), ("CSCO", 166, "buy"), ("TXN", 65, "buy"),
        ("AMD", 38, "buy"), ("PLD", 139, "buy"), ("XLK", 108, "buy"),
        ("AAPL", 13, "buy"), ("MSFT", 22, "sell"),
    ]
    all_ok = True
    for tk, qty, side in expected:
        order = cur.execute(
            """
            SELECT o.status, o.quantity FROM orders o
            JOIN instruments i ON i.id = o.instrument_id
            WHERE i.ticker = ? AND LOWER(o.side) = ?
              AND o.created_at >= datetime('now', '-8 hours')
            ORDER BY o.created_at DESC LIMIT 1
            """,
            (tk, side.lower()),
        ).fetchone()
        if order:
            d = dict(order)
            qty_ok = "OK" if abs(d["quantity"] - qty) < 0.01 else f"qty REEL={d['quantity']}"
            status_ok = "OK" if d["status"] == "filled" else d["status"].upper()
            print(f"  {tk:<7} {side.upper():<5} qty_attendu={qty:>4}  status={d['status']:<10} {qty_ok}")
            if d["status"] != "filled" or abs(d["quantity"] - qty) >= 0.01:
                all_ok = False
        else:
            print(f"  {tk:<7} {side.upper():<5} qty_attendu={qty:>4}  AUCUN ORDRE")
            all_ok = False
    print()
    if all_ok:
        print("  >>> Cycle 10:25 execute COMPLETEMENT et CONFORMEMENT au plan <<<")
    else:
        print("  >>> Au moins un ordre divergent - voir details ci-dessus <<<")

    # -- 6. Verification specifique : les 5 nouveaux equity sont-ils en portfolio?
    section("6. JALON 4.1 - les 5 nouveaux equity sont-ils en portefeuille?")
    new_equity = ["CAT", "CSCO", "TXN", "AMD", "PLD"]
    for tk in new_equity:
        # net position via orders
        net = cur.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN side='buy' THEN quantity ELSE -quantity END), 0) AS net
            FROM orders o
            JOIN instruments i ON i.id = o.instrument_id
            WHERE i.ticker = ? AND o.status IN ('filled', 'executed')
            """, (tk,)
        ).fetchone()[0]
        verdict = "OUI" if net > 0 else "NON"
        print(f"  {tk:<6} net_qty={net:>+8.2f}  -> en portefeuille: {verdict}")

    conn.close()
    print("\n" + "=" * 70)
    print("  Check termine")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
