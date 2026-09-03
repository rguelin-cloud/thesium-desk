# -*- coding: utf-8 -*-
# [NEXTONES-BROKER-ADD-SYMBOL-V2]
# Ajout unitaire d'un symbole ActivTrades dans broker_universe_activtrades.
# V2 = aligne sur le schema reel constate via nextones-diag-broker-tables.
#
# Cas d'usage actuel : REET.US (iShares Global REIT ETF), oublie du seed initial.
#
# Schema reel :
#   broker_universe_activtrades(
#       broker_symbol PK, description, asset_class, underlying_ticker,
#       is_cfd, quote_ccy, discovered_at, last_seen_at, notes)
#   instrument_broker_mapping(
#       thesium_ticker PK, broker_symbol FK, instrument_type,
#       contract_size, min_lots, lot_step, tick_size, tick_value,
#       quote_ccy, tradable, last_verified_at, verification_source, notes)
#   broker_mapping_audit(
#       id, ts, action, thesium_ticker, broker_symbol, payload_json, notes)
#
# Usage :
#   py -3.13 nextones-broker-add-symbol.py --dry-run
#   py -3.13 nextones-broker-add-symbol.py
#   py -3.13 nextones-broker-add-symbol.py --rollback

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
SEED_NOTE = "manual_add_v2_2026-05-30"
AUDIT_NOTE = "[NEXTONES-BROKER-ADD-SYMBOL-V2]"

# ---- Symbole a ajouter --------------------------------------------------
SYMBOL = {
    "broker_symbol": "REET.US",
    "description": "iShares Trust - iShares Global REIT ETF",
    "asset_class": "etf_us",
    "underlying_ticker": "REET",
    "is_cfd": 1,
    "quote_ccy": "USD",
    # Specs broker pour eventuel mapping instrument_broker_mapping
    "contract_size": 1.0,
    "lot_step": 1.0,
    "min_lots": 1.0,
    "instrument_type": "etf",
    "tradable": 1,
    "verification_source": "manual_capture_2026-05-30",
}
# -------------------------------------------------------------------------


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def connect():
    if not os.path.exists(DB_PATH):
        log(f"ERREUR: base introuvable {DB_PATH}")
        sys.exit(2)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def table_exists(con, name):
    cur = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


def precheck(con):
    required = [
        "broker_universe_activtrades",
        "instrument_broker_mapping",
        "broker_mapping_audit",
    ]
    missing = [t for t in required if not table_exists(con, t)]
    if missing:
        log(f"ERREUR: tables manquantes -> {missing}")
        sys.exit(3)
    log("Precheck tables broker: OK")


def already_in_universe(con, broker_symbol):
    cur = con.execute(
        "SELECT 1 FROM broker_universe_activtrades WHERE broker_symbol=?",
        (broker_symbol,),
    )
    return cur.fetchone() is not None


def instrument_exists(con, ticker):
    if not table_exists(con, "instruments"):
        return False
    cur = con.execute("SELECT 1 FROM instruments WHERE ticker=? LIMIT 1", (ticker,))
    return cur.fetchone() is not None


def mapping_exists(con, thesium_ticker):
    cur = con.execute(
        "SELECT 1 FROM instrument_broker_mapping WHERE thesium_ticker=?",
        (thesium_ticker,),
    )
    return cur.fetchone() is not None


def insert_universe(con, dry_run):
    if already_in_universe(con, SYMBOL["broker_symbol"]):
        log(
            f"broker_universe_activtrades: {SYMBOL['broker_symbol']} deja present -> skip"
        )
        return False
    now = utcnow_iso()
    sql = """
        INSERT INTO broker_universe_activtrades
            (broker_symbol, description, asset_class, underlying_ticker,
             is_cfd, quote_ccy, discovered_at, last_seen_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        SYMBOL["broker_symbol"],
        SYMBOL["description"],
        SYMBOL["asset_class"],
        SYMBOL["underlying_ticker"],
        SYMBOL["is_cfd"],
        SYMBOL["quote_ccy"],
        now,
        now,
        SEED_NOTE,
    )
    if dry_run:
        log(f"DRY-RUN universe INSERT -> {params}")
        return True
    con.execute(sql, params)
    log(f"broker_universe_activtrades: insert OK {SYMBOL['broker_symbol']}")
    return True


def insert_mapping(con, dry_run):
    """
    Insere instrument_broker_mapping UNIQUEMENT si l'instrument logique
    existe dans la table instruments. Sinon skip propre (la table universe
    suffit pour que resolver/translator passent).
    """
    thesium_ticker = SYMBOL["underlying_ticker"]
    if not instrument_exists(con, thesium_ticker):
        log(
            f"instruments: ticker {thesium_ticker} non trouve "
            f"-> instrument_broker_mapping non cree (univers broker suffit)"
        )
        return False
    if mapping_exists(con, thesium_ticker):
        log(
            f"instrument_broker_mapping: mapping pour {thesium_ticker} deja present -> skip"
        )
        return False

    now = utcnow_iso()
    sql = """
        INSERT INTO instrument_broker_mapping
            (thesium_ticker, broker_symbol, instrument_type,
             contract_size, min_lots, lot_step,
             quote_ccy, tradable,
             last_verified_at, verification_source, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        thesium_ticker,
        SYMBOL["broker_symbol"],
        SYMBOL["instrument_type"],
        SYMBOL["contract_size"],
        SYMBOL["min_lots"],
        SYMBOL["lot_step"],
        SYMBOL["quote_ccy"],
        SYMBOL["tradable"],
        now,
        SYMBOL["verification_source"],
        SEED_NOTE,
    )
    if dry_run:
        log(f"DRY-RUN mapping INSERT -> {params}")
        return True
    con.execute(sql, params)
    log(
        f"instrument_broker_mapping: insert OK {thesium_ticker} -> {SYMBOL['broker_symbol']}"
    )
    return True


