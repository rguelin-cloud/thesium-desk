# nextones-apply-scheduler-geo-pplx-v2.ps1
# Comme v1 mais delta tolère idempotence (+0 ou +1)

$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak_geo_sched_v2_$ts"

Copy-Item $target $backup -Force
Write-Host "[1/4] Backup -> $backup"

$src = Get-Content $target -Raw -Encoding UTF8
$nbDefBefore = ([regex]::Matches($src, '(?m)^\s+def\s+refresh_\w+')).Count
$nbAddJobBefore = ([regex]::Matches($src, 'scheduler\.add_job')).Count
$alreadyPatched = $src.Contains("[SCHEDULER_GEO_PPLX_V1]")
Write-Host "[2/4] AVANT : $nbDefBefore refresh_*, $nbAddJobBefore add_job, idempotent=$alreadyPatched"

$helper = Join-Path $env:TEMP "apply_sched_geo_v2_$ts.py"
$helperContent = @'
# -*- coding: utf-8 -*-
import re, sys
from pathlib import Path

target = Path(sys.argv[1])
raw = target.read_text(encoding="utf-8-sig")

# Idempotence : si déjà patché on vire ancien bloc def + add_job
if "[SCHEDULER_GEO_PPLX_V1]" in raw:
    print("[i] Marker déjà présent, remplacement...")
    raw = re.sub(
        r'\n    def refresh_pplx_geo\(\):\s*\n.*?\n(?=    (?:def |from datetime|scheduler\.add_job))',
        '\n',
        raw,
        flags=re.DOTALL,
        count=1,
    )
    raw = re.sub(
        r'\n    scheduler\.add_job\(refresh_pplx_geo[^\n]*\n',
        '\n',
        raw,
        count=1,
    )

def_factor_pattern = re.compile(
    r'(    def refresh_pplx_factor\(\):.*?print\(f"\[scheduler\] PPLX factor refresh error: \{e\}"\)\n)',
    re.DOTALL
)
m1 = def_factor_pattern.search(raw)
if not m1:
    print("[KO] def refresh_pplx_factor introuvable")
    sys.exit(2)

new_def = '''
    def refresh_pplx_geo():
        """[SCHEDULER_GEO_PPLX_V1] Refresh contexte geopolitique Perplexity (top 5 risques, 4h cache)."""
        try:
            print("[scheduler] Refreshing Perplexity geo context...")
            from pplx_geo_agent import run_geo_agent
            run_geo_agent(force=True)
            print("[scheduler] PPLX geo context refreshed.")
        except Exception as e:
            print(f"[scheduler] PPLX geo refresh error: {e}")
'''

raw = raw[:m1.end()] + new_def + raw[m1.end():]
print("[OK] def refresh_pplx_geo injectée")

addjob_pattern = re.compile(
    r'(    scheduler\.add_job\(refresh_pplx_factor[^\n]*\n)'
)
m2 = addjob_pattern.search(raw)
if not m2:
    print("[KO] scheduler.add_job(refresh_pplx_factor introuvable")
    sys.exit(3)

new_addjob = "    scheduler.add_job(refresh_pplx_geo,    'interval', hours=4,  id='refresh_pplx_geo',    next_run_time=_now + _td(minutes=8))\n"

raw = raw[:m2.end()] + new_addjob + raw[m2.end():]
print("[OK] add_job(refresh_pplx_geo) injectée")

target.write_text(raw, encoding="utf-8", newline="\n")
print("[OK] Fichier écrit")
'@

Set-Content -Path $helper -Value $helperContent -Encoding UTF8

Write-Host "[3/4] Helper -> $helper"
py -3.13 $helper $target
if ($LASTEXITCODE -ne 0) {
    Write-Host "[KO] Helper a échoué. Restore." -ForegroundColor Red
    Copy-Item $backup $target -Force
    exit 1
}

# Comptage APRES
$src2 = Get-Content $target -Raw -Encoding UTF8
$nbDefAfter = ([regex]::Matches($src2, '(?m)^\s+def\s+refresh_\w+')).Count
$nbAddJobAfter = ([regex]::Matches($src2, 'scheduler\.add_job')).Count
Write-Host "    APRES : $nbDefAfter refresh_*, $nbAddJobAfter add_job"

# Validation : si idempotent, delta=0 OK ; si premier patch, delta=+1 attendu
$deltaRefresh = $nbDefAfter - $nbDefBefore
$deltaAddJob = $nbAddJobAfter - $nbAddJobBefore
Write-Host "    Delta : refresh=$deltaRefresh, add_job=$deltaAddJob"

if ($alreadyPatched) {
    # Idempotent : delta doit être 0
    if ($deltaRefresh -ne 0 -or $deltaAddJob -ne 0) {
        Write-Host "[KO] Delta inattendu pour patch idempotent. Restore." -ForegroundColor Red
        Copy-Item $backup $target -Force
        exit 1
    }
    Write-Host "    OK (idempotent : ancien bloc remplace par nouveau)"
} else {
    # Premier patch : delta doit être +1
    if ($deltaRefresh -ne 1 -or $deltaAddJob -ne 1) {
        Write-Host "[KO] Delta attendu +1/+1, eu $deltaRefresh/$deltaAddJob. Restore." -ForegroundColor Red
        Copy-Item $backup $target -Force
        exit 1
    }
    Write-Host "    OK (premier patch : +1 refresh, +1 add_job)"
}

# Vérif marker présent
if (-not $src2.Contains("[SCHEDULER_GEO_PPLX_V1]")) {
    Write-Host "[KO] Marker absent. Restore." -ForegroundColor Red
    Copy-Item $backup $target -Force
    exit 1
}

# Vérif présence add_job refresh_pplx_geo
if (-not $src2.Contains("refresh_pplx_geo,    'interval'")) {
    Write-Host "[!] add_job refresh_pplx_geo non trouvé textuellement (vérification visuelle requise)" -ForegroundColor Yellow
}

# Vérif syntaxe
Write-Host "[4/4] Validation syntaxe..."
py -3.13 -c "import ast; ast.parse(open(r'$target', encoding='utf-8').read()); print('[OK] syntaxe valide')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[KO] Erreur syntaxe. Restore." -ForegroundColor Red
    Copy-Item $backup $target -Force
    exit 1
}

Write-Host ""
Write-Host "=== PATCH OK ===" -ForegroundColor Green
Write-Host "Backup : $backup"
Write-Host ""
Write-Host "Si API tourne deja, kill + relance :"
Write-Host "  Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess -Force"
Write-Host "  py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000"
Write-Host ""
Write-Host "A T+8min apres startup tu verras : [scheduler] Refreshing Perplexity geo context..."
