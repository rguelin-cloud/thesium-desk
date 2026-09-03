#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Diag : pourquoi BTC absent des ordres alors que forced_exit
# Verifie :
# - position BTC actuelle (qty + valeur)
# - dernier portfolio_targets BTC
# - convergence_snapshots dernier verdict BTC
# - orders pending BTC

import os
import sys
import sqlite3
import json

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def main():
    if not os.path.isfile(DB):
        print("ERR : DB introuvable :", DB)
        sys.exit(1)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    print("=== 1. Position BTC actuelle (portfolio) ===")
    try:
        rows = conn.execute("""
            SELECT * FROM portfolio
            WHERE UPPER(ticker) = 'BTC'
        """).fetchall()
        if not rows:
            print("  Aucune ligne portfolio pour BTC")
        for r in rows:
            print("  ", dict(r))
    except Exception as e:
        print("  ERR portfolio :", e)

    print()
    print("=== 2. Dernier portfolio_targets BTC ===")
    try:
        rows = conn.execute("""
            SELECT * FROM portfolio_targets
            WHERE UPPER(ticker) = 'BTC'
            ORDER BY id DESC LIMIT 3
        """).fetchall()
        if not rows:
            print("  Aucune ligne portfolio_targets pour BTC")
        for r in rows:
            print("  ", dict(r))
    except Exception as e:
        print("  ERR targets :", e)

    print()
    print("=== 3. Dernier convergence_snapshots BTC (verdict + forced_exit) ===")
    try:
        rows = conn.execute("""
            SELECT id, cycle_id, ticker, verdict, forced_exit,
                   sizing_multiplier, created_at
            FROM convergence_snapshots
            WHERE UPPER(ticker) = 'BTC'
            ORDER BY id DESC LIMIT 3
        """).fetchall()
        if not rows:
            print("  Aucun snapshot convergence pour BTC")
        for r in rows:
            print("  ", dict(r))
    except Exception as e:
        print("  ERR convergence :", e)

    print()
    print("=== 4. Orders pending BTC (status pending ou validation) ===")
    try:
        rows = conn.execute("""
            SELECT id, ticker, side, qty, status, created_at
            FROM orders
            WHERE UPPER(ticker) = 'BTC'
              AND status IN ('pending', 'validation', 'pending_validation')
            ORDER BY id DESC LIMIT 10
        """).fetchall()
        if not rows:
            print("  Aucun order pending pour BTC")
        for r in rows:
            print("  ", dict(r))
    except Exception as e:
        print("  ERR orders :", e)

    print()
    print("=== 5. Dernier order BTC tout statut ===")
    try:
        rows = conn.execute("""
            SELECT id, ticker, side, qty, status, created_at
            FROM orders
            WHERE UPPER(ticker) = 'BTC'
            ORDER BY id DESC LIMIT 5
        """).fetchall()
        if not rows:
            print("  Aucun order pour BTC")
        for r in rows:
            print("  ", dict(r))
    except Exception as e:
        print("  ERR orders all :", e)

    print()
    print("=== 6. Dernier portfolio_targets_history BTC ===")
    try:
        rows = conn.execute("""
            SELECT id, cycle_id, ticker, score, target_weight_pct,
                   prev_target_weight_pct, included, created_at
            FROM portfolio_targets_history
            WHERE UPPER(ticker) = 'BTC'
            ORDER BY id DESC LIMIT 3
        """).fetchall()
        if not rows:
            print("  Aucune history pour BTC")
        for r in rows:
            print("  ", dict(r))
    except Exception as e:
        print("  ERR history :", e)

    conn.close()
    print()
    print("=== DONE diag BTC ===")


if __name__ == "__main__":
    main()
