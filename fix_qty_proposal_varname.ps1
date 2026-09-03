# fix_qty_proposal_varname.ps1
# Corrige le bug var name : remplace 'proposal' par 'p' UNIQUEMENT dans le corps de _qty_for_proposal
# (le reste du fichier peut contenir 'proposal' legitimement, on ne touche pas)

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$engine = Join-Path $root "execution_engine.py"

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = "$engine.bak.varname.$ts"
Copy-Item $engine $backup -Force
Write-Host "[OK] Backup : $backup" -ForegroundColor Green

$py = @'
import re, sys
p = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"
with open(p, "r", encoding="utf-8") as f:
    src = f.read()
lines = src.split("\n")

# Localise def _qty_for_proposal
start = None
for i, ln in enumerate(lines):
    if re.match(r"\s*def\s+_qty_for_proposal\s*\(", ln):
        start = i
        break
if start is None:
    print("[KO] def _qty_for_proposal introuvable")
    sys.exit(2)

# Verifie signature
sig = lines[start]
print(f"[INFO] Signature : {sig.strip()}")
if "self, p)" not in sig and "self, p " not in sig:
    print("[WARN] Signature inattendue, arret par securite")
    sys.exit(3)

base_indent = len(lines[start]) - len(lines[start].lstrip())
end = len(lines)
for j in range(start+1, len(lines)):
    ln = lines[j]
    if ln.strip() == "":
        continue
    ind = len(ln) - len(ln.lstrip())
    if ind <= base_indent and (ln.lstrip().startswith("def ") or ln.lstrip().startswith("class ") or ln.lstrip().startswith("@")):
        end = j
        break

# Patch : dans le corps [start+1, end), remplace les occurrences de la variable 'proposal'
# Strategie : remplace 'proposal.get(' par 'p.get(' et 'proposal[' par 'p['
# (suffisant pour le corps actuel genere)
replaced = 0
for k in range(start+1, end):
    old = lines[k]
    new = old.replace("proposal.get(", "p.get(").replace("proposal[", "p[")
    # Cas isolé : 'proposal ' en fin/milieu — on ne touche pas pour rester safe
    if new != old:
        replaced += 1
        lines[k] = new
        print(f"L{k+1:04d}| -> {new}")

if replaced == 0:
    print("[WARN] Aucun 'proposal' a remplacer dans le corps")
else:
    print(f"[OK] {replaced} ligne(s) corrigee(s)")

with open(p, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

# Validation AST
import ast
try:
    ast.parse(open(p, "r", encoding="utf-8").read())
    print("[OK] AST parse ok")
except SyntaxError as e:
    print(f"[KO] AST: {e}")
    sys.exit(4)
'@

$tmp = Join-Path $env:TEMP "fix_varname_$ts.py"
$py | Out-File -FilePath $tmp -Encoding utf8 -Force
py -3.13 $tmp
$rc = $LASTEXITCODE
Remove-Item $tmp -Force

if ($rc -ne 0) {
    Write-Host "[ERREUR] Patch KO (code $rc). Restauration backup." -ForegroundColor Red
    Copy-Item $backup $engine -Force
    exit $rc
}

Write-Host "`n=== Verification corps _qty_for_proposal ===" -ForegroundColor Cyan
$py2 = @'
import re
p = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"
with open(p, "r", encoding="utf-8") as f:
    lines = f.read().split("\n")
start = None
for i, ln in enumerate(lines):
    if re.match(r"\s*def\s+_qty_for_proposal\s*\(", ln):
        start = i; break
base_indent = len(lines[start]) - len(lines[start].lstrip())
end = len(lines)
for j in range(start+1, len(lines)):
    ln = lines[j]
    if ln.strip() == "": continue
    ind = len(ln) - len(ln.lstrip())
    if ind <= base_indent and (ln.lstrip().startswith("def ") or ln.lstrip().startswith("class ")):
        end = j; break
for k in range(start, end):
    print(f"L{k+1:04d}| {lines[k]}")
'@
$tmp2 = Join-Path $env:TEMP "show_qty_$ts.py"
$py2 | Out-File -FilePath $tmp2 -Encoding utf8 -Force
py -3.13 $tmp2
Remove-Item $tmp2 -Force

Write-Host "`n[SUCCESS] Corrige. Redemarre uvicorn puis lance un cycle." -ForegroundColor Green
Write-Host "  Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/orders/execute-cycle' -Method POST" -ForegroundColor Yellow
