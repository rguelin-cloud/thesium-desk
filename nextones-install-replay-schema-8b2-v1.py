# -*- coding: utf-8 -*-
# Jalon 8B.2 - Ajoute 3 tables replay_* :
#   - replay_convergence_snapshots
#   - replay_targets
#   - replay_targets_history
#
# Mirror du schema prod + colonnes run_id + cycle_id_replay + day_t pour le replay.

import sqlite3
import sys

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

DDL = [
    # ----- replay_convergence_snapshots -----
    """
    CREATE TABLE IF NOT EXISTS replay_convergence_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        cycle_id_replay INTEGER NOT NULL,
        day_t TEXT NOT NULL,
        cycle_id_prod TEXT,
        ticker TEXT NOT NULL,
        direction_consensus TEXT,
        n_aligned INTEGER DEFAULT 0,
        n_present INTEGER DEFAULT 0,
        convergence_pct REAL DEFAULT 0,
        sizing_multiplier REAL DEFAULT 0,
        forced_exit INTEGER DEFAULT 0,
        drift INTEGER DEFAULT 0,
        is_crypto INTEGER DEFAULT 0,
        buckets_json TEXT,
        created_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_replay_conv_run_cycle ON replay_convergence_snapshots(run_id, cycle_id_replay)",
    "CREATE INDEX IF NOT EXISTS idx_replay_conv_ticker ON replay_convergence_snapshots(ticker)",

    # ----- replay_targets -----
    """
    CREATE TABLE IF NOT EXISTS replay_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        cycle_id_replay INTEGER NOT NULL,
        day_t TEXT NOT NULL,
        ticker TEXT NOT NULL,
        target_weight_pct REAL NOT NULL,
        active INTEGER DEFAULT 1,
        source TEXT DEFAULT 'replay_agent_v1',
        snapshot_id TEXT,
        score REAL,
        agent_decided INTEGER DEFAULT 0,
        created_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_replay_targets_run_cycle ON replay_targets(run_id, cycle_id_replay)",
    "CREATE INDEX IF NOT EXISTS idx_replay_targets_ticker ON replay_targets(ticker)",

    # ----- replay_targets_history -----
    """
    CREATE TABLE IF NOT EXISTS replay_targets_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        cycle_id_replay INTEGER NOT NULL,
        day_t TEXT NOT NULL,
        snapshot_id TEXT,
        ticker TEXT NOT NULL,
        score REAL,
        target_weight_pct REAL,
        prev_target_weight_pct REAL,
        components_json TEXT,
        regime TEXT,
        included INTEGER,
        cap_floor_applied TEXT,
        created_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_replay_hist_run_cycle ON replay_targets_history(run_id, cycle_id_replay)",
    "CREATE INDEX IF NOT EXISTS idx_replay_hist_ticker ON replay_targets_history(ticker)",
]


def main():
    print("=" * 70)
    print("JALON 8B.2 - Install replay_* schema (convergence + targets)")
    print("=" * 70)
    print(f"DB: {DB_PATH}\n")

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()

    for stmt in DDL:
        s = stmt.strip()
        first = s.split("\n", 1)[0][:80]
        try:
            cur.execute(s)
            print(f"  OK  : {first}")
        except sqlite3.Error as e:
            print(f"  ERR : {first} -> {e}")
            conn.close()
            sys.exit(1)

    conn.commit()

    # Verifie tables presentes
    print("\n  Verification :")
    for t in ("replay_convergence_snapshots", "replay_targets", "replay_targets_history"):
        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (t,))
        present = cur.fetchone()[0] == 1
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        rows = cur.fetchone()[0]
        flag = "OK" if present else "MISSING"
        print(f"    {t:35s} [{flag}]  rows={rows}")

    conn.close()
    print("\n  Schema 8B.2 installe.")


if __name__ == "__main__":
    main()
