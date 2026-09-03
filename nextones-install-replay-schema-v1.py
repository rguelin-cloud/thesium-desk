# -*- coding: utf-8 -*-
# nextones-install-replay-schema-v1.py
# Jalon 8A - Schema migration : 6 tables replay_*
# Idempotent (CREATE IF NOT EXISTS)
# Tables isolees de la prod, kill-switch NEXTONES_REPLAY_MODE=1

import os
import sys
import sqlite3
from datetime import datetime

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

SCHEMAS = {
    "replay_runs": """
        CREATE TABLE IF NOT EXISTS replay_runs (
            run_id           INTEGER PRIMARY KEY AUTOINCREMENT,
            label            TEXT NOT NULL,
            window_start     TEXT NOT NULL,
            window_end       TEXT NOT NULL,
            initial_capital  REAL NOT NULL,
            ablation_flags   TEXT,
            agents_perimeter TEXT,
            created_at       TEXT NOT NULL,
            finished_at      TEXT,
            status           TEXT NOT NULL DEFAULT 'pending',
            git_sha          TEXT,
            notes            TEXT
        )
    """,
    "replay_cycles": """
        CREATE TABLE IF NOT EXISTS replay_cycles (
            cycle_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id           INTEGER NOT NULL,
            day_t            TEXT NOT NULL,
            cycle_seq        INTEGER NOT NULL,
            regime_equity    TEXT,
            regime_crypto    TEXT,
            vix              REAL,
            cycle_status     TEXT NOT NULL DEFAULT 'ok',
            details_json     TEXT,
            created_at       TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES replay_runs(run_id)
        )
    """,
    "replay_orders": """
        CREATE TABLE IF NOT EXISTS replay_orders (
            order_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id           INTEGER NOT NULL,
            cycle_id         INTEGER NOT NULL,
            day_t            TEXT NOT NULL,
            ticker           TEXT NOT NULL,
            asset_class      TEXT,
            side             TEXT NOT NULL,
            qty              REAL NOT NULL,
            price_at_decision REAL,
            price_filled     REAL,
            slippage_bps     REAL,
            convergence      REAL,
            risk_check       TEXT,
            status           TEXT NOT NULL DEFAULT 'pending',
            reason           TEXT,
            created_at       TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES replay_runs(run_id),
            FOREIGN KEY (cycle_id) REFERENCES replay_cycles(cycle_id)
        )
    """,
    "replay_positions": """
        CREATE TABLE IF NOT EXISTS replay_positions (
            pos_id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id           INTEGER NOT NULL,
            day_t            TEXT NOT NULL,
            ticker           TEXT NOT NULL,
            qty              REAL NOT NULL,
            avg_cost         REAL,
            market_value     REAL,
            unrealized_pnl   REAL,
            asset_class      TEXT,
            FOREIGN KEY (run_id) REFERENCES replay_runs(run_id)
        )
    """,
    "replay_nav": """
        CREATE TABLE IF NOT EXISTS replay_nav (
            nav_id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id           INTEGER NOT NULL,
            day_t            TEXT NOT NULL,
            cash             REAL NOT NULL,
            positions_value  REAL NOT NULL,
            nav              REAL NOT NULL,
            daily_return     REAL,
            cumulative_return REAL,
            drawdown         REAL,
            FOREIGN KEY (run_id) REFERENCES replay_runs(run_id)
        )
    """,
    "replay_regime_log": """
        CREATE TABLE IF NOT EXISTS replay_regime_log (
            log_id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id           INTEGER NOT NULL,
            cycle_id         INTEGER,
            day_t            TEXT NOT NULL,
            regime_equity    TEXT,
            regime_crypto    TEXT,
            vix              REAL,
            spy_dd_20j       REAL,
            btc_dd_20j       REAL,
            vol_equity       REAL,
            vol_crypto       REAL,
            multiplier_equity REAL,
            multiplier_crypto REAL,
            details_json     TEXT,
            FOREIGN KEY (run_id) REFERENCES replay_runs(run_id)
        )
    """,
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_replay_cycles_run_day ON replay_cycles(run_id, day_t)",
    "CREATE INDEX IF NOT EXISTS idx_replay_orders_run_day ON replay_orders(run_id, day_t)",
    "CREATE INDEX IF NOT EXISTS idx_replay_orders_ticker ON replay_orders(ticker)",
    "CREATE INDEX IF NOT EXISTS idx_replay_positions_run_day ON replay_positions(run_id, day_t)",
    "CREATE INDEX IF NOT EXISTS idx_replay_nav_run_day ON replay_nav(run_id, day_t)",
    "CREATE INDEX IF NOT EXISTS idx_replay_regime_log_run_day ON replay_regime_log(run_id, day_t)",
]


def main():
    print("=" * 70)
    print("JALON 8A - INSTALL REPLAY SCHEMA V1")
    print("=" * 70)
    print(f"DB: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[ERR] DB introuvable: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    cur = conn.cursor()

    created = 0
    existed = 0
    for table_name, ddl in SCHEMAS.items():
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        already = cur.fetchone() is not None
        cur.execute(ddl)
        if already:
            existed += 1
            print(f"  [SKIP] {table_name:25s} existait deja")
        else:
            created += 1
            print(f"  [NEW ] {table_name:25s} cree")

    print()
    print("Index:")
    for ddl in INDEXES:
        cur.execute(ddl)
    print(f"  {len(INDEXES)} index OK (CREATE IF NOT EXISTS)")

    conn.commit()

    print()
    print("Verification finale:")
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'replay_%' ORDER BY name"
    )
    tables = [row[0] for row in cur.fetchall()]
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        n = cur.fetchone()[0]
        print(f"  {t:25s} rows={n}")

    conn.close()

    print()
    print(f"Tables creees : {created} | deja existantes : {existed}")
    print(f"Total replay_* : {len(tables)}")
    print()
    print("[DONE] Schema replay pret pour jalon 8B (orchestrator)")


if __name__ == "__main__":
    main()
