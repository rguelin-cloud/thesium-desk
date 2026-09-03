# -*- coding: utf-8 -*-
# nextones-add-reet-instrument.py
# Ajoute REET (iShares Global REIT ETF) a l'outil NEXTONES :
#  1. broker_mapping : REET (Yahoo) <-> REET.US (ActivTrades via MetaApi)
#  2. instruments : enregistrement REET, asset_class=ETF, sector=REAL_ESTATE
#  3. universe_equity_candidates : pre-promotion REET en liste de scan
#  4. prices : telechargement 90 jours Yahoo Finance
#
# Usage : py -3.13 nextones-add-reet-instrument.py
# Pre-requis : yfinance, sqlite3 (stdlib), api server peut tourner (WAL mode)

import sqlite3
import sys
import os
from datetime import datetime, timedelta

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

TICKER_INTERNAL  = "REET"
TICKER_YAHOO     = "REET"
TICKER_ACTIV     = "REET.US"
ASSET_CLASS      = "ETF"
SECTOR           = "REAL_ESTATE"
CURRENCY         = "USD"
NAME             = "iShares Global REIT ETF"


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


def step1_broker_mapping(conn):
    """Insertion dans broker_mapping (UPSERT)."""
    cur = conn.cursor()
    # Verifier la structure de la table
    cur.execute("PRAGMA table_info(broker_mapping)")
    cols = [r[1] for r in cur.fetchall()]
    if not cols:
        log("WARN : table broker_mapping inexistante, on skip step1")
        return False

    log(f"broker_mapping colonnes : {cols}")

    # Schema attendu (cf. nextones-broker-mapping-schema.py) :
    # internal_symbol, broker, broker_symbol, asset_class, currency,
    # status, created_at, updated_at
    cur.execute("""
        SELECT internal_symbol, broker, broker_symbol
        FROM broker_mapping
        WHERE internal_symbol = ? AND broker = ?
    """, (TICKER_INTERNAL, "ActivTrades"))
    existing = cur.fetchone()

    now = datetime.utcnow().isoformat()
    if existing:
        log(f"step1 : entree existante -> UPDATE ({existing})")
        cur.execute("""
            UPDATE broker_mapping
            SET broker_symbol = ?, asset_class = ?, currency = ?,
                status = 'active', updated_at = ?
            WHERE internal_symbol = ? AND broker = ?
        """, (TICKER_ACTIV, ASSET_CLASS, CURRENCY, now,
              TICKER_INTERNAL, "ActivTrades"))
    else:
        log("step1 : INSERT nouvelle entree broker_mapping")
        cur.execute("""
            INSERT INTO broker_mapping
            (internal_symbol, broker, broker_symbol, asset_class,
             currency, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
        """, (TICKER_INTERNAL, "ActivTrades", TICKER_ACTIV,
              ASSET_CLASS, CURRENCY, now, now))

    conn.commit()
    log(f"step1 OK : {TICKER_INTERNAL} <-> {TICKER_ACTIV} (ActivTrades)")
    return True


def step2_instruments(conn):
    """Insertion dans instruments (table coeur de l'outil)."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(instruments)")
    cols = [r[1] for r in cur.fetchall()]
    if not cols:
        log("WARN : table instruments inexistante, on skip step2")
        return False

    log(f"instruments colonnes : {cols}")

    cur.execute("SELECT ticker FROM instruments WHERE ticker = ?",
                (TICKER_INTERNAL,))
    if cur.fetchone():
        log(f"step2 : {TICKER_INTERNAL} deja present dans instruments -> skip")
        return True

    now = datetime.utcnow().isoformat()
    # On insere uniquement les colonnes qui existent reellement
    payload = {
        "ticker": TICKER_INTERNAL,
        "name": NAME,
        "asset_class": ASSET_CLASS,
        "sector": SECTOR,
        "currency": CURRENCY,
        "active": 1,
        "created_at": now,
    }
    keys = [k for k in payload.keys() if k in cols]
    vals = [payload[k] for k in keys]
    placeholders = ",".join("?" * len(keys))
    sql = f"INSERT INTO instruments ({','.join(keys)}) VALUES ({placeholders})"
    log(f"step2 SQL : {sql}")
    cur.execute(sql, vals)
    conn.commit()
    log(f"step2 OK : REET insere dans instruments (sector={SECTOR})")
    return True


def step3_universe_candidates(conn):
    """Pre-positionne REET dans universe_equity_candidates pour le prochain scan."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(universe_equity_candidates)")
    cols = [r[1] for r in cur.fetchall()]
    if not cols:
        # Fallback : table universe_candidates (sans suffixe)
        cur.execute("PRAGMA table_info(universe_candidates)")
        cols = [r[1] for r in cur.fetchall()]
        table = "universe_candidates"
    else:
        table = "universe_equity_candidates"

    if not cols:
        log("WARN : aucune table universe_candidates(_equity), on skip step3")
        return False

    log(f"{table} colonnes : {cols}")

    cur.execute(f"SELECT ticker FROM {table} WHERE ticker = ?",
                (TICKER_INTERNAL,))
    if cur.fetchone():
        log(f"step3 : {TICKER_INTERNAL} deja present dans {table} -> skip")
        return True

    now = datetime.utcnow().isoformat()
    payload = {
        "ticker": TICKER_INTERNAL,
        "asset_class": ASSET_CLASS,
        "sector": SECTOR,
        "status": "pending",
        "source": "manual_add_reet",
        "created_at": now,
        "updated_at": now,
    }
    keys = [k for k in payload.keys() if k in cols]
    vals = [payload[k] for k in keys]
    placeholders = ",".join("?" * len(keys))
    sql = f"INSERT INTO {table} ({','.join(keys)}) VALUES ({placeholders})"
    log(f"step3 SQL : {sql}")
    cur.execute(sql, vals)
    conn.commit()
    log(f"step3 OK : REET pre-positionne dans {table} (status=pending)")
    return True


