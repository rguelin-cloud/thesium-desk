# [KILL_UVICORN_V1] Force-kill du process uvicorn sur le port 8000
# Usage: powershell -ExecutionPolicy Bypass -File .\kill_uvicorn.ps1
# Strategie:
#   1. Recupere les PIDs ecoutant sur 8000 via Get-NetTCPConnection
#   2. Kill chaque PID via Stop-Process -Force
#   3. Affiche le resultat
$ErrorActionPreference = "Continue"
$port = 8000

Write-Host "[KILL] Recherche des process ecoutant sur le port $port..." -ForegroundColor Cyan

try {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
} catch {
    Write-Host "[INFO] Aucun process n'ecoute sur le port $port" -ForegroundColor Yellow
    exit 0
}

if (-not $conns) {
    Write-Host "[INFO] Aucun process trouve sur le port $port" -ForegroundColor Yellow
    exit 0
}

$pidList = $conns | Select-Object -ExpandProperty OwningProcess -Unique

foreach ($processId in $pidList) {
    try {
        $proc = Get-Process -Id $processId -ErrorAction Stop
        Write-Host "[KILL] PID=$processId Name=$($proc.ProcessName) -> Stop-Process -Force" -ForegroundColor Yellow
        Stop-Process -Id $processId -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 300
        Write-Host "[OK]   PID=$processId tue" -ForegroundColor Green
    } catch {
        Write-Host "[WARN] PID=$processId : $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Verifier qu'il ne reste rien
Start-Sleep -Milliseconds 500
try {
    $remaining = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
    Write-Host "[WARN] Il reste des connexions sur $port" -ForegroundColor Red
    $remaining | Format-Table -AutoSize
} catch {
    Write-Host "[DONE] Port $port libere" -ForegroundColor Green
}
