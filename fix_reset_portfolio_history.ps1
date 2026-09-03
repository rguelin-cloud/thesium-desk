# fix_reset_portfolio_history.ps1
# Ajoute le champ 'date' obligatoire dans le bloc INSERT portfolio_history
# de reset_portfolio_full.ps1 (sinon warning NOT NULL au reset)
# Marqueur idempotent : [RESET_DATE_FIX_V1]

$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\reset_portfolio_full.ps1"

if (-not (Test-Path $target)) {
    Write-Host "[ERR] $target introuvable" -ForegroundColor Red
    exit 1
}

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak.date_fix.$ts"
Copy-Item $target $backup -Force
Write-Host "[OK] Backup : $backup" -ForegroundColor Green

$bytes = [System.IO.File]::ReadAllBytes($target)
$content = [System.Text.Encoding]::UTF8.GetString($bytes)
if ($content.Length -gt 0 -and $content[0] -eq [char]0xFEFF) {
    $content = $content.Substring(1)
}

# Idempotence
if ($content -match "\[RESET_DATE_FIX_V1\]") {
    Write-Host "[SKIP] Marqueur deja present" -ForegroundColor Yellow
    exit 0
}

# Pattern : ligne "data_h = {}" suivie des if/sinon
# On insere "data_h['date'] = ..." apres le data_h = {}
$pattern = '(?ms)(?<line>data_h\s*=\s*\{\}\s*\r?\n)'
$m = [regex]::Match($content, $pattern)

if (-not $m.Success) {
    Write-Host "[ERR] Pattern 'data_h = {}' introuvable" -ForegroundColor Red
    exit 2
}

# On veut injecter en Python (puisque c'est dans un heredoc PowerShell)
# Recuperer indentation
$next_chars = $content.Substring($m.Index + $m.Length, [Math]::Min(100, $content.Length - $m.Index - $m.Length))
$ind_match = [regex]::Match($next_chars, '^(?<ind>[ \t]+)')
$ind = if ($ind_match.Success) { $ind_match.Groups["ind"].Value } else { "    " }

$injection = "${ind}# [RESET_DATE_FIX_V1] colonne 'date' NOT NULL obligatoire`r`n"
$injection += "${ind}from datetime import date as _date_today`r`n"
$injection += "${ind}if `"date`" in cols_h: data_h[`"date`"] = _date_today.today().isoformat()`r`n"

$new_content = $content.Substring(0, $m.Index + $m.Length) + $injection + $content.Substring($m.Index + $m.Length)

$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($target, $new_content, $utf8NoBom)

Write-Host "[OK] Patch applique a l'offset $($m.Index)" -ForegroundColor Green

# Verif marqueur
$check = Get-Content $target -Raw -Encoding UTF8
if ($check -match "\[RESET_DATE_FIX_V1\]") {
    Write-Host "[OK] Marqueur [RESET_DATE_FIX_V1] present" -ForegroundColor Green
} else {
    Write-Host "[ERR] Marqueur absent apres patch" -ForegroundColor Red
    Copy-Item $backup $target -Force
    exit 3
}

Write-Host ""
Write-Host "=== TERMINE ===" -ForegroundColor Cyan
Write-Host "Au prochain reset, plus de warning portfolio_history.date NOT NULL" -ForegroundColor White
