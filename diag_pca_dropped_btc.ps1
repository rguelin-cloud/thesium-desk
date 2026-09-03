# =====================================================================
# diag_pca_dropped_btc.ps1
# 1. Confirme quel PCA est utilise (jalon2)
# 2. Verifie son contenu (stub R ? helper ?)
# 3. Lit la 'reason' du BTC DROPPED
# =====================================================================

$ErrorActionPreference = "Continue"
$Root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
Set-Location $Root

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  DIAG PCA reel + BTC DROPPED" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

$py = @'
import sqlite3
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

# =====================================================================
# 1. Comparaison des 2 PCA
# =====================================================================
print("=" * 70)
print("1. Fichiers portfolio_construction_agent*.py")
print("=" * 70)

for f in ROOT.glob("portfolio_construction_agent*.py"):
    n_lines = sum(1 for _ in f.open(encoding="utf-8", errors="ignore"))
    size = f.stat().st_size
    print(f"  {f.name:<50} {n_lines:>5} lines  {size:>8} bytes")

# =====================================================================
# 2. Contenu de jalon2 - cherche compute_realized_score
# =====================================================================
print()
print("=" * 70)
print("2. portfolio_construction_agent_jalon2.py - compute_realized_score")
print("=" * 70)

j2 = ROOT / "portfolio_construction_agent_jalon2.py"
if not j2.exists():
    print("  FICHIER ABSENT")
else:
    src = j2.read_text(encoding="utf-8", errors="ignore")
    lines = src.splitlines()
    
    # Cherche compute_realized_score
    for i, line in enumerate(lines):
        if re.match(r"^def\s+compute_realized_score\s*\(", line):
            print(f"  Trouvee L{i+1} :")
            # Affiche les 15 lignes suivantes
            for j in range(i, min(i+20, len(lines))):
                print(f"  L{j+1:>4}  {lines[j]}")
            print()
            break
    
    # Cherche _fetch_log_returns
    for i, line in enumerate(lines):
        if re.match(r"^def\s+_fetch_log_returns\s*\(", line):
            print(f"  _fetch_log_returns trouvee L{i+1}")
            break
    else:
        print("  _fetch_log_returns ABSENTE de jalon2")
    
    # Cherche "Stub" 
    if "Stub Jalon 3" in src:
        print("  >>> jalon2 contient ENCORE le STUB compute_realized_score <<<")
    if "Jalon 3 - Sharpe annualise" in src:
        print("  >>> jalon2 contient le VRAI Sharpe (patche) <<<")

# =====================================================================
# 3. Verifie si jalon2.py est strictement identique a .py ou pas
# =====================================================================
print()
print("=" * 70)
print("3. Comparaison contenu : pca.py vs pca_jalon2.py")
print("=" * 70)
pca = ROOT / "portfolio_construction_agent.py"
import hashlib
def md5(p):
    return hashlib.md5(p.read_bytes()).hexdigest()
print(f"  portfolio_construction_agent.py        md5={md5(pca)}")
print(f"  portfolio_construction_agent_jalon2.py md5={md5(j2)}")
if md5(pca) == md5(j2):
    print("  -> IDENTIQUES (symlink ou copie)")
else:
    print("  -> DIFFERENTS - jalon2 doit etre patche separement")

# =====================================================================
# 4. Reason BTC DROPPED dans cycle_reconciliation_log
# =====================================================================
print()
print("=" * 70)
print("4. cycle_reconciliation_log - BTC details derniers cycles")
print("=" * 70)

con = sqlite3.connect(ROOT / "thesium.db")
con.row_factory = sqlite3.Row
cur = con.cursor()

cur.execute("""
    SELECT cycle_id, ticker, action, reason, signals_in, qty_in, side_in,
           conviction_max, delta_signal_pct, delta_target_pct, created_at
    FROM cycle_reconciliation_log
    WHERE ticker='BTC'
    ORDER BY id DESC LIMIT 10
""")
btc_rows = cur.fetchall()
if not btc_rows:
    print("  BTC jamais log par le Reconciler")
else:
    for r in btc_rows:
        print(f"\n  cycle={r['cycle_id']}  action={r['action']}")
        print(f"    reason : {r['reason']}")
        print(f"    signals_in={r['signals_in']} qty_in={r['qty_in']} side_in={r['side_in']}")
        print(f"    conv_max={r['conviction_max']}  delta_signal={r['delta_signal_pct']}  delta_target={r['delta_target_pct']}")

# =====================================================================
# 5. Tout le cycle 20260525-092135 (le dernier)
# =====================================================================
print()
print("=" * 70)
print("5. Tout le cycle 20260525-092135")
print("=" * 70)
cur.execute("""
    SELECT ticker, action, reason, signals_in, qty_in, side_in, conviction_max
    FROM cycle_reconciliation_log
    WHERE cycle_id='20260525-092135'
    ORDER BY id
""")
for r in cur.fetchall():
    print(f"\n  {r['ticker']:<6} {r['action']:<15} qty_in={r['qty_in']}  side={r['side_in']}")
    print(f"     reason : {r['reason']}")

con.close()

# =====================================================================
# 6. Verifie le code execution_engine pour l'action DROPPED
# =====================================================================
print()
print("=" * 70)
print("6. execution_engine.py - logique DROPPED")
print("=" * 70)
ee = (ROOT / "execution_engine.py").read_text(encoding="utf-8", errors="ignore").splitlines()
for i, line in enumerate(ee):
    if "DROPPED" in line:
        print(f"  L{i+1:>5}  {line.strip()[:140]}")
'@

$tmp = "$env:TEMP\_diag_pca_dropped.py"
$py | Set-Content -Path $tmp -Encoding UTF8
py $tmp

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  TERMINE" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
