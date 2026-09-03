# -*- coding: utf-8 -*-
# nextones-cleanup-seed-risk-check-v1.py
# Cleanup : UPDATE orders SET risk_check_result = NULL WHERE id IN (343, 344, 345)
# Idempotent : safe a re-executer (pose juste NULL).
import sqlite3
import sys
import os

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
TARGET_IDS = (343, 344, 345)

def main():
    if not os.path.exists(DB):
        print("FAIL: DB not found at", DB)
        sys.exit(1)

    conn = sqlite3.connect(DB, timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        cur = conn.cursor()

        # AVANT
        print("=== AVANT cleanup ===")
        for oid in TARGET_IDS:
            row = cur.execute(
                "SELECT id, ticker, side, status, risk_check_result FROM orders WHERE id = ?",
                (oid,),
            ).fetchone()
            if row is None:
                print("  id=%d : NOT FOUND" % oid)
            else:
                rcr = row[4]
                rcr_disp = (rcr[:80] + "...") if (rcr and len(rcr) > 80) else rcr
                print("  id=%d ticker=%s side=%s status=%s risk_check_result=%s" % (
                    row[0], row[1], row[2], row[3], rcr_disp
                ))

        # UPDATE
        placeholders = ",".join(["?"] * len(TARGET_IDS))
        sql = "UPDATE orders SET risk_check_result = NULL WHERE id IN (%s)" % placeholders
        cur.execute(sql, TARGET_IDS)
        affected = cur.rowcount
        conn.commit()
        print()
        print("UPDATE applied : %d rows affected" % affected)
        print()

        # APRES
        print("=== APRES cleanup ===")
        for oid in TARGET_IDS:
            row = cur.execute(
                "SELECT id, ticker, side, status, risk_check_result FROM orders WHERE id = ?",
                (oid,),
            ).fetchone()
            if row is None:
                print("  id=%d : NOT FOUND" % oid)
            else:
                print("  id=%d ticker=%s side=%s status=%s risk_check_result=%s" % (
                    row[0], row[1], row[2], row[3], row[4]
                ))

        print()
        print("OK cleanup done")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
