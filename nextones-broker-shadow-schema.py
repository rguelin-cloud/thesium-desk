# -*- coding: utf-8 -*-
# [NEXTONES-BROKER-SHADOW-SCHEMA-V1]
# DDL pour les tables d'execution "shadow" (paper) cote broker:
#   - broker_shadow_orders : chaque ordre Thesium accepte par le translator
#                            est dedouble en shadow (sans envoi PineConnector)
#   - broker_shadow_pnl    : snapshot quotidien du P&L shadow (mark-to-market
#                            au prix MetaAPI courant)
#   - broker_shadow_audit  : trace d'execution + raisons rejets
#
# Idempotent. Aucun seed.
#
# Usage:
#   py -3.13 nextones-broker-shadow-schema.py

import os
import sys
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "THESIUM_DB",
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db",
)

DDL = {
    "broker_shadow_orders": """
CREATE TABLE IF NOT EXISTS broker_shadow_orders (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                    TEXT NOT NULL,
    cycle_id              TEXT,
    thesium_ticker        TEXT NOT NULL,
    broker_symbol         TEXT NOT NULL,
    side                  TEXT NOT NULL,
    qty_requested         REAL NOT NULL,
    volume_lots           REAL NOT NULL,
    rounding_gap_pct      REAL,
    asset_class           TEXT,
    quote_ccy             TEXT,
    contract_size         REAL,
    lot_step              REAL,
    entry_price_metaapi   REAL,
    est_notional          REAL,
    est_margin            REAL,
    leverage_assumed      REAL,
    sl                    REAL,
    tp                    REAL,
    status                TEXT NOT NULL DEFAULT 'open',
    notes                 TEXT
);
""",
    "broker_shadow_pnl": """
CREATE TABLE IF NOT EXISTS broker_shadow_pnl (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_ts           TEXT NOT NULL,
    shadow_order_id       INTEGER NOT NULL,
    broker_symbol         TEXT NOT NULL,
    side                  TEXT NOT NULL,
    volume_lots           REAL NOT NULL,
    entry_price           REAL,
    mark_price            REAL,
    pnl_quote_ccy         REAL,
    pnl_eur               REAL,
    slippage_vs_thesium   REAL,
    notes                 TEXT,
    FOREIGN KEY (shadow_order_id) REFERENCES broker_shadow_orders(id)
);
""",
    "broker_shadow_audit": """
CREATE TABLE IF NOT EXISTS broker_shadow_audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    action          TEXT NOT NULL,
    cycle_id        TEXT,
    thesium_ticker  TEXT,
    broker_symbol   TEXT,
    payload_json    TEXT,
    notes           TEXT
);
""",
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sso_ticker ON broker_shadow_orders(thesium_ticker);",
    "CREATE INDEX IF NOT EXISTS idx_sso_broker ON broker_shadow_orders(broker_symbol);",
    "CREATE INDEX IF NOT EXISTS idx_sso_status ON broker_shadow_orders(status);",
    "CREATE INDEX IF NOT EXISTS idx_sso_cycle  ON broker_shadow_orders(cycle_id);",
    "CREATE INDEX IF NOT EXISTS idx_spnl_order ON broker_shadow_pnl(shadow_order_id);",
    "CREATE INDEX IF NOT EXISTS idx_spnl_ts    ON broker_shadow_pnl(snapshot_ts);",
    "CREATE INDEX IF NOT EXISTS idx_ssa_cycle  ON broker_shadow_audit(cycle_id);",
]


def main():
    if not os.path.exists(DB_PATH):
        print("[ERR] DB introuvable: " + DB_PATH)
        sys.exit(2)
    print("[INFO] DB: " + DB_PATH)
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        for name, ddl in DDL.items():
            cur.execute(ddl)
        for idx in INDEXES:
            cur.execute(idx)
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cur.execute(
            "INSERT INTO broker_shadow_audit(ts, action, payload_json, notes) "
            "VALUES(?, ?, ?, ?)",
            (ts, "schema_init", "{}", "Phase 2 shadow DDL applied"),
        )
        con.commit()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND "
            "name IN ('broker_shadow_orders','broker_shadow_pnl','broker_shadow_audit')"
        )
        rows = [r[0] for r in cur.fetchall()]
        print("[OK] Tables presentes: " + ", ".join(sorted(rows)))
    finally:
        con.close()


if __name__ == "__main__":
    main()
