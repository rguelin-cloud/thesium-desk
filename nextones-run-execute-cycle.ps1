# nextones-run-execute-cycle.ps1
# Bypass du verrou [CYCLE_LOCK_V1] via endpoint /api/orders/execute-cycle (sans lock)
# Lance un cycle complet : agents + risk + execution + memo
# Affiche en fin : statut HTTP + nouveaux ordres + 15 dernieres entrees reconciler

$ErrorActionPreference = "Stop"
$BaseUrl = "http://127.0.0.1:8000"
$DbPath  = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

# Token Bearer optionnel (decommenter et remplir si auth requise)
# $env:BEARER_TOKEN = "xxx"

$headers = @{ "Content-Type" = "application/json" }
if ($env:BEARER_TOKEN) {
    $headers["Authorization"] = "Bearer $($env:BEARER_TOKEN)"
    Write-Host "[INFO] Auth Bearer activee" -ForegroundColor Cyan
}

$tsBefore = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "[INFO] Timestamp avant cycle : $tsBefore" -ForegroundColor Cyan

# === Etape 1 : appel endpoint sans verrou ===
$endpoint = "$BaseUrl/api/orders/execute-cycle"
Write-Host "`n[STEP 1] POST $endpoint" -ForegroundColor Yellow

try {
    $resp = Invoke-WebRequest -Uri $endpoint -Method POST -Headers $headers -Body "{}" -UseBasicParsing -TimeoutSec 180
    Write-Host "[OK] Status : $($resp.StatusCode)" -ForegroundColor Green
    Write-Host "[OK] Body   :" -ForegroundColor Green
    $resp.Content | ConvertFrom-Json | ConvertTo-Json -Depth 6
}
catch {
    Write-Host "[ERR] Echec appel execute-cycle :" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    if ($_.Exception.Response) {
        $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "[ERR] Body :" -ForegroundColor Red
        Write-Host $sr.ReadToEnd() -ForegroundColor Red
    }
    Write-Host "`n[FALLBACK] Tente /api/run-agents?force=true ..." -ForegroundColor Yellow
    try {
        $resp2 = Invoke-WebRequest -Uri "$BaseUrl/api/run-agents?force=true" -Method POST -Headers $headers -Body "{}" -UseBasicParsing -TimeoutSec 180
        Write-Host "[OK] Status (fallback) : $($resp2.StatusCode)" -ForegroundColor Green
        $resp2.Content | ConvertFrom-Json | ConvertTo-Json -Depth 6
    }
    catch {
        Write-Host "[ERR] Fallback echec : $($_.Exception.Message)" -ForegroundColor Red
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
