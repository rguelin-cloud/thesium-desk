# -*- coding: utf-8 -*-
"""
[FETCH_SOL_HISTORY_V1]
Telecharge 365 jours d'historique SOL (USD) depuis CoinGecko et insere
dans la table prices. Ne fait rien si SOL a deja >= 90 prix.

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-fetch-sol-history.py
"""
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
TICKER = "SOL"
COIN_ID = "solana"
DAYS = 365

def main():
    try:
        import requests
    except ImportError:
        print("[FAIL] pip install requests d'abord.")
        return 1

    conn = sqlite3.connect(str(DB), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        inst = conn.execute(
            "SELECT id FROM instruments WHERE ticker=?", (TICKER,)
        ).fetchone()
        if not inst:
            print(f"[FAIL] {TICKER} absent de instruments.")
            return 2
        iid = inst["id"]

        n_before = conn.execute(
            "SELECT COUNT(*) c FROM prices WHERE instrument_id=?", (iid,)
        ).fetchone()["c"]
        print(f"[INFO] prices({TICKER}) avant: {n_before}")

        if n_before >= 90:
            print(f"[SKIP] >=90 prix deja presents ({n_before}). Rien a faire.")
            return 0

        url = f"https://api.coingecko.com/api/v3/coins/{COIN_ID}/market_chart"
        params = {"vs_currency": "usd", "days": DAYS, "interval": "daily"}
        print(f"[FETCH] CoinGecko {COIN_ID} ({DAYS}j)...")
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        prices_arr = data.get("prices", [])     # [[ts_ms, price], ...]
        volumes_arr = data.get("total_volumes", [])  # [[ts_ms, vol], ...]
        if not prices_arr:
            print("[FAIL] reponse vide CoinGecko.")
            return 3

        vol_map = {int(ts): v for ts, v in volumes_arr}

        inserted = 0
        skipped = 0
        for ts_ms, close in prices_arr:
            d = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            vol = vol_map.get(int(ts_ms), None)
            # Verifier doublon
            existing = conn.execute(
                "SELECT 1 FROM prices WHERE instrument_id=? AND date=? LIMIT 1",
                (iid, d)
            ).fetchone()
            if existing:
                skipped += 1
                continue
            conn.execute(
                """INSERT INTO prices (instrument_id, date, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (iid, d, close, close, close, close, vol)
            )
            inserted += 1

        conn.commit()

        n_after = conn.execute(
            "SELECT COUNT(*) c FROM prices WHERE instrument_id=?", (iid,)
        ).fetchone()["c"]
        print(f"[OK] insere={inserted}, skip(doublon)={skipped}")
        print(f"[INFO] prices({TICKER}) apres: {n_after}")

        last = conn.execute(
            "SELECT date, close FROM prices WHERE instrument_id=? ORDER BY date DESC LIMIT 3",
            (iid,)
        ).fetchall()
        print("[LAST]")
        for r in last:
            print(f"  {dict(r)}")

        if n_after >= 90:
            print(f"\n[OK] SOL est pret pour scoring complet (RSI/momentum/sharpe).")
        else:
            print(f"\n[WARN] SOL a {n_after} prix, encore < 90 pour Sharpe complet.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
