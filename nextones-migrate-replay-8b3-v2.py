# nextones-migrate-replay-8b3-v2.py
# Migration Jalon 8B.3 - drop tables anciennes vides + create schema 8B.3 aligne (cycle_id_replay)
#
# Pre-conditions verifiees au prealable :
#   - replay_orders     : 0 rows (schema obsolete avec cycle_id)
#   - replay_positions  : 0 rows (schema obsolete sans cycle_id)
#   - replay_nav        : 0 rows (sera remplace par replay_nav_history)
#
# Actions :
#   1. DROP replay_orders / replay_positions / replay_nav
#   2. CREATE replay_orders (avec cycle_id_replay)
#   3. CREATE replay_fills (nouveau)
#   4. CREATE replay_positions (avec cycle_id_replay)
#   5. CREATE replay_nav_history (nouveau, remplace replay_nav)
#   6. CREATE indexes
#   7. Verifie chaque table cible
#
# Usage : py -3.13 nextones-migrate-replay-8b3-v2.py

import os
import sys
import sqlite3
import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

DDL = [
    # === replay_orders (cycle_id_replay) ===
    """
    CREATE TABLE IF NOT EXISTS replay_orders (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id          INTEGER NOT NULL REFERENCES replay_runs(run_id),
        cycle_id_replay INTEGER NOT NULL REFERENCES replay_cycles(cycle_id),
        day_t           TEXT NOT NULL,
        cycle_id_prod   TEXT,
        ticker          TEXT NOT NULL,
        side            TEXT NOT NULL,
        qty             REAL NOT NULL,
        qty_target      REAL,
        qty_current     REAL,
        target_weight_pct REAL,
        status          TEXT NOT NULL,
        fill_price      REAL,
        slippage_bps    REAL,
        price_close_t   REAL,
        nav_before      REAL,
        risk_check_json TEXT,
        rejection_reason TEXT,
        created_at      TEXT DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_replay_orders_run ON replay_orders(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_replay_orders_cycle ON replay_orders(cycle_id_replay)",
    "CREATE INDEX IF NOT EXISTS idx_replay_orders_ticker ON replay_orders(run_id, ticker)",

    # === replay_fills (nouveau) ===
    """
    CREATE TABLE IF NOT EXISTS replay_fills (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id          INTEGER NOT NULL REFERENCES replay_runs(run_id),
        cycle_id_replay INTEGER NOT NULL REFERENCES replay_cycles(cycle_id),
        day_t           TEXT NOT NULL,
        day_fill        TEXT,
        ticker          TEXT NOT NULL,
        side            TEXT NOT NULL,
        fill_price      REAL NOT NULL,
        fill_quantity   REAL NOT NULL,
        open_j1         REAL,
        slippage_bps    REAL,
        fees            REAL DEFAULT 0,
        notional        REAL,
        created_at      TEXT DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_replay_fills_run ON replay_fills(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_replay_fills_cycle ON replay_fills(cycle_id_replay)",

    # === replay_positions (cycle_id_replay) ===
    """
    CREATE TABLE IF NOT EXISTS replay_positions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id          INTEGER NOT NULL REFERENCES replay_runs(run_id),
        cycle_id_replay INTEGER NOT NULL REFERENCES replay_cycles(cycle_id),
        day_t           TEXT NOT NULL,
        ticker          TEXT NOT NULL,
        quantity        REAL NOT NULL,
        avg_cost        REAL,
        current_price   REAL,
        weight_pct      REAL,
        unrealized_pnl  REAL,
        created_at      TEXT DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_replay_positions_run ON replay_positions(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_replay_positions_cycle ON replay_positions(cycle_id_replay)",

    # === replay_nav_history (nouveau) ===
    """
    CREATE TABLE IF NOT EXISTS replay_nav_history (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id          INTEGER NOT NULL REFERENCES replay_runs(run_id),
        cycle_id_replay INTEGER NOT NULL REFERENCES replay_cycles(cycle_id),
        day_t           TEXT NOT NULL,
        nav             REAL NOT NULL,
        cash            REAL NOT NULL,
        positions_value REAL NOT NULL,
        daily_pnl       REAL DEFAULT 0,
        daily_pnl_pct   REAL DEFAULT 0,
        cumul_pnl       REAL DEFAULT 0,
        cumul_pnl_pct   REAL DEFAULT 0,
        n_positions     INTEGER DEFAULT 0,
        n_orders        INTEGER DEFAULT 0,
        n_fills         INTEGER DEFAULT 0,
        created_at      TEXT DEFAULT (datetime('now')),
        UNIQUE(run_id, day_t)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_replay_nav_run ON replay_nav_history(run_id)",
]


def log(msg=""):
    print(msg, flush=True)


def main():
    log("=" * 72)
    log("MIGRATION 8B.3 - drop anciennes + create nouvelles tables")
    log("=" * 72)
    log(f"DB : {DB}")

    if not os.path.exists(DB):
        log("FAIL : DB introuvable")
        sys.exit(1)

    conn = sqlite3.connect(DB, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()

    # 1. Verifie 0 rows avant drop (securite)
    log("\n[1/4] Verif 0 rows avant DROP")
    for tbl in ["replay_orders", "replay_positions", "replay_nav"]:
        try:
            n = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            log(f"  {tbl:<25s} : {n} rows  {'OK' if n == 0 else 'ABORT'}")
            if n > 0:
                log(f"FAIL : {tbl} contient {n} rows - migration annulee")
                conn.close()
                sys.exit(2)
        except sqlite3.OperationalError:
            log(f"  {tbl:<25s} : table inexistante (ok)")

    # 2. DROP anciennes
    log("\n[2/4] DROP tables anciennes")
    for tbl in ["replay_orders", "replay_positions", "replay_nav"]:
        try:
            cur.execute(f"DROP TABLE IF EXISTS {tbl}")
            log(f"  DROP {tbl} OK")
        except Exception as e:
            log(f"  FAIL DROP {tbl}: {e}")
            conn.rollback()
            conn.close()
            sys.exit(3)

    # 3. CREATE schema 8B.3
    log("\n[3/4] CREATE schema 8B.3 (4 tables + indexes)")
    for stmt in DDL:
        try:
            cur.execute(stmt)
            head = stmt.strip().split("\n")[0].strip()
            log(f"  OK : {head[:70]}")
        except Exception as e:
            log(f"  FAIL : {e}")
            log(f"  stmt : {stmt[:200]}")
            conn.rollback()
            conn.close()
            sys.exit(4)

    conn.commit()

    # 4. Verif tables creees
    log("\n[4/4] Verification finale")
    expected = ["replay_orders", "replay_fills", "replay_positions", "replay_nav_history"]
    all_ok = True
    for tbl in expected:
        row = cur.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchone()
        if row:
            # Verifie colonne cycle_id_replay presente
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({tbl})").fetchall()]
            has_cir = "cycle_id_replay" in cols
            log(f"  {tbl:<25s} : OK ({len(cols)} cols, cycle_id_replay={'YES' if has_cir else 'NO'})")
            if not has_cir:
                all_ok = False
        else:
            log(f"  {tbl:<25s} : FAIL (introuvable)")
            all_ok = False

    conn.close()

    log("\n" + "=" * 72)
    if all_ok:
        log("MIGRATION 8B.3 COMPLETE - PASS")
        log("Next : py -3.13 nextones-run-replay-8b3-v2.py")
    else:
        log("MIGRATION 8B.3 - FAIL (voir details ci-dessus)")
        sys.exit(5)
    log("=" * 72)


if __name__ == "__main__":
    main()
