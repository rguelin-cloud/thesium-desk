# [STOP_UVICORN_CLEAN_V1]
# Arret propre d'uvicorn sur le port 8000.
#
# Strategie :
#   1) Trouve le PID qui ecoute sur :8000
#   2) Tente Stop-Process -Force (rapide, fiable sur Windows)
#   3) Verifie que le port est libere
#
# Usage : powershell -ExecutionPolicy Bypass -File .\nextones-stop-uvicorn-clean.ps1

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  [STOP_UVICORN_CLEAN_V1] Arret propre uvicorn port 8000" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1) Trouve les PIDs ecoutant sur :8000
$conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $conns) {
    Write-Host "[OK]   Aucun process n'ecoute sur :8000, deja libre." -ForegroundColor Green
    exit 0
}

$pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
Write-Host "[INFO] PIDs detectes sur :8000 : $($pids -join ', ')" -ForegroundColor Yellow

foreach ($targetPid in $pids) {
    try {
        $proc = Get-Process -Id $targetPid -ErrorAction Stop
        Write-Host ("[INFO] PID {0}  Name={1}  CPU={2}s" -f $targetPid, $proc.ProcessName, [math]::Round($proc.CPU,1))
    } catch {
        Write-Host "[WARN] Impossible de lire PID $targetPid : $_" -ForegroundColor Yellow
        continue
    }

    Write-Host "[ACT]  Stop-Process -Id $targetPid -Force ..." -ForegroundColor Yellow
    try {
        Stop-Process -Id $targetPid -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 500
        Write-Host "[OK]   PID $targetPid termine." -ForegroundColor Green
    } catch {
        Write-Host "[ERR]  Stop-Process echoue : $_" -ForegroundColor Red
    }
}

# 2) Verification
Start-Sleep -Seconds 1
$still = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($still) {
    Write-Host "[FAIL] Le port :8000 est encore occupe. PIDs restants : $($still.OwningProcess -join ', ')" -ForegroundColor Red
    exit 1
} else {
    Write-Host ""
    Write-Host "[SUCCESS] Port :8000 libere. Tu peux relancer uvicorn :" -ForegroundColor Green
    Write-Host "          py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000" -ForegroundColor Gray
}
