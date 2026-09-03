# nextones-run-full-cycle-and-verify-v2.ps1
# Cycle COMPLET defense en profondeur :
# 1. Auth JWT
# 2. POST /api/orders/execute-cycle (theses + convergence + pretrade + orders)
# 3. POST /api/construction/run (PCA -> regenere portfolio_targets avec sizing applique)
# 4. Verifications SQL

$ErrorActionPreference = "Continue"
$BASE = "http://localhost:8000"

Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host "CYCLE COMPLET v2 (execute-cycle + construction/run)" -ForegroundColor Cyan
Write-Host "===============================================================" -ForegroundColor Cyan

# 1. Auth
Write-Host "`n--- 1. Authentification ---" -ForegroundColor Yellow
$loginBody = @{ username = "rguelin"; password = "Thesium2026!" } | ConvertTo-Json
try {
    $loginResp = Invoke-RestMethod -Uri "$BASE/api/auth/login" -Method POST -Body $loginBody -ContentType "application/json"
    $token = $loginResp.access_token
    Write-Host "[OK] Token JWT obtenu" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Login : $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

$headers = @{ Authorization = "Bearer $token" }

# 2. execute-cycle
Write-Host "`n--- 2. POST /api/orders/execute-cycle ---" -ForegroundColor Yellow
$t0 = Get-Date
try {
    $r1 = Invoke-RestMethod -Uri "$BASE/api/orders/execute-cycle" -Method POST -Headers $headers -ContentType "application/json" -TimeoutSec 600
    $d1 = ((Get-Date) - $t0).TotalSeconds
    Write-Host "[OK] execute-cycle en $d1 s" -ForegroundColor Green
    Write-Host "  agent_results : $($r1.cycle_result.agent_results | ConvertTo-Json -Compress)"
    Write-Host "  orders_pending : $($r1.cycle_result.orders_pending)"
    Write-Host "  memo_id : $($r1.cycle_result.memo_id)"
} catch {
    Write-Host "[WARN] execute-cycle : $($_.Exception.Message)" -ForegroundColor Yellow
}

Start-Sleep -Seconds 2

# 3. construction/run
Write-Host "`n--- 3. POST /api/construction/run ---" -ForegroundColor Yellow
$t0 = Get-Date
try {
    $r2 = Invoke-RestMethod -Uri "$BASE/api/construction/run" -Method POST -Headers $headers -ContentType "application/json" -TimeoutSec 600
    $d2 = ((Get-Date) - $t0).TotalSeconds
    Write-Host "[OK] construction/run en $d2 s" -ForegroundColor Green
    Write-Host ($r2 | ConvertTo-Json -Depth 6 -Compress).Substring(0, [Math]::Min(1500, ($r2 | ConvertTo-Json -Depth 6 -Compress).Length))
} catch {
    Write-Host "[WARN] construction/run : $($_.Exception.Message)" -ForegroundColor Yellow
}

Start-Sleep -Seconds 2

# 4. Verifs SQL
Write-Host "`n--- 4. Verifications SQL ---" -ForegroundColor Yellow
py -3.13 .\nextones-verify-full-cycle.py

Write-Host "`n--- 5. Re-execute-cycle pour valider qu'aucun BUY n'est genere sur forced_exit ---" -ForegroundColor Yellow
try {
    $r3 = Invoke-RestMethod -Uri "$BASE/api/orders/execute-cycle" -Method POST -Headers $headers -ContentType "application/json" -TimeoutSec 600
    Write-Host "[OK] re-cycle : orders_pending=$($r3.cycle_result.orders_pending)" -ForegroundColor Green
    if ($r3.cycle_result.orders) {
        Write-Host "Orders generes :"
        $r3.cycle_result.orders | ForEach-Object { Write-Host "  $($_ | ConvertTo-Json -Compress)" }
    }
} catch {
    Write-Host "[WARN] re-cycle : $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host "`n--- 6. Verif finale post-cycle ---" -ForegroundColor Yellow
py -3.13 .\nextones-verify-full-cycle.py
