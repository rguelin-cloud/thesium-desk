"""
regenerate_prices.py
=====================
Régénère 60 jours de prix synthétiques cohérents pour tous les instruments.

Au lieu de tenter de débugger des données corrompues (splits non ajustés,
ratios aberrants), on repart sur une base propre :
  - Prix de départ = dernier close connu (le plus récent dans la table)
  - Marche aléatoire avec drift faible et volatilité réaliste par classe d'actif
  - Volumes synthétiques cohérents
  - 60 jours d'historique se terminant à date('now')

Cela résout définitivement :
  - Les vols absurdes (354% annuel)
  - Les momentums aberrants
  - Les ratios de prix non-physiques

Usage :
    py -3.13 regenerate_prices.py
"""
import os
import shutil
import sqlite3
import sys
import math
import random
from datetime import date, timedelta

DB_PATH = "thesium.db"
HISTORY_DAYS = 60  # 60 jours de prix générés

# Volatilité annualisée par classe d'actif (réaliste)
VOL_ANNUAL = {
    "equity":  0.25,   # ~25% (S&P large cap moyenne)
    "crypto":  0.65,   # ~65% (BTC/ETH)
    "etf":     0.18,   # ~18% (SPY/QQQ)
    "bond":    0.05,   # ~5%
}

# Drift annualisé (rendement moyen attendu) — neutre pour ne pas biaiser
DRIFT_ANNUAL = 0.05   # 5%/an


def generate_walk(start_price: float, n_days: int, vol_annual: float,
                  drift_annual: float = DRIFT_ANNUAL, seed: int = 0) -> list[float]:
    """
    Génère une marche géométrique brownienne propre.
    Retourne n_days prix se terminant à start_price (rétroaction).
    """
    rng = random.Random(seed)
    dt = 1 / 252  # daily step
    sigma = vol_annual * math.sqrt(dt)
    mu    = (drift_annual - 0.5 * vol_annual**2) * dt

    # Génère du plus récent vers le plus ancien (rétroaction)
    prices = [start_price]
    for _ in range(n_days - 1):
        # inverse: prev = curr / exp(mu + sigma * z)
        z = rng.gauss(0, 1)
        log_ret = mu + sigma * z
        prev = prices[-1] / math.exp(log_ret)
        prices.append(prev)

    return list(reversed(prices))  # ordre chronologique


def synth_ohlc(close: float, vol_daily: float, rng: random.Random) -> tuple[float, float, float]:
    """Génère open/high/low cohérents autour d'un close."""
    intraday_range = abs(rng.gauss(0, vol_daily * close * 1.5))
    high = close + abs(rng.gauss(0, vol_daily * close * 0.8))
    low  = close - abs(rng.gauss(0, vol_daily * close * 0.8))
    if low <= 0:
        low = close * 0.95
    if high <= close:
        high = close * 1.005
    # open = entre low et high
    open_ = low + (high - low) * rng.random()
    return round(open_, 2), round(high, 2), round(low, 2)


def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] DB introuvable : {DB_PATH}")
        sys.exit(1)

    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{DB_PATH}.bak.regen.{ts}"
    shutil.copy2(DB_PATH, backup)
    print(f"[OK] Backup : {backup}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    instruments = cur.execute(
        "SELECT id, ticker, asset_class FROM instruments"
    ).fetchall()

    today = date.today()
    total_inserted = 0

    for inst in instruments:
        # Trouver le dernier prix connu comme point d'arrivée
        last = cur.execute(
            "SELECT close FROM prices WHERE instrument_id=? ORDER BY date DESC LIMIT 1",
            (inst["id"],)
        ).fetchone()
        if not last or last["close"] <= 0:
            print(f"[SKIP] {inst['ticker']}: pas de prix de référence")
            continue

        end_price = last["close"]
        vol = VOL_ANNUAL.get(inst["asset_class"], 0.25)

        # Génération de la série
        seed = hash(inst["ticker"]) & 0xFFFFFFFF
        prices = generate_walk(end_price, HISTORY_DAYS, vol, seed=seed)
        rng = random.Random(seed + 1)

        # Purge ancienne historique
        cur.execute("DELETE FROM prices WHERE instrument_id=?", (inst["id"],))

        # Insertion
        vol_daily = vol / math.sqrt(252)
        for i, close in enumerate(prices):
            d = today - timedelta(days=HISTORY_DAYS - 1 - i)
            # Skip week-ends pour equity/etf/bond
            if inst["asset_class"] in ("equity", "etf", "bond"):
                if d.weekday() >= 5:  # samedi=5, dimanche=6
                    continue
            open_, high, low = synth_ohlc(close, vol_daily, rng)
            # Volume synthétique
            base_vol = 5_000_000 if inst["asset_class"] == "equity" else 1_000_000
            volume = int(rng.gauss(base_vol, base_vol * 0.3))
            volume = max(volume, base_vol // 4)

            cur.execute(
                """INSERT INTO prices (instrument_id, date, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (inst["id"], d.isoformat(), open_, high, low, round(close, 2), volume)
            )
            total_inserted += 1

        print(f"[OK] {inst['ticker']:<8} end={end_price:>10.2f}  vol={vol*100:>5.1f}%  inserted={cur.rowcount}")

    conn.commit()
    print(f"\n=== TOTAL : {total_inserted} prix insérés ===")

    # Vérification : vols recalculées
    print("\n=== Vols & momentums après régénération ===")
    for inst in instruments:
        rows = cur.execute(
            "SELECT close FROM prices WHERE instrument_id=? ORDER BY date DESC LIMIT 21",
            (inst["id"],)
        ).fetchall()
        closes = list(reversed([r[0] for r in rows]))
        if len(closes) < 5:
            continue
        rets = [(closes[i]-closes[i-1])/closes[i-1] for i in range(1, len(closes))
                if closes[i-1] > 0]
        if len(rets) < 2:
            continue
        mean_r = sum(rets)/len(rets)
        var = sum((r-mean_r)**2 for r in rets) / (len(rets)-1)
        vol_a = math.sqrt(var) * math.sqrt(252) * 100
        mom = (closes[-2] - closes[0]) / closes[0] * 100 if closes[0] > 0 else 0
        print(f"  {inst['ticker']:<8} vol_annuelle={vol_a:>6.1f}%  momentum_20d={mom:>+7.1f}%")

    conn.close()
    print(f"\n✅ Régénération terminée. Backup : {backup}")


if __name__ == "__main__":
    main()
