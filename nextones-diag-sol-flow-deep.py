# -*- coding: utf-8 -*-
# nextones-diag-sol-flow-deep.py
# Investigation profonde : pourquoi SOL passe 4.77 -> 2.77 et order #266 BUY ?
#
# Hypotheses :
# 1. apply_convergence_sizing est correcte (w*0=0) MAIS sol n'est pas dans allocations
# 2. L'order #266 (BUY 51.69 ce matin 08:26) a precede les patches convergence/SL
# 3. Le sizing est applique apres apply_convergence_sizing mais ecrase
# 4. portfolio_targets stocke des valeurs deja periemes

import os
import sys
import sqlite3
import json

PROD_ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
PCA_PATH = os.path.join(PROD_ROOT, "portfolio_construction_agent.py")
DB_PATH = os.path.join(PROD_ROOT, "thesium.db")


def main():
    print("=" * 70)
    print("DIAG SOL DEEP - apply_convergence_sizing + flow construction")
    print("=" * 70)

    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row

    # 1. Convergence snapshots SOL (les 5 dernieres)
    print("\n--- 1. convergence_snapshots SOL ---")
    try:
        rows = c.execute(
            """SELECT cycle_id, ticker, sizing_multiplier, regime, forced_exit, drift,
                      direction_consensus, created_at
               FROM convergence_snapshots
               WHERE ticker = 'SOL'
               ORDER BY created_at DESC LIMIT 5"""
        ).fetchall()
        for r in rows:
            print("  " + dict(r).__repr__())
    except Exception as e:
        print("  [ERR] " + str(e))

    # 2. portfolio_targets SOL (schema first)
    print("\n--- 2. Schema portfolio_targets ---")
    try:
        rows = c.execute("PRAGMA table_info(portfolio_targets)").fetchall()
        for r in rows:
            print("  " + dict(r).__repr__())
    except Exception as e:
        print("  [ERR] " + str(e))

    print("\n--- portfolio_targets SOL (toutes lignes) ---")
    try:
        rows = c.execute(
            """SELECT * FROM portfolio_targets WHERE ticker = 'SOL'"""
        ).fetchall()
        for r in rows:
            print("  " + dict(r).__repr__())
    except Exception as e:
        print("  [ERR] " + str(e))

    print("\n--- portfolio_targets_history SOL (5 dernieres) ---")
    try:
        rows = c.execute(
            """SELECT * FROM portfolio_targets_history
               WHERE ticker = 'SOL'
               ORDER BY rowid DESC LIMIT 5"""
        ).fetchall()
        for r in rows:
            print("  " + dict(r).__repr__())
    except Exception as e:
        print("  [ERR] " + str(e))

    # 3. Cycles recents
    print("\n--- 3. Derniers cycles ---")
    try:
        rows = c.execute(
            """SELECT cycle_id, COUNT(*) as n_tickers,
                      SUM(CASE WHEN forced_exit=1 THEN 1 ELSE 0 END) as n_forced,
                      MAX(created_at) as ts
               FROM convergence_snapshots
               GROUP BY cycle_id
               ORDER BY ts DESC LIMIT 5"""
        ).fetchall()
        for r in rows:
            print("  " + dict(r).__repr__())
    except Exception as e:
        print("  [ERR] " + str(e))

    # 4. Order #266 detail
    print("\n--- 4. Order #266 (SOL BUY 51.69 ce matin) ---")
    try:
        row = c.execute(
            """SELECT o.*, i.ticker FROM orders o
               JOIN instruments i ON i.id = o.instrument_id
               WHERE o.id = 266"""
        ).fetchone()
        if row:
            d = dict(row)
            print("  side=" + str(d.get("side")))
            print("  qty=" + str(d.get("quantity")))
            print("  status=" + str(d.get("status")))
            print("  created_at=" + str(d.get("created_at")))
            print("  validated_at=" + str(d.get("validated_at")))
            print("  thesis_id=" + str(d.get("thesis_id")))
            rcr = d.get("risk_check_result")
            print("  risk_check_result=" + str(rcr)[:500])
    except Exception as e:
        print("  [ERR] " + str(e))

    # 5. Trouver le code qui ecrit dans portfolio_targets / construit qty SOL
    print("\n--- 5. Search 'portfolio_targets' / 'INSERT INTO orders' dans PCA ---")
    with open(PCA_PATH, "r", encoding="utf-8-sig") as f:
        src = f.read()
    lines = src.split("\n")
    keywords = ["portfolio_targets", "INSERT INTO orders", "target_qty", "delta_qty",
                "apply_convergence_sizing(", "sizing_multiplier"]
    for kw in keywords:
        print("\n  [kw=" + kw + "]")
        for i, ln in enumerate(lines, 1):
            if kw in ln:
                print("    L" + str(i) + ": " + ln.rstrip()[:160])

    # 6. Construction agent : cherche la fonction qui calcule new_qty / delta
    print("\n--- 6. Fonctions principales PCA ---")
    for i, ln in enumerate(lines, 1):
        if ln.startswith("def "):
            print("  L" + str(i) + ": " + ln.rstrip())

    # 7. Cycle actuel des targets : qty cible vs actuelle SOL
    print("\n--- 7. SOL actuel vs target ---")
    try:
        pos = c.execute(
            """SELECT pp.quantity, pp.current_price, pp.weight_pct
               FROM portfolio_positions pp
               JOIN instruments i ON i.id = pp.instrument_id
               WHERE i.ticker = 'SOL'"""
        ).fetchone()
        tgt = c.execute(
            """SELECT * FROM portfolio_targets WHERE ticker = 'SOL'"""
        ).fetchone()
        if pos:
            print("  position : " + dict(pos).__repr__())
        if tgt:
            print("  target   : " + dict(tgt).__repr__())
            # Calcul du delta attendu si forced_exit
            tgt_w = tgt["target_weight_pct"] if "target_weight_pct" in tgt.keys() else None
            if tgt_w is not None:
                print("  target_weight_pct = " + str(tgt_w) + " -> si forced_exit=1, devrait etre 0")
    except Exception as e:
        print("  [ERR] " + str(e))

    c.close()


if __name__ == "__main__":
    main()
