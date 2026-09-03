# nextones-install-replay-v5.ps1
# Installe les versions v5 (8B.2) de replay_db_view.py et replay_orchestrator.py
# depuis le dossier courant vers C:\Users\RichardGUELIN\Prod\ThesiumDesk
# avec backup horodate des anciennes versions.

$ErrorActionPreference = "Stop"

$ProdDir = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$Stamp = Get-Date -Format "yyyyMMddHHmmss"

$Files = @(
    "replay_db_view.py",
    "replay_orchestrator.py"
)

Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host " INSTALL 8B.2 - replay_db_view + replay_orchestrator (v5)" -ForegroundColor Cyan
Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host "Source : $PSScriptRoot"
Write-Host "Target : $ProdDir"
Write-Host ""

foreach ($f in $Files) {
    $src = Join-Path $PSScriptRoot $f
    $dst = Join-Path $ProdDir $f

    if (-not (Test-Path $src)) {
        Write-Host "  [SKIP] source absente : $src" -ForegroundColor Yellow
        continue
    }

    $srcSize = (Get-Item $src).Length
    Write-Host "  [$f]" -ForegroundColor Green
    Write-Host "    source size : $srcSize bytes"

    if (Test-Path $dst) {
        $dstSize = (Get-Item $dst).Length
        Write-Host "    target old  : $dstSize bytes"

        $bak = "$dst.bak.$Stamp"
        Copy-Item -Path $dst -Destination $bak -Force
        Write-Host "    backup      : $bak" -ForegroundColor Gray
    } else {
        Write-Host "    target old  : (absent, premier install)"
    }

    Copy-Item -Path $src -Destination $dst -Force
    $newSize = (Get-Item $dst).Length
    Write-Host "    installed   : $newSize bytes" -ForegroundColor Green

    if ($srcSize -ne $newSize) {
        Write-Host "    WARN size mismatch !" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host " VALIDATION post-install" -ForegroundColor Cyan
Write-Host "===============================================================" -ForegroundColor Cyan

# Marqueurs attendus dans la v5 de replay_db_view
$rdv = Join-Path $ProdDir "replay_db_view.py"
$markers = @("static_tables", "state_tables", "theses", "convergence_snapshots", "portfolio_state")
$content = Get-Content -Raw -Path $rdv -Encoding UTF8

Write-Host "Marqueurs v5 dans replay_db_view.py :"
foreach ($m in $markers) {
    $found = $content.Contains($m)
    $flag = if ($found) { "OK" } else { "MISS" }
    $color = if ($found) { "Green" } else { "Red" }
    Write-Host "  [$flag] $m" -ForegroundColor $color
}

Write-Host ""
Write-Host "Pret pour le smoke-test :" -ForegroundColor Yellow
Write-Host "  py -3.13 .\nextones-run-replay-8b2-v1.py" -ForegroundColor Yellow
