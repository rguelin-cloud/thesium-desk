# Relance PortfolioConstructionAgent via l'endpoint REST
# Apres execution, les portfolio_targets seront recalcules avec les nouveaux caps + smoothing.

Write-Host "[1/3] Appel /api/construction/run ..." -ForegroundColor Cyan
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/construction/run" `
        -Method POST `
        -ContentType "application/json" `
        -TimeoutSec 60
    Write-Host "[OK] Reponse :" -ForegroundColor Green
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Host "[ERR] $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Endpoint introuvable ou erreur serveur." -ForegroundColor Yellow
    Write-Host "Verifie que uvicorn tourne sur le port 8000." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "[2/3] Verification : nouveaux targets en base" -ForegroundColor Cyan
py -3.13 -c @"
import sqlite3
con = sqlite3.connect(r'C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db')
con.row_factory = sqlite3.Row
cur = con.cursor()
rows = cur.execute('SELECT ticker, target_weight_pct, snapshot_id, updated_at FROM portfolio_targets WHERE active=1 ORDER BY target_weight_pct DESC').fetchall()
total = 0
for r in rows:
    print(f'  {r[\"ticker\"]:<6} target={r[\"target_weight_pct\"]:>6.2f}%  snap={r[\"snapshot_id\"]}  updated={r[\"updated_at\"]}')
    total += r['target_weight_pct'] or 0
print(f'\n  Sum target : {total:.2f}%')
con.close()
"@

Write-Host ""
Write-Host "[3/3] Lance ensuite 'Run Decision Cycle' dans l'UI pour generer des ordres" -ForegroundColor Cyan
