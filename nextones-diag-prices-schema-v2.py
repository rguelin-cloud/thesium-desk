"""Diag : schema reel prices + autres tables prix candidates."""
import sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

# Lister toutes tables avec 'price' dans le nom
print("=== TABLES contenant 'price' ===")
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%price%' ORDER BY name")
for r in cur.fetchall():
    print(f"  {r[0]}")

# Schema de 'prices'
print("\n=== prices columns ===")
cur.execute("PRAGMA table_info(prices)")
for c in cur.fetchall():
    print(f"  {c[1]:30s} {c[2]:15s} nn={c[3]} pk={c[5]}")

print("\n=== prices sample (5 rows) ===")
cur.execute("SELECT * FROM prices LIMIT 5")
cols = [d[0] for d in cur.description]
print(" | ".join(cols))
for r in cur.fetchall():
    print(" | ".join(str(v)[:25] for v in r))

print("\n=== prices stats ===")
# Detecter colonne ticker/symbol
cur.execute("PRAGMA table_info(prices)")
prices_cols = [c[1] for c in cur.fetchall()]
print(f"  cols : {prices_cols}")

# Detect ticker col
ticker_col = None
for cand in ["symbol", "ticker", "instrument", "instrument_id", "asset"]:
    if cand in prices_cols:
        ticker_col = cand
        break
print(f"  ticker col detected : {ticker_col}")

if ticker_col:
    # Detect date col
    date_col = None
    for cand in ["date", "day", "datetime", "ts", "timestamp"]:
        if cand in prices_cols:
            date_col = cand
            break
    print(f"  date col detected   : {date_col}")
    if date_col:
        cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT {ticker_col}), MIN({date_col}), MAX({date_col}) FROM prices")
        r = cur.fetchone()
        print(f"  rows={r[0]} tickers={r[1]} {date_col}_min={r[2]} {date_col}_max={r[3]}")

        # Verif couverture J-90
        cur.execute(f"SELECT COUNT(DISTINCT {date_col}) FROM prices WHERE {date_col} >= '2026-03-14'")
        print(f"  dates uniques depuis 2026-03-14 (J-90) : {cur.fetchone()[0]}")

# Tables candidates supplementaires
print("\n=== Autres tables avec 'close' ou 'price' col ===")
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
all_tables = [r[0] for r in cur.fetchall()]
for t in all_tables:
    try:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [c[1] for c in cur.fetchall()]
        if "close" in cols or "close_price" in cols:
            print(f"  {t}: {cols[:8]}")
    except Exception:
        pass

conn.close()
