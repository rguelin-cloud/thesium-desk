# =====================================================================
# enrich_prices_90d.ps1
# Jalon 3 - Enrichissement prix a 90 jours via yfinance
# Tickers : AAPL AMZN BAC GOOGL JNJ JPM META MSFT NVDA QQQ SPY TSLA UNH XOM
#         + BTC ETH LINK SOL (crypto avec -USD)
# =====================================================================

$ErrorActionPreference = "Stop"
$Root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
Set-Location $Root

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  ENRICHISSEMENT PRIX A 90 JOURS via yfinance" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item "$Root\thesium.db" "$Root\_backup_thesium_$ts.db" -Force
Write-Host "[1/3] Backup DB : $Root\_backup_thesium_$ts.db" -ForegroundColor Green

$py = @'
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB   = ROOT / "thesium.db"

try:
    import yfinance as yf
except ImportError:
    print("[!] yfinance manquant - py -m pip install yfinance")
    sys.exit(1)

# Tickers DB -> ticker yfinance (crypto = base-USD)
CRYPTO = {"BTC", "ETH", "LINK", "SOL", "ADA", "DOT", "MATIC", "AVAX"}

def yf_ticker(t):
    return f"{t}-USD" if t in CRYPTO else t

# =====================================================================
# 1. Liste des instruments en DB + couverture actuelle
# =====================================================================
print()
print("=" * 70)
print("1. Etat actuel des prix (avant enrichissement)")
print("=" * 70)

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

cur.execute("""
    SELECT i.id, i.ticker, i.asset_class, COUNT(p.id) AS n,
           MIN(p.date) AS first_d, MAX(p.date) AS last_d
    FROM instruments i
    LEFT JOIN prices p ON p.instrument_id = i.id
    GROUP BY i.id, i.ticker
    ORDER BY i.ticker
""")
instruments = cur.fetchall()

print(f"{'Ticker':<8} {'Class':<10} {'Jours':>6}  {'First':<12} {'Last':<12}  Action")
print("-" * 70)
to_fetch = []
for r in instruments:
    n = r["n"] or 0
    needed = max(0, 100 - n)  # on vise 100 pour avoir marge
    status = "OK" if n >= 90 else f"a enrichir (+{needed}j vise)"
    print(f"{r['ticker']:<8} {r['asset_class'] or '?':<10} {n:>6}  {(r['first_d'] or '-'):<12} {(r['last_d'] or '-'):<12}  {status}")
    if n < 90:
        to_fetch.append({"id": r["id"], "ticker": r["ticker"]})

if not to_fetch:
    print()
    print("[OK] Tous les instruments ont >= 90 jours - rien a faire")
    con.close()
    sys.exit(0)

# =====================================================================
# 2. Telechargement yfinance
# =====================================================================
print()
print("=" * 70)
print(f"2. Telechargement yfinance ({len(to_fetch)} tickers)")
print("=" * 70)

# Schema attendu : id, instrument_id, date, open, high, low, close, volume
# On INSERT OR IGNORE pour ne pas dupliquer (assume unique sur instrument_id+date)
# Si pas de contrainte UNIQUE, on fait DELETE+INSERT par instrument

# D'abord verifier si contrainte UNIQUE existe
cur.execute("PRAGMA index_list(prices)")
indexes = cur.fetchall()
has_unique = False
for idx in indexes:
    if idx["unique"]:
        cur.execute(f"PRAGMA index_info({idx['name']})")
        cols = [c["name"] for c in cur.fetchall()]
        if "instrument_id" in cols and "date" in cols:
            has_unique = True
            print(f"[i] Index UNIQUE detecte : {idx['name']} ({cols}) - INSERT OR IGNORE")
            break

if not has_unique:
    print("[i] Pas d'index UNIQUE (instrument_id, date) - dedup manuel via SELECT")

end_date   = datetime.now()
start_date = end_date - timedelta(days=120)  # marge pour weekends

