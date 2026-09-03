#requires -Version 5.1
<#
.SYNOPSIS
  Rollback du déplacement panel pplx — restaure le backup le plus récent
  index.html.bak_pplx_move_*.
#>
$ErrorActionPreference = 'Stop'
$root = 'C:\Users\RichardGUELIN\Prod\ThesiumDesk'
$html = Join-Path $root 'index.html'

# Cherche le backup le plus récent
$backup = Get-ChildItem -Path $root -Filter 'index.html.bak_pplx_move_*' |
          Sort-Object LastWriteTime -Descending |
          Select-Object -First 1

if (-not $backup) {
  Write-Host "[ERR] Aucun backup index.html.bak_pplx_move_* trouvé." -ForegroundColor Red
  exit 1
}

Write-Host "[INFO] Backup trouvé : $($backup.Name)" -ForegroundColor Cyan
Write-Host "[INFO] Restauration vers index.html..." -ForegroundColor Cyan

Copy-Item $backup.FullName $html -Force

Write-Host "[OK] index.html restauré." -ForegroundColor Green
Write-Host "    Recharge l'UI avec Ctrl+F5. Tous les onglets doivent revenir." -ForegroundColor Green
Write-Host "    Le panel pplx reste tout en bas du body (avant correction)." -ForegroundColor Yellow
