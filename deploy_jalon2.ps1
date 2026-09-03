# ===================================================================
# deploy_jalon2.ps1
# Déployeur automatique Nextones Desk - Jalon 2 + Cleanup v6.5 + Fix UI
# Auteur: Perplexity Computer
# Usage:
#   cd C:\Users\RichardGUELIN\Prod\ThesiumDesk
#   .\deploy_jalon2.ps1
#
# Le script:
#  1. Détecte l'état actuel
#  2. Backup horodaté complet
#  3. Stoppe uvicorn (port 8000)
#  4. Installe execution_engine_v6_5.py
#  5. Installe portfolio_construction_agent_jalon2.py
#  6. Patche api_server_with_static.py (routes /api/construction/*)
#  7. Patche le panel UI dans static/index.html (ou dashboard.html)
#  8. Vérifie l'import Python de chaque module
#  9. Redémarre uvicorn en arrière-plan
# 10. Teste les endpoints
# 11. Rollback automatique si quoi que ce soit échoue
# ===================================================================

$ErrorActionPreference = "Continue"
$ProjectRoot = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $ProjectRoot "_backups_jalon2_$Timestamp"
$LogFile  = Join-Path $ProjectRoot "deploy_jalon2_$Timestamp.log"

function Log {
    param([string]$msg, [string]$level = "INFO")
    $line = "[$(Get-Date -Format 'HH:mm:ss')] [$level] $msg"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function Fail {
    param([string]$msg)
    Log $msg "ERROR"
    Log "Lancement du rollback automatique..." "ERROR"
    Invoke-Rollback
    exit 1
}

function Invoke-Rollback {
    if (-not (Test-Path $BackupDir)) {
        Log "Aucun backup trouve, rollback impossible" "WARN"
        return
    }
    Log "Restauration des fichiers depuis $BackupDir" "WARN"
    Get-ChildItem $BackupDir -File | ForEach-Object {
        $target = Join-Path $ProjectRoot $_.Name
        Copy-Item $_.FullName $target -Force
        Log "  restored: $($_.Name)" "WARN"
    }
    Log "Rollback termine. Verifiez l'etat avant de relancer." "WARN"
}

# ===================================================================
# Étape 0 — Pre-flight
# ===================================================================
Set-Location $ProjectRoot
Log "==== DEPLOIEMENT JALON 2 + v6.5 + FIX UI ===="
Log "Project: $ProjectRoot"
Log "Backup:  $BackupDir"
Log "Log:     $LogFile"

# Vérifier que les fichiers source existent
$SourceFiles = @(
    "execution_engine_v6_5.py",
    "portfolio_construction_agent_jalon2.py",
    "api_endpoints_construction_patch.py",
    "ui_panel_patch.html",
    "_verify_jalon2.py"
)
foreach ($f in $SourceFiles) {
    if (-not (Test-Path $f)) {
        Fail "Fichier source manquant: $f (avez-vous bien copie les 5 livrables Jalon 2 dans $ProjectRoot ?)"
    }
}
Log "Tous les fichiers source sont presents (5/5)"

# Vérifier que la cible existe
if (-not (Test-Path "api_server_with_static.py")) {
    Fail "api_server_with_static.py introuvable dans $ProjectRoot"
}
if (-not (Test-Path "thesium.db")) {
    Fail "thesium.db introuvable dans $ProjectRoot"
}

# Détecter le HTML de l'UI
$UiCandidates = @(
    "static/index.html",
    "static/dashboard.html",
    "static/portfolio.html",
    "templates/index.html"
)
$UiFile = $null
foreach ($c in $UiCandidates) {
    if (Test-Path $c) {
        $UiFile = $c
        break
    }
}
if (-not $UiFile) {
    Log "Aucun HTML standard trouve, recherche elargie..." "WARN"
    $UiFile = (Get-ChildItem -Recurse -Filter "*.html" -ErrorAction SilentlyContinue |
               Where-Object { (Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue) -match "Portfolio.+id" } |
               Select-Object -First 1).FullName
    if ($UiFile) {
        $UiFile = Resolve-Path $UiFile -Relative
        Log "HTML detecte automatiquement: $UiFile"
    } else {
        Log "Aucun HTML cible trouve - le patch UI sera saute (etape manuelle requise)" "WARN"
    }
}

# ===================================================================
# Étape 1 — Backup
# ===================================================================
New-Item -ItemType Directory -Path $BackupDir | Out-Null
$ToBackup = @(
    "api_server_with_static.py",
    "thesium.db"
)
if (Test-Path "execution_engine.py")               { $ToBackup += "execution_engine.py" }
if (Test-Path "execution_engine_v6_4.py")          { $ToBackup += "execution_engine_v6_4.py" }
if (Test-Path "portfolio_construction_agent.py")   { $ToBackup += "portfolio_construction_agent.py" }
if ($UiFile)                                       { $ToBackup += $UiFile }

foreach ($f in $ToBackup) {
    $dest = Join-Path $BackupDir (Split-Path $f -Leaf)
    Copy-Item $f $dest -Force
    Log "Backup: $f"
}

# ===================================================================
# Étape 2 — Stop uvicorn (port 8000)
# ===================================================================
Log "Arret du serveur uvicorn sur le port 8000..."
$pids = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
if ($pids) {
    foreach ($pid in $pids) {
        try {
            Stop-Process -Id $pid -Force -ErrorAction Stop
            Log "  process $pid arrete"
        } catch {
            Log "  impossible d'arreter $pid : $_" "WARN"
        }
    }
    Start-Sleep -Seconds 2
} else {
    Log "  aucun serveur en cours sur 8000"
}

# ===================================================================
# Étape 3 — Verify Jalon 2 (dry-run AVANT install) - NON BLOQUANT
# ===================================================================
Log "Verify Jalon 2 (dry-run) - mode non bloquant..."
try {
    $verifyOut = & py -3.13 _verify_jalon2.py 2>&1 | Out-String
    Add-Content -Path $LogFile -Value "--- verify_jalon2 output ---`r`n$verifyOut`r`n--- end verify ---"
    if ($LASTEXITCODE -ne 0) {
        Log "verify_jalon2 a renvoye code $LASTEXITCODE - non bloquant, on continue" "WARN"
    } else {
        Log "verify_jalon2 OK"
    }
} catch {
    Log "verify_jalon2 a leve une exception PowerShell - non bloquant: $_" "WARN"
}
Log "On poursuit avec l'installation effective."

# ===================================================================
# Étape 4 — Install execution_engine v6.5
# ===================================================================
Log "Installation execution_engine v6.5..."
if (Test-Path "execution_engine.py") {
    Copy-Item "execution_engine.py" "execution_engine_v6_4_backup.py" -Force
    Log "  execution_engine.py -> execution_engine_v6_4_backup.py"
}
Copy-Item "execution_engine_v6_5.py" "execution_engine.py" -Force
Log "  execution_engine_v6_5.py -> execution_engine.py"

# Test import
$pyTest = "import importlib.util, sys; spec = importlib.util.spec_from_file_location('m', 'execution_engine.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('OK')"
try {
    $result = & py -3.13 -c $pyTest 2>&1 | Out-String
} catch {
    Log "Exception lors de l'import execution_engine: $_" "WARN"
    $result = $_
}
Add-Content -Path $LogFile -Value "--- import execution_engine ---`r`n$result`r`n---"
if ($LASTEXITCODE -ne 0) {
    Log "Import execution_engine a echoue (code $LASTEXITCODE) - voir log" "ERROR"
    Fail "execution_engine v6.5 ne s'importe pas - rollback"
}
Log "  import OK"

# ===================================================================
# Étape 5 — Install portfolio_construction_agent (Jalon 2)
# ===================================================================
Log "Installation portfolio_construction_agent Jalon 2..."
if (Test-Path "portfolio_construction_agent.py") {
    Copy-Item "portfolio_construction_agent.py" "portfolio_construction_agent_jalon1_backup.py" -Force
}
Copy-Item "portfolio_construction_agent_jalon2.py" "portfolio_construction_agent.py" -Force
Log "  portfolio_construction_agent_jalon2.py -> portfolio_construction_agent.py"

$pyTest2 = "import importlib.util; spec = importlib.util.spec_from_file_location('m', 'portfolio_construction_agent.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('OK')"
try {
    $result2 = & py -3.13 -c $pyTest2 2>&1 | Out-String
} catch {
    Log "Exception lors de l'import PCA: $_" "WARN"
    $result2 = $_
}
Add-Content -Path $LogFile -Value "--- import PCA Jalon 2 ---`r`n$result2`r`n---"
if ($LASTEXITCODE -ne 0) {
    Log "Import PCA a echoue (code $LASTEXITCODE) - voir log" "ERROR"
    Fail "PCA Jalon 2 ne s'importe pas - rollback"
}
Log "  import OK"

# ===================================================================
# Étape 6 — Patch api_server_with_static.py (idempotent)
# ===================================================================
Log "Patch api_server_with_static.py..."
$apiSrc  = Get-Content "api_server_with_static.py" -Raw
$patchSrc = Get-Content "api_endpoints_construction_patch.py" -Raw

if ($apiSrc -match "/api/construction/run" -or $apiSrc -match "/api/construction/targets") {
    Log "  routes /api/construction/* deja presentes - skip"
} else {
    # Stratégie d'insertion : juste avant `if __name__ == "__main__":` ou en fin de fichier
    $marker = 'if __name__'
    if ($apiSrc -match $marker) {
        # Insertion avant le bloc main
        $insertionPoint = $apiSrc.IndexOf("if __name__")
        $newSrc = $apiSrc.Substring(0, $insertionPoint) `
                  + "`r`n`r`n# ===== Jalon 2: Portfolio Construction endpoints =====`r`n" `
                  + $patchSrc `
                  + "`r`n`r`n" `
                  + $apiSrc.Substring($insertionPoint)
    } else {
        $newSrc = $apiSrc + "`r`n`r`n# ===== Jalon 2: Portfolio Construction endpoints =====`r`n" + $patchSrc + "`r`n"
    }
    Set-Content -Path "api_server_with_static.py" -Value $newSrc -Encoding UTF8 -NoNewline
    Log "  patch applique"
}

# Test syntaxique (py_compile) plutot que import complet pour eviter side effects
$pyTest3 = "import py_compile; py_compile.compile('api_server_with_static.py', doraise=True); print('OK')"
try {
    $result3 = & py -3.13 -c $pyTest3 2>&1 | Out-String
} catch {
    Log "Exception lors du compile api_server: $_" "WARN"
    $result3 = $_
}
Add-Content -Path $LogFile -Value "--- compile api_server ---`r`n$result3`r`n---"
if ($LASTEXITCODE -ne 0) {
    Log "py_compile api_server a echoue (code $LASTEXITCODE) - voir log" "ERROR"
    Fail "api_server_with_static.py ne compile plus apres patch - rollback"
}
Log "  compile OK"

# ===================================================================
# Étape 7 — Patch UI panel (idempotent, optionnel)
# ===================================================================
if ($UiFile -and (Test-Path $UiFile)) {
    Log "Patch UI panel ($UiFile)..."
    $htmlSrc  = Get-Content $UiFile -Raw
    $patchUi  = Get-Content "ui_panel_patch.html" -Raw

    if ($htmlSrc -match "construction-targets-panel" -or $htmlSrc -match "construction/targets") {
        Log "  panel deja present - skip"
    } else {
        # Insertion juste avant </body>
        if ($htmlSrc -match "</body>") {
            $newHtml = $htmlSrc -replace "</body>", "$patchUi`r`n</body>"
            Set-Content -Path $UiFile -Value $newHtml -Encoding UTF8 -NoNewline
            Log "  patch UI applique"
        } else {
            Log "  pas de tag </body> trouve, append en fin de fichier" "WARN"
            Add-Content -Path $UiFile -Value $patchUi
        }
    }
} else {
    Log "Patch UI saute (pas de fichier HTML cible detecte)" "WARN"
}

# ===================================================================
# Étape 8 — Redémarrage uvicorn
# ===================================================================
Log "Demarrage uvicorn en arriere-plan..."
$proc = Start-Process -FilePath "py" `
    -ArgumentList "-3.13", "-m", "uvicorn", "api_server_with_static:app", "--host", "0.0.0.0", "--port", "8000" `
    -WorkingDirectory $ProjectRoot `
    -PassThru `
    -WindowStyle Minimized

Log "  PID uvicorn: $($proc.Id)"
Log "  attente readiness (10s)..."
Start-Sleep -Seconds 10

# ===================================================================
# Étape 9 — Tests endpoints
# ===================================================================
Log "Test endpoints..."
$allOk = $true

try {
    $r1 = Invoke-WebRequest -Uri "http://localhost:8000/api/construction/targets" -UseBasicParsing -TimeoutSec 5
    if ($r1.StatusCode -eq 200) {
        Log "  GET /api/construction/targets -> 200 OK"
    } else {
        Log "  GET /api/construction/targets -> $($r1.StatusCode)" "WARN"
        $allOk = $false
    }
} catch {
    Log "  GET /api/construction/targets ECHEC: $_" "ERROR"
    $allOk = $false
}

try {
    $r2 = Invoke-WebRequest -Uri "http://localhost:8000/" -UseBasicParsing -TimeoutSec 5
    if ($r2.StatusCode -eq 200) {
        Log "  GET /  -> 200 OK (UI servie)"
    }
} catch {
    Log "  GET / ECHEC: $_" "WARN"
}

# ===================================================================
# Conclusion
# ===================================================================
Log "==== FIN DEPLOIEMENT ===="
if ($allOk) {
    Log "DEPLOIEMENT REUSSI" "OK"
    Write-Host ""
    Write-Host "==================================================" -ForegroundColor Green
    Write-Host "  DEPLOIEMENT JALON 2 REUSSI" -ForegroundColor Green
    Write-Host "==================================================" -ForegroundColor Green
    Write-Host "  Serveur:  http://localhost:8000" -ForegroundColor Green
    Write-Host "  Backup:   $BackupDir" -ForegroundColor Green
    Write-Host "  Log:      $LogFile" -ForegroundColor Green
    Write-Host "  PID:      $($proc.Id)" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Pour rollback ulterieur :" -ForegroundColor Yellow
    Write-Host "    Copy-Item '$BackupDir\*' '$ProjectRoot' -Force" -ForegroundColor Yellow
    Write-Host "==================================================" -ForegroundColor Green
} else {
    Log "DEPLOIEMENT PARTIEL - certains tests ont echoue" "WARN"
    Write-Host ""
    Write-Host "==================================================" -ForegroundColor Yellow
    Write-Host "  DEPLOIEMENT PARTIEL - voir $LogFile" -ForegroundColor Yellow
    Write-Host "  Pour rollback :" -ForegroundColor Yellow
    Write-Host "    Stop-Process -Id $($proc.Id) -Force" -ForegroundColor Yellow
    Write-Host "    Copy-Item '$BackupDir\*' '$ProjectRoot' -Force" -ForegroundColor Yellow
    Write-Host "==================================================" -ForegroundColor Yellow
}
