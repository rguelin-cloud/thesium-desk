$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$out  = "$root\lots"
New-Item -ItemType Directory -Force -Path $out | Out-Null
Remove-Item "$out\*.md" -ErrorAction SilentlyContinue

$exclude = '\\(venv|\.venv|__pycache__|\.git|node_modules|lots|export)\\'
$maxKo   = 400

$lots = @{
  '1_shadow'    = 'shadow|variant|perf_roll|promote'
  '2_risk'      = 'risk|pretrade|guard|limit'
  '3_execution' = 'execution|broker|order|fill|paper'
  '4_portfolio' = 'portfolio|position|target|construct|nav'
  '5_agents'    = 'agent'
  '6_converge'  = 'converg|consensus|cycle|orchestr|exit'
  '7_api'       = 'api_server|main|route|endpoint'
  '8_models'    = 'model|schema|migration|db'
}

$files = Get-ChildItem -Path $root -Recurse -Include *.py |
         Where-Object { $_.FullName -notmatch $exclude }

$assigned = @{}
foreach ($lot in $lots.Keys | Sort-Object) {
    $pattern = $lots[$lot]
    foreach ($f in $files) {
        if ($assigned.ContainsKey($f.FullName)) { continue }
        if ($f.Name -match $pattern) {
            $assigned[$f.FullName] = $lot
            $rel  = $f.FullName.Replace("$root\", "")
            $dest = "$out\lot$lot.md"
            Add-Content $dest "`n`n===== FICHIER: $rel =====`n"
            Add-Content $dest (Get-Content $f.FullName -Raw)
        }
    }
}

# Fichiers non classes
foreach ($f in $files) {
    if (-not $assigned.ContainsKey($f.FullName)) {
        $rel = $f.FullName.Replace("$root\", "")
        Add-Content "$out\lot9_reste.md" "`n`n===== FICHIER: $rel =====`n"
        Add-Content "$out\lot9_reste.md" (Get-Content $f.FullName -Raw)
    }
}

Write-Host "`n=== LOTS GENERES ===" -ForegroundColor Cyan
Get-ChildItem "$out\*.md" | ForEach-Object {
    $ko = [math]::Round($_.Length/1KB,1)
    $flag = if ($ko -gt $maxKo) { " <-- TROP GROS, a decouper" } else { "" }
    Write-Host ("{0,-20} {1,8} Ko{2}" -f $_.Name, $ko, $flag)
}

Write-Host "`n=== VERIFICATION SECRETS ===" -ForegroundColor Yellow
$hits = Select-String -Path "$out\*.md" `
    -Pattern "api_key\s*=\s*[`"']|API_KEY\s*=\s*[`"']|secret\s*=\s*[`"']|token\s*=\s*[`"']|password\s*=\s*[`"']|sk-[A-Za-z0-9]{20}|pplx-[A-Za-z0-9]{20}"
if ($hits) { $hits | Select-Object Filename, LineNumber, Line | Format-Table -Wrap }
else { Write-Host "Aucun secret detecte." -ForegroundColor Green }