# -*- coding: utf-8 -*-
# [SEED_TEST_APPROVED_ORDER_V1]
# Cree 1 order de test en status='approved' pour valider la card UI Pending Approvals
# et le flux Execute/Reject end-to-end. Choix : BUY de 1.0 unite sur le premier
# instrument disponible avec un prix recent. Tag cycle_id = cycle courant (regime_log).
# Idempotent : si un order de test existe deja (validated_by='seed_test_v1'), on skip.

import io
import os
import sys
import sqlite3
from datetime import datetime

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(ROOT, "thesium.db")
SEED_TAG = "seed_test_v1"


def main():
    if not os.path.exists(DB):
        print("MISSING DB:", DB); sys.exit(2)

    con = sqlite3.connect(DB, timeout=15)
    con.execute("PRAGMA busy_timeout=15000")
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # 1) Idempotence : check si seed deja present (approved + tag)
    existing = cur.execute(
        "SELECT id, status, validated_by FROM orders "
        "WHERE validated_by = ? AND status = 'approved' "
        "ORDER BY id DESC LIMIT 5",
        (SEED_TAG,)
    ).fetchall()
    if existing:
        print("[SKIP] seed test orders already present:")
        for r in existing:
            print("  id={0} status={1} validated_by={2}".format(
                r["id"], r["status"], r["validated_by"]))
        print("\n[INFO] /api/orders/pending_approval va deja les renvoyer.")
        con.close()
        return

    # 2) Cycle courant
    row = cur.execute(
        "SELECT cycle_id FROM regime_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row:
        print("[FAIL] aucun cycle dans regime_log"); sys.exit(3)
    cycle_id = row["cycle_id"]
    print("[INFO] cycle courant:", cycle_id)

    # 3) Trouver un instrument avec prix recent
    inst = cur.execute("""
        SELECT i.id, i.ticker, i.name,
               (SELECT close FROM prices WHERE instrument_id = i.id
                ORDER BY date DESC LIMIT 1) AS last_price
        FROM instruments i
        WHERE i.ticker IN ('AAPL', 'MSFT', 'NVDA', 'SPY')
          AND (SELECT close FROM prices WHERE instrument_id = i.id ORDER BY date DESC LIMIT 1) IS NOT NULL
        ORDER BY i.id LIMIT 1
    """).fetchone()
    if not inst:
        # Fallback : premier instrument avec prix
        inst = cur.execute("""
            SELECT i.id, i.ticker, i.name,
                   (SELECT close FROM prices WHERE instrument_id = i.id
                    ORDER BY date DESC LIMIT 1) AS last_price
            FROM instruments i
            WHERE (SELECT close FROM prices WHERE instrument_id = i.id ORDER BY date DESC LIMIT 1) IS NOT NULL
            ORDER BY i.id LIMIT 1
        """).fetchone()
    if not inst:
        print("[FAIL] aucun instrument avec prix"); sys.exit(4)

    print("[INFO] instrument cible: id={0} ticker={1} last_price={2}".format(
        inst["id"], inst["ticker"], inst["last_price"]))

    # 4) Insertion des 3 orders de test : 1 BUY + 1 SELL + 1 BUY autre instrument
    now = datetime.utcnow().isoformat()

    orders_to_seed = [
        # (side, quantity, instrument_id, ticker)
        ("buy",  1.0, inst["id"], inst["ticker"]),
        ("sell", 1.0, inst["id"], inst["ticker"]),
    ]

    # Ajouter un 2e instrument si possible
    inst2 = cur.execute("""
        SELECT i.id, i.ticker,
               (SELECT close FROM prices WHERE instrument_id = i.id
                ORDER BY date DESC LIMIT 1) AS last_price
        FROM instruments i
        WHERE i.id != ?
          AND i.ticker IN ('MSFT', 'NVDA', 'SPY', 'QQQ', 'GOOGL')
          AND (SELECT close FROM prices WHERE instrument_id = i.id ORDER BY date DESC LIMIT 1) IS NOT NULL
        ORDER BY i.id LIMIT 1
    """, (inst["id"],)).fetchone()
    if inst2:
        orders_to_seed.append(("buy", 2.0, inst2["id"], inst2["ticker"]))

    inserted = []
    for side, qty, iid, ticker in orders_to_seed:
        cur.execute("""
            INSERT INTO orders
            (instrument_id, thesis_id, side, quantity, order_type, limit_price,
             status, risk_check_result, created_at, validated_by, cycle_id)
            VALUES (?, NULL, ?, ?, 'market', NULL, 'approved', '{"seed":true}',
                    ?, ?, ?)
        """, (iid, side, qty, now, SEED_TAG, cycle_id))
        oid = cur.lastrowid
        inserted.append((oid, side, qty, ticker))
        print("[OK] inserted order #{0} : {1} {2} {3}".format(oid, side, qty, ticker))

    con.commit()
    con.close()

    print("\n[DONE] {0} order(s) de test cree(s).".format(len(inserted)))
    print("[NEXT] Recharge l'UI : la card 'Pending Approvals' doit afficher {0} ligne(s).".format(
        len(inserted)))
    print("[NEXT] Tu peux cliquer Execute sur un order pour valider le flux complet.")


if __name__ == "__main__":
    main()
