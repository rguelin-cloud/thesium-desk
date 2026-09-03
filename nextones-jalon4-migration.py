# -*- coding: utf-8 -*-
"""
NEXTONES - Jalon 4 - Migration DB universe_candidates
Marker: [JALON4_DB_V1]

Cree la table universe_candidates et son index.
Idempotent : peut etre rejoue sans casser.

Usage:
    py -3.13 nextones-jalon4-migration.py
"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

DB_PATH = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
MARKER = "[JALON4_DB_V1]"

SCHEMA = """
CREATE TABLE IF NOT EXISTS universe_candidates (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker                   TEXT    NOT NULL,
    name                     TEXT,
    asset_class              TEXT    NOT NULL,
    sector                   TEXT,
    proposed_at              TEXT    NOT NULL,
    scan_batch               TEXT    NOT NULL,
    score                    REAL,
    momentum_12m_minus_1m    REAL,
    momentum_3m              REAL,
    realized_vol_90d         REAL,
    sharpe_90d               REAL,
    trend_strength_r2        REAL,
    volume_growth_3m         REAL,
    volume_usd_30d_avg       REAL,
    max_correl_existing      REAL,
    max_correl_with          TEXT,
    suggested_cap_pct        REAL,
    rationale                TEXT,
    rationale_source         TEXT,
    status                   TEXT    NOT NULL DEFAULT 'pending',
    reviewed_by              TEXT,
    reviewed_at              TEXT,
    notes                    TEXT,
    created_at               TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_unicand_status ON universe_candidates(status);",
    "CREATE INDEX IF NOT EXISTS idx_unicand_batch ON universe_candidates(scan_batch);",
    "CREATE INDEX IF NOT EXISTS idx_unicand_ticker ON universe_candidates(ticker);",
    "CREATE INDEX IF NOT EXISTS idx_unicand_proposed_at ON universe_candidates(proposed_at DESC);",
]


def main():
    if not DB_PATH.exists():
        print(f"ERROR: DB introuvable - {DB_PATH}")
        sys.exit(1)

    print(f"=== {MARKER} ===")
    print(f"DB: {DB_PATH}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.execute("PRAGMA busy_timeout=30000;")
    cur = conn.cursor()

    # Check si table existe deja
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='universe_candidates';"
    )
    exists_before = cur.fetchone() is not None
    print(f"Table existait avant patch: {exists_before}")

    # Apply schema
    cur.executescript(SCHEMA)
    for idx in INDEXES:
        cur.execute(idx)
    conn.commit()

    # Verif
    cur.execute("PRAGMA table_info(universe_candidates);")
    cols = cur.fetchall()
    print(f"\nTable universe_candidates - {len(cols)} colonnes:")
    for c in cols:
        print(f"  {c[0]:>3}  {c[1]:<28}  {c[2]:<10}  NotNull={c[3]}  Default={c[4]}")

    cur.execute("SELECT COUNT(*) FROM universe_candidates;")
    n = cur.fetchone()[0]
    print(f"\nLignes presentes: {n}")

    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='universe_candidates';"
    )
    idxs = [r[0] for r in cur.fetchall()]
    print(f"Index actifs: {len(idxs)}")
    for i in idxs:
        print(f"  - {i}")

    conn.close()
    print(f"\n=== {MARKER} OK ===")


if __name__ == "__main__":
    main()
