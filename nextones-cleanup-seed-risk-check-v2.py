# -*- coding: utf-8 -*-
# nextones-cleanup-seed-risk-check-v2.py
# Diag schema orders puis UPDATE risk_check_result = NULL pour 343/344/345
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

        # 1) Schema
        print("=== Schema orders ===")
        cols = cur.execute("PRAGMA table_info(orders)").fetchall()
        col_names = [c[1] for c in cols]
        for c in cols:
            print("  cid=%s name=%s type=%s notnull=%s dflt=%s pk=%s" % (c[0], c[1], c[2], c[3], c[4], c[5]))

        # Determine symbol-like column
        symbol_col = None
        for cand in ("symbol", "ticker", "instrument", "asset", "pair"):
            if cand in col_names:
                symbol_col = cand
                break

        # 2) AVANT
        print()
        print("=== AVANT cleanup ===")
        sel_cols = ["id"]
        if symbol_col:
            sel_cols.append(symbol_col)
        for extra in ("side", "status", "risk_check_result"):
            if extra in col_names:
                sel_cols.append(extra)
        sel_sql = "SELECT " + ", ".join(sel_cols) + " FROM orders WHERE id = ?"
        for oid in TARGET_IDS:
            row = cur.execute(sel_sql, (oid,)).fetchone()
            if row is None:
                print("  id=%d : NOT FOUND" % oid)
            else:
                parts = []
                for name, val in zip(sel_cols, row):
                    if name == "risk_check_result" and val is not None and len(str(val)) > 80:
                        val = str(val)[:80] + "..."
                    parts.append("%s=%s" % (name, val))
                print("  " + " ".join(parts))

        if "risk_check_result" not in col_names:
            print()
            print("FAIL: column risk_check_result not in orders table")
            sys.exit(1)

        # 3) UPDATE
        placeholders = ",".join(["?"] * len(TARGET_IDS))
        sql = "UPDATE orders SET risk_check_result = NULL WHERE id IN (%s)" % placeholders
        cur.execute(sql, TARGET_IDS)
        affected = cur.rowcount
        conn.commit()
        print()
        print("UPDATE applied : %d rows affected" % affected)

        # 4) APRES
        print()
        print("=== APRES cleanup ===")
        for oid in TARGET_IDS:
            row = cur.execute(sel_sql, (oid,)).fetchone()
            if row is None:
                print("  id=%d : NOT FOUND" % oid)
            else:
                parts = []
                for name, val in zip(sel_cols, row):
                    parts.append("%s=%s" % (name, val))
                print("  " + " ".join(parts))

        print()
        print("OK cleanup done")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
