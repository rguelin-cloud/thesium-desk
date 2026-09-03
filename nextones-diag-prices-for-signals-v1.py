"""
Diag prerequis pour reimplementer fetch_stock_signals depuis prices maison.

Verifie que la table `prices` a assez de donnees pour calculer :
- RSI(14) : besoin de 15+ jours de closes
- SMA20/50/200 : besoin de 200+ jours pour SMA200
- Perf Week/Month/YTD : besoin de closes historiques
- Rel Volume : besoin de volumes sur 30 jours

Sur les tickers de la carte Stock Signals :
BAC CAT COP CSCO GOOGL GS JNJ JPM META MRK MS MSFT NVDA PLD QQQ REET SPY
TSLA TXN UNH UNP XLB XLE XLI XLK XOM
"""
import os
import sqlite3
from datetime import datetime, timedelta

DB = os.environ.get("THESIUM_DB", r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")

TICKERS = [
    "BAC", "CAT", "COP", "CSCO", "GOOGL", "GS", "JNJ", "JPM",
    "META", "MRK", "MS", "MSFT", "NVDA", "PLD", "QQQ", "REET",
    "SPY", "TSLA", "TXN", "UNH", "UNP", "XLB", "XLE", "XLI", "XLK", "XOM",
]

print(f"[DB] {DB}")
print()
conn = sqlite3.connect(DB, timeout=10.0)
conn.row_factory = sqlite3.Row

# Schema check
print("[STAGE 1] Schema table prices")
print("-" * 70)
cols = conn.execute("PRAGMA table_info(prices)").fetchall()
for c in cols:
    print(f"  {c['name']:20s} {c['type']}")
print()

# Instruments IDs pour ces tickers
print("[STAGE 2] Coverage par ticker (nb lignes, min/max date)")
print("-" * 70)
print(f"  {'TICKER':8s} {'ID':>6s} {'NB_ROWS':>8s} {'MIN_DATE':12s} {'MAX_DATE':12s} {'DAYS':>6s}")
print("  " + "-" * 66)

ready_for_rsi = []
ready_for_sma200 = []
missing = []

for t in TICKERS:
    row = conn.execute(
        "SELECT id FROM instruments WHERE ticker = ?", (t,)
    ).fetchone()
    if not row:
        print(f"  {t:8s} {'--':>6s} INSTRUMENT NOT FOUND")
        missing.append(t)
        continue
    iid = row["id"]

    stats = conn.execute(
        """SELECT COUNT(*) as n, MIN(date) as mind, MAX(date) as maxd
           FROM prices WHERE instrument_id = ?""",
        (iid,),
    ).fetchone()
    n = stats["n"] if stats else 0
    mind = stats["mind"] if stats else "-"
    maxd = stats["maxd"] if stats else "-"

    days = 0
    if mind and maxd:
        try:
            d1 = datetime.strptime(mind, "%Y-%m-%d")
            d2 = datetime.strptime(maxd, "%Y-%m-%d")
            days = (d2 - d1).days
        except Exception:
            days = 0

    print(f"  {t:8s} {iid:>6d} {n:>8d} {mind or '-':12s} {maxd or '-':12s} {days:>6d}")

    if n >= 15:
        ready_for_rsi.append(t)
    if n >= 200:
        ready_for_sma200.append(t)

print()
print(f"[SUMMARY]")
print(f"  Tickers instruments manquants  : {len(missing):3d} / {len(TICKERS)}")
print(f"  Ready for RSI(14)              : {len(ready_for_rsi):3d} / {len(TICKERS)}")
print(f"  Ready for SMA200               : {len(ready_for_sma200):3d} / {len(TICKERS)}")

if missing:
    print(f"  Missing: {missing}")

# Check si close est dispo (pas juste price)
print()
print("[STAGE 3] Sample data pour AAPL / SPY (verifier close disponible)")
print("-" * 70)
for tt in ["AAPL", "SPY", "NVDA"]:
    row = conn.execute("SELECT id FROM instruments WHERE ticker = ?", (tt,)).fetchone()
    if not row:
        print(f"  {tt}: not found")
        continue
    iid = row["id"]
    rows = conn.execute(
        """SELECT date, open, high, low, close, volume FROM prices
           WHERE instrument_id = ? ORDER BY date DESC LIMIT 3""",
        (iid,),
    ).fetchall()
    print(f"  {tt}:")
    for r in rows:
        print(f"    {r['date']:12s} O={r['open']} H={r['high']} L={r['low']} C={r['close']} V={r['volume']}")

conn.close()

# Test HTTP Finviz pour vue apercu HTML actuel (pour parser custom)
print()
print("[STAGE 4] HTML Finviz pour AAPL - extraire les tags les + utiles")
print("-" * 70)
try:
    import urllib.request
    import re
    url = "https://finviz.com/quote.ashx?t=AAPL"
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    resp = urllib.request.urlopen(req, timeout=15)
    body = resp.read().decode("utf-8", errors="replace")

    # Cherche pattern "LABEL</td><td...><b>VALUE</b>" pour Recom / Target Price / Short Float / Sector
    targets = ["Recom", "Target Price", "Short Float", "Sector", "Price"]
    print("  Extraits :")
    for label in targets:
        # regex tolerant
        pat = re.compile(
            r'>' + re.escape(label) + r'\s*</[^>]+>[^<]*<td[^>]*>[^<]*<[^>]*>([^<]+)</',
            re.IGNORECASE,
        )
        m = pat.search(body)
        if m:
            print(f"    {label}: {m.group(1)[:60]}")
        else:
            # Autre pattern
            pat2 = re.compile(
                r'>' + re.escape(label) + r'\s*</[^>]+>.{0,400}?<b>([^<]+)</b>',
                re.IGNORECASE | re.DOTALL,
            )
            m2 = pat2.search(body)
            if m2:
                print(f"    {label}: {m2.group(1)[:60]}  (pat2)")
            else:
                print(f"    {label}: [NOT FOUND]")
except Exception as e:
    print(f"  [ERR] {type(e).__name__}: {e}")