def step4_fetch_prices_90d(conn):
    """Telechargement 90 jours d'historique Yahoo Finance."""
    try:
        import yfinance as yf
    except ImportError:
        log("WARN : yfinance non installe, on skip step4")
        log("       -> py -3.13 -m pip install yfinance")
        return False

    cur = conn.cursor()
    cur.execute("PRAGMA table_info(prices)")
    cols = [r[1] for r in cur.fetchall()]
    if not cols:
        log("WARN : table prices inexistante, on skip step4")
        return False

    log(f"prices colonnes : {cols}")

    end = datetime.utcnow()
    start = end - timedelta(days=120)  # marge pour 90 jours ouvres
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

    log(f"step4 : {len(df)} jours recus de Yahoo")

    inserted = 0
    for idx, row in df.iterrows():
        try:
            date_str = idx.strftime("%Y-%m-%d")
            # Gerer MultiIndex columns (yfinance 0.2+ peut renvoyer (Open, REET))
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
    log(f"step4 OK : {inserted} lignes prices inserees pour REET")
    return True


def step5_verification(conn):
    """Verification finale post-insertion."""
    cur = conn.cursor()

    log("--- VERIFICATION ---")
    try:
        cur.execute("""
            SELECT internal_symbol, broker, broker_symbol, status
            FROM broker_mapping
            WHERE internal_symbol = ?
        """, (TICKER_INTERNAL,))
        for r in cur.fetchall():
            log(f"  broker_mapping  : {r}")
    except Exception as e:
        log(f"  broker_mapping query KO : {e}")

    try:
        cur.execute("SELECT ticker, name, asset_class, sector FROM instruments WHERE ticker = ?",
                    (TICKER_INTERNAL,))
        for r in cur.fetchall():
            log(f"  instruments     : {r}")
    except Exception as e:
        log(f"  instruments query KO : {e}")

    for tbl in ("universe_equity_candidates", "universe_candidates"):
        try:
            cur.execute(f"SELECT ticker, status FROM {tbl} WHERE ticker = ?",
                        (TICKER_INTERNAL,))
            rows = cur.fetchall()
            if rows:
                for r in rows:
                    log(f"  {tbl} : {r}")
        except Exception:
            pass

    try:
        cur.execute("""
            SELECT COUNT(*), MIN(date), MAX(date)
            FROM prices WHERE ticker = ?
        """, (TICKER_INTERNAL,))
        cnt, dmin, dmax = cur.fetchone()
        log(f"  prices          : {cnt} lignes du {dmin} au {dmax}")
    except Exception as e:
        log(f"  prices query KO : {e}")


def main():
    log("=== nextones-add-reet-instrument START ===")
    conn = open_db()
    try:
        step1_broker_mapping(conn)
        step2_instruments(conn)
        step3_universe_candidates(conn)
        step4_fetch_prices_90d(conn)
        step5_verification(conn)
    finally:
        conn.close()
    log("=== nextones-add-reet-instrument END ===")
    log("Prochaines etapes :")
    log("  1. Relancer un scan univers : POST /api/universe/scan (ou attendre cron mensuel)")
    log("  2. Verifier promotion : GET /api/universe/candidates?status=promoted")
    log("  3. REET restera en SHADOW tant que LIVE_INSTRUMENTS ne contient pas 'REET'")


if __name__ == "__main__":
    main()
