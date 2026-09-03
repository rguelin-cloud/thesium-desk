# =====================================================================
# fix_jalon2_and_qty_cast.ps1
# 1. Applique le patch R sur portfolio_construction_agent_jalon2.py
# 2. Trouve les int(qty) dans execution_engine.py qui cassent les fractions
# =====================================================================

$ErrorActionPreference = "Stop"
$Root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
Set-Location $Root

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  FIX Jalon2 + Cast qty crypto fractionnaire" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "$Root\_backups_jalon2_qty_$ts"
New-Item -ItemType Directory -Path $backupDir | Out-Null
Copy-Item "$Root\portfolio_construction_agent_jalon2.py" "$backupDir\" -Force
Copy-Item "$Root\execution_engine.py" "$backupDir\" -Force
Write-Host "[1/4] Backup OK : $backupDir" -ForegroundColor Green

# =====================================================================
# Patch A : jalon2.py - vrai Sharpe annualise (helper deja la)
# =====================================================================
$pyA = @'
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
target = ROOT / "portfolio_construction_agent_jalon2.py"

src = target.read_text(encoding="utf-8", errors="ignore")
if "# Jalon 3 - Sharpe annualise" in src:
    print("[A] Deja applique")
else:
    lines = src.splitlines(keepends=False)
    # Trouve def compute_realized_score
    idx = None
    for i, l in enumerate(lines):
        if re.match(r"^def\s+compute_realized_score\s*\(", l):
            idx = i
            break
    if idx is None:
        print("[A] def compute_realized_score INTROUVABLE dans jalon2")
    else:
        # Cherche fin = prochaine ligne 'def ' ou separateur
        end = idx + 1
        for j in range(idx + 1, len(lines)):
            if lines[j].startswith("def ") or (lines[j].startswith("#") and "===" in lines[j]):
                end = j
                break
        new_func = [
            "def compute_realized_score(conn, ticker: str, days: int = 90) -> float:",
            '    """Jalon 3 - Sharpe annualise sur log-returns des `days` derniers jours.',
            "",
            "    Formule : R = mean(log_returns) / std(log_returns) * sqrt(252)",
            "    Capped a [-3, +3]. Renvoie 0.5 (neutre) si data insuffisante.",
            '    """',
            "    try:",
            "        log_returns = _fetch_log_returns(conn, ticker, days=days)",
            "    except Exception as e:",
            '        print(f"[score_R] {ticker} erreur fetch returns : {e}")',
            "        return 0.5",
            "",
            "    if not log_returns or len(log_returns) < 5:",
            '        print(f"[score_R] {ticker:<6} data insuffisante n={len(log_returns) if log_returns else 0} -> 0.5")',
            "        return 0.5",
            "",
            "    n = len(log_returns)",
            "    mean = sum(log_returns) / n",
            "    var = sum((x - mean) ** 2 for x in log_returns) / n",
            "    std = math.sqrt(var)",
            "",
            "    if std < 1e-9:",
            '        print(f"[score_R] {ticker:<6} std nulle n={n} -> 0.5")',
            "        return 0.5",
            "",
            "    sharpe = mean / std * math.sqrt(252)",
            "    sharpe = max(-3.0, min(3.0, sharpe))",
            '    print(f"[score_R] {ticker:<6} n={n:>2} mean={mean:+.5f} std={std:.5f} sharpe={sharpe:+.3f}")',
            "    return sharpe",
            "",
        ]
        lines[idx:end] = new_func
        new_src = "\n".join(lines) + ("\n" if src.endswith("\n") else "")
        target.write_text(new_src, encoding="utf-8")
        print(f"[A] Stub remplace dans jalon2.py (L{idx+1} -> L{end+1})")
'@
$tmpA = "$env:TEMP\_fix_jalon2.py"
$pyA | Set-Content -Path $tmpA -Encoding UTF8

Write-Host ""
Write-Host "[2/4] Patch A : jalon2.py compute_realized_score..." -ForegroundColor Yellow
py $tmpA

# =====================================================================
# Patch B : execution_engine.py - cherche les int(qty) qui cassent
# =====================================================================
Write-Host ""
Write-Host "[3/4] Diagnostic : ou les fractions sont castees en int ?" -ForegroundColor Yellow
$pyB = @'
import re
from pathlib import Path
ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

ee = ROOT / "execution_engine.py"
src = ee.read_text(encoding="utf-8", errors="ignore")
lines = src.splitlines()

print()
print("=" * 70)
print("Recherche des operations qty qui pourraient casser les fractions")
print("=" * 70)

# Patterns suspects
patterns = [
    (r"\bint\s*\(\s*qty\b", "int(qty"),
    (r"\bqty\s*=\s*int\s*\(", "qty = int("),
    (r"\bquantity\s*=\s*int\s*\(", "quantity = int("),
    (r"\bint\s*\(\s*quantity\b", "int(quantity"),
    (r"qty_in", "qty_in (Reconciler)"),
    (r"signals_in", "signals_in"),
    (r"delta_signal_pct", "delta_signal_pct"),
    (r"trop petit", "filtre 'trop petit'"),
    (r"MIN_SIGNAL", "MIN_SIGNAL constante"),
    (r"min_signal", "min_signal"),
    (r"_DROP_BELOW", "_DROP_BELOW"),
    (r"0\.3\s*%", "seuil 0.3%"),
    (r"0\.003\b", "seuil 0.003 (=0.3%)"),
]

for pat, label in patterns:
    rgx = re.compile(pat, re.IGNORECASE)
    matches = []
    for i, line in enumerate(lines):
        if rgx.search(line):
            matches.append((i+1, line.rstrip()))
    if matches:
        print(f"\n  [{label}] {len(matches)} matches :")
        for ln, content in matches[:8]:
            print(f"    L{ln:>5}  {content[:130]}")

# Cherche specifiquement la classe Reconciler ou la fonction _log avec DROPPED
print()
print("=" * 70)
print("Bloc autour de L544 (premier DROPPED)")
print("=" * 70)
for i in range(530, 570):
    if i < len(lines):
        print(f"  L{i+1:>4}  {lines[i].rstrip()[:140]}")
'@
$tmpB = "$env:TEMP\_diag_qty.py"
$pyB | Set-Content -Path $tmpB -Encoding UTF8
py $tmpB

# =====================================================================
# 4. Verif jalon2 patche
# =====================================================================
Write-Host ""
Write-Host "[4/4] Verification jalon2 patche L268-310..." -ForegroundColor Yellow
$verifyJ = @'
from pathlib import Path
src = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent_jalon2.py").read_text(encoding="utf-8", errors="ignore")
lines = src.splitlines()
for i in range(268, 315):
    if i < len(lines):
        print(f"  L{i+1}  {lines[i]}")
'@
$tmpV = "$env:TEMP\_verif_jalon2.py"
$verifyJ | Set-Content -Path $tmpV -Encoding UTF8
py $tmpV

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  TERMINE - colle l'output, on patche le cast int(qty)" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
