# [GDELT_TIMEOUT_FIX_V1] Augmente le timeout GDELT a 45s et ajoute UA
# Idempotent : detecte le marqueur avant d'appliquer

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$src  = Join-Path $root "data_geopolitical.py"
$bak  = Join-Path $root ("data_geopolitical.py.bak_" + (Get-Date -Format "yyyyMMdd_HHmmss"))

if (-not (Test-Path $src)) { throw "Fichier introuvable : $src" }

# Lecture utf-8-sig pour neutraliser un eventuel BOM
$bytes = [System.IO.File]::ReadAllBytes($src)
$content = [System.Text.Encoding]::UTF8.GetString($bytes)
if ($content.StartsWith([char]0xFEFF)) { $content = $content.Substring(1) }

# Marqueur d'idempotence
if ($content -match "\[GDELT_TIMEOUT_FIX_V1\]") {
    Write-Host "[SKIP] Patch deja applique (marqueur trouve)." -ForegroundColor Yellow
    exit 0
}

# Backup
Copy-Item $src $bak -Force
Write-Host "[BACKUP] $bak" -ForegroundColor Cyan

# --- Patch 1 : timeout=20 -> timeout=45 + User-Agent header ---
$old1 = 'resp = requests.get(GDELT_GKG_API, params=params, timeout=20)'
$new1 = '# [GDELT_TIMEOUT_FIX_V1] timeout 20->45s + UA explicite (GDELT met souvent 20-26s)' + "`n" +
        '                resp = requests.get(GDELT_GKG_API, params=params, timeout=45, headers={"User-Agent": "NEXTONES-thesium/1.0"})'

if ($content -notmatch [regex]::Escape($old1)) {
    throw "[ERR] Ligne timeout=20 introuvable. Verifier manuellement L173."
}
$content = $content.Replace($old1, $new1)

# --- Patch 2 : ajouter retry sur Timeout avec _gdelt_last_call NON mis a jour ---
# (deja gere par le code existant -- on ne touche pas)

# --- Patch 3 : ajouter un log indicatif au debut du module ---
$marker = "# [GDELT_TIMEOUT_FIX_V1] applied " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
if ($content -notmatch "GDELT_TIMEOUT_FIX_V1\] applied") {
    $content = $marker + "`n" + $content
}

# Validation AST avant ecriture
$tmp = Join-Path $env:TEMP "data_geopolitical_patched.py"
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($tmp, $content, $utf8NoBom)

$astCheck = py -3.13 -c "import ast,sys; ast.parse(open(r'$tmp',encoding='utf-8').read()); print('AST OK')"
if ($astCheck -notmatch "AST OK") {
    Write-Host "[ABORT] AST invalide. Restauration ignoree (fichier source intact)." -ForegroundColor Red
    Remove-Item $tmp -Force
    exit 1
}

# Ecriture finale utf-8 sans BOM
[System.IO.File]::WriteAllText($src, $content, $utf8NoBom)
Remove-Item $tmp -Force

Write-Host ""
Write-Host "[OK] Patch applique avec succes." -ForegroundColor Green
Write-Host "     - timeout requests : 20s -> 45s"
Write-Host "     - User-Agent : NEXTONES-thesium/1.0"
Write-Host ""
Write-Host "Redemarrer uvicorn pour que le module soit recharge :" -ForegroundColor Yellow
Write-Host "  py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000"
Write-Host ""
Write-Host "Vider le cache geo en plus (sinon les anciennes valeurs vides restent en memoire) :" -ForegroundColor Yellow
Write-Host "  - Soit redemarrer le process (recommande)"
Write-Host "  - Soit attendre l'expiration du cache_ttl_seconds dans le module"
