# -*- coding: utf-8 -*-
"""
DIAG PHASE 9.5 - Perf rolling J-30 prereq
- shadow_perf_rolling schema (DDL + columns)
- shadow_fills schema + sample row + date range
- prices schema + instrument_id mapping (ticker -> instrument_id)
- Estimation J-30 coverage : combien de cycles dans fenetre J-30 from 20260612
"""
import sqlite3
import sys
import os

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def header(title):
    print("=" * 78)
    print(title)
    print("=" * 78)

def main():
    if not os.path.exists(DB):
        print("[ERR] DB not found:", DB)
        sys.exit(1)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---------- shadow_perf_rolling ----------
    header("shadow_perf_rolling : DDL + columns")
    row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='shadow_perf_rolling'"
    ).fetchone()
    if row:
        print(row["sql"])
    else:
        print("[ERR] table shadow_perf_rolling not found")
    print()
    print("PRAGMA table_info :")
    for r in cur.execute("PRAGMA table_info(shadow_perf_rolling)").fetchall():
        print("  cid={} name={} type={} notnull={} dflt={} pk={}".format(
            r["cid"], r["name"], r["type"], r["notnull"], r["dflt_value"], r["pk"]
        ))
    n = cur.execute("SELECT COUNT(*) AS n FROM shadow_perf_rolling").fetchone()["n"]
    print()
    print("rows actuelles :", n)

    # ---------- shadow_fills ----------
    print()
    header("shadow_fills : DDL + columns + sample + range")
    row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='shadow_fills'"
    ).fetchone()
    print(row["sql"] if row else "[ERR] table shadow_fills not found")
    print()
    print("PRAGMA table_info :")
    for r in cur.execute("PRAGMA table_info(shadow_fills)").fetchall():
        print("  name={} type={} notnull={}".format(r["name"], r["type"], r["notnull"]))
    print()
    n = cur.execute("SELECT COUNT(*) AS n FROM shadow_fills").fetchone()["n"]
    print("rows totales :", n)
    print()
    print("Sample 3 rows :")
    for r in cur.execute("SELECT * FROM shadow_fills LIMIT 3").fetchall():
        print("  ", dict(r))
    print()
    print("Cycles distincts dans shadow_fills :")
    for r in cur.execute(
        "SELECT SUBSTR(cycle_id,1,8) AS day, COUNT(DISTINCT cycle_id) AS n_cyc, "
        "COUNT(*) AS n_fills FROM shadow_fills "
        "GROUP BY day ORDER BY day"
    ).fetchall():
        print("  day={} n_cyc={} n_fills={}".format(r["day"], r["n_cyc"], r["n_fills"]))

    # ---------- prices ----------
    print()
    header("prices : DDL + columns + sample")
    row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='prices'"
    ).fetchone()
    print(row["sql"] if row else "[ERR]")
    print()
    print("PRAGMA table_info :")
    for r in cur.execute("PRAGMA table_info(prices)").fetchall():
        print("  name={} type={}".format(r["name"], r["type"]))
    print()
    print("Sample 3 rows :")
    for r in cur.execute("SELECT * FROM prices LIMIT 3").fetchall():
        print("  ", dict(r))

    # ---------- instruments mapping ----------
    print()
    header("instruments : ticker -> instrument_id mapping")
    row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='instruments'"
    ).fetchone()
    print(row["sql"] if row else "[ERR]")
    print()
    print("Sample 5 rows :")
    for r in cur.execute("SELECT * FROM instruments LIMIT 5").fetchall():
        print("  ", dict(r))
    print()
    n = cur.execute("SELECT COUNT(*) AS n FROM instruments").fetchone()["n"]
    print("total instruments :", n)

    # ---------- J-30 coverage estimation ----------
    print()
    header("J-30 coverage from 20260612")
    print()
    print("Fenetre J-30 = 20260513 -> 20260612 (30 jours)")
    print()
    print("Cycles dans shadow_fills sur cette fenetre :")
    rows = cur.execute(
        "SELECT SUBSTR(cycle_id,1,8) AS day, COUNT(DISTINCT cycle_id) AS n_cyc "
        "FROM shadow_fills "
        "WHERE SUBSTR(cycle_id,1,8) >= '20260513' AND SUBSTR(cycle_id,1,8) <= '20260612' "
        "GROUP BY day ORDER BY day"
    ).fetchall()
    total = 0
    for r in rows:
        print("  day={} n_cyc={}".format(r["day"], r["n_cyc"]))
        total += r["n_cyc"]
    print()
    print("TOTAL cycles J-30 :", total)
    print()
    print("Variants actifs :")
    for r in cur.execute(
        "SELECT id, name, active FROM shadow_variants WHERE active=1 ORDER BY id"
    ).fetchall():
        print("  id={} name={} active={}".format(r["id"], r["name"], r["active"]))

    conn.close()
    print()
    print("=" * 78)
    print("DIAG DONE")
    print("=" * 78)

if __name__ == "__main__":
    main()
