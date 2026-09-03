# Cron Shadow Jalon 9.5 + 9.5b
# Daily 22h00 : recalcul perf rolling J-30 PUIS generation memo IA pour les 4 variants
# Logs dans logs\shadow_perf_YYYYMMDD.log

$ErrorActionPreference = "Continue"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
Set-Location $root

$dateStr = Get-Date -Format "yyyyMMdd"
$logDir = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "shadow_perf_$dateStr.log"

function Write-Log {
    param([string]$msg)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Output $line
    Add-Content -Path $logFile -Value $line
}

Write-Log "=========================================="
Write-Log "SHADOW CRON START (perf-rolling + memo)"
Write-Log "=========================================="

# Etape 1 : shadow_perf_rolling_j30.py
Write-Log "[1/2] Run shadow_perf_rolling_j30.py ..."
$out1 = py -3.13 .\shadow_perf_rolling_j30.py 2>&1
$exit1 = $LASTEXITCODE
$out1 | ForEach-Object { Add-Content -Path $logFile -Value $_ }
Write-Log "[1/2] exit=$exit1"

if ($exit1 -ne 0) {
    Write-Log "[ABORT] perf_rolling exit code non-zero, skip memo"
    Write-Log "SHADOW CRON END"
    exit $exit1
}

# Etape 2 : shadow_memo_generator.py
Write-Log "[2/2] Run shadow_memo_generator.py --force ..."
$out2 = py -3.13 .\shadow_memo_generator.py --force 2>&1
$exit2 = $LASTEXITCODE
$out2 | ForEach-Object { Add-Content -Path $logFile -Value $_ }
Write-Log "[2/2] exit=$exit2"

Write-Log "SHADOW CRON END (exit perf=$exit1 memo=$exit2)"
exit $exit2
