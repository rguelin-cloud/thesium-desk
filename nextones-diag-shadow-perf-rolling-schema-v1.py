"""Diag : schemas shadow_perf_rolling + shadow_fills + samples.

Phase 9.5 : verifier ce dont on dispose pour calculer perf rolling.
"""
import sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

for table in ["shadow_perf_rolling", "shadow_fills", "shadow_cycle_snapshots", "shadow_orders"]:
    print(f"\n=== {table} columns ===")
    cur.execute(f"PRAGMA table_info({table})")
    for c in cur.fetchall():
        print(f"  {c[1]:30s} {c[2]:15s} nn={c[3]} pk={c[5]}")

print("\n=== shadow_fills sample (10 rows) ===")
cur.execute("SELECT * FROM shadow_fills ORDER BY cycle_id DESC, id LIMIT 10")
cols = [d[0] for d in cur.description]
print(" | ".join(cols))
for r in cur.fetchall():
    print(" | ".join(str(v)[:25] for v in r))

print("\n=== shadow_fills aggregate stats ===")
cur.execute("SELECT COUNT(*), COUNT(DISTINCT cycle_id), COUNT(DISTINCT variant_id), COUNT(DISTINCT ticker), MIN(fill_day), MAX(fill_day) FROM shadow_fills")
r = cur.fetchone()
print(f"  total_fills={r[0]} cycles={r[1]} variants={r[2]} tickers={r[3]} fill_day_min={r[4]} fill_day_max={r[5]}")

# Couverture prices pour fenetre J-30
print("\n=== Couverture prices (table prices ou ohlcv) ===")
for t in ["prices", "ohlcv", "instrument_prices", "etf_prices", "crypto_prices"]:
    try:
        cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT ticker), MIN(date), MAX(date) FROM {t}")
        r = cur.fetchone()
        print(f"  {t:20s} rows={r[0]} tickers={r[1]} min={r[2]} max={r[3]}")
    except Exception as e:
        print(f"  {t:20s} N/A ({e})")

conn.close()
