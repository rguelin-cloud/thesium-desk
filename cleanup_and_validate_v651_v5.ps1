# =====================================================================
# cleanup_and_validate_v651_v5.ps1
# Nextones Desk - Cleanup doublons + Validation ordres frais
# Correction v5 : login JSON avec champ "username" (pas "email")
# =====================================================================

$ErrorActionPreference = "Stop"

$Base = "http://127.0.0.1:8000"

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  CLEANUP + VALIDATE v6.5.1  (v5 - JSON username)" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------
# 0. API UP ?
# ---------------------------------------------------------------------
Write-Host "[0/5] Verification API server sur $Base..." -ForegroundColor Yellow
try {
    $ping = Invoke-WebRequest -Uri "$Base/" -Method Get -TimeoutSec 3 -UseBasicParsing
    Write-Host "  API UP (status $($ping.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "  API DOWN sur $Base" -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------
# 1. Snapshot AVANT
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[1/5] Snapshot des ordres pending_validation AVANT..." -ForegroundColor Yellow

$snapshotBefore = @'
import sqlite3
con = sqlite3.connect(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
con.row_factory = sqlite3.Row
cur = con.cursor()
cur.execute("""
    SELECT o.id, i.ticker, o.side, o.quantity, o.status,
           datetime(o.created_at,'localtime') AS created
      FROM orders o
      JOIN instruments i ON i.id = o.instrument_id
     WHERE o.status='pending_validation'
     ORDER BY o.id
""")
rows = cur.fetchall()
print(f"[snapshot_before] {len(rows)} ordres en pending_validation")
for r in rows:
    print(f"  #{r['id']:>4}  {r['ticker']:<6}  {r['side']:<4}  qty={r['quantity']:<8}  created={r['created']}")
con.close()
'@

$tmpPy = "$env:TEMP\_snapshot_pending_v5.py"
$snapshotBefore | Set-Content -Path $tmpPy -Encoding UTF8
py $tmpPy

Write-Host ""
$ok = Read-Host "Confirmer le rejet de #165 et #166 + validation de #167, #168, #169 ? (o/N)"
if ($ok -ne "o" -and $ok -ne "O") {
    Write-Host "Annule." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------
# 2. Login - tente plusieurs combinaisons (champ + endpoint)
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[2/5] Login (essais multiples)..." -ForegroundColor Yellow

$token     = $null
$tokenType = "Bearer"

$attempts = @(
    @{ Label = "JSON username (login)";    Endpoint = "/api/auth/login";    Body = @{ username="rguelin@nextones.fr"; password="Thesium2026!" } | ConvertTo-Json; CT = "application/json" }
    @{ Label = "JSON email (login)";       Endpoint = "/api/auth/login";    Body = @{ email   ="rguelin@nextones.fr"; password="Thesium2026!" } | ConvertTo-Json; CT = "application/json" }
    @{ Label = "JSON username (token)";    Endpoint = "/api/auth/token";    Body = @{ username="rguelin@nextones.fr"; password="Thesium2026!" } | ConvertTo-Json; CT = "application/json" }
    @{ Label = "Form OAuth2 (token)";      Endpoint = "/api/auth/token";    Body = "username=rguelin%40nextones.fr&password=Thesium2026!";                       CT = "application/x-www-form-urlencoded" }
)

foreach ($att in $attempts) {
    try {
        Write-Host "  -> $($att.Label) sur $($att.Endpoint)..." -ForegroundColor Gray
        $resp = Invoke-RestMethod -Uri "$Base$($att.Endpoint)" `
                                  -Method Post `
                                  -ContentType $att.CT `
                                  -Body $att.Body `
                                  -ErrorAction Stop
        if ($resp.access_token) { $token = $resp.access_token; $tokenType = $resp.token_type }
        elseif ($resp.token)    { $token = $resp.token }
        if ($token) {
            Write-Host "  LOGIN OK avec : $($att.Label)" -ForegroundColor Green
            break
        }
    } catch {
        Write-Host "     KO : $($_.ErrorDetails.Message)" -ForegroundColor DarkGray
    }
}

if (-not $token) {
    Write-Host "  Aucun login n'a marche - inspecter les endpoints disponibles :" -ForegroundColor Red
    Write-Host "      Invoke-RestMethod $Base/openapi.json | ConvertTo-Json -Depth 4 | Select-String 'auth'" -ForegroundColor Yellow
    exit 1
}

$headers = @{ "Authorization" = "$tokenType $token" }
if ($tokenType -ne "Bearer" -and $tokenType -ne "bearer") {
    $headers = @{ "Authorization" = "Bearer $token" }
}

# ---------------------------------------------------------------------
# 3. Rejet doublons
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[3/5] Rejet doublons stale (cycle 17:57)..." -ForegroundColor Yellow

$rejectIds = @(165, 166)
foreach ($id in $rejectIds) {
    try {
        $body = @{ reason = "Stale duplicate from cycle 17:57 - superseded by fresh cycle 20:59 (post-v6.5.1)" } | ConvertTo-Json
        Invoke-RestMethod -Uri "$Base/api/orders/$id/reject" `
                          -Method Post -Headers $headers `
                          -ContentType "application/json" -Body $body | Out-Null
        Write-Host "  Reject #$id  OK" -ForegroundColor Green
    } catch {
        Write-Host "  Reject #$id  KO : $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

# ---------------------------------------------------------------------
# 4. Validation ordres frais
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[4/5] Validation ordres frais (cycle 20:59, post-CAP)..." -ForegroundColor Yellow

$validateIds = @(167, 168, 169)
foreach ($id in $validateIds) {
    try {
        Invoke-RestMethod -Uri "$Base/api/orders/$id/validate" `
                          -Method Post -Headers $headers `
                          -ContentType "application/json" -Body "{}" | Out-Null
        Write-Host "  Validate #$id  OK" -ForegroundColor Green
    } catch {
        Write-Host "  Validate #$id  KO : $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

# ---------------------------------------------------------------------
# 5. Snapshot APRES
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[5/5] Snapshot APRES..." -ForegroundColor Yellow

$snapshotAfter = @'
import sqlite3
con = sqlite3.connect(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
con.row_factory = sqlite3.Row
cur = con.cursor()

cur.execute("""
    SELECT o.id, i.ticker, o.side, o.quantity
      FROM orders o
      JOIN instruments i ON i.id = o.instrument_id
     WHERE o.status='pending_validation'
     ORDER BY o.id
""")
pending = cur.fetchall()
print(f"[snapshot_after] {len(pending)} en pending_validation restants")
for r in pending:
    print(f"  #{r['id']:>4}  {r['ticker']:<6}  {r['side']:<4}  qty={r['quantity']}")

cur.execute("""
    SELECT o.id, i.ticker, o.side, o.quantity, o.status,
           datetime(o.validated_at,'localtime') AS validated,
           o.rejection_reason
      FROM orders o
      JOIN instruments i ON i.id = o.instrument_id
     WHERE o.id IN (165,166,167,168,169)
     ORDER BY o.id
""")
print()
print("[final_state] ordres concernes :")
for r in cur.fetchall():
    reason = (r['rejection_reason'] or "")[:50]
    print(f"  #{r['id']:>4}  {r['ticker']:<6}  {r['side']:<4}  qty={r['quantity']:<8}  "
          f"status={r['status']:<22}  validated={r['validated'] or '-':<20}  {reason}")

cur.execute("""
    SELECT i.ticker, pp.quantity, pp.weight_pct, pt.target_weight_pct AS tgt
      FROM portfolio_positions pp
      JOIN instruments i ON i.id = pp.instrument_id
 LEFT JOIN portfolio_targets pt ON pt.ticker = i.ticker AND pt.active=1
     WHERE i.ticker IN ('META','LINK','ETH')
     ORDER BY i.ticker
""")
print()
print("[positions cles] post-fills :")
for r in cur.fetchall():
    tgt = r['tgt'] or 0
    print(f"  {r['ticker']:<6} qty={r['quantity']:<10}  weight={r['weight_pct']:>6.2f}%  target={tgt:>6.2f}%")

con.close()
'@

$tmpPy2 = "$env:TEMP\_snapshot_after_v5.py"
$snapshotAfter | Set-Content -Path $tmpPy2 -Encoding UTF8
py $tmpPy2

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  TERMINE" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
