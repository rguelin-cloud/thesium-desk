# =====================================================================
# fix_qty_for_proposal.ps1
# Bug : _qty_for_proposal retourne int() ce qui casse les fractions crypto
# Solution : crypto-aware _qty_for_proposal + adapter MIN_TRADE_WEIGHT_PCT
# =====================================================================

$ErrorActionPreference = "Stop"
$Root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
Set-Location $Root

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  FIX _qty_for_proposal pour crypto" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "$Root\_backups_qty_prop_$ts"
New-Item -ItemType Directory -Path $backupDir | Out-Null
Copy-Item "$Root\execution_engine.py" "$backupDir\" -Force
Write-Host "[1/4] Backup OK : $backupDir" -ForegroundColor Green

# =====================================================================
# 1. Inspection des methodes pertinentes
# =====================================================================
Write-Host ""
Write-Host "[2/4] Inspection _qty_for_proposal et MIN_TRADE_WEIGHT_PCT..." -ForegroundColor Yellow
$pyInspect = @'
import re
from pathlib import Path
ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
ee = ROOT / "execution_engine.py"
src = ee.read_text(encoding="utf-8", errors="ignore")
lines = src.splitlines()

# _qty_for_proposal
print("=" * 70)
print("def _qty_for_proposal (corps complet)")
print("=" * 70)
for i, l in enumerate(lines):
    if re.match(r"^\s+def\s+_qty_for_proposal\s*\(", l):
        # Affiche jusqu'a la prochaine def ou fin du bloc
        for j in range(i, min(i+30, len(lines))):
            print(f"  L{j+1:>4}  {lines[j]}")
            # Stop si on retombe sur un def au meme niveau ou au niveau classe
            if j > i and re.match(r"^    def\s+", lines[j]):
                break
        break

print()
print("=" * 70)
print("MIN_TRADE_WEIGHT_PCT - definition")
print("=" * 70)
for i, l in enumerate(lines):
    if "MIN_TRADE_WEIGHT_PCT" in l and "=" in l and "self." not in l:
        print(f"  L{i+1:>4}  {l.strip()}")

# Affiche le bloc filtre L600-630
print()
print("=" * 70)
print("Bloc filtre signal trop petit L605-635")
print("=" * 70)
for i in range(604, 635):
    if i < len(lines):
        print(f"  L{i+1:>4}  {lines[i]}")
'@
$tmpI = "$env:TEMP\_inspect.py"
$pyInspect | Set-Content -Path $tmpI -Encoding UTF8
py $tmpI

# =====================================================================
# 2. Application du patch
# =====================================================================
Write-Host ""
Write-Host "[3/4] Patch _qty_for_proposal crypto-aware + bypass filtre..." -ForegroundColor Yellow
$pyPatch = @'
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
ee = ROOT / "execution_engine.py"
src = ee.read_text(encoding="utf-8", errors="ignore")
lines = src.splitlines(keepends=False)

CRYPTO_TICKERS_LINE = "CRYPTO_TICKERS_FRACTIONAL = {'BTC', 'ETH', 'LINK', 'SOL', 'ADA', 'DOT', 'MATIC', 'AVAX'}"

# Patch 1 : trouver et reecrire _qty_for_proposal
print()
patched_q = False
for i, line in enumerate(lines):
    if re.match(r"^\s+def\s+_qty_for_proposal\s*\(", line):
        # Trouver indent
        m = re.match(r"^(\s+)def\s+_qty_for_proposal\s*\(", line)
        indent = m.group(1)
        body_indent = indent + "    "
        
        # Trouver fin (prochaine def au meme indent)
        end = i + 1
        for j in range(i + 1, len(lines)):
            mj = re.match(rf"^{indent}def\s+", lines[j])
            if mj:
                end = j
                break
        else:
            end = len(lines)
        
        # Marqueur deja patche ?
        existing_body = "\n".join(lines[i:end])
        if "# Jalon 3 - qty fractionnaire crypto-aware" in existing_body:
            print("[Q] _qty_for_proposal deja patche")
            patched_q = True
            break
        
        # Recuperer signature (peut etre multi-ligne)
        sig_line = lines[i]
        sig_end = i
        if not sig_line.rstrip().endswith(":"):
            # Multi-ligne
            for k in range(i + 1, end):
                sig_end = k
                if lines[k].rstrip().endswith(":"):
                    break
        
        # Reecrit corps
        new_body = [
            body_indent + "# Jalon 3 - qty fractionnaire crypto-aware",
            body_indent + "CRYPTO = {'BTC', 'ETH', 'LINK', 'SOL', 'ADA', 'DOT', 'MATIC', 'AVAX'}",
            body_indent + "ticker = proposal.get('ticker', '')",
            body_indent + "is_crypto = ticker in CRYPTO",
            body_indent + "qpct = float(proposal.get('quantity_pct', 0) or 0)",
            body_indent + "price = float(self.prices.get(ticker, 0) or 0)",
            body_indent + "if price <= 0 or qpct <= 0:",
            body_indent + "    return 0.0 if is_crypto else 0",
            body_indent + "signal_value = qpct / 100.0 * self.nav",
            body_indent + "if is_crypto:",
            body_indent + "    qty = round(signal_value / price, 6)",
            body_indent + "else:",
            body_indent + "    import math as _m",
            body_indent + "    qty = _m.floor(signal_value / price)",
            body_indent + "return max(qty, 0.0 if is_crypto else 0)",
        ]
        
        lines[sig_end + 1:end] = new_body
        print(f"[Q] _qty_for_proposal patche (L{i+1} -> body reecrit jusqu'a L{sig_end+len(new_body)+1})")
        patched_q = True
        break

