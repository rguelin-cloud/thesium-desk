# -*- coding: utf-8 -*-
# Diag : etat de la DB apres dernier cycle
# - dernier cycle_id (regime_log)
# - orders du dernier cycle (tous statuts)
# - count par statut sur les 24 dernieres heures
# - test direct de l'endpoint SQL pending_approval modifie
import sqlite3, os, sys, datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def main():
    if not os.path.exists(DB):
        print("FAIL: DB not found"); sys.exit(1)
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1) Dernier cycle
    print("=== Dernier cycle_id (regime_log) ===")
    try:
        row = cur.execute(
            "SELECT id, cycle_id, regime, created_at FROM regime_log "
            "ORDER BY id DESC LIMIT 5"
        ).fetchall()
        for r in row:
            print("  id=%s cycle_id=%s regime=%s created_at=%s" %
                  (r["id"], r["cycle_id"], r["regime"], r["created_at"]))
    except Exception as e:
        print("  ERR regime_log:", e)
    print()

    # 2) Last 10 orders created
    print("=== 10 derniers orders (tous statuts) ===")
    rows = cur.execute(
        "SELECT o.id, o.cycle_id, o.status, o.side, o.quantity, "
        "i.ticker, o.created_at, o.rejection_reason "
        "FROM orders o LEFT JOIN instruments i ON i.id = o.instrument_id "
        "ORDER BY o.id DESC LIMIT 10"
    ).fetchall()
    for r in rows:
        print("  id=%d cycle=%s ticker=%s side=%s qty=%s status=%s reason=%s created=%s" %
              (r["id"], r["cycle_id"], r["ticker"], r["side"], r["quantity"],
               r["status"], r["rejection_reason"], r["created_at"]))
    print()

    # 3) Distribution status sur 24h
    print("=== Distribution status (24h) ===")
    rows = cur.execute(
        "SELECT status, COUNT(*) as n FROM orders "
        "WHERE created_at >= datetime('now', '-1 day') "
        "GROUP BY status ORDER BY n DESC"
    ).fetchall()
    for r in rows:
        print("  %s : %d" % (r["status"], r["n"]))
    print()

    # 4) Test du SELECT exact de l'endpoint
    print("=== Test SELECT endpoint /api/orders/pending_approval ===")
    rows = cur.execute("""
        SELECT o.id, o.side, o.quantity, o.status, o.cycle_id,
               o.created_at, o.thesis_id, o.order_type, o.limit_price,
               i.ticker, i.name,
               (SELECT close FROM prices WHERE instrument_id = o.instrument_id
                ORDER BY date DESC LIMIT 1) AS last_price
        FROM orders o
        JOIN instruments i ON i.id = o.instrument_id
        WHERE o.status IN ('approved', 'pending_validation')
        ORDER BY o.created_at DESC
        LIMIT 50
    """).fetchall()
    print("  count =", len(rows))
    for r in rows:
        print("  id=%d %s %s qty=%s status=%s cycle=%s" %
              (r["id"], r["ticker"], r["side"], r["quantity"], r["status"], r["cycle_id"]))

    conn.close()

if __name__ == "__main__":
    main()
