# -*- coding: utf-8 -*-
# nextones-add-reet-instrument-v2.py
# Ajoute REET (iShares Global REIT ETF) a l'outil NEXTONES.
#
# Corrige v1 :
#  - Bonne table broker : instrument_broker_mapping (et non broker_mapping)
#  - Verifie / insere dans broker_universe_activtrades (REET.US)
#  - universe_candidates : ajoute proposed_at + scan_batch (NOT NULL)
#  - Utilise datetime.now(timezone.utc) (3.13+)
#  - Skip instruments (deja insere par v1)
#
# Usage : py -3.13 nextones-add-reet-instrument-v2.py

import sqlite3
import sys
import os
from datetime import datetime, timezone, timedelta

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

TICKER_INTERNAL  = "REET"
TICKER_YAHOO     = "REET"
TICKER_ACTIV     = "REET.US"
ASSET_CLASS      = "ETF"          # pour instruments / universe_candidates
INSTR_TYPE       = "equity_us"    # pour instrument_broker_mapping (coherent CAT/CSCO)
BROKER_AC        = "equity_us"    # pour broker_universe_activtrades.asset_class
SECTOR           = "REAL_ESTATE"
CURRENCY         = "USD"
NAME             = "iShares Global REIT ETF"


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def open_db():
    if not os.path.exists(DB_PATH):
        log(f"FATAL : DB introuvable -> {DB_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def table_cols(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]


def step1_instrument_broker_mapping(conn):
    """Insere REET <-> REET.US dans instrument_broker_mapping."""
    cur = conn.cursor()
    cols = table_cols(cur, "instrument_broker_mapping")
    if not cols:
        log("WARN : instrument_broker_mapping absente -> skip step1")
        return False
    log(f"instrument_broker_mapping cols : {cols}")

    cur.execute("""
        SELECT thesium_ticker, broker_symbol
        FROM instrument_broker_mapping
        WHERE thesium_ticker = ?
    """, (TICKER_INTERNAL,))
    existing = cur.fetchone()

    now = now_utc()
    if existing:
        log(f"step1 : entree existante {existing} -> UPDATE")
        cur.execute("""
            UPDATE instrument_broker_mapping
            SET broker_symbol = ?, instrument_type = ?, contract_size = ?,
                min_lots = ?, lot_step = ?, quote_ccy = ?, tradable = 1,
                last_verified_at = ?, verification_source = ?, notes = ?
            WHERE thesium_ticker = ?
        """, (TICKER_ACTIV, INSTR_TYPE, 1.0, 1.0, 1.0, CURRENCY,
              now, "manual_add_reet_v2",
              "REET iShares Global REIT ETF - ajoute manuellement",
              TICKER_INTERNAL))
    else:
        log("step1 : INSERT instrument_broker_mapping")
        cur.execute("""
            INSERT INTO instrument_broker_mapping
            (thesium_ticker, broker_symbol, instrument_type,
             contract_size, min_lots, lot_step, tick_size, tick_value,
             quote_ccy, tradable, last_verified_at, verification_source, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        """, (TICKER_INTERNAL, TICKER_ACTIV, INSTR_TYPE,
              1.0, 1.0, 1.0, 0.01, 0.01,
              CURRENCY, now, "manual_add_reet_v2",
              "REET iShares Global REIT ETF - ajoute manuellement"))
    conn.commit()
    log(f"step1 OK : {TICKER_INTERNAL} <-> {TICKER_ACTIV}")
    return True


def step2_broker_universe_activtrades(conn):
    """Verifie / insere REET.US dans broker_universe_activtrades."""
    cur = conn.cursor()
    cols = table_cols(cur, "broker_universe_activtrades")
    if not cols:
        log("WARN : broker_universe_activtrades absente -> skip step2")
        return False
    log(f"broker_universe_activtrades cols : {cols}")

    cur.execute("""
        SELECT broker_symbol, asset_class, underlying_ticker
        FROM broker_universe_activtrades
        WHERE broker_symbol = ?
    """, (TICKER_ACTIV,))
    found = cur.fetchone()
    if found:
        log(f"step2 : REET.US deja present dans seed ActivTrades -> {found}")
        return True

    now = now_utc()
    log("step2 : INSERT REET.US dans broker_universe_activtrades")
    cur.execute("""
        INSERT INTO broker_universe_activtrades
        (broker_symbol, description, asset_class, underlying_ticker,
         is_cfd, quote_ccy, discovered_at, last_seen_at, notes)
        VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
    """, (TICKER_ACTIV, NAME, BROKER_AC, TICKER_INTERNAL,
          CURRENCY, now, now, "manual_add_reet_v2"))
    conn.commit()
    log("step2 OK : REET.US enregistre dans seed ActivTrades")
    return True


def step3_universe_candidates(conn):
    """Pre-positionne REET dans universe_candidates (status=pending)."""
    cur = conn.cursor()
    cols = table_cols(cur, "universe_candidates")
    if not cols:
        log("WARN : universe_candidates absente -> skip step3")
        return False
    log(f"universe_candidates cols : {len(cols)} colonnes")

    cur.execute("""
        SELECT id, ticker, status FROM universe_candidates
        WHERE ticker = ?
        ORDER BY id DESC LIMIT 1
    """, (TICKER_INTERNAL,))
    existing = cur.fetchone()
    if existing:
        log(f"step3 : {existing} deja present -> skip")
        return True

    now = now_utc()
    scan_batch = f"manual-add-reet-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"

    payload = {
        "ticker": TICKER_INTERNAL,
        "name": NAME,
        "asset_class": ASSET_CLASS,
        "sector": SECTOR,
        "proposed_at": now,
        "scan_batch": scan_batch,
        "status": "pending",
        "rationale": "Ajout manuel - ETF immobilier global, diversification REIT",
        "rationale_source": "manual_user_request",
        "notes": "Insertion manuelle via nextones-add-reet-instrument-v2",
    }
    keys = [k for k in payload.keys() if k in cols]
    vals = [payload[k] for k in keys]
    placeholders = ",".join("?" * len(keys))
    sql = f"INSERT INTO universe_candidates ({','.join(keys)}) VALUES ({placeholders})"
    log(f"step3 SQL : {sql}")
    cur.execute(sql, vals)
    conn.commit()
    log(f"step3 OK : REET ajoute (scan_batch={scan_batch}, status=pending)")
    return True


def step4_fetch_prices_90d(conn):
    """Telechargement 90 jours Yahoo Finance."""
    try:
        import yfinance as yf
    except ImportError:
        log("WARN : yfinance non installe -> skip step4")
        log("       -> py -3.13 -m pip install yfinance")
        return False

    cur = conn.cursor()
    cols = table_cols(cur, "prices")
    if not cols:
        log("WARN : table prices absente -> skip step4")
        return False
    log(f"prices cols : {cols}")

    # Verifier si on a deja des prix REET
    cur.execute("SELECT COUNT(*) FROM prices WHERE ticker = ?", (TICKER_INTERNAL,))
    existing_cnt = cur.fetchone()[0]
    if existing_cnt > 0:
        log(f"step4 : {existing_cnt} prix REET deja en base -> on rafraichit quand meme")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=120)
    log(f"step4 : fetch Yahoo {TICKER_YAHOO} du {start.date()} au {end.date()}")

    try:
        df = yf.download(TICKER_YAHOO,
                         start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"),
                         progress=False,
                         auto_adjust=False)
    except Exception as e:
        log(f"ERROR yfinance : {e}")
        return False

    if df is None or df.empty:
        log("ERROR : Yahoo n'a retourne aucune donnee pour REET")
        return False

    log(f"step4 : {len(df)} jours recus")

    inserted = 0
    for idx, row in df.iterrows():
        try:
            date_str = idx.strftime("%Y-%m-%d")
            def gv(col):
                try:
                    v = row[col]
                    if hasattr(v, "item"):
                        return float(v.item())
                    return float(v)
                except Exception:
                    return None

            open_p  = gv("Open")
            high_p  = gv("High")
            low_p   = gv("Low")
            close_p = gv("Close")
            vol     = gv("Volume")

            if close_p is None:
                continue

            payload = {
                "ticker": TICKER_INTERNAL,
                "date": date_str,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": vol,
                "source": "yahoo",
            }
            keys = [k for k in payload.keys() if k in cols]
            vals = [payload[k] for k in keys]
            placeholders = ",".join("?" * len(keys))
            sql = (f"INSERT OR REPLACE INTO prices "
                   f"({','.join(keys)}) VALUES ({placeholders})")
            cur.execute(sql, vals)
            inserted += 1
        except Exception as e:
            log(f"  skip {idx} : {e}")
            continue

    conn.commit()
    log(f"step4 OK : {inserted} lignes prices upsertees")
    return True