def write_audit(con, action, payload, dry_run):
    sql = """
        INSERT INTO broker_mapping_audit
            (ts, action, thesium_ticker, broker_symbol, payload_json, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    params = (
        utcnow_iso(),
        action,
        SYMBOL["underlying_ticker"],
        SYMBOL["broker_symbol"],
        json.dumps(payload, ensure_ascii=False),
        AUDIT_NOTE,
    )
    if dry_run:
        log(f"DRY-RUN audit -> action={action} payload={params[4]}")
        return
    con.execute(sql, params)
    log(f"broker_mapping_audit: trace ecrite (action={action})")


def do_add(dry_run):
    con = connect()
    try:
        precheck(con)
        con.execute("BEGIN")
        added_univ = insert_universe(con, dry_run)
        added_map = insert_mapping(con, dry_run)
        write_audit(
            con,
            action="add_symbol",
            payload={
                "broker_symbol": SYMBOL["broker_symbol"],
                "asset_class": SYMBOL["asset_class"],
                "underlying_ticker": SYMBOL["underlying_ticker"],
                "universe_inserted": added_univ,
                "mapping_inserted": added_map,
                "dry_run": dry_run,
            },
            dry_run=dry_run,
        )
        if dry_run:
            con.execute("ROLLBACK")
            log("DRY-RUN termine (rollback transaction).")
        else:
            con.execute("COMMIT")
            log("COMMIT OK.")
            # Verification post-commit
            cur = con.execute(
                "SELECT broker_symbol, asset_class, is_cfd, quote_ccy "
                "FROM broker_universe_activtrades WHERE broker_symbol=?",
                (SYMBOL["broker_symbol"],),
            )
            row = cur.fetchone()
            if row:
                log(f"VERIF post-commit -> {dict(row)}")
            cur = con.execute(
                "SELECT COUNT(*) AS n FROM broker_universe_activtrades"
            )
            log(f"Total broker_universe_activtrades = {cur.fetchone()['n']}")
    except Exception as e:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        log(f"ERREUR -> ROLLBACK: {e}")
        sys.exit(4)
    finally:
        con.close()


def do_rollback():
    con = connect()
    try:
        precheck(con)
        con.execute("BEGIN")
        cur = con.execute(
            "DELETE FROM instrument_broker_mapping WHERE broker_symbol=?",
            (SYMBOL["broker_symbol"],),
        )
        log(f"instrument_broker_mapping: {cur.rowcount} ligne(s) supprimee(s)")
        cur = con.execute(
            "DELETE FROM broker_universe_activtrades WHERE broker_symbol=?",
            (SYMBOL["broker_symbol"],),
        )
        log(f"broker_universe_activtrades: {cur.rowcount} ligne(s) supprimee(s)")
        write_audit(
            con,
            action="rollback_add_symbol",
            payload={"broker_symbol": SYMBOL["broker_symbol"]},
            dry_run=False,
        )
        con.execute("COMMIT")
        log("ROLLBACK applique avec succes.")
    except Exception as e:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        log(f"ERREUR rollback: {e}")
        sys.exit(5)
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="simulation sans ecrire")
    ap.add_argument("--rollback", action="store_true", help="retire REET.US")
    args = ap.parse_args()

    log(f"Cible : {SYMBOL['broker_symbol']} ({SYMBOL['asset_class']})")
    log(f"DB    : {DB_PATH}")
    log(f"Tag   : {AUDIT_NOTE}")

    if args.rollback:
        do_rollback()
    else:
        do_add(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