total_added = 0
for tk in to_fetch:
    db_id   = tk["id"]
    sym     = tk["ticker"]
    yf_sym  = yf_ticker(sym)

    try:
        df = yf.download(
            yf_sym,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=False,
        )
    except Exception as e:
        print(f"  {sym:<6} ERREUR download : {e}")
        continue

    if df is None or df.empty:
        print(f"  {sym:<6} pas de data yfinance")
        continue

    # yfinance retourne parfois un MultiIndex (Open, '') ; on aplatit
    if hasattr(df.columns, "levels"):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    # Recupere dates deja en DB pour ce ticker
    cur.execute("SELECT date FROM prices WHERE instrument_id = ?", (db_id,))
    existing = {r["date"] for r in cur.fetchall()}

    added = 0
    for idx_d, row in df.iterrows():
        d_str = idx_d.strftime("%Y-%m-%d")
        if d_str in existing:
            continue
        try:
            o = float(row["Open"]) if "Open" in row and row["Open"] == row["Open"] else None
            h = float(row["High"]) if "High" in row and row["High"] == row["High"] else None
            l = float(row["Low"])  if "Low"  in row and row["Low"]  == row["Low"]  else None
            c = float(row["Close"]) if "Close" in row and row["Close"] == row["Close"] else None
            v = float(row["Volume"]) if "Volume" in row and row["Volume"] == row["Volume"] else None
        except Exception as e:
            print(f"  {sym} {d_str} parse KO : {e}")
            continue

        if c is None or c <= 0:
            continue

        cur.execute(
            "INSERT INTO prices (instrument_id, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (db_id, d_str, o, h, l, c, v),
        )
        added += 1

    print(f"  {sym:<6} (yf={yf_sym:<10}) +{added} jours ajoutes")
    total_added += added

con.commit()
print()
print(f"[OK] Total ajoute : {total_added} lignes prices")

# =====================================================================
# 3. Etat final
# =====================================================================
print()
print("=" * 70)
print("3. Etat final apres enrichissement")
print("=" * 70)

cur.execute("""
    SELECT i.ticker, COUNT(p.id) AS n,
           MIN(p.date) AS first_d, MAX(p.date) AS last_d
    FROM instruments i
    LEFT JOIN prices p ON p.instrument_id = i.id
    GROUP BY i.ticker
    ORDER BY i.ticker
""")
print(f"{'Ticker':<8} {'Jours':>6}  {'First':<12} {'Last':<12}  Statut")
print("-" * 50)
for r in cur.fetchall():
    n = r["n"] or 0
    statut = "[OK 90j+]" if n >= 90 else "[short]"
    print(f"{r['ticker']:<8} {n:>6}  {(r['first_d'] or '-'):<12} {(r['last_d'] or '-'):<12}  {statut}")

con.close()
print()
'@

$tmp = "$env:TEMP\_enrich_90d.py"
$py | Set-Content -Path $tmp -Encoding UTF8

Write-Host ""
Write-Host "[2/3] Telechargement et insertion..." -ForegroundColor Yellow
py $tmp

# =====================================================================
# 3. Re-test compute_realized_score apres enrichissement
# =====================================================================
Write-Host ""
Write-Host "[3/3] Re-test compute_realized_score avec 90j de donnees..." -ForegroundColor Yellow
$retestPy = @'
import sys, sqlite3
from pathlib import Path
ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
sys.path.insert(0, str(ROOT))
from portfolio_construction_agent import compute_realized_score, _fetch_log_returns

con = sqlite3.connect(ROOT / "thesium.db")
con.row_factory = sqlite3.Row

print()
print("  Ticker | n_returns | R (Sharpe annualise)")
print("  " + "-" * 50)
for ticker in ["AAPL", "AMZN", "BTC", "ETH", "GOOGL", "LINK", "MSFT", "META", "NVDA", "TSLA"]:
    try:
        lr = _fetch_log_returns(con, ticker, days=90)
        r = compute_realized_score(con, ticker, days=90)
        print(f"  {ticker:<6} |    n={len(lr):>3}  | R = {r:+.4f}")
    except Exception as e:
        print(f"  {ticker:<6} | ERREUR : {e}")
con.close()
'@
$tmpRetest = "$env:TEMP\_retest_R.py"
$retestPy | Set-Content -Path $tmpRetest -Encoding UTF8
py $tmpRetest

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  TERMINE - Prochaine etape :" -ForegroundColor Cyan
Write-Host "  1. Redemarre uvicorn (Ctrl+C dans sa fenetre + relance)" -ForegroundColor Cyan
Write-Host "  2. Ctrl+Shift+R dans le navigateur" -ForegroundColor Cyan
Write-Host "  3. Lance un nouveau cycle" -ForegroundColor Cyan
Write-Host "  4. Verifie : BTC BUY ~0.26 + logs [score_R]" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
