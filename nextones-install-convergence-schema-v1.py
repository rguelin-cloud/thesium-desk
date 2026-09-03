"""
[INSTALL_CONVERGENCE_SCHEMA_V1]
Cree la table convergence_snapshots + indexes.

Schema :
  - cycle_id          : TEXT NOT NULL
  - ticker            : TEXT NOT NULL
  - direction_consensus : TEXT NOT NULL (long/short/neutral)
  - n_aligned         : INTEGER
  - n_present         : INTEGER
  - convergence_pct   : REAL
  - sizing_multiplier : REAL
  - forced_exit       : INTEGER (0/1)
  - drift             : INTEGER (0/1)
  - is_crypto         : INTEGER (0/1)
  - buckets_json      : TEXT (detail L1-L5)
  - created_at        : TEXT

PK composite (cycle_id, ticker) via UNIQUE.
"""

import os
import sqlite3

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS convergence_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    direction_consensus TEXT NOT NULL,
    n_aligned INTEGER NOT NULL DEFAULT 0,
    n_present INTEGER NOT NULL DEFAULT 0,
    convergence_pct REAL NOT NULL DEFAULT 0,
    sizing_multiplier REAL NOT NULL DEFAULT 0,
    forced_exit INTEGER NOT NULL DEFAULT 0,
    drift INTEGER NOT NULL DEFAULT 0,
    is_crypto INTEGER NOT NULL DEFAULT 0,
    buckets_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(cycle_id, ticker)
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_convergence_cycle "
    "ON convergence_snapshots(cycle_id);",
    "CREATE INDEX IF NOT EXISTS idx_convergence_ticker "
    "ON convergence_snapshots(ticker);",
    "CREATE INDEX IF NOT EXISTS idx_convergence_created "
    "ON convergence_snapshots(created_at);",
]


def main():
    if not os.path.exists(DB_PATH):
        print("ERROR: DB not found at %s" % DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        for idx_sql in INDEXES:
            conn.execute(idx_sql)
        conn.commit()

        # Verifications
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='convergence_snapshots'"
        )
        ok_table = cur.fetchone() is not None
        cur = conn.execute("PRAGMA table_info(convergence_snapshots)")
        cols = [r[1] for r in cur.fetchall()]
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='convergence_snapshots'"
        )
        idxs = [r[0] for r in cur.fetchall()]

        print("table convergence_snapshots : %s" % ("OK" if ok_table else "MISSING"))
        print("columns (%d) : %s" % (len(cols), ", ".join(cols)))
        print("indexes (%d) : %s" % (len(idxs), ", ".join(idxs)))
        print("DONE")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
