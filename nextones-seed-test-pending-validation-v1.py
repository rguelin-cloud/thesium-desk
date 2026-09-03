# -*- coding: utf-8 -*-
# Cree un ordre de test en status='pending_validation' pour verifier
# que la card Pending Approvals l'affiche bien apres patch Option 2.
import sqlite3, os, sys, json

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def main():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Trouver un ticker existant (AAPL de preference)
    row = cur.execute(
        "SELECT id, ticker FROM instruments WHERE ticker = 'AAPL' LIMIT 1"
    ).fetchone()
    if not row:
        row = cur.execute("SELECT id, ticker FROM instruments LIMIT 1").fetchone()
    if not row:
        print("FAIL: no instrument found"); sys.exit(1)
    instrument_id = row["id"]
    ticker = row["ticker"]
    print("Using instrument:", ticker, "(id=" + str(instrument_id) + ")")

    # Last cycle
    cyc = cur.execute(
        "SELECT cycle_id FROM regime_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    cycle_id = cyc["cycle_id"] if cyc else "test-cycle"
    print("Cycle:", cycle_id)

    # INSERT order pending_validation
    cur.execute(
        "INSERT INTO orders (instrument_id, thesis_id, side, quantity, "
        "order_type, status, risk_check_result, cycle_id) "
        "VALUES (?, NULL, ?, ?, 'market', 'pending_validation', ?, ?)",
        (instrument_id, "buy", 1.0,
         json.dumps({"approved": True, "action": "approve", "approved_quantity": 1.0}),
         cycle_id)
    )
    new_id = cur.lastrowid
    conn.commit()
    print("Inserted order id =", new_id, "ticker =", ticker,
          "side=buy qty=1 status=pending_validation")

    # Verif via le SELECT de l'endpoint
    print()
    print("=== Test endpoint SELECT ===")
    rows = cur.execute("""
        SELECT o.id, o.side, o.status, i.ticker
        FROM orders o JOIN instruments i ON i.id = o.instrument_id
        WHERE o.status IN ('approved', 'pending_validation')
        ORDER BY o.created_at DESC LIMIT 10
    """).fetchall()
    print("count =", len(rows))
    for r in rows:
        print("  id=%d %s %s %s" % (r["id"], r["ticker"], r["side"], r["status"]))

    conn.close()

if __name__ == "__main__":
    main()
