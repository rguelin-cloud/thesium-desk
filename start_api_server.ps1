# =====================================================================
# start_api_server.ps1
# Demarre l'API server avec gestion auto du venv / install deps
# =====================================================================

$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"

Set-Location $ProjectRoot

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  START API SERVER (auto-detect venv / deps)" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------
# 1. Chercher un venv existant
# ---------------------------------------------------------------------
Write-Host "[1/4] Recherche d'un venv local..." -ForegroundColor Yellow

$venvCandidates = @(
    "$ProjectRoot\.venv\Scripts\python.exe",
    "$ProjectRoot\venv\Scripts\python.exe",
    "$ProjectRoot\env\Scripts\python.exe"
)

$pyExe = $null
foreach ($cand in $venvCandidates) {
    if (Test-Path $cand) {
        $pyExe = $cand
        Write-Host "  Venv trouve : $cand" -ForegroundColor Green
        break
    }
}

if (-not $pyExe) {
    Write-Host "  Aucun venv trouve. Utilisation du Python global (py)." -ForegroundColor Yellow
    $pyExe = "py"
}

# ---------------------------------------------------------------------
# 2. Verifier uvicorn et fastapi
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[2/4] Verification des dependances..." -ForegroundColor Yellow

$checkScript = @'
import importlib, sys
mods = ["uvicorn", "fastapi", "sqlite3", "bcrypt", "jose"]
missing = []
for m in mods:
    try:
        importlib.import_module(m)
        print(f"  OK  {m}")
    except ImportError:
        print(f"  MISS {m}")
        missing.append(m)
sys.exit(len(missing))
'@

$tmpCheck = "$env:TEMP\_check_deps.py"
$checkScript | Set-Content -Path $tmpCheck -Encoding UTF8

& $pyExe $tmpCheck
$missingCount = $LASTEXITCODE

# ---------------------------------------------------------------------
# 3. Install si necessaire
# ---------------------------------------------------------------------
if ($missingCount -gt 0) {
    Write-Host ""
    Write-Host "[3/4] Installation des dependances manquantes..." -ForegroundColor Yellow

    $reqFile = "$ProjectRoot\requirements.txt"
    if (Test-Path $reqFile) {
        Write-Host "  requirements.txt trouve, install via pip..." -ForegroundColor Gray
        & $pyExe -m pip install -r $reqFile
    } else {
        Write-Host "  requirements.txt absent, install minimal..." -ForegroundColor Gray
        & $pyExe -m pip install uvicorn fastapi bcrypt "python-jose[cryptography]" pydantic
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Install KO" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Install OK" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[3/4] Toutes les dependances sont presentes." -ForegroundColor Green
}

# ---------------------------------------------------------------------
# 4. Lancer le serveur
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[4/4] Demarrage du serveur sur http://127.0.0.1:8765 ..." -ForegroundColor Yellow
Write-Host "  (Ctrl+C pour arreter, laisser cette fenetre OUVERTE)" -ForegroundColor Gray
Write-Host ""

& $pyExe api_server_with_static.py
