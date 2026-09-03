# -*- coding: utf-8 -*-
# [DIAG_IC_MEMO_ORDERS_SOURCE_V3]
# Lit memo_generator.py autour du SELECT proposed_changes (L556 et L587 reperes V2)
# et inspecte les hooks ou un cycle_id pourrait etre injecte.
# ASCII pur, Windows-safe, read utf-8-sig / write utf-8 sans BOM.

import io
import os
import re
import sys
import sqlite3

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MEMO = os.path.join(ROOT, "memo_generator.py")
EXEC_ = os.path.join(ROOT, "execution_engine.py")
RISK = os.path.join(ROOT, "risk_engine.py")
DB = os.path.join(ROOT, "thesium.db")


def read_file(path):
    with io.open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read().splitlines()


def dump_range(path, start, end, label):
    print("")
    print("=" * 78)
    print("FILE: " + path)
    print("RANGE: L{0}-L{1}  [{2}]".format(start, end, label))
    print("=" * 78)
    lines = read_file(path)
    n = len(lines)
    s = max(1, start)
    e = min(n, end)
    for i in range(s, e + 1):
        print("{0:5d} | {1}".format(i, lines[i - 1]))


def grep_all(path, pattern, label):
    print("")
    print("-" * 78)
    print("GREP in {0} : {1}  [{2}]".format(os.path.basename(path), pattern, label))
    print("-" * 78)
    lines = read_file(path)
    rx = re.compile(pattern, re.IGNORECASE)
    hits = 0
    for idx, ln in enumerate(lines, 1):
        if rx.search(ln):
            print("  L{0:5d}: {1}".format(idx, ln.rstrip()))
            hits += 1
    if hits == 0:
        print("  (no match)")
    return hits


def main():
    if not os.path.exists(MEMO):
        print("MISSING: " + MEMO)
        sys.exit(2)

    # 1) Dump large autour de _build_proposed_changes_section et du SELECT L587
    dump_range(MEMO, 540, 680, "memo proposed_changes section")

    # 2) Cherche tout SELECT FROM orders
    grep_all(MEMO, r"FROM\s+orders", "SELECT orders dans memo")
    grep_all(MEMO, r"def\s+_build_proposed_changes_section", "fonction proposed_changes")
    grep_all(MEMO, r"current_cycle|cycle_id|regime_log", "refs cycle dans memo")

    # 3) Signature du generateur principal (pour comprendre comment on lui passe le cycle)
    grep_all(MEMO, r"def\s+generate_ic_memo|def\s+build_ic_memo|def\s+generate_memo", "entry points memo")

    # 4) Cote execution_engine : ou s'effectue le UPDATE status='filled'
    dump_range(EXEC_, 1050, 1110, "execution_engine UPDATE filled")
    grep_all(EXEC_, r"UPDATE\s+orders\s+SET\s+status", "UPDATE orders status")
    grep_all(EXEC_, r"INSERT\s+INTO\s+orders", "INSERT orders")
    grep_all(EXEC_, r"create_and_execute_order|create_order", "create order fn")
    grep_all(EXEC_, r"regime_log|cycle_id|current_cycle", "cycle refs in exec")

    # 5) Cote risk_engine : ou create_and_execute_order est appele depuis le decision cycle
    grep_all(RISK, r"create_and_execute_order|create_order|INSERT\s+INTO\s+orders", "risk -> orders")
    grep_all(RISK, r"regime_log|cycle_id|current_cycle", "cycle refs in risk")

    # 6) DB : derniers regime_log + sample orders
    if os.path.exists(DB):
        print("")
        print("=" * 78)
        print("DB checks")
        print("=" * 78)
        try:
            con = sqlite3.connect(DB, timeout=5)
            con.row_factory = sqlite3.Row
            cur = con.cursor()

            print("\n--- PRAGMA table_info(orders) ---")
            for r in cur.execute("PRAGMA table_info(orders)").fetchall():
                print("  ", dict(r))

            print("\n--- 5 derniers cycles regime_log ---")
            try:
                for r in cur.execute(
                    "SELECT cycle_id, ts FROM regime_log ORDER BY id DESC LIMIT 5"
                ).fetchall():
                    print("  ", dict(r))
            except Exception as e:
                print("  regime_log err:", e)
                # Essai sans colonne ts
                try:
                    for r in cur.execute(
                        "SELECT * FROM regime_log ORDER BY rowid DESC LIMIT 5"
                    ).fetchall():
                        print("  ", dict(r))
                except Exception as e2:
                    print("  regime_log fallback err:", e2)

            print("\n--- 10 derniers orders (id desc) ---")
            for r in cur.execute(
                "SELECT id, instrument_id, side, quantity, status, created_at, validated_at "
                "FROM orders ORDER BY id DESC LIMIT 10"
            ).fetchall():
                print("  ", dict(r))

            print("\n--- distinct status counts ---")
            for r in cur.execute(
                "SELECT status, COUNT(*) AS n FROM orders GROUP BY status ORDER BY n DESC"
            ).fetchall():
                print("  ", dict(r))

            con.close()
        except Exception as e:
            print("DB error:", e)
    else:
        print("\nDB missing: " + DB)


if __name__ == "__main__":
    main()
