# =====================================================================
# apply_jalon3_patches.ps1  -  Jalon 3 complet
#   1. Fix qty fractionnaire pour cryptos (BTC, ETH, LINK, SOL)
#   2. Remplacer le stub compute_realized_score par vrai Sharpe annualise
#   3. Activer enable_realized dans la config PCA
# =====================================================================

$ErrorActionPreference = "Stop"
$Root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
Set-Location $Root

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  JALON 3 - Patchs (crypto fractional + realized R)" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "$Root\_backups_jalon3_$ts"
New-Item -ItemType Directory -Path $backupDir | Out-Null
Copy-Item "$Root\execution_engine.py"             "$backupDir\" -Force
Copy-Item "$Root\portfolio_construction_agent.py" "$backupDir\" -Force
Write-Host "[1/4] Backup OK : $backupDir" -ForegroundColor Green

# ---------------------------------------------------------------------
# 2. Patch execution_engine.py : qty fractionnaire pour cryptos
# ---------------------------------------------------------------------
$patchPy = @'
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

# =====================================================================
# Patch A : execution_engine.py - qty fractionnaire pour cryptos
# =====================================================================
ee = ROOT / "execution_engine.py"
src = ee.read_text(encoding="utf-8", errors="ignore")

if "# Jalon 3 - qty fractionnaire crypto" in src:
    print("[A] Patch crypto deja applique, skip")
else:
    # Remplace le bloc autour de L1444 (qty = math.floor(delta_val / price))
    # On reecrit la ligne en mode adaptatif crypto vs equity
    old = """        side = "buy" if delta_pct > 0 else "sell"
        # quantit\u00e9 cible : on comble le delta entier (choix utilisateur : 1 cycle)
        delta_val = abs(delta_pct) / 100 * total_value
        qty       = math.floor(delta_val / price)

        # Pour les SELL, plafonner \u00e0 la position d\u00e9tenue
        if side == "sell":
            qty = int(min(qty, math.floor(held_qty)))

        if qty <= 0:"""

    new = """        side = "buy" if delta_pct > 0 else "sell"
        # quantit\u00e9 cible : on comble le delta entier (choix utilisateur : 1 cycle)
        delta_val = abs(delta_pct) / 100 * total_value
        # Jalon 3 - qty fractionnaire crypto
        CRYPTO_TICKERS = {"BTC", "ETH", "LINK", "SOL", "ADA", "DOT", "MATIC", "AVAX"}
        is_crypto = ticker in CRYPTO_TICKERS
        if is_crypto:
            qty = round(delta_val / price, 6)
        else:
            qty = math.floor(delta_val / price)

        # Pour les SELL, plafonner \u00e0 la position d\u00e9tenue
        if side == "sell":
            if is_crypto:
                qty = min(qty, round(held_qty, 6))
            else:
                qty = int(min(qty, math.floor(held_qty)))

        # Seuil minimal : crypto >= 0.0001, equity >= 1
        min_qty = 0.0001 if is_crypto else 1
        if qty < min_qty:"""

    if old in src:
        src = src.replace(old, new)
        print("[A] Bloc qty fractionnaire INJECTE en L~1441")
    else:
        print("[A] Pattern exact introuvable - dump du bloc original autour de L1440 :")
        ll = src.splitlines()
        for i in range(1438, 1455):
            print(f"    L{i+1}  {ll[i]}")

ee.write_text(src, encoding="utf-8")

# =====================================================================
# Patch B : portfolio_construction_agent.py - vrai compute_realized_score
# =====================================================================
pca = ROOT / "portfolio_construction_agent.py"
psrc = pca.read_text(encoding="utf-8", errors="ignore")

if "# Jalon 3 - Sharpe annualise" in psrc:
    print("[B] Patch realized_score deja applique, skip")
else:
    old_stub = '''def compute_realized_score(conn, ticker: str, days: int = 90) -> float:
    """Stub Jalon 3 \u2014 renvoie 0 (R non calcul\u00e9 avant Jalon 3)."""
    return 0.0'''

    new_func = '''def compute_realized_score(conn, ticker: str, days: int = 90) -> float:
    """Jalon 3 - Sharpe annualise sur log-returns des `days` derniers jours.

    Formule : R = mean(log_returns) / std(log_returns) * sqrt(252)
    Si data insuffisante (<5 jours), renvoie 0.5 (neutre).
    """
    try:
        log_returns = _fetch_log_returns(conn, ticker, days=days)
    except Exception as e:
        print(f"[score_R] {ticker} erreur fetch returns : {e}")
        return 0.5

    if not log_returns or len(log_returns) < 5:
        return 0.5

    n = len(log_returns)
    mean = sum(log_returns) / n
    var = sum((x - mean) ** 2 for x in log_returns) / n
    std = math.sqrt(var)

    if std < 1e-9:
        return 0.5

    sharpe = mean / std * math.sqrt(252)
    # Cap softer : sharpe est ramene dans [-3, +3] avant normalize_components
    sharpe = max(-3.0, min(3.0, sharpe))
    return sharpe'''

    if old_stub in psrc:
        psrc = psrc.replace(old_stub, new_func)
        print("[B] compute_realized_score remplace par vrai Sharpe annualise")
    else:
        print("[B] Stub introuvable - check manuel L272")