def step5_verification(conn):
    """Verification finale."""
    cur = conn.cursor()
    log("--- VERIFICATION ---")

    try:
        cur.execute("""
            SELECT thesium_ticker, broker_symbol, instrument_type,
                   tradable, last_verified_at
            FROM instrument_broker_mapping
            WHERE thesium_ticker = ?
        """, (TICKER_INTERNAL,))
        for r in cur.fetchall():
            log(f"  instrument_broker_mapping  : {r}")
    except Exception as e:
        log(f"  instrument_broker_mapping KO : {e}")

    try:
        cur.execute("""
            SELECT broker_symbol, description, asset_class, underlying_ticker
            FROM broker_universe_activtrades
            WHERE broker_symbol = ?
        """, (TICKER_ACTIV,))
        for r in cur.fetchall():
            log(f"  broker_universe_activtrades : {r}")
    except Exception as e:
        log(f"  broker_universe_activtrades KO : {e}")

    try:
        cur.execute("""
            SELECT ticker, name, asset_class, sector
            FROM instruments WHERE ticker = ?
        """, (TICKER_INTERNAL,))
        for r in cur.fetchall():
            log(f"  instruments                : {r}")
    except Exception as e:
        log(f"  instruments KO : {e}")

    try:
        cur.execute("""
            SELECT ticker, asset_class, sector, status, scan_batch, proposed_at
            FROM universe_candidates WHERE ticker = ?
            ORDER BY id DESC LIMIT 1
        """, (TICKER_INTERNAL,))
        for r in cur.fetchall():
            log(f"  universe_candidates        : {r}")
    except Exception as e:
        log(f"  universe_candidates KO : {e}")

    try:
        cur.execute("""
            SELECT COUNT(*), MIN(date), MAX(date)
            FROM prices WHERE ticker = ?
        """, (TICKER_INTERNAL,))
        cnt, dmin, dmax = cur.fetchone()
        log(f"  prices                     : {cnt} lignes du {dmin} au {dmax}")
    except Exception as e:
        log(f"  prices KO : {e}")


def main():
    log("=== nextones-add-reet-instrument-v2 START ===")
    conn = open_db()
    try:
        step1_instrument_broker_mapping(conn)
        step2_broker_universe_activtrades(conn)
        step3_universe_candidates(conn)
        step4_fetch_prices_90d(conn)
        step5_verification(conn)
    finally:
        conn.close()
    log("=== nextones-add-reet-instrument-v2 END ===")
    log("")
    log("Prochaines etapes :")
    log("  1. Relancer un scan univers : POST /api/universe/scan")
    log("     (ou attendre cron mensuel)")
    log("  2. Verifier : GET /api/universe/candidates?status=approved")
    log("  3. REET reste en SHADOW tant que LIVE_INSTRUMENTS ne contient")
    log("     pas 'REET' dans bridge_config.py")


if __name__ == "__main__":
    main()
