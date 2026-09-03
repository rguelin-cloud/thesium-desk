# ============================================================================
# Fix INSERT INTO theses — execution_engine.py & execution_engine_v6_5.py
# Renomme: agent->agent_type, conviction->conviction_score,
#          signal->proposed_action, rationale->thesis_text
# Crée backup + patche + recompile + diagnostic
# ============================================================================
$ErrorActionPreference = "Continue"
$ProjectPath = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
Set-Location $ProjectPath

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = ".\_backups_thesesfix_$timestamp"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Write-Host "[fix_theses] Backup dir: $backupDir" -ForegroundColor Cyan

$targets = @("execution_engine.py", "execution_engine_v6_5.py")

foreach ($file in $targets) {
    if (-not (Test-Path $file)) {
        Write-Host "[fix_theses] SKIP $file (not found)" -ForegroundColor Yellow
        continue
    }
    Copy-Item $file "$backupDir\$file" -Force
    Write-Host "[fix_theses] Backed up $file" -ForegroundColor Gray

    $content = Get-Content $file -Raw

    # Patch 1 : la ligne INSERT INTO theses
    # On vise le tuple "(instrument_id, agent, conviction, signal, rationale, created_at)"
    $oldInsert = '(instrument_id, agent, conviction, signal, rationale, created_at)'
    $newInsert = '(instrument_id, agent_type, conviction_score, proposed_action, thesis_text, created_at)'

    if ($content.Contains($oldInsert)) {
        $content = $content.Replace($oldInsert, $newInsert)
        Write-Host "[fix_theses] $file : INSERT colonnes renommees" -ForegroundColor Green
    } else {
        Write-Host "[fix_theses] $file : tuple INSERT non trouve (deja patche ?)" -ForegroundColor Yellow
    }

    Set-Content -Path $file -Value $content -Encoding UTF8 -NoNewline
}

# Vérifier la compilation
Write-Host ""
Write-Host "[fix_theses] Compilation check..." -ForegroundColor Cyan
foreach ($file in $targets) {
    if (Test-Path $file) {
        py -3.13 -m py_compile $file 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[fix_theses] $file : OK" -ForegroundColor Green
        } else {
            Write-Host "[fix_theses] $file : COMPILATION ERROR" -ForegroundColor Red
        }
    }
}

# Vérifier qu'il ne reste plus d'INSERT cassé
Write-Host ""
Write-Host "[fix_theses] Verification finale : reste-t-il des INSERT casses ?" -ForegroundColor Cyan
$remaining = Get-ChildItem -Path . -Filter *.py |
    Where-Object { $_.Name -notmatch '_backup|_v6_4|_jalon1' } |
    Select-String -Pattern 'INSERT.*\binstrument_id,\s*agent,\s*conviction\b'

if ($remaining) {
    Write-Host "[fix_theses] ATTENTION : INSERT casses restants :" -ForegroundColor Red
    $remaining | Format-Table Path, LineNumber, Line -AutoSize
} else {
    Write-Host "[fix_theses] Aucun INSERT casse restant. OK." -ForegroundColor Green
}

# Tuer l'ancien serveur sur port 8000 si actif
Write-Host ""
Write-Host "[fix_theses] Arret serveur sur port 8000..." -ForegroundColor Cyan
$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    $pid8000 = $conn.OwningProcess | Select-Object -First 1
    Stop-Process -Id $pid8000 -Force -ErrorAction SilentlyContinue
    Write-Host "[fix_theses] Process PID $pid8000 stoppe" -ForegroundColor Green
    Start-Sleep -Seconds 2
} else {
    Write-Host "[fix_theses] Aucun serveur actif sur 8000" -ForegroundColor Gray
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " PATCH APPLIQUE. Pour relancer le serveur :" -ForegroundColor Cyan
Write-Host "" -ForegroundColor Cyan
Write-Host "   py -3.13 -m uvicorn api_server_with_static:app --host 127.0.0.1 --port 8000" -ForegroundColor White
Write-Host "" -ForegroundColor Cyan
Write-Host " Puis depuis l'UI, clique Run Decision Cycle." -ForegroundColor Cyan
Write-Host " Le 500 doit disparaitre, les orders doivent etre crees." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
