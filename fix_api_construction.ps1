# ===================================================================
# fix_api_construction.ps1
# Corrige les endpoints /api/construction/* qui crashent en 500
# (get_db() n'existe pas dans api_server_with_static.py)
#
# Strategie : remplacer "conn = get_db()" par une connexion sqlite3
# directe avec row_factory pour conserver l'acces .keys() / dict-like.
# ===================================================================

$ErrorActionPreference = "Continue"
Set-Location "C:\Users\RichardGUELIN\Prod\ThesiumDesk"

$File = "api_server_with_static.py"
$Backup = "api_server_with_static.py.bak_pre_fix_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

Write-Host "Backup : $Backup"
Copy-Item $File $Backup -Force

$src = Get-Content $File -Raw

# Detection rapide de la facon dont la DB est accedee ailleurs dans le fichier
Write-Host "`nAnalyse des appels DB existants..."
$dbCalls = Select-String -Path $File -Pattern "sqlite3\.connect|thesium\.db|DATABASE" -AllMatches |
           Select-Object LineNumber, Line | Select-Object -First 5
$dbCalls | Format-Table -AutoSize

# Si DB_PATH n'est pas defini, on l'ajoute en debut de fichier
if ($src -notmatch '^\s*DB_PATH\s*=') {
    Write-Host "DB_PATH absent - ajout en haut du fichier"
    # Trouver la fin des imports : la 1re ligne vide apres "from ... import"
    $injectAfter = '^(import |from )'
    $lines = $src -split "`r?`n"
    $lastImportIdx = -1
    for ($i = 0; $i -lt $lines.Length; $i++) {
        if ($lines[$i] -match $injectAfter) { $lastImportIdx = $i }
    }
    if ($lastImportIdx -ge 0) {
        $before = $lines[0..$lastImportIdx] -join "`r`n"
        $after  = $lines[($lastImportIdx + 1)..($lines.Length - 1)] -join "`r`n"
        $src = $before + "`r`nimport sqlite3`r`nimport os`r`nDB_PATH = os.environ.get('THESIUM_DB', 'thesium.db')`r`n`r`n" + $after
    }
}

# Remplacement : conn = get_db()  ->  conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
$pattern = 'conn\s*=\s*get_db\(\)'
$replacement = "conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row"
$nMatches = ([regex]::Matches($src, $pattern)).Count
Write-Host "Remplacements get_db() detectes : $nMatches"

$src = [regex]::Replace($src, $pattern, $replacement)

Set-Content -Path $File -Value $src -Encoding UTF8 -NoNewline
Write-Host "`nPatch applique."

# Verification syntaxique
Write-Host "Verification py_compile..."
$result = & py -3.13 -c "import py_compile; py_compile.compile('$File', doraise=True); print('SYNTAX_OK')" 2>&1
Write-Host $result

if ($LASTEXITCODE -ne 0) {
    Write-Host "ECHEC compilation - restauration backup" -ForegroundColor Red
    Copy-Item $Backup $File -Force
    exit 1
}

# Redemarrage uvicorn
Write-Host "`nRedemarrage uvicorn..."
$portPids = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
foreach ($p in $portPids) {
    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    Write-Host "  process $p arrete"
}
Start-Sleep -Seconds 2

$proc = Start-Process -FilePath "py" `
    -ArgumentList "-3.13", "-m", "uvicorn", "api_server_with_static:app", "--host", "0.0.0.0", "--port", "8000" `
    -PassThru -WindowStyle Minimized

Write-Host "  uvicorn PID : $($proc.Id)"
Start-Sleep -Seconds 8

# Test endpoint
Write-Host "`nTest GET /api/construction/targets..."
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8000/api/construction/targets" -UseBasicParsing -TimeoutSec 10
    Write-Host "  Status: $($r.StatusCode)" -ForegroundColor Green
    Write-Host "  Body (200 premiers chars):"
    Write-Host ($r.Content.Substring(0, [Math]::Min(200, $r.Content.Length)))
    Write-Host "`n==================================================" -ForegroundColor Green
    Write-Host "  FIX OK - endpoints /api/construction/* operationnels" -ForegroundColor Green
    Write-Host "==================================================" -ForegroundColor Green
} catch {
    Write-Host "  ECHEC : $_" -ForegroundColor Red
    Write-Host "`nPour voir le traceback complet, relancez uvicorn en foreground :" -ForegroundColor Yellow
    Write-Host "  Stop-Process -Id $($proc.Id) -Force" -ForegroundColor Yellow
    Write-Host "  py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000" -ForegroundColor Yellow
}
