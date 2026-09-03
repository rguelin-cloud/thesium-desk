# nextones-fix-scheduler-geo-pplx.ps1
# Ajoute un job APScheduler 4h pour pplx_geo_agent dans api_server.py
# Marker idempotent : [GEO_PPLX_V1]
# Pattern : on suit la convention des autres jobs PPLX (crypto/factor/thesis) déjà présents

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$target = Join-Path $root "api_server.py"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak_geo_sched_$ts"

if (-not (Test-Path $target)) {
    Write-Host "[KO] $target introuvable" -ForegroundColor Red
    exit 1
}

Copy-Item $target $backup -Force
Write-Host "[1/4] Backup -> $backup"

# Helper : diagnostic d'abord pour repérer les autres jobs PPLX
$diag = Join-Path $env:TEMP "diag_scheduler_$ts.py"
$diagContent = @'
# -*- coding: utf-8 -*-
import re, sys
from pathlib import Path
target = Path(sys.argv[1])
src = target.read_text(encoding="utf-8-sig")

# Recherche scheduler.add_job
print("=== add_job(...) occurrences ===")
for m in re.finditer(r'(scheduler|sched)\.add_job\s*\([^)]+\)', src, re.DOTALL):
    line = src[:m.start()].count('\n') + 1
    txt = m.group(0).replace('\n', ' ')[:200]
    print(f"  L{line}: {txt}")

print("\n=== markers existants ===")
for marker in ["[CRYPTO_PPLX_V1]", "[FACTOR_PPLX_V1]", "[THESIS_PPLX_V1]", "[GEO_PPLX_V1]", "PPLX_CRYPTO", "PPLX_FACTOR", "PPLX_THESIS"]:
    cnt = src.count(marker)
    if cnt:
        print(f"  {marker} : {cnt}")

print("\n=== imports pplx_*_agent ===")
for m in re.finditer(r'(?m)^(?:from|import)\s+pplx_\w+(?:_agent)?[\s\w,]*', src):
    print(f"  L{src[:m.start()].count(chr(10))+1}: {m.group(0)}")

# Cherche les blocs de scheduler par marker
print("\n=== Blocs marker scheduler (BEGIN...END) ===")
for m in re.finditer(r'#\s*===\s*\[(\w+)\]\s*BEGIN\s*===', src):
    name = m.group(1)
    line = src[:m.start()].count('\n') + 1
    # find matching END
    end = src.find(f"# === [{name}] END ===", m.end())
    if end > 0:
        end_line = src[:end].count('\n') + 1
        print(f"  [{name}] L{line}-{end_line} ({end_line-line+1} lignes)")
'@

Set-Content -Path $diag -Value $diagContent -Encoding UTF8

Write-Host "[2/4] Diag scheduler existant..."
py -3.13 $diag $target

Write-Host ""
Write-Host "[3/4] Pause : vérifie la sortie ci-dessus avant de continuer le patch."
Write-Host "       Si tu vois bien [CRYPTO_PPLX_V1] ou similaire, on suit le même pattern."
Write-Host ""
Write-Host "Lance ensuite : powershell -ExecutionPolicy Bypass -File .\nextones-apply-scheduler-geo-pplx.ps1"
