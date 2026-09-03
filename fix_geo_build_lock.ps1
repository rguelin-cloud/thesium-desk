# [GEO_BUILD_LOCK_V1] Serialise les appels concurrents a _build_geopolitical_result()
# Un seul thread fait le build a la fois; les autres attendent et recuperent le cache.
# Idempotent, AST valide, rollback auto.

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$target = Join-Path $root "data_geopolitical.py"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak_buildlock_$ts"

Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

$helper = Join-Path $env:TEMP "geo_build_lock_$ts.py"

$pyCode = @'
import io, re, sys, ast

TARGET = r"__TARGET__"
MARKER = "[GEO_BUILD_LOCK_V1]"

with io.open(TARGET, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER in src:
    print("[SKIP] Patch deja applique")
    sys.exit(0)

# 1) Ajouter _build_lock dans la zone des globals (juste apres _bg_fetch_started)
old_globals = "_bg_fetch_done = threading.Event()\n_bg_fetch_started = False\n"
new_globals = old_globals + "\n# " + MARKER + " serialise les appels concurrents au build complet\n_build_lock = threading.Lock()\n"

if old_globals not in src:
    print("[ERR] Globals _bg_fetch_* introuvables")
    sys.exit(1)

src2 = src.replace(old_globals, new_globals, 1)

# 2) Remplacer le corps de fetch_geopolitical_risk() pour utiliser _build_lock
# On capture toute la fonction.
fn_pattern = re.compile(
    r'def fetch_geopolitical_risk\(\) -> dict:\s*\n'
    r'(?:[ \t]+.*\n)+',  # corps indente
    re.M
)

m = fn_pattern.search(src2)
if not m:
    print("[ERR] fetch_geopolitical_risk introuvable")
    sys.exit(1)

new_fn = '''def fetch_geopolitical_risk() -> dict:
    """Main entry point. ''' + MARKER + '''
    Returns the full geopolitical risk dashboard.
    Serialise les builds concurrents via _build_lock.
    """
    cache_key = "geopolitical_risk_full"

    # Si cache complet et frais, retourner immediatement
    if _is_cached(cache_key):
        cached = _get_cache(cache_key)
        if cached.get("_complete", True):
            return cached
        age = datetime.now().timestamp() - _cache_ts.get(cache_key, 0)
        if age < 120:
            return cached

    # Si le background pre-fetch tourne encore, attendre (sans timeout dur)
    if _bg_fetch_started and not _bg_fetch_done.is_set():
        print("[GEO] Waiting for background pre-fetch to complete...")
        _bg_fetch_done.wait(timeout=120)
        if _is_cached(cache_key):
            return _get_cache(cache_key)

    # Section critique: un seul thread build a la fois
    with _build_lock:
        # Re-check cache apres acquisition du lock (un autre thread a pu finir)
        if _is_cached(cache_key):
            cached = _get_cache(cache_key)
            if cached.get("_complete", True):
                return cached

        cached = _get_cache(cache_key) if cache_key in _cache else None

        # Si on a un partiel recent, on patch les theaters manquants
        if cached and not cached.get("_complete", True):
            result = _patch_missing_theaters(cached)
            _set_cache(cache_key, result)
            return result

        # Sinon, build complet
        result = _build_geopolitical_result()
        _set_cache(cache_key, result)
        return result


'''

src3 = src2[:m.start()] + new_fn + src2[m.end():]

# Validation AST
try:
    ast.parse(src3)
except SyntaxError as e:
    print("[ERR] ERR_AST: " + str(e))
    if e.lineno:
        ls = src3.splitlines()
        a = max(0, e.lineno - 8)
        b = min(len(ls), e.lineno + 8)
        for i in range(a, b):
            print(f"{i+1:5d}|{ls[i]}")
    sys.exit(1)

with io.open(TARGET, "w", encoding="utf-8", newline="\n") as f:
    f.write(src3)

print("[OK] " + MARKER + " applique: _build_lock ajoute + fetch_geopolitical_risk serialise")
'@

$pyCode = $pyCode.Replace("__TARGET__", $target.Replace("\","\\"))
Set-Content -Path $helper -Value $pyCode -Encoding UTF8

try {
    & py -3.13 $helper
    if ($LASTEXITCODE -ne 0) { throw "Helper Python a echoue (exit $LASTEXITCODE)" }
    & py -3.13 -c "import ast; ast.parse(open(r'$target', encoding='utf-8-sig').read()); print('[AST-OK]')"
    if ($LASTEXITCODE -ne 0) { throw "Validation AST finale KO" }
    Write-Host "[DONE] Patch applique avec succes" -ForegroundColor Green
}
catch {
    Write-Host "[ERR] $_" -ForegroundColor Red
    Write-Host "[ROLLBACK] depuis $backup" -ForegroundColor Yellow
    Copy-Item $backup $target -Force
    exit 1
}
finally {
    if (Test-Path $helper) { Remove-Item $helper -Force }
}