if not patched_q:
    print("[Q] _qty_for_proposal introuvable - ERREUR")

# Patch 2 : MIN_TRADE_WEIGHT_PCT - faire bypass pour crypto dans le filtre
# Cherche le bloc L605-625 environ : if abs(delta_signal_pct) < self.MIN_TRADE_WEIGHT_PCT:
src_after_q = "\n".join(lines)
lines = src_after_q.splitlines()

patched_filter = False
for i, line in enumerate(lines):
    if "abs(delta_signal_pct)" in line and "MIN_TRADE_WEIGHT_PCT" in line:
        # Verifier qu'on n'a pas deja patche
        ctx_start = max(0, i - 3)
        ctx = "\n".join(lines[ctx_start:i+1])
        if "# Jalon 3 - bypass crypto" in ctx:
            print("[F] Filtre signal trop petit deja patche")
            patched_filter = True
            break
        # Inserer juste avant : si crypto avec qty > min_qty crypto, on bypass
        m = re.match(r"^(\s+)", line)
        ind = m.group(1) if m else "            "
        new_check = [
            f"{ind}# Jalon 3 - bypass crypto si qty fractionnaire valide",
            f"{ind}CRYPTO_BYPASS = {{'BTC', 'ETH', 'LINK', 'SOL', 'ADA', 'DOT', 'MATIC', 'AVAX'}}",
            f"{ind}if ticker in CRYPTO_BYPASS and qty_net >= 0.0001:",
            f"{ind}    pass  # ne pas filtrer les crypto fractionnaires",
            f"{ind}elif abs(delta_signal_pct) < self.MIN_TRADE_WEIGHT_PCT:",
        ]
        # Remplace la ligne 'if abs(delta_signal_pct) < self.MIN_TRADE_WEIGHT_PCT:'
        lines[i] = "\n".join(new_check)
        print(f"[F] Filtre signal trop petit adapte crypto en L{i+1}")
        patched_filter = True
        break

if not patched_filter:
    print("[F] Filtre signal trop petit introuvable - inspecter manuellement")

# Reecriture
ee.write_text("\n".join(lines) + ("\n" if src.endswith("\n") else ""), encoding="utf-8")
print()
print("[OK] execution_engine.py reecrit")
'@
$tmpP = "$env:TEMP\_patch_qty.py"
$pyPatch | Set-Content -Path $tmpP -Encoding UTF8
py $tmpP

# =====================================================================
# 3. Verification
# =====================================================================
Write-Host ""
Write-Host "[4/4] Verification _qty_for_proposal + filtre patches..." -ForegroundColor Yellow
$pyVerif = @'
import re
from pathlib import Path
ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
ee = ROOT / "execution_engine.py"
src = ee.read_text(encoding="utf-8", errors="ignore")
lines = src.splitlines()

# _qty_for_proposal
print("=" * 70)
print("_qty_for_proposal patche")
print("=" * 70)
for i, l in enumerate(lines):
    if re.match(r"^\s+def\s+_qty_for_proposal\s*\(", l):
        for j in range(i, min(i+22, len(lines))):
            print(f"  L{j+1:>4}  {lines[j]}")
            if j > i and re.match(r"^    def\s+", lines[j]):
                break
        break

print()
print("=" * 70)
print("Filtre signal trop petit patche")
print("=" * 70)
for i, l in enumerate(lines):
    if "Jalon 3 - bypass crypto" in l:
        for j in range(max(0, i-1), min(i+10, len(lines))):
            print(f"  L{j+1:>4}  {lines[j]}")
        break
'@
$tmpV = "$env:TEMP\_verif_qty.py"
$pyVerif | Set-Content -Path $tmpV -Encoding UTF8
py $tmpV

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  TERMINE" -ForegroundColor Cyan
Write-Host "  Prochaines etapes :" -ForegroundColor Cyan
Write-Host "  1. Ctrl+C + relance uvicorn" -ForegroundColor Cyan
Write-Host "  2. Lance un nouveau cycle (UI ou POST /api/orders/execute-cycle)" -ForegroundColor Cyan
Write-Host "  3. Verifie : BTC BUY 0.258 en pending + logs [score_R] visibles" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
