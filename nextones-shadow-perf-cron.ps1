# nextones-shadow-perf-cron.ps1
# Phase 9.5 - Cron daily wrapper pour shadow_perf_rolling_j30.py
#
# Lance le calcul perf rolling J-30 et logge stdout/stderr dans
# logs\shadow_perf_YYYYMMDD.log (un fichier par jour, append).
#
# Usage manuel :
#   powershell -ExecutionPolicy Bypass -File .\nextones-shadow-perf-cron.ps1
#
# Installation cron Windows Task Scheduler (a faire 1 fois, en admin) :
#   schtasks /Create /TN "Nextones-ShadowPerfRolling" `
#     /TR "powershell -ExecutionPolicy Bypass -File C:\Users\RichardGUELIN\Prod\ThesiumDesk\nextones-shadow-perf-cron.ps1" `
#     /SC DAILY /ST 22:00 /RL HIGHEST /F

$ErrorActionPreference = "Continue"

# Repertoire de base
$BaseDir = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$LogDir  = Join-Path $BaseDir "logs"
$Script  = Join-Path $BaseDir "shadow_perf_rolling_j30.py"

# Creer logs/ si absent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Nom de fichier log : shadow_perf_YYYYMMDD.log (date UTC pour matcher as-of)
$Stamp   = (Get-Date).ToUniversalTime().ToString("yyyyMMdd")
$LogFile = Join-Path $LogDir "shadow_perf_$Stamp.log"

# Header
$HeaderTime = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")
$Header = @"
==============================================================================
SHADOW PERF ROLLING CRON - run start
Started        : $HeaderTime
UTC stamp      : $Stamp
Script         : $Script
==============================================================================
"@
Add-Content -Path $LogFile -Value $Header -Encoding UTF8

# Run
$StartTime = Get-Date
try {
    # py -3.13 lance shadow_perf_rolling_j30.py sans --as-of (default = aujourd hui UTC)
    # 2>&1 redirige stderr vers stdout pour capture unifiee
    $Output = & py -3.13 $Script 2>&1
    $ExitCode = $LASTEXITCODE
    Add-Content -Path $LogFile -Value $Output -Encoding UTF8
} catch {
    $ExitCode = 99
    Add-Content -Path $LogFile -Value "[EXCEPTION] $_" -Encoding UTF8
}

$EndTime = Get-Date
$Elapsed = ($EndTime - $StartTime).TotalSeconds

# Footer
$Footer = @"

==============================================================================
SHADOW PERF ROLLING CRON - run end
Finished       : $($EndTime.ToString("yyyy-MM-dd HH:mm:ss zzz"))
Elapsed        : $($Elapsed.ToString("F2")) sec
Exit code      : $ExitCode
==============================================================================

"@
Add-Content -Path $LogFile -Value $Footer -Encoding UTF8

# Echo console (utile si lance manuellement)
Write-Host "Shadow perf rolling done. Exit=$ExitCode Elapsed=$([math]::Round($Elapsed,2))s Log=$LogFile"

exit $ExitCode
