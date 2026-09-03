# -*- coding: utf-8 -*-
# nextones-verify-full-cycle.py
# Verifie le dernier cycle apres execute-cycle :
# 3. convergence_snapshots du nouveau cycle (forced_exit count)
# 4. portfolio_targets : les forced_exit doivent etre a 0
# 5. orders : aucun BUY sur les forced_exit
# 6. risk_pretrade_log : blocked_by

import os
import sys
import sqlite3
import json

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"


def main():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row

    # 3. Dernier cycle convergence
    print("--- 3. convergence_snapshots dernier cycle ---")
    row = c.execute(
        """SELECT cycle_id, MAX(created_at) as ts,
                  SUM(CASE WHEN forced_exit=1 THEN 1 ELSE 0 END) as n_forced,
                  COUNT(*) as n
           FROM convergence_snapshots
           GROUP BY cycle_id ORDER BY ts DESC LIMIT 1"""
    ).fetchone()
    cycle_id = row["cycle_id"]
    n_forced = row["n_forced"]
    print("cycle_id=" + cycle_id + " ts=" + row["ts"])
    print("n_tickers=" + str(row["n"]) + " n_forced_exit=" + str(n_forced))

    # Liste des forced_exit
    fr = c.execute(
        """SELECT ticker, sizing_multiplier, direction_consensus
           FROM convergence_snapshots
           WHERE cycle_id=? AND forced_exit=1
           ORDER BY ticker""",
        (cycle_id,),
    ).fetchall()
    forced_tickers = [r["ticker"] for r in fr]
    print("Forced exit : " + str(forced_tickers))

    # 4. portfolio_targets - les forced_exit doivent etre a 0
    print("\n--- 4. portfolio_targets sur forced_exit ---")
    pass_targets = 0
    fail_targets = 0
    for t in forced_tickers:
        tr = c.execute(
            "SELECT ticker, target_weight_pct, updated_at, snapshot_id FROM portfolio_targets WHERE ticker=?",
            (t,),
        ).fetchone()
        if tr is None:
            print("  [WARN] " + t + " : pas de ligne dans portfolio_targets")
            continue
        w = tr["target_weight_pct"]
        ts_ = tr["updated_at"]
        if abs(w) < 1e-9:
            print("  [OK]   " + t + " target_weight_pct=" + str(w) + " updated_at=" + str(ts_))
            pass_targets += 1
        else:
            print("  [FAIL] " + t + " target_weight_pct=" + str(w) + " (attendu 0) updated_at=" + str(ts_))
            fail_targets += 1
    print("Resultat targets : " + str(pass_targets) + "/" + str(len(forced_tickers)) + " a 0")

    # 5. Orders du jour - aucun BUY sur les forced_exit
    print("\n--- 5. Orders du jour ---")
    rows = c.execute(
        """SELECT o.id, o.side, o.quantity, o.status, o.created_at, i.ticker
           FROM orders o JOIN instruments i ON i.id = o.instrument_id
           WHERE date(o.created_at) = date('now')
           ORDER BY o.created_at DESC LIMIT 30"""
    ).fetchall()
    print("Total orders aujourd'hui : " + str(len(rows)))
    illegal_buys = []
    for r in rows:
        d = dict(r)
        flag = ""
        if d["side"] == "buy" and d["ticker"] in forced_tickers:
            flag = " [ILLEGAL_BUY_ON_FORCED_EXIT]"
            illegal_buys.append(d)
        print("  #" + str(d["id"]) + " " + d["ticker"] + " " + d["side"]
              + " " + str(d["quantity"]) + " " + d["status"] + " @ " + d["created_at"] + flag)

    if illegal_buys:
        print("\n[ALERT] " + str(len(illegal_buys)) + " BUY illegitimes detectes !")
    else:
        print("\n[OK] Aucun BUY sur forced_exit detecte")

    # 6. risk_pretrade_log
    print("\n--- 6. risk_pretrade_log recent ---")
    rows = c.execute(
        """SELECT ts, symbol, side, qty, passed, blocked_by, marker
           FROM risk_pretrade_log
           ORDER BY id DESC LIMIT 15"""
    ).fetchall()
    blocked_counts = {}
    for r in rows:
        d = dict(r)
        bb = d["blocked_by"] or "(passed)"
        blocked_counts[bb] = blocked_counts.get(bb, 0) + 1
        print("  " + d["ts"] + " " + d["symbol"] + " " + d["side"]
              + " qty=" + str(d["qty"])
              + " passed=" + str(d["passed"]) + " blocked_by=" + str(d["blocked_by"]))

    print("\nResume blocked_by : " + str(blocked_counts))

    # 7. Last memo
    print("\n--- 7. Dernier memo ic ---")
    m = c.execute(
        "SELECT id, created_at FROM ic_memos ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if m:
        print("memo #" + str(m["id"]) + " " + m["created_at"])
        print("URL : http://localhost:8000/api/memos/" + str(m["id"]) + "/markdown")

    c.close()


if __name__ == "__main__":
    main()
