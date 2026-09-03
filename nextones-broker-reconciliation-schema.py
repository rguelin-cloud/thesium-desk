# -*- coding: utf-8 -*-
# [NEXTONES-BROKER-RECONCILIATION-SCHEMA-V1]
# Cree la table broker_reconciliation_log pour stocker chaque cycle de
# reconciliation entre les positions ActivTrades (MetaAPI) et les positions
# Thesium (portfolio_positions).
#
# Schema :
#   broker_reconciliation_runs (1 ligne par cycle de reconciliation)
#     id, ts, source ('metaapi_live'|'shadow_only'), status, n_thesium,
#     n_broker, n_matched, n_drifts_qty, n_thesium_only, n_broker_only,
#     account_id, balance, equity, notes
#
#   broker_reconciliation_log (1 ligne par instrument compare)
#     id, run_id (FK), ts, thesium_ticker, broker_symbol,
#     qty_thesium, qty_broker, qty_drift, qty_drift_pct,
#     notional_thesium_usd, notional_broker_usd, notional_drift_usd,
#     status ('match'|'drift_qty'|'thesium_only'|'broker_only'),
#     details_json

import os
import sqlite3
import sys

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(PROD_DIR, "thesium.db")


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


def main():
    if not os.path.exists(DB):
        print(f"[FAIL] DB introuvable : {DB}")
        sys.exit(2)

    banner("[1] Connexion DB")
    con = sqlite3.connect(DB, timeout=10.0)
    con.execute("PRAGMA busy_timeout=10000")
    cur = con.cursor()

    banner("[2] Cree broker_reconciliation_runs")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS broker_reconciliation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            source TEXT NOT NULL CHECK(source IN ('metaapi_live','shadow_only')),
            status TEXT NOT NULL CHECK(status IN ('ok','partial','error')),
            n_thesium INTEGER NOT NULL DEFAULT 0,
            n_broker INTEGER NOT NULL DEFAULT 0,
            n_matched INTEGER NOT NULL DEFAULT 0,
            n_drifts_qty INTEGER NOT NULL DEFAULT 0,
            n_thesium_only INTEGER NOT NULL DEFAULT 0,
            n_broker_only INTEGER NOT NULL DEFAULT 0,
            account_id TEXT,
            balance REAL,
            equity REAL,
            notes TEXT
        )
    """)
    print("  [OK] broker_reconciliation_runs cree (ou existant)")

    banner("[3] Cree broker_reconciliation_log")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS broker_reconciliation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            ts TEXT NOT NULL,
            thesium_ticker TEXT,
            broker_symbol TEXT,
            qty_thesium REAL,
            qty_broker REAL,
            qty_drift REAL,
            qty_drift_pct REAL,
            notional_thesium_usd REAL,
            notional_broker_usd REAL,
            notional_drift_usd REAL,
            status TEXT NOT NULL CHECK(status IN
                ('match','drift_qty','thesium_only','broker_only','unmapped')),
            details_json TEXT,
            FOREIGN KEY (run_id) REFERENCES broker_reconciliation_runs(id)
        )
    """)
    print("  [OK] broker_reconciliation_log cree (ou existant)")

    banner("[4] Index")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_recon_log_run
        ON broker_reconciliation_log(run_id)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_recon_log_ticker
        ON broker_reconciliation_log(thesium_ticker)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_recon_log_status
        ON broker_reconciliation_log(status)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_recon_runs_ts
        ON broker_reconciliation_runs(ts)
    """)
    print("  [OK] index crees (4)")

    con.commit()

    banner("[5] Verification schema final")
    for tbl in ("broker_reconciliation_runs", "broker_reconciliation_log"):
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({tbl})").fetchall()]
        print(f"  {tbl} ({len(cols)} cols) : {cols}")
        n = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"    -> {n} lignes existantes")

    con.close()
    banner("[VERDICT] Schema reconciliation pret")
    print("  Tables : broker_reconciliation_runs + broker_reconciliation_log")
    print("  Index  : 4")
    print()
    print("Suivant : py -3.13 nextones-broker-reconciler.py")


if __name__ == "__main__":
    main()