# =====================================================================
# Patch C : activer enable_realized dans la config par defaut
# =====================================================================
# Cherche le seed config et active enable_realized si necessaire
m = re.search(r"def\s+seed_config_if_empty\s*\([^)]*\)\s*:.*?(?=\ndef\s)", psrc, re.DOTALL)
if m:
    seed_body = m.group(0)
    if "enable_realized" in seed_body and re.search(r"enable_realized\s*[\":]+\s*(0|False)", seed_body):
        new_seed = re.sub(r'(["\'])enable_realized\1\s*:\s*(0|False)',
                          r'\1enable_realized\1: 1', seed_body)
        psrc = psrc.replace(seed_body, new_seed)
        print("[C] enable_realized force a 1 dans seed_config_if_empty")
    else:
        print("[C] enable_realized deja a 1 ou pas dans seed_config (check manuel)")
else:
    print("[C] seed_config_if_empty introuvable - skip")

pca.write_text(psrc, encoding="utf-8")

# =====================================================================
# Patch D : forcer enable_realized=1 dans target_construction_config en DB
# =====================================================================
import sqlite3
con = sqlite3.connect(ROOT / "thesium.db")
cur = con.cursor()
try:
    cur.execute("PRAGMA table_info(target_construction_config)")
    cols = [c[1] for c in cur.fetchall()]
    if "enable_realized" in cols:
        cur.execute("UPDATE target_construction_config SET enable_realized=1 WHERE id=1")
        con.commit()
        print(f"[D] target_construction_config.enable_realized=1 (rows affected={cur.rowcount})")
        cur.execute("SELECT enable_realized FROM target_construction_config WHERE id=1")
        v = cur.fetchone()
        print(f"    Verification : enable_realized = {v[0] if v else 'NULL'}")
    else:
        print(f"[D] Colonne enable_realized absente (cols dispo : {cols})")
except Exception as e:
    print(f"[D] Erreur : {e}")
con.close()

print()
print("=" * 60)
print("PATCHS JALON 3 APPLIQUES")
print("=" * 60)
'@

$tmpPy = "$env:TEMP\_apply_jalon3.py"
$patchPy | Set-Content -Path $tmpPy -Encoding UTF8

Write-Host ""
Write-Host "[2/4] Application des patchs..." -ForegroundColor Yellow
py $tmpPy

# ---------------------------------------------------------------------
# 3. Verification : afficher les lignes patchees
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[3/4] Verification du patch crypto (L1441-1460)..." -ForegroundColor Yellow
$verifyPy = @'
from pathlib import Path
src = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py").read_text(encoding="utf-8", errors="ignore")
lines = src.splitlines()
for i in range(1438, 1465):
    if i < len(lines):
        print(f"  L{i+1}  {lines[i]}")
'@
$tmpVer = "$env:TEMP\_verify_jalon3.py"
$verifyPy | Set-Content -Path $tmpVer -Encoding UTF8
py $tmpVer

Write-Host ""
Write-Host "[4/4] Verification compute_realized_score (L272-300)..." -ForegroundColor Yellow
$verifyPca = @'
from pathlib import Path
src = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py").read_text(encoding="utf-8", errors="ignore")
lines = src.splitlines()
for i in range(270, 305):
    if i < len(lines):
        print(f"  L{i+1}  {lines[i]}")
'@
$tmpVerP = "$env:TEMP\_verify_pca.py"
$verifyPca | Set-Content -Path $tmpVerP -Encoding UTF8
py $tmpVerP

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  TERMINE" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  PROCHAINES ETAPES :" -ForegroundColor Yellow
Write-Host "  1. Redemarrer uvicorn (Ctrl+C puis relance)" -ForegroundColor Gray
Write-Host "  2. Verifier UI accents (UTF-8 patch precedent)" -ForegroundColor Gray
Write-Host "  3. Lancer un cycle complet (UI ou execute-cycle endpoint)" -ForegroundColor Gray
Write-Host "  4. Verifier qu'un ordre BTC BUY est cree (qty ~ 0.26)" -ForegroundColor Gray
Write-Host "  5. Verifier dans les logs : [score_R] xx ou logs pondrations" -ForegroundColor Gray
Write-Host ""
