# -*- coding: utf-8 -*-
# nextones-diag-jalon8b4-window-v1.py
# Cadrage Jalon 8B.4 : determiner la fenetre 90 jours et verifier
# 1. Couverture replay_adapters (prices + macro) sur la fenetre
# 2. Donnees prod disponibles pour benchmark (NAV history)
#
# Pas d'ecriture. ASCII pur.
# Usage : py -3.13 nextones-diag-jalon8b4-window-v1.py

import sqlite3
from datetime import datetime, date, timedelta

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"


def _is_trading_day(d):
    return d.weekday() < 5


def _trading_days(start, end):
    out = []
    d = start
    while d <= end:
        if _is_trading_day(d):
            out.append(d)
        d += timedelta(days=1)
    return out


con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 72)
print("DIAG Jalon 8B.4 - cadrage fenetre 90j")
print("=" * 72)

# 1. Donnees prices disponibles
print("\n[1] Couverture replay_prices (table prod 'prices') :")
row = cur.execute(
    "SELECT MIN(date) min_d, MAX(date) max_d, COUNT(DISTINCT date) n_days, "
    "       COUNT(DISTINCT instrument_id) n_inst "
    "FROM prices"
).fetchone()
print(f"    min={row['min_d']}  max={row['max_d']}  days={row['n_days']}  instruments={row['n_inst']}")

# 2. Macro coverage
print("\n[2] Couverture macro_history :")
row = cur.execute(
    "SELECT MIN(date) min_d, MAX(date) max_d, COUNT(DISTINCT date) n_days "
    "FROM macro_history"
).fetchone()
print(f"    min={row['min_d']}  max={row['max_d']}  days={row['n_days']}")

# 3. Proposer fenetre 90j se terminant a max_prices
prices_max = cur.execute("SELECT MAX(date) FROM prices").fetchone()[0]
end_date = datetime.strptime(prices_max, "%Y-%m-%d").date()
# 90 jours calendaires AVANT pour avoir des jours pleins
start_date = end_date - timedelta(days=90)
# Mais on a besoin de 90 jours d'historique AVANT start pour score_R (n=90)
# Donc start_date - 90 jours doit etre dans la couverture
score_R_min_needed = start_date - timedelta(days=130)  # buffer week-ends

prices_min = cur.execute("SELECT MIN(date) FROM prices").fetchone()[0]
prices_min_d = datetime.strptime(prices_min, "%Y-%m-%d").date()

print(f"\n[3] Fenetre 8B.4 proposee :")
print(f"    end_date         = {end_date}")
print(f"    start_date (-90) = {start_date}")
print(f"    score_R needs    >= {score_R_min_needed}")
print(f"    prices min       = {prices_min_d}")
margin_days = (score_R_min_needed - prices_min_d).days
print(f"    margin           = {margin_days} jours (positif = OK)")

trading_days = _trading_days(start_date, end_date)
print(f"    trading_days     = {len(trading_days)} cycles attendus")

# 4. Existe-t-il des donnees portfolio_history prod sur cette fenetre (benchmark) ?
print(f"\n[4] portfolio_history prod (benchmark) sur fenetre [{start_date} -> {end_date}] :")
try:
    rows = cur.execute(
        "SELECT MIN(date) min_d, MAX(date) max_d, COUNT(*) n, "
        "       MIN(total_value) min_nav, MAX(total_value) max_nav "
        "FROM portfolio_history WHERE date BETWEEN ? AND ?",
        (str(start_date), str(end_date)),
    ).fetchone()
    if rows and rows['n']:
        print(f"    rows={rows['n']}  min_d={rows['min_d']}  max_d={rows['max_d']}")
        print(f"    NAV min=${rows['min_nav']:>12,.2f}  max=${rows['max_nav']:>12,.2f}")
    else:
        print(f"    AUCUN row (pas de benchmark prod sur cette fenetre)")
except Exception as e:
    print(f"    ERR : {e}")

# 5. orders/fills prod sur fenetre (autre benchmark possible)
print(f"\n[5] orders/fills prod sur fenetre [{start_date} -> {end_date}] :")
try:
    rows = cur.execute(
        "SELECT COUNT(*) n_orders, COUNT(DISTINCT cycle_id) n_cycles "
        "FROM orders WHERE created_at BETWEEN ? AND ?",
        (str(start_date) + " 00:00", str(end_date) + " 23:59"),
    ).fetchone()
    print(f"    orders={rows['n_orders']}  cycles={rows['n_cycles']}")
except Exception as e:
    print(f"    ERR orders : {e}")

try:
    rows = cur.execute(
        "SELECT COUNT(*) n_fills FROM fills WHERE filled_at BETWEEN ? AND ?",
        (str(start_date) + " 00:00", str(end_date) + " 23:59"),
    ).fetchone()
    print(f"    fills={rows['n_fills']}")
except Exception as e:
    print(f"    ERR fills : {e}")

# 6. Anciens runs replay (pour cleanup eventuel)
print(f"\n[6] replay_runs existants :")
for r in cur.execute(
    "SELECT id, label, status, window_start, window_end "
    "FROM replay_runs ORDER BY id DESC LIMIT 5"
).fetchall():
    print(f"    id={r['id']:3d}  status={r['status']:10s}  "
          f"window=[{r['window_start']} -> {r['window_end']}]  label={r['label']}")

con.close()

print("\n" + "=" * 72)
print("RECO 8B.4 :")
print("=" * 72)
print(f"  label        = jalon-8b4-90d-<ts>")
print(f"  window_start = {start_date}")
print(f"  window_end   = {end_date}")
print(f"  cycles_attendus = {len(trading_days)}")
print(f"  benchmark    = portfolio_history (NAV final + total return)")
