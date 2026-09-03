# nextones-run-execute-cycle-auth.ps1
# Version authentifiee de run-execute-cycle :
#   1. login JWT -> recupere access_token
#   2. POST /api/orders/execute-cycle avec Bearer
#   3. Liste nouveaux ordres, reconciler log, targets snapshot
#
# Idempotent, ne modifie aucun fichier code.

$ErrorActionPreference = "Stop"
$BaseUrl = "http://127.0.0.1:8000"
$DbPath  = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

$User     = "rguelin"
$Password = "Thesium2026!"

$tsBefore = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "[INFO] Timestamp avant cycle : $tsBefore" -ForegroundColor Cyan

# === Etape 0 : login JWT ===
Write-Host "`n[STEP 0] POST $BaseUrl/api/auth/login" -ForegroundColor Yellow
$loginBody = @{ username = $User; password = $Password } | ConvertTo-Json
try {
    $loginResp = Invoke-WebRequest -Uri "$BaseUrl/api/auth/login" `
        -Method POST `
        -Headers @{ "Content-Type" = "application/json" } `
        -Body $loginBody `
        -UseBasicParsing -TimeoutSec 30
    $loginJson = $loginResp.Content | ConvertFrom-Json
    $token = $loginJson.access_token
    if (-not $token) {
        Write-Host "[ERR] Pas de access_token dans la reponse :" -ForegroundColor Red
        Write-Host $loginResp.Content -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Token recu (premiers chars) : $($token.Substring(0, [Math]::Min(40, $token.Length)))..." -ForegroundColor Green
}
catch {
    Write-Host "[ERR] Login echec : $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "[ERR] Body : $($sr.ReadToEnd())" -ForegroundColor Red
    }
    exit 1
}

$headers = @{
    "Content-Type"  = "application/json"
    "Authorization" = "Bearer $token"
}

# === Etape 1 : appel execute-cycle ===
$endpoint = "$BaseUrl/api/orders/execute-cycle"
Write-Host "`n[STEP 1] POST $endpoint (avec Bearer)" -ForegroundColor Yellow

try {
    $resp = Invoke-WebRequest -Uri $endpoint -Method POST -Headers $headers -Body "{}" -UseBasicParsing -TimeoutSec 300
    Write-Host "[OK] Status : $($resp.StatusCode)" -ForegroundColor Green
    Write-Host "[OK] Body   :" -ForegroundColor Green
    $resp.Content | ConvertFrom-Json | ConvertTo-Json -Depth 8
}
catch {
    Write-Host "[ERR] Echec execute-cycle :" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "[ERR] Body :" -ForegroundColor Red
        Write-Host $sr.ReadToEnd() -ForegroundColor Red
    }
    Write-Host "`n[FALLBACK] Tente /api/run-agents?force=true ..." -ForegroundColor Yellow
    try {
        $resp2 = Invoke-WebRequest -Uri "$BaseUrl/api/run-agents?force=true" -Method POST -Headers $headers -Body "{}" -UseBasicParsing -TimeoutSec 300
        Write-Host "[OK] Status (fallback) : $($resp2.StatusCode)" -ForegroundColor Green
        $resp2.Content | ConvertFrom-Json | ConvertTo-Json -Depth 8
    }
    catch {
        Write-Host "[ERR] Fallback echec : $($_.Exception.Message)" -ForegroundColor Red
        if ($_.Exception.Response) {
            $sr2 = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            Write-Host "[ERR] Body fallback : $($sr2.ReadToEnd())" -ForegroundColor Red
        }
        exit 1
    }
}

# === Etape 2 : nouveaux ordres ===
Write-Host "`n[STEP 2] Nouveaux ordres depuis $tsBefore" -ForegroundColor Yellow
$qOrders = @"
SELECT id, symbol, side, qty, conviction, status, created_at
FROM orders
WHERE created_at >= '$tsBefore'
ORDER BY created_at DESC
LIMIT 30;
"@
$qOrders | & sqlite3 -header -column $DbPath

# === Etape 3 : 15 dernieres entrees reconciler ===
Write-Host "`n[STEP 3] 15 dernieres entrees reconciler" -ForegroundColor Yellow
$qRec = @"
SELECT symbol, side, conviction, action, reason, created_at
FROM reconciler_log
ORDER BY created_at DESC
LIMIT 15;
"@
$qRec | & sqlite3 -header -column $DbPath

# === Etape 4 : snapshot des targets actifs ===
Write-Host "`n[STEP 4] Targets actifs (snapshot courant)" -ForegroundColor Yellow
$qTargets = @"
SELECT symbol, ROUND(target_weight_pct, 3) AS target_pct, ROUND(current_weight_pct, 3) AS current_pct,
       ROUND(target_weight_pct - current_weight_pct, 3) AS delta_pct
FROM portfolio_targets
WHERE snapshot_id = (SELECT snapshot_id FROM portfolio_targets ORDER BY created_at DESC LIMIT 1)
ORDER BY target_weight_pct DESC;
"@
$qTargets | & sqlite3 -header -column $DbPath

Write-Host "`n[DONE]" -ForegroundColor Green
