# nextones-fix-geo-db-path.ps1
# Corrige DB_PATH non défini dans _pplx_geo_load_snapshot et _pplx_geo_book_exposure
# Utilise le pattern local Path(__file__).parent / "thesium.db" comme les autres helpers PPLX

$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak_geo_db_$ts"

Copy-Item $target $backup -Force
Write-Host "[1/3] Backup -> $backup"

$helper = Join-Path $env:TEMP "fix_geo_db_$ts.py"
$helperContent = @'
# -*- coding: utf-8 -*-
import re, sys
from pathlib import Path

target = Path(sys.argv[1])
raw = target.read_text(encoding="utf-8-sig")

# Compte AVANT
before_count = raw.count("connect(DB_PATH)")
print(f"[i] connect(DB_PATH) AVANT : {before_count}")

# Pattern : remplace 'con = sqlite3.connect(DB_PATH)' par bloc local Path(__file__)
old_pattern = "con = sqlite3.connect(DB_PATH)"
new_block = (
    "from pathlib import Path as _Path_geo\n"
    "        _db_geo = _Path_geo(__file__).resolve().parent / \"thesium.db\"\n"
    "        con = sqlite3.connect(str(_db_geo))"
)

# On veut remplacer EXACTEMENT dans nos 2 helpers (pas ailleurs).
# Stratégie : on remplace les 2 occurrences (il n'y en a que 2 dans tout le fichier d'après le diag).
new_raw = raw.replace(old_pattern, new_block)

after_count = new_raw.count("connect(DB_PATH)")
replaced = before_count - after_count
print(f"[i] connect(DB_PATH) APRES : {after_count}")
print(f"[i] Remplacements effectués : {replaced}")

if replaced != 2:
    print(f"[KO] Attendu 2 remplacements, eu {replaced}")
    sys.exit(2)

target.write_text(new_raw, encoding="utf-8", newline="\n")
print("[OK] Fichier écrit")
'@

Set-Content -Path $helper -Value $helperContent -Encoding UTF8

Write-Host "[2/3] Helper -> $helper"
py -3.13 $helper $target
if ($LASTEXITCODE -ne 0) {
    Write-Host "[KO] Helper a échoué. Restore." -ForegroundColor Red
    Copy-Item $backup $target -Force
    exit 1
}

# Validation syntaxe
Write-Host "[3/3] Validation syntaxe..."
py -3.13 -c "import ast; ast.parse(open(r'$target', encoding='utf-8').read()); print('[OK] syntaxe valide')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[KO] Erreur syntaxe. Restore." -ForegroundColor Red
    Copy-Item $backup $target -Force
    exit 1
}

Write-Host ""
Write-Host "=== PATCH OK ===" -ForegroundColor Green
Write-Host "Backup : $backup"
Write-Host ""
Write-Host "Redemarre l'API et retest :"
Write-Host "  (Invoke-RestMethod http://localhost:8000/api/pplx/geo) | ConvertTo-Json -Depth 10"
