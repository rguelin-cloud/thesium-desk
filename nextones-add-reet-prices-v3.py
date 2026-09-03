# -*- coding: utf-8 -*-
# nextones-add-reet-prices-v3.py
# Patch final : telecharge 90j de prix Yahoo pour REET en utilisant
# instrument_id (FK vers instruments.id) au lieu de ticker.
#
# Le reste de l'integration REET est deja en place :
#  - instruments (v1)
#  - instrument_broker_mapping (v2 step1)
#  - broker_universe_activtrades (deja seed)
#  - universe_candidates (v2 step3)
#
# Usage : py -3.13 nextones-add-reet-prices-v3.py

import sqlite3
import sys
import os
from datetime import datetime, timezone, timedelta

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

TICKER_INTERNAL = "REET"
TICKER_YAHOO    = "REET"


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


def get_instrument_id(conn, ticker):
    cur = conn.cursor()
    cur.execute("SELECT id FROM instruments WHERE ticker = ?", (ticker,))
    row = cur.fetchone()
    if not row:
        log(f"FATAL : instruments.ticker={ticker} introuvable")
        return None
    return row[0]


def fetch_prices(conn, instrument_id):
    try:
        import yfinance as yf
    except ImportError:
        log("FATAL : yfinance non installe")
        log("        -> py -3.13 -m pip install yfinance")
        return False

    cur = conn.cursor()
    cur.execute("PRAGMA table_info(prices)")
    cols = [r[1] for r in cur.fetchall()]
    log(f"prices cols : {cols}")

    # Index unique potentiel
    cur.execute("""
        SELECT sql FROM sqlite_master
        WHERE type IN ('index','table') AND tbl_name = 'prices'
    """)
    for r in cur.fetchall():
        log(f"  prices schema/index : {r[0]}")

    cur.execute("SELECT COUNT(*) FROM prices WHERE instrument_id = ?", (instrument_id,))
    existing = cur.fetchone()[0]
    log(f"prices existant pour instrument_id={instrument_id} : {existing} lignes")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=120)
    log(f"fetch Yahoo {TICKER_YAHOO} du {start.date()} au {end.date()}")

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

    log(f"recus : {len(df)} jours")

    inserted = 0
    skipped = 0
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
                skipped += 1
                continue

            # INSERT OR REPLACE pour gerer le cas ou un index unique existe
            payload = {
                "instrument_id": instrument_id,
                "date": date_str,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": vol,
            }
            keys = [k for k in payload.keys() if k in cols]
            vals = [payload[k] for k in keys]
            placeholders = ",".join("?" * len(keys))
            sql = (f"INSERT OR REPLACE INTO prices "
                   f"({','.join(keys)}) VALUES ({placeholders})")
            cur.execute(sql, vals)
            inserted += 1
        except sqlite3.IntegrityError as e:
            log(f"  IntegrityError {idx} : {e} (probablement deja present)")
            skipped += 1
        except Exception as e:
            log(f"  skip {idx} : {e}")
            skipped += 1

    conn.commit()
    log(f"OK : {inserted} lignes upsertees, {skipped} skippees")
    return True


def verification(conn, instrument_id):
    cur = conn.cursor()
    log("--- VERIFICATION ---")
    try:
        cur.execute("""
            SELECT COUNT(*), MIN(date), MAX(date),
                   ROUND(AVG(close), 2), ROUND(AVG(volume), 0)
            FROM prices WHERE instrument_id = ?
        """, (instrument_id,))
        cnt, dmin, dmax, avg_close, avg_vol = cur.fetchone()
        log(f"  prices REET : {cnt} lignes")
        log(f"  periode     : {dmin} -> {dmax}")
        log(f"  close moyen : {avg_close} USD")
        log(f"  volume moyen: {avg_vol}")

        cur.execute("""
            SELECT date, open, close, volume FROM prices
            WHERE instrument_id = ?
            ORDER BY date DESC LIMIT 5
        """, (instrument_id,))
        log("  derniers jours :")
        for r in cur.fetchall():
            log(f"    {r}")
    except Exception as e:
        log(f"  KO : {e}")


def main():
    log("=== nextones-add-reet-prices-v3 START ===")
    conn = open_db()
    try:
        inst_id = get_instrument_id(conn, TICKER_INTERNAL)
        if inst_id is None:
            log("ABORT : REET pas dans instruments")
            return
        log(f"REET.instrument_id = {inst_id}")
        fetch_prices(conn, inst_id)
        verification(conn, inst_id)
    finally:
        conn.close()
    log("=== nextones-add-reet-prices-v3 END ===")
    log("")
    log("Integration REET maintenant complete :")
    log("  - instruments (id et metadata)")
    log("  - instrument_broker_mapping (REET <-> REET.US ActivTrades)")
    log("  - broker_universe_activtrades (REET.US deja en seed comme etf_us)")
    log("  - universe_candidates (status=pending)")
    log("  - prices (90 jours Yahoo)")
    log("")
    log("Prochaine etape : declencher un scan ou attendre cron mensuel")


if __name__ == "__main__":
    main()
