# [GEO_DEDUP_V1] Supprime le worker doublon dans api_server.py.
# - get_geopolitical_risk() appelle directement data_geopolitical.fetch_geopolitical_risk()
#   (qui a son propre cache module + connait _bg_fetch_done du startup)
# - Le _geo_cache disque sert de filet de securite si l'appel direct echoue
# - Le scheduler peut continuer d'appeler data_geopolitical.start_background_fetch()
#   sans concurrence cote api_server
# Idempotent, AST valide, rollback auto.

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$target = Join-Path $root "api_server.py"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak_dedup_$ts"

Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

$helper = Join-Path $env:TEMP "geo_dedup_$ts.py"

$pyCode = @'
import io, re, sys, ast

TARGET = r"__TARGET__"
MARKER = "[GEO_DEDUP_V1]"

with io.open(TARGET, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER in src:
    print("[SKIP] Patch deja applique")
    sys.exit(0)

# On remplace le corps de get_geopolitical_risk() par une version qui delegue
# directement a data_geopolitical.fetch_geopolitical_risk(), avec fallback sur _geo_cache.

# Pattern: capture toute la fonction de "@app.get(...)/risk" jusqu'au prochain "@app." ou "def " top-level
fn_pattern = re.compile(
    r'(@app\.get\("/api/geopolitical/risk"\)\s*\n'
    r'def get_geopolitical_risk\(\):.*?)'
    r'(?=\n@app\.|^def\s)', re.S | re.M
)

m = fn_pattern.search(src)
if not m:
    print("[ERR] Fonction get_geopolitical_risk introuvable")
    sys.exit(1)

new_fn = '''@app.get("/api/geopolitical/risk")
def get_geopolitical_risk():
    """Geopolitical Risk Dashboard. ''' + MARKER + '''
    Appelle directement data_geopolitical.fetch_geopolitical_risk() qui gere
    son propre cache module et l'attente du background pre-fetch.
    Le _geo_cache disque sert de fallback si l'appel direct echoue."""
    import time as _t, threading
    try:
        data = data_geopolitical.fetch_geopolitical_risk()
        if data:
            enriched = _enrich_geo_data(data)
            clean = _sanitize_for_json(enriched)
            _geo_cache["data"] = clean
            _geo_cache["ts"] = _t.time()
            _save_geo_cache(_geo_cache)
            return JSONResponse(content=clean)
    except Exception as _e:
        print(f"[GEO-API] fetch direct echoue: {_e}; bascule sur cache disque")

    # Fallback: cache disque persiste
    if _geo_cache.get("data"):
        print("[GEO-API] Sert cache disque (age=" + str(int(_t.time() - _geo_cache.get("ts", 0))) + "s)")
        return JSONResponse(content=_geo_cache["data"])

    raise HTTPException(status_code=503, detail="Donnees geopolitiques en cours de chargement. Rechargez dans 30s.")

'''

src2 = src[:m.start()] + new_fn + src[m.end():]

# Validation AST
try:
    ast.parse(src2)
except SyntaxError as e:
    print("[ERR] ERR_AST: " + str(e))
    if e.lineno:
        ls = src2.splitlines()
        a = max(0, e.lineno - 8)
        b = min(len(ls), e.lineno + 8)
        for i in range(a, b):
            print(f"{i+1:5d}|{ls[i]}")
    sys.exit(1)

with io.open(TARGET, "w", encoding="utf-8", newline="\n") as f:
    f.write(src2)

print("[OK] " + MARKER + " applique: get_geopolitical_risk delegue a data_geopolitical")
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
