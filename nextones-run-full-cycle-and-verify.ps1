# nextones-run-full-cycle-and-verify.ps1
# Lance un cycle complet et verifie la defense en profondeur :
# 1. Auth JWT
# 2. POST /api/orders/execute-cycle
# 3. Verifie convergence_snapshots du nouveau cycle (forced_exit count)
# 4. Verifie portfolio_targets : les forced_exit doivent etre a 0
# 5. Verifie orders generes : aucun BUY sur les forced_exit
# 6. Verifie risk_pretrade_log : blocked_by stop_loss/convergence/etc.

$ErrorActionPreference = "Continue"
$BASE = "http://localhost:8000"
$DB = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host "CYCLE COMPLET + VERIFICATION DEFENSE EN PROFONDEUR" -ForegroundColor Cyan
Write-Host "===============================================================" -ForegroundColor Cyan

# 1. Auth
Write-Host "`n--- 1. Authentification ---" -ForegroundColor Yellow
$loginBody = @{ username = "rguelin"; password = "Thesium2026!" } | ConvertTo-Json
try {
    $loginResp = Invoke-RestMethod -Uri "$BASE/api/auth/login" -Method POST -Body $loginBody -ContentType "application/json"
    $token = $loginResp.access_token
    if (-not $token) {
        Write-Host "[FAIL] Pas de token recu" -ForegroundColor Red
        Write-Host ($loginResp | ConvertTo-Json -Depth 5)
        exit 1
    }
    Write-Host "[OK] Token JWT obtenu" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Login : $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

$headers = @{ Authorization = "Bearer $token" }

# 2. Cycle
Write-Host "`n--- 2. Execute cycle complet ---" -ForegroundColor Yellow
$cycleStart = Get-Date
try {
    $cycleResp = Invoke-RestMethod -Uri "$BASE/api/orders/execute-cycle" -Method POST -Headers $headers -ContentType "application/json" -TimeoutSec 600
    $cycleEnd = Get-Date
    $dur = ($cycleEnd - $cycleStart).TotalSeconds
    Write-Host "[OK] Cycle execute en $dur secondes" -ForegroundColor Green
    Write-Host ($cycleResp | ConvertTo-Json -Depth 5 -Compress).Substring(0, [Math]::Min(800, ($cycleResp | ConvertTo-Json -Depth 5 -Compress).Length))
} catch {
    Write-Host "[WARN] Execute-cycle erreur : $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "On continue les verifications quand meme..."
}

# Attendre 2s pour que les ecritures DB soient flushees
Start-Sleep -Seconds 2

# 3-6. Lance le verif Python (plus simple pour SQL)
Write-Host "`n--- 3-6. Verifications SQL ---" -ForegroundColor Yellow
py -3.13 .\nextones-verify-full-cycle.py
