# =====================================================================
# enable_realized_and_test.ps1
# 1. Active enable_realized=1 dans params_json (pas une colonne)
# 2. Smoke test propre avec row_factory=Row
# =====================================================================

$ErrorActionPreference = "Stop"
$Root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
Set-Location $Root

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  Activer enable_realized + smoke test correct" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

$py = @'
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB   = ROOT / "thesium.db"

# =====================================================================
# 1. Activer enable_realized dans params_json
# =====================================================================
print("=" * 60)
print("1. Modification params_json -> enable_realized=1")
print("=" * 60)

con = sqlite3.connect(DB)
cur = con.cursor()

cur.execute("SELECT params_json FROM target_construction_config WHERE id=1")
row = cur.fetchone()
if not row:
    print("[!] Pas de ligne id=1 dans target_construction_config")
    sys.exit(1)

params = json.loads(row[0])
print()
print("AVANT :")
for k, v in params.items():
    if k.startswith("enable_"):
        print(f"  {k:<22} = {v}")

# On active uniquement R pour Jalon 3
# Macro / Diversif / Vol penalty restent off (Jalons ulterieurs)
params["enable_realized"] = 1

new_json = json.dumps(params)
cur.execute(
    "UPDATE target_construction_config SET params_json=?, updated_at=datetime('now') WHERE id=1",
    (new_json,),
)
con.commit()

print()
print("APRES :")
for k, v in params.items():
    if k.startswith("enable_"):
        print(f"  {k:<22} = {v}")
print()
print("[OK] enable_realized=1 active dans params_json")

# =====================================================================
# 2. Smoke test avec row_factory=Row (comme run_construction_agent)
# =====================================================================
print()
print("=" * 60)
print("2. Smoke test compute_realized_score (row_factory=Row)")
print("=" * 60)
print()

sys.path.insert(0, str(ROOT))
try:
    from portfolio_construction_agent import compute_realized_score, _fetch_log_returns
    print("[SMOKE] Import OK")
except Exception as e:
    print(f"[SMOKE] Import KO : {e}")
    sys.exit(1)

con.row_factory = sqlite3.Row

print()
print("  Ticker | n_returns | R (Sharpe annualise)")
print("  " + "-" * 50)
for ticker in ["AAPL", "BTC", "ETH", "LINK", "MSFT", "META", "NVDA", "TSLA"]:
    try:
        lr = _fetch_log_returns(con, ticker, days=90)
        r = compute_realized_score(con, ticker, days=90)
        print(f"  {ticker:<6} |    n={len(lr):>3}  | R = {r:+.4f}")
    except Exception as e:
        print(f"  {ticker:<6} | ERREUR : {e}")

con.close()

# =====================================================================
# 3. Verif params apres
# =====================================================================
print()
print("=" * 60)
print("3. Verification finale config")
print("=" * 60)

con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute("SELECT params_json, updated_at FROM target_construction_config WHERE id=1")
row = cur.fetchone()
params = json.loads(row[0])
print(f"  updated_at : {row[1]}")
print(f"  enable_realized   : {params.get('enable_realized')}")
print(f"  enable_macro      : {params.get('enable_macro')}")
print(f"  enable_diversif   : {params.get('enable_diversif')}")
print(f"  enable_vol_penalty: {params.get('enable_vol_penalty')}")
print(f"  w_conviction      : {params.get('w_conviction')}")
print(f"  w_realized        : {params.get('w_realized')}")
print(f"  beta_temp         : {params.get('beta_temp')}")
print(f"  conviction_lookback_days : {params.get('conviction_lookback_days')}")
con.close()
'@

$tmp = "$env:TEMP\_enable_realized.py"
$py | Set-Content -Path $tmp -Encoding UTF8
py $tmp

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  TERMINE" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
