# =====================================================================
# run_cycle_and_check_btc.ps1
# Jalon 3 - Lance un cycle complet + verifie ordre BTC + logs [score_R]
# =====================================================================

$ErrorActionPreference = "Continue"
$Root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
Set-Location $Root

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  JALON 3 - Run Cycle + Check BTC + Logs R" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

# =====================================================================
# 1. Etat AVANT cycle
# =====================================================================
Write-Host "[1/4] Etat AVANT cycle..." -ForegroundColor Yellow
$pyAvant = @'
import sqlite3
from pathlib import Path
DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

cur.execute("SELECT COUNT(*) AS n FROM orders WHERE status='pending_validation'")
print(f"  Ordres pending_validation : {cur.fetchone()['n']}")

cur.execute("SELECT COUNT(*) AS n, MAX(created_at) AS last FROM run_cycle_log")
r = cur.fetchone()
print(f"  Derniers cycles (run_cycle_log) : {r['n']} total, dernier = {r['last']}")

con.close()
'@
$tmp = "$env:TEMP\_avant.py"
$pyAvant | Set-Content -Path $tmp -Encoding UTF8
py $tmp

# =====================================================================
# 2. Appel execute-cycle
# =====================================================================
Write-Host ""
Write-Host "[2/4] Appel POST /api/execute-cycle..." -ForegroundColor Yellow
Write-Host ""

try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/execute-cycle" -Method POST -ContentType "application/json" -TimeoutSec 180
    Write-Host "  REPONSE API :" -ForegroundColor Green
    $resp | ConvertTo-Json -Depth 5 | Write-Host
} catch {
    Write-Host "  ERREUR appel API : $_" -ForegroundColor Red
    Write-Host "  Status code : $($_.Exception.Response.StatusCode)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        Write-Host "  Details : $($_.ErrorDetails.Message)" -ForegroundColor Red
    }
}

# =====================================================================
# 3. Etat APRES cycle - focus BTC + score_R dans theses
# =====================================================================
Write-Host ""
Write-Host "[3/4] Etat APRES cycle..." -ForegroundColor Yellow
$pyApres = @'
import sqlite3
from pathlib import Path
DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print()
print("Ordres pending_validation crees aujourd'hui :")
cur.execute("""
    SELECT o.id, i.ticker, o.side, o.quantity, o.order_type, o.status, o.created_at
    FROM orders o
    JOIN instruments i ON i.id = o.instrument_id
    WHERE o.status='pending_validation'
      AND DATE(o.created_at)=DATE('now')
    ORDER BY o.created_at DESC
""")
rows = cur.fetchall()
if not rows:
    print("  (aucun)")
else:
    print(f"  {'ID':<6} {'Ticker':<8} {'Side':<6} {'Qty':>10} {'Type':<8} {'Created':<20}")
    print("  " + "-" * 65)
    for r in rows:
        print(f"  {r['id']:<6} {r['ticker']:<8} {r['side']:<6} {r['quantity']:>10.4f} {r['order_type']:<8} {r['created_at']}")

print()
print("BTC en particulier :")
cur.execute("""
    SELECT o.id, o.side, o.quantity, o.status, o.created_at
    FROM orders o
    JOIN instruments i ON i.id = o.instrument_id
    WHERE i.ticker = 'BTC'
    ORDER BY o.created_at DESC LIMIT 5
""")
btc = cur.fetchall()
if not btc:
    print("  AUCUN ordre BTC jamais")
else:
    for r in btc:
        print(f"  #{r['id']}  {r['side']}  qty={r['quantity']:.6f}  {r['status']}  {r['created_at']}")

print()
print("Derniers cycles (run_cycle_log) :")
cur.execute("SELECT cycle_id, status, started_at, finished_at FROM run_cycle_log ORDER BY started_at DESC LIMIT 5")
for r in cur.fetchall():
    print(f"  {r['cycle_id']}  status={r['status']}  start={r['started_at']}  end={r['finished_at']}")

print()
print("Derniere reconciliation BTC :")
cur.execute("""
    SELECT cycle_id, ticker, action_type, decision, details, created_at
    FROM cycle_reconciliation_log
    WHERE ticker='BTC'
    ORDER BY created_at DESC LIMIT 5
""")
btc_rec = cur.fetchall()
if not btc_rec:
    print("  BTC jamais vu par le Reconciler")
else:
    for r in btc_rec:
        print(f"  {r['cycle_id']}  {r['action_type']}  decision={r['decision']}")
        if r['details']:
            print(f"     details={r['details'][:200]}")

print()
print("Theses BTC du dernier cycle :")
cur.execute("""
    SELECT t.id, t.agent_type, t.cycle_id, t.status, t.action, t.conviction, t.created_at
    FROM theses t
    JOIN instruments i ON i.id = t.instrument_id
    WHERE i.ticker='BTC'
    ORDER BY t.created_at DESC LIMIT 5
""")
for r in cur.fetchall():
    print(f"  #{r['id']}  agent={r['agent_type']:<22}  cycle={r['cycle_id']}  conv={r['conviction']}  status={r['status']}")
    print(f"     action={r['action'][:120] if r['action'] else 'NULL'}")

con.close()
'@
$tmp2 = "$env:TEMP\_apres.py"
$pyApres | Set-Content -Path $tmp2 -Encoding UTF8
py $tmp2

# =====================================================================
# 4. Resume
# =====================================================================
Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  TERMINE" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Pour voir les logs [score_R] :" -ForegroundColor Yellow
Write-Host "  -> regarde la fenetre uvicorn (output console)" -ForegroundColor Yellow
Write-Host "  -> ou copie/colle les 50 dernieres lignes ici" -ForegroundColor Yellow
