# -*- coding: utf-8 -*-
# Affichage des snapshots SOL/ZEC/BTC du dernier cycle convergence

import sqlite3

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

con = sqlite3.connect(DB, timeout=5.0)
con.row_factory = sqlite3.Row

print()
print("=" * 72)
print("[1] Cycles convergence_snapshots (5 derniers par created_at)")
print("-" * 72)
rows = con.execute(
    "SELECT cycle_id, COUNT(*) AS n, MIN(created_at) AS first_ts, MAX(created_at) AS last_ts "
    "FROM convergence_snapshots GROUP BY cycle_id ORDER BY MAX(created_at) DESC LIMIT 5"
).fetchall()
for r in rows:
    print("  cycle=%s  rows=%d  first=%s  last=%s" % (r["cycle_id"], r["n"], r["first_ts"], r["last_ts"]))

last_cid = rows[0]["cycle_id"] if rows else None
print()
print("  Dernier cycle disponible : %s" % last_cid)

print()
print("=" * 72)
print("[2] Snapshots SOL/ZEC/BTC/ETH/LINK dans le dernier cycle")
print("-" * 72)
if last_cid:
    for tk in ("SOL", "ZEC", "BTC", "ETH", "LINK", "HYPE"):
        r = con.execute(
            "SELECT * FROM convergence_snapshots WHERE cycle_id = ? AND ticker = ?",
            (last_cid, tk)
        ).fetchone()
        if r:
            print()
            print("  --- %s ---" % tk)
            for k in r.keys():
                v = r[k]
                if isinstance(v, str) and len(v) > 220:
                    v = v[:220] + "..."
                print("    %-25s = %s" % (k, v))
        else:
            print("  %s : ABSENT" % tk)

print()
print("=" * 72)
print("[3] Tous tickers en forced_exit dans le dernier cycle")
print("-" * 72)
if last_cid:
    rows = con.execute(
        "SELECT ticker, direction_consensus, convergence_pct, sizing_multiplier, forced_exit, drift "
        "FROM convergence_snapshots WHERE cycle_id = ? AND forced_exit = 1 "
        "ORDER BY ticker",
        (last_cid,)
    ).fetchall()
    print("  forced_exit=1 : %d tickers" % len(rows))
    for r in rows:
        print("    %-8s dir=%-12s conv=%.3f mult=%.3f drift=%d" % (
            r["ticker"], r["direction_consensus"], r["convergence_pct"],
            r["sizing_multiplier"], r["drift"]))

print()
print("=" * 72)
print("[4] SOL : tous les snapshots historiques (max 5)")
print("-" * 72)
rows = con.execute(
    "SELECT cycle_id, direction_consensus, convergence_pct, sizing_multiplier, forced_exit, drift, created_at "
    "FROM convergence_snapshots WHERE ticker = 'SOL' "
    "ORDER BY created_at DESC LIMIT 5"
).fetchall()
for r in rows:
    print("  cycle=%s dir=%-12s conv=%.3f mult=%.3f fe=%d drift=%d at=%s" % (
        r["cycle_id"], r["direction_consensus"], r["convergence_pct"],
        r["sizing_multiplier"], r["forced_exit"], r["drift"], r["created_at"]))

print()
print("=" * 72)
print("FIN DIAG")
print("=" * 72)
con.close()
