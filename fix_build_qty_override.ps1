# fix_build_qty_override.ps1
# Patch override BUILD : force quantity=1 pour equities en phase BUILD
# Si quantity calculee >= 1 -> force a 1 ; sinon skip (continue)
# Crypto exemptes (laisse [RDC_CRYPTO_V1] inchange)
# Marqueur idempotent : [BUILD_QTY1_V1]

$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"

if (-not (Test-Path $target)) {
    Write-Host "[ERR] Fichier introuvable : $target" -ForegroundColor Red
    exit 1
}

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak.build_qty1.$ts"
Copy-Item $target $backup -Force
Write-Host "[OK] Backup : $backup" -ForegroundColor Green

# Lecture utf-8-sig
$bytes = [System.IO.File]::ReadAllBytes($target)
$content = [System.Text.Encoding]::UTF8.GetString($bytes)
if ($content.Length -gt 0 -and $content[0] -eq [char]0xFEFF) {
    $content = $content.Substring(1)
    Write-Host "[INFO] BOM detecte et retire" -ForegroundColor Yellow
}

if ($content -match "\[BUILD_QTY1_V1\]") {
    Write-Host "[SKIP] Patch deja applique (marqueur [BUILD_QTY1_V1] present)" -ForegroundColor Yellow
    exit 0
}

# On insere notre bloc JUSTE APRES le bloc SELL max_qty (L1869)
# et JUSTE AVANT le filtre [RDC_CRYPTO_V1] tolerate (L1871)
#
# Pattern d'ancrage : la ligne "quantity = int(min(quantity, math.floor(proposal["max_qty"])))"
# suivie d'une ligne vide puis du commentaire "# [RDC_CRYPTO_V1] tolerate"

$pattern = '(?ms)(?<anchor>quantity\s*=\s*int\(min\(quantity,\s*math\.floor\(proposal\["max_qty"\]\)\)\)\s*\r?\n)(?<blank>\s*\r?\n)(?<next>[ \t]+# \[RDC_CRYPTO_V1\] tolerate)'

$m = [regex]::Match($content, $pattern)
if (-not $m.Success) {
    Write-Host "[ERR] Pattern d'ancrage introuvable (apres SELL max_qty, avant [RDC_CRYPTO_V1] tolerate)" -ForegroundColor Red
    Write-Host "[HINT] Lignes contenant max_qty :" -ForegroundColor Yellow
    $lines = $content -split "`n"
    for ($i = 0; $i -lt $lines.Length; $i++) {
        if ($lines[$i] -match 'max_qty') {
            Write-Host ("  L{0}: {1}" -f ($i+1), $lines[$i].TrimEnd()) -ForegroundColor Cyan
        }
    }
    exit 2
}

# Recuperer indentation de la ligne suivante pour aligner notre injection
$next_line = $m.Groups["next"].Value
$ind = ($next_line -replace '^([ \t]+).*$', '$1')
Write-Host "[OK] Pattern trouve a l'offset $($m.Index), indentation = $($ind.Length) chars" -ForegroundColor Green

# Bloc injecte : detection BUILD via regime + side=='buy' + equity (non crypto)
# On lit le regime depuis le contexte (variable 'regime' ou proposal.get('regime'))
# Fallback : detecter via total_value / invested si regime absent
$injection = @"
${ind}# [BUILD_QTY1_V1] override BUILD : equities BUY force a qty=1 par cycle si >= 1
${ind}try:
${ind}    _bq1_regime = str(proposal.get("regime", "")).upper()
${ind}    if not _bq1_regime:
${ind}        # fallback : recalc invested_pct
${ind}        _bq1_inv_pct = 0.0
${ind}        try:
${ind}            _bq1_inv_pct = float(conn.execute(
${ind}                "SELECT COALESCE(SUM(quantity * avg_price),0)/NULLIF(?,0)*100 FROM portfolio_positions",
${ind}                (total_value,)
${ind}            ).fetchone()[0] or 0.0)
${ind}        except Exception:
${ind}            pass
${ind}        _bq1_regime = "BUILD" if _bq1_inv_pct < 20.0 else "MAINTAIN"
${ind}    _bq1_is_build = (_bq1_regime == "BUILD")
${ind}    _bq1_is_buy = (str(proposal.get("side", "")).lower() == "buy")
${ind}    if _bq1_is_build and _bq1_is_buy and not _rdc_is_crypto:
${ind}        if quantity >= 1:
${ind}            print(f"[BUILD_QTY1_V1] {_rdc_ticker} : qty {quantity} -> 1 (BUILD equity override)")
${ind}            quantity = 1
${ind}        else:
${ind}            print(f"[BUILD_QTY1_V1] {_rdc_ticker} : qty {quantity} < 1 -> SKIP")
${ind}            continue
${ind}except Exception as _bq1_e:
${ind}    print(f"[BUILD_QTY1_V1] error : {_bq1_e}")

"@

$new_content = $content.Substring(0, $m.Index + $m.Groups["anchor"].Length + $m.Groups["blank"].Length) + $injection + $content.Substring($m.Index + $m.Groups["anchor"].Length + $m.Groups["blank"].Length)

# Ecriture utf-8 SANS BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($target, $new_content, $utf8NoBom)
Write-Host "[OK] Ecriture utf-8 sans BOM" -ForegroundColor Green

# Validation AST
$validation = & py -3.13 -c "import ast; ast.parse(open(r'$target', encoding='utf-8').read()); print('AST_OK')" 2>&1
if ($validation -match "AST_OK") {
    Write-Host "[OK] AST valide" -ForegroundColor Green
} else {
    Write-Host "[ERR] AST invalide ! Restauration backup..." -ForegroundColor Red
    Write-Host $validation -ForegroundColor Red
    Copy-Item $backup $target -Force
    exit 3
}

# Verif marqueur
$check = Get-Content $target -Raw -Encoding UTF8
$count = ([regex]::Matches($check, "\[BUILD_QTY1_V1\]")).Count
Write-Host "[OK] Marqueur [BUILD_QTY1_V1] present ($count occurrences)" -ForegroundColor Green

# Verif que [RDC_CRYPTO_V1] est toujours la
$cryptoCount = ([regex]::Matches($check, "\[RDC_CRYPTO_V1\]")).Count
Write-Host "[OK] Marqueur [RDC_CRYPTO_V1] preserve ($cryptoCount occurrences)" -ForegroundColor Green

Write-Host ""
Write-Host "=== PATCH BUILD_QTY1_V1 APPLIQUE ===" -ForegroundColor Cyan
Write-Host "Comportement attendu en BUILD :" -ForegroundColor White
Write-Host "  - equities BUY avec qty calculee >= 1 -> force a qty=1" -ForegroundColor White
Write-Host "  - equities BUY avec qty calculee  < 1 -> SKIP (continue)" -ForegroundColor White
Write-Host "  - crypto BUY -> inchange (round 6 decimales)" -ForegroundColor White
Write-Host "  - SELL -> inchange" -ForegroundColor White
Write-Host ""
Write-Host "Etapes :" -ForegroundColor Cyan
Write-Host "  1. Ctrl+C uvicorn" -ForegroundColor White
Write-Host "  2. py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000" -ForegroundColor White
Write-Host "  3. UI 'Run Decision Cycle'" -ForegroundColor White
Write-Host "  4. py -3.13 verif_btc_orders_table.py" -ForegroundColor White
Write-Host ""
Write-Host "Attendu : META=1, AAPL=1, AMZN=1, etc. + BTC=0.258 (fractionnaire)" -ForegroundColor Green
