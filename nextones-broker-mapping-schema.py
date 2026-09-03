# -*- coding: utf-8 -*-
# [NEXTONES-BROKER-MAPPING-SCHEMA-V1]
# Cree les tables instrument_broker_mapping et broker_universe_activtrades
# dans thesium.db. Idempotent (CREATE TABLE IF NOT EXISTS).
#
# Usage:
#   py -3.13 nextones-broker-mapping-schema.py
#
# Tables creees:
#   - broker_universe_activtrades : liste brute des symboles disponibles
#     chez ActivTrades (source de verite univers tradable)
#   - instrument_broker_mapping   : pont thesium_ticker <-> broker_symbol
#     avec specs MetaAPI (lot_step, tick_size, tick_value, min_lots, ...)
#
# Aucune ecriture de donnees ici : ce script ne fait que le DDL + index.
# Le seed des symboles est fait par nextones-broker-seed-universe.py.

import os
import sys
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "THESIUM_DB",
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db",
)

DDL_BROKER_UNIVERSE = """
CREATE TABLE IF NOT EXISTS broker_universe_activtrades (
    broker_symbol      TEXT PRIMARY KEY,
    description        TEXT,
    asset_class        TEXT NOT NULL,
    underlying_ticker  TEXT,
    is_cfd             INTEGER NOT NULL DEFAULT 1,
    quote_ccy          TEXT,
    discovered_at      TEXT NOT NULL,
    last_seen_at       TEXT NOT NULL,
    notes              TEXT
);
"""

DDL_BROKER_MAPPING = """
CREATE TABLE IF NOT EXISTS instrument_broker_mapping (
    thesium_ticker        TEXT PRIMARY KEY,
    broker_symbol         TEXT,
    instrument_type       TEXT NOT NULL,
    contract_size         REAL,
    min_lots              REAL,
    lot_step              REAL,
    tick_size             REAL,
    tick_value            REAL,
    quote_ccy             TEXT,
    tradable              INTEGER NOT NULL DEFAULT 0,
    last_verified_at      TEXT,
    verification_source   TEXT,
    notes                 TEXT,
    FOREIGN KEY (broker_symbol)
        REFERENCES broker_universe_activtrades(broker_symbol)
);
"""

DDL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_bu_act_class ON broker_universe_activtrades(asset_class);",
    "CREATE INDEX IF NOT EXISTS idx_bu_act_underlying ON broker_universe_activtrades(underlying_ticker);",
    "CREATE INDEX IF NOT EXISTS idx_ibm_broker ON instrument_broker_mapping(broker_symbol);",
    "CREATE INDEX IF NOT EXISTS idx_ibm_tradable ON instrument_broker_mapping(tradable);",
    "CREATE INDEX IF NOT EXISTS idx_ibm_type ON instrument_broker_mapping(instrument_type);",
]

DDL_AUDIT = """
CREATE TABLE IF NOT EXISTS broker_mapping_audit (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT NOT NULL,
    action            TEXT NOT NULL,
    thesium_ticker    TEXT,
    broker_symbol     TEXT,
    payload_json      TEXT,
    notes             TEXT
);
"""


def main():
    if not os.path.exists(DB_PATH):
        print("[ERR] DB introuvable: " + DB_PATH)
        sys.exit(2)

    print("[INFO] DB: " + DB_PATH)
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute(DDL_BROKER_UNIVERSE)
        cur.execute(DDL_BROKER_MAPPING)
        cur.execute(DDL_AUDIT)
        for ddl in DDL_INDEXES:
            cur.execute(ddl)

        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cur.execute(
            "INSERT INTO broker_mapping_audit(ts, action, payload_json, notes) "
            "VALUES(?, ?, ?, ?)",
            (ts, "schema_init", "{}", "Phase 1 DDL applied"),
        )
        con.commit()

        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
            "('broker_universe_activtrades','instrument_broker_mapping','broker_mapping_audit')"
        )
        rows = [r[0] for r in cur.fetchall()]
        print("[OK] Tables presentes: " + ", ".join(sorted(rows)))
    finally:
        con.close()


if __name__ == "__main__":
    main()
