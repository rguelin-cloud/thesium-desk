# nextones-run-construction-auth.ps1
# Login JWT -> POST /api/construction/run -> inspect snapshot via script Python separe
# Pas de heredoc, pas d'accents. ASCII pur.

$ErrorActionPreference = "Stop"

$BASE = "http://127.0.0.1:8000"
$USER = "rguelin"
$PASS = "Thesium2026!"

Write-Host "==> Login JWT" -ForegroundColor Cyan
$loginBody = @{ username = $USER; password = $PASS } | ConvertTo-Json -Compress
try {
    $loginResp = Invoke-RestMethod -Uri "$BASE/api/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
} catch {
    Write-Host "LOGIN FAIL: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host $reader.ReadToEnd() -ForegroundColor Red
    }
    exit 1
}

$token = $loginResp.access_token
if (-not $token) {
    Write-Host "Token absent dans la reponse" -ForegroundColor Red
    $loginResp | ConvertTo-Json -Depth 5
    exit 1
}
Write-Host "OK token (len=$($token.Length))" -ForegroundColor Green

$headers = @{ Authorization = "Bearer $token" }

# Liste d'endpoints candidats a tester dans l'ordre
$endpoints = @(
    "/api/construction/run",
    "/api/portfolio/construction/run",
    "/api/targets/rebuild",
    "/api/portfolio-targets/rebuild",
    "/api/run-construction",
    "/api/construction/build"
)

$ok = $false
$lastErr = $null

foreach ($ep in $endpoints) {
    Write-Host ""
    Write-Host "==> Test POST $ep" -ForegroundColor Cyan
    try {
        $resp = Invoke-RestMethod -Uri "$BASE$ep" -Method Post -Headers $headers -ContentType "application/json" -Body "{}"
        Write-Host "SUCCESS sur $ep" -ForegroundColor Green
        $resp | ConvertTo-Json -Depth 8
        $ok = $true
        break
    } catch {
        $code = $null
        if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
        Write-Host "FAIL $ep -> HTTP $code" -ForegroundColor Yellow
        $lastErr = $_.Exception.Message
        if ($_.Exception.Response) {
            try {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $body = $reader.ReadToEnd()
                if ($body.Length -lt 500) { Write-Host $body -ForegroundColor DarkYellow }
            } catch {}
        }
    }
}

if (-not $ok) {
    Write-Host ""
    Write-Host "Aucun endpoint construction n'a repondu 200." -ForegroundColor Red
    Write-Host "Dernier message: $lastErr" -ForegroundColor Red
    Write-Host "On va quand meme inspecter le dernier snapshot (peut etre deja a jour)..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==> Inspection du dernier snapshot portfolio_targets" -ForegroundColor Cyan
py -3.13 .\nextones-show-construction-snapshot-now.py

Write-Host ""
Write-Host "==> Fin du script" -ForegroundColor Green
