# fix_run_decision_cycle_crypto.ps1
# Patch L1858-1866 de execution_engine.py pour gerer les fractions crypto
# dans run_decision_cycle (le VRAI chemin d'insertion d'ordres)
# Marqueur idempotent : [RDC_CRYPTO_V1]

$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"

if (-not (Test-Path $target)) {
    Write-Host "[ERR] Fichier introuvable : $target" -ForegroundColor Red
    exit 1
}

# Backup horodate
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak.rdc_crypto.$ts"
Copy-Item $target $backup -Force
Write-Host "[OK] Backup : $backup" -ForegroundColor Green

# Lecture utf-8-sig (gere BOM eventuel)
$bytes = [System.IO.File]::ReadAllBytes($target)
$content = [System.Text.Encoding]::UTF8.GetString($bytes)
if ($content.Length -gt 0 -and $content[0] -eq [char]0xFEFF) {
    $content = $content.Substring(1)
    Write-Host "[INFO] BOM detecte et retire" -ForegroundColor Yellow
}

# Verif idempotence
if ($content -match "\[RDC_CRYPTO_V1\]") {
    Write-Host "[SKIP] Patch deja applique (marqueur [RDC_CRYPTO_V1] present)" -ForegroundColor Yellow
    exit 0
}

# Pattern cible : bloc L1858-1866
# target_value = total_value * (proposal["quantity_pct"] / 100)
# quantity = math.floor(target_value / price)
# ...
# if proposal["side"] == "sell" and "max_qty" in proposal:
#     quantity = int(min(quantity, math.floor(proposal["max_qty"])))
#
# if quantity <= 0:
#     continue

# On utilise un regex multilignes robuste, indentation conservee
$pattern = '(?ms)(^(?<ind>[ \t]+)target_value\s*=\s*total_value\s*\*\s*\(proposal\["quantity_pct"\]\s*/\s*100\)\s*\r?\n)(?<ind2>[ \t]+)quantity\s*=\s*math\.floor\(target_value\s*/\s*price\)\s*\r?\n'

$m = [regex]::Match($content, $pattern)
if (-not $m.Success) {
    Write-Host "[ERR] Pattern L1858-1859 introuvable. Le fichier a peut-etre deja ete modifie." -ForegroundColor Red
    Write-Host "[HINT] Recherche manuelle :" -ForegroundColor Yellow
    $lines = $content -split "`n"
    for ($i = 0; $i -lt $lines.Length; $i++) {
        if ($lines[$i] -match "quantity\s*=\s*math\.floor\(target_value") {
            Write-Host ("  L{0}: {1}" -f ($i+1), $lines[$i].TrimEnd()) -ForegroundColor Cyan
        }
    }
    exit 2
}

$ind = $m.Groups["ind"].Value
$ind2 = $m.Groups["ind2"].Value

Write-Host "[OK] Pattern trouve a l'offset $($m.Index)" -ForegroundColor Green

# Remplacement : injecte detection crypto + branche fractionnaire
$replacement = @"
${ind}target_value = total_value * (proposal["quantity_pct"] / 100)
${ind2}# [RDC_CRYPTO_V1] crypto-aware quantity computation
${ind2}_rdc_crypto_set = {'BTC','ETH','LINK','SOL','ADA','DOT','MATIC','AVAX'}
${ind2}_rdc_ticker = str(proposal.get("ticker","")).upper()
${ind2}_rdc_is_crypto = _rdc_ticker in _rdc_crypto_set
${ind2}if _rdc_is_crypto:
${ind2}    quantity = round(target_value / price, 6)
${ind2}else:
${ind2}    quantity = math.floor(target_value / price)

"@

$new_content = $content.Substring(0, $m.Index) + $replacement + $content.Substring($m.Index + $m.Length)

# Patch du filtre "if quantity <= 0: continue" qui suit immediatement
# On cible la PREMIERE occurrence apres notre remplacement
$idx_after = $m.Index + $replacement.Length

$tail = $new_content.Substring($idx_after)
$pattern_filter = '(?ms)^(?<find>[ \t]+)if\s+quantity\s*<=\s*0:\s*\r?\n(?<find2>[ \t]+)continue\s*\r?\n'
$mf = [regex]::Match($tail, $pattern_filter)

if ($mf.Success) {
    $find = $mf.Groups["find"].Value
    $find2 = $mf.Groups["find2"].Value
    $filter_replacement = @"
${find}# [RDC_CRYPTO_V1] tolerate crypto fractional positions
${find}_rdc_min_qty = 0.0001 if _rdc_is_crypto else 0
${find}if quantity <= _rdc_min_qty:
${find2}continue

"@
    $new_content = $new_content.Substring(0, $idx_after + $mf.Index) + $filter_replacement + $new_content.Substring($idx_after + $mf.Index + $mf.Length)
    Write-Host "[OK] Filtre 'if quantity <= 0' patche aussi" -ForegroundColor Green
} else {
    Write-Host "[WARN] Filtre 'if quantity <= 0' non trouve apres le bloc. A verifier manuellement." -ForegroundColor Yellow
}

# Ecriture en utf-8 SANS BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($target, $new_content, $utf8NoBom)

Write-Host "[OK] Ecriture utf-8 sans BOM" -ForegroundColor Green

# Validation AST via py -3.13
$validation = & py -3.13 -c "import ast; ast.parse(open(r'$target', encoding='utf-8').read()); print('AST_OK')" 2>&1

if ($validation -match "AST_OK") {
    Write-Host "[OK] AST valide" -ForegroundColor Green
} else {
    Write-Host "[ERR] AST invalide ! Restauration backup..." -ForegroundColor Red
    Write-Host $validation -ForegroundColor Red
    Copy-Item $backup $target -Force
    Write-Host "[OK] Backup restaure" -ForegroundColor Yellow
    exit 3
}

# Verif marqueur present
$check = Get-Content $target -Raw -Encoding UTF8
if ($check -match "\[RDC_CRYPTO_V1\]") {
    $count = ([regex]::Matches($check, "\[RDC_CRYPTO_V1\]")).Count
    Write-Host "[OK] Marqueur [RDC_CRYPTO_V1] present ($count occurrences)" -ForegroundColor Green
} else {
    Write-Host "[ERR] Marqueur absent apres patch !" -ForegroundColor Red
    exit 4
}

Write-Host ""
Write-Host "=== PATCH APPLIQUE ===" -ForegroundColor Cyan
Write-Host "Etapes suivantes :" -ForegroundColor Cyan
Write-Host "  1. Tuer uvicorn en cours (Ctrl+C dans la fenetre)" -ForegroundColor White
Write-Host "  2. Relancer : py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000" -ForegroundColor White
Write-Host "  3. UI : cliquer 'Run Decision Cycle'" -ForegroundColor White
Write-Host "  4. Verifier BTC dans orders : py -3.13 verif_btc_orders_table.py" -ForegroundColor White
Write-Host ""
Write-Host "BTC BUY attendu : quantity ~0.258 (instrument_id=15)" -ForegroundColor Green
