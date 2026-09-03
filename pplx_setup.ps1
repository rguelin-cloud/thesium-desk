# [PPLX_SETUP_V1] Setup initial Perplexity API pour NEXTONES.
# - Cree tables pplx_cache et pplx_audit dans thesium.db
# - Verifie/cree .env avec PPLX_API_KEY (saisie interactive si absente)
# - Installe python-dotenv et requests si necessaire
# Idempotent.

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$db = Join-Path $root "thesium.db"
$envFile = Join-Path $root ".env"

Set-Location $root

# 1) Verifier que python-dotenv et requests sont installes
Write-Host "[1/4] Verification dependances Python..." -ForegroundColor Cyan
$check = & py -3.13 -c "import dotenv, requests; print('OK')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Installation python-dotenv et requests..." -ForegroundColor Yellow
    & py -3.13 -m pip install python-dotenv requests
}
else {
    Write-Host "  python-dotenv et requests deja installes" -ForegroundColor Green
}

# 2) Gerer .env
Write-Host "[2/4] Configuration .env..." -ForegroundColor Cyan
$envContent = ""
if (Test-Path $envFile) {
    $envContent = Get-Content $envFile -Raw -Encoding UTF8
}

if ($envContent -notmatch "PPLX_API_KEY\s*=") {
    Write-Host ""
    Write-Host "  Aucune cle PPLX_API_KEY trouvee dans .env" -ForegroundColor Yellow
    Write-Host "  Recupere ta cle sur https://www.perplexity.ai/settings/api" -ForegroundColor Yellow
    $key = Read-Host "  Colle ta cle Perplexity API (commence par pplx-...)"
    if ([string]::IsNullOrWhiteSpace($key)) {
        Write-Host "[ERR] Cle vide, abort" -ForegroundColor Red
        exit 1
    }
    $key = $key.Trim()
    if (-not $key.StartsWith("pplx-")) {
        Write-Host "[WARN] La cle ne commence pas par 'pplx-', je l'enregistre quand meme" -ForegroundColor Yellow
    }
    $newLine = "PPLX_API_KEY=$key"
    if ($envContent -and -not $envContent.EndsWith("`n")) {
        $envContent += "`n"
    }
    $envContent += "$newLine`n"
    # Ecriture UTF-8 SANS BOM
    [System.IO.File]::WriteAllText($envFile, $envContent, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "  Cle ecrite dans $envFile" -ForegroundColor Green
}
else {
    Write-Host "  PPLX_API_KEY deja present dans .env" -ForegroundColor Green
}

# 3) Creer tables DB
Write-Host "[3/4] Creation tables SQLite..." -ForegroundColor Cyan
$pyHelper = @"
import sqlite3
DB = r'$db'
conn = sqlite3.connect(DB)
conn.execute('''
CREATE TABLE IF NOT EXISTS pplx_cache (
    key TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    ts INTEGER NOT NULL
)
''')
conn.execute('CREATE INDEX IF NOT EXISTS idx_pplx_cache_ts ON pplx_cache(ts)')
conn.execute('''
CREATE TABLE IF NOT EXISTS pplx_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,
    prompt TEXT,
    response TEXT,
    citations TEXT,
    model TEXT,
    cost_usd REAL DEFAULT 0,
    ts INTEGER NOT NULL
)
''')
conn.execute('CREATE INDEX IF NOT EXISTS idx_pplx_audit_agent_ts ON pplx_audit(agent, ts)')
conn.commit()
# Verifier
cnt_cache = conn.execute('SELECT COUNT(*) FROM pplx_cache').fetchone()[0]
cnt_audit = conn.execute('SELECT COUNT(*) FROM pplx_audit').fetchone()[0]
print(f'[DB] pplx_cache: {cnt_cache} entrees | pplx_audit: {cnt_audit} entrees')
conn.close()
"@
$tmpPy = Join-Path $env:TEMP "pplx_setup_db.py"
Set-Content -Path $tmpPy -Value $pyHelper -Encoding UTF8
try {
    & py -3.13 $tmpPy
    if ($LASTEXITCODE -ne 0) { throw "Creation tables KO" }
}
finally {
    Remove-Item $tmpPy -Force -ErrorAction SilentlyContinue
}

# 4) Test rapide chargement .env
Write-Host "[4/4] Test chargement .env..." -ForegroundColor Cyan
$testPy = @"
import os
from dotenv import load_dotenv
load_dotenv(r'$envFile')
k = os.environ.get('PPLX_API_KEY','')
if not k:
    print('[ERR] PPLX_API_KEY non chargee')
    exit(1)
print(f'[OK] Cle chargee: {k[:8]}...{k[-4:]}')
"@
$tmpPy = Join-Path $env:TEMP "pplx_setup_envtest.py"
Set-Content -Path $tmpPy -Value $testPy -Encoding UTF8
try {
    & py -3.13 $tmpPy
    if ($LASTEXITCODE -ne 0) { throw "Test .env KO" }
}
finally {
    Remove-Item $tmpPy -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "[DONE] Setup Perplexity termine" -ForegroundColor Green
Write-Host "  - .env : $envFile" -ForegroundColor White
Write-Host "  - DB tables : pplx_cache, pplx_audit" -ForegroundColor White
Write-Host "  - Prochaine etape : deployer pplx_client.py puis pplx_crypto_agent.py" -ForegroundColor White
