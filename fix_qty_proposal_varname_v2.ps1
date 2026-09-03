# fix_qty_proposal_varname_v2.ps1
# v2 : tolere BOM UTF-8 + reecrit sans BOM

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$engine = Join-Path $root "execution_engine.py"

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = "$engine.bak.varname2.$ts"
Copy-Item $engine $backup -Force
Write-Host "[OK] Backup : $backup" -ForegroundColor Green

$py = @'
import re, sys, io
p = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"

# Lecture tolerante au BOM
with open(p, "r", encoding="utf-8-sig") as f:
    src = f.read()

# Diagnostic BOM
had_bom = False
with open(p, "rb") as f:
    raw = f.read(3)
    if raw[:3] == b"\xef\xbb\xbf":
        had_bom = True
print(f"[INFO] BOM present en tete : {had_bom}")

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

sig = lines[start]
print(f"[INFO] Signature : {sig.strip()}")
if "self, p)" not in sig and "self, p " not in sig:
    print("[WARN] Signature inattendue, arret")
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

replaced = 0
for k in range(start+1, end):
    old = lines[k]
    new = old.replace("proposal.get(", "p.get(").replace("proposal[", "p[")
    if new != old:
        replaced += 1
        lines[k] = new
        print(f"L{k+1:04d}| -> {new}")

print(f"[OK] {replaced} ligne(s) corrigee(s)")

new_src = "\n".join(lines)

# Reecriture SANS BOM (utf-8 pur)
with open(p, "w", encoding="utf-8", newline="") as f:
    f.write(new_src)

# Re-verifie absence BOM
with open(p, "rb") as f:
    raw = f.read(3)
    still_bom = (raw[:3] == b"\xef\xbb\xbf")
print(f"[INFO] BOM apres reecriture : {still_bom}")

# Validation AST sur lecture utf-8-sig pour tolerer
import ast
try:
    with open(p, "r", encoding="utf-8-sig") as f:
        ast.parse(f.read())
    print("[OK] AST parse ok (lecture utf-8-sig)")
except SyntaxError as e:
    print(f"[KO] AST: {e}")
    sys.exit(4)
'@

$tmp = Join-Path $env:TEMP "fix_varname_v2_$ts.py"
# Ecrit le script Python SANS BOM
[System.IO.File]::WriteAllText($tmp, $py, (New-Object System.Text.UTF8Encoding $false))
py -3.13 $tmp
$rc = $LASTEXITCODE
Remove-Item $tmp -Force

if ($rc -ne 0) {
    Write-Host "[ERREUR] Patch KO (code $rc). Restauration backup." -ForegroundColor Red
    Copy-Item $backup $engine -Force
    exit $rc
}

Write-Host "`n=== Corps _qty_for_proposal apres patch ===" -ForegroundColor Cyan
$py2 = @'
import re
p = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"
with open(p, "r", encoding="utf-8-sig") as f:
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
$tmp2 = Join-Path $env:TEMP "show_qty_v2_$ts.py"
[System.IO.File]::WriteAllText($tmp2, $py2, (New-Object System.Text.UTF8Encoding $false))
py -3.13 $tmp2
Remove-Item $tmp2 -Force

Write-Host "`n[SUCCESS] Patche. Redemarre uvicorn puis lance un cycle :" -ForegroundColor Green
Write-Host "  Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/orders/execute-cycle' -Method POST" -ForegroundColor Yellow
