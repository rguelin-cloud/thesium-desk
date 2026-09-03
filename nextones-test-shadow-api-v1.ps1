# Test endpoints Shadow API Phase 9.6
# Login -> GET /api/shadow/variants -> GET /api/shadow/perf-rolling?window=30

$ErrorActionPreference = "Stop"

Write-Host "=============================================================================="
Write-Host "TEST SHADOW API ENDPOINTS"
Write-Host "=============================================================================="

# 1. Login
Write-Host ""
Write-Host "[1] Login..."
$loginBody = @{username="rguelin"; password="Thesium2026!"} | ConvertTo-Json
$loginResp = Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" `
    -Method Post -Body $loginBody -ContentType "application/json"
$tok = $loginResp.access_token
if (-not $tok) {
    Write-Host "[ERR] No token retrieved" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Token recu (longueur=$($tok.Length))"

# 2. GET /api/shadow/variants
Write-Host ""
Write-Host "[2] GET /api/shadow/variants"
$variants = Invoke-RestMethod -Uri "http://localhost:8000/api/shadow/variants" `
    -Headers @{Authorization="Bearer $tok"}
Write-Host "success : $($variants.success)"
Write-Host "n variants : $($variants.variants.Count)"
foreach ($v in $variants.variants) {
    Write-Host "  v$($v.variant_id) name=$($v.name) settings_keys=$($v.settings.PSObject.Properties.Name -join ',')"
}

# 3. GET /api/shadow/perf-rolling?window=30
Write-Host ""
Write-Host "[3] GET /api/shadow/perf-rolling?window=30"
$perf = Invoke-RestMethod -Uri "http://localhost:8000/api/shadow/perf-rolling?window=30" `
    -Headers @{Authorization="Bearer $tok"}
Write-Host "success     : $($perf.success)"
Write-Host "window_days : $($perf.window_days)"
Write-Host "as_of_day   : $($perf.as_of_day)"
Write-Host "n rows      : $($perf.rows.Count)"
Write-Host ""
foreach ($r in $perf.rows) {
    $ret  = if ($r.return_variant_pct -ne $null) { "{0:N3}%" -f $r.return_variant_pct } else { "N/A" }
    $dlt  = if ($r.delta_pct -ne $null) { "{0:N3}%" -f $r.delta_pct } else { "N/A" }
    $shr  = if ($r.sharpe_variant -ne $null) { "{0:N2}" -f $r.sharpe_variant } else { "N/A" }
    $dd   = if ($r.max_dd_variant_pct -ne $null) { "{0:N3}%" -f $r.max_dd_variant_pct } else { "N/A" }
    Write-Host ("  v{0} ({1,-18}) ret={2,9} delta={3,9} sharpe={4,6} dd={5,9} n_ord={6,4} reco={7}" -f `
        $r.variant_id, $r.variant_name, $ret, $dlt, $shr, $dd, $r.n_orders_variant, $r.recommendation)
}

Write-Host ""
Write-Host "=============================================================================="
Write-Host "TEST DONE"
Write-Host "=============================================================================="
