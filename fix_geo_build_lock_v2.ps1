# [GEO_BUILD_LOCK_V2] Deplace le _build_lock dans _build_geopolitical_result()
# pour serialiser TOUS les appels (y compris ceux du _bg_worker startup).
# Idempotent, AST valide, rollback auto.

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$target = Join-Path $root "data_geopolitical.py"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak_buildlock2_$ts"

Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

$helper = Join-Path $env:TEMP "geo_build_lock2_$ts.py"

$pyCode = @'
import io, re, sys, ast

TARGET = r"__TARGET__"
MARKER = "[GEO_BUILD_LOCK_V2]"

with io.open(TARGET, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER in src:
    print("[SKIP] Patch deja applique")
    sys.exit(0)

# Strategie: wrapper _build_geopolitical_result en _build_geopolitical_result_inner
# et creer un wrapper _build_geopolitical_result qui prend _build_lock.

# 1) Renommer la fonction existante en _build_geopolitical_result_inner
src2 = src.replace(
    "def _build_geopolitical_result() -> dict:",
    "def _build_geopolitical_result_inner() -> dict:",
    1
)

# 2) Inserer juste avant cette fonction un wrapper qui prend le lock.
# On le pose juste apres la ligne "# ---------------------------------------------------------------------------"
# ou directement avant "def _build_geopolitical_result_inner".
wrapper = '''def _build_geopolitical_result() -> dict:
    """''' + MARKER + ''' Wrapper qui serialise les builds concurrents via _build_lock.
    Re-check le cache apres acquisition pour eviter les doublons.
    """
    # Si un autre thread vient de finir, on prend le cache
    if _is_cached("geopolitical_risk_full"):
        cached = _get_cache("geopolitical_risk_full")
        if cached and cached.get("_complete", True):
            return cached
    with _build_lock:
        # Re-check apres acquisition (autre thread peut avoir fini pendant qu'on attendait)
        if _is_cached("geopolitical_risk_full"):
            cached = _get_cache("geopolitical_risk_full")
            if cached and cached.get("_complete", True):
                return cached
        return _build_geopolitical_result_inner()


'''

# Inserer le wrapper juste avant "def _build_geopolitical_result_inner"
marker_def = "def _build_geopolitical_result_inner() -> dict:"
idx = src2.find(marker_def)
if idx == -1:
    print("[ERR] _build_geopolitical_result_inner introuvable apres rename")
    sys.exit(1)

src3 = src2[:idx] + wrapper + src2[idx:]

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

print("[OK] " + MARKER + " applique: wrapper _build_geopolitical_result avec _build_lock")
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
