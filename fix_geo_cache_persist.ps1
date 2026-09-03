# [GEO_CACHE_PERSIST_V2] Persiste _geo_cache sur disque pour resister aux redemarrages
# Idempotent, AST valide, rollback auto.

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$target = Join-Path $root "api_server.py"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak_geo_$ts"

if (-not (Test-Path $target)) {
    Write-Host "[ERR] $target introuvable" -ForegroundColor Red
    exit 1
}

Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

$helper = Join-Path $env:TEMP "geo_cache_persist_$ts.py"

# Helper Python: lit le source, patche via regex (preserve l'indentation reelle), valide AST.
$pyCode = @'
import io, os, re, sys, ast, json

TARGET = r"__TARGET__"
MARKER = "[GEO_CACHE_PERSIST_V2]"

with io.open(TARGET, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER in src:
    print("[SKIP] Patch deja applique")
    sys.exit(0)

# 1) Remplacer la declaration du cache par une version persistee
old_decl = '_geo_cache = {"data": None, "ts": 0}'
if old_decl not in src:
    print("[ERR] Declaration _geo_cache introuvable")
    sys.exit(1)

new_decl = '''# ''' + MARKER + '''  Cache persiste sur disque
_GEO_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".geo_cache.json")

def _load_geo_cache():
    try:
        if os.path.exists(_GEO_CACHE_FILE):
            with open(_GEO_CACHE_FILE, "r", encoding="utf-8") as _f:
                _c = json.load(_f)
            if isinstance(_c, dict) and "data" in _c and "ts" in _c:
                print("[GEO-CACHE] Charge depuis disque, age=" + str(int(__import__("time").time() - _c.get("ts", 0))) + "s")
                return _c
    except Exception as _e:
        print("[GEO-CACHE] Lecture disque echouee: " + str(_e))
    return {"data": None, "ts": 0}

def _save_geo_cache(_c):
    try:
        with open(_GEO_CACHE_FILE, "w", encoding="utf-8") as _f:
            json.dump(_c, _f, ensure_ascii=False)
    except Exception as _e:
        print("[GEO-CACHE] Ecriture disque echouee: " + str(_e))

_geo_cache = _load_geo_cache()'''

# On verifie que les imports json/os sont presents en haut du fichier; sinon on les ajoute
needed_imports = []
if not re.search(r"^\s*import\s+json\b", src, re.M):
    needed_imports.append("import json")
if not re.search(r"^\s*import\s+os\b", src, re.M):
    needed_imports.append("import os")

src2 = src.replace(old_decl, new_decl, 1)

if needed_imports:
    # Inserer apres la premiere ligne d'import detectable
    m = re.search(r"(^\s*import\s+\w+[^\n]*\n)", src2, re.M)
    if m:
        inject = "\n".join(needed_imports) + "\n"
        src2 = src2[:m.end()] + inject + src2[m.end():]

# 2) Apres chaque "_geo_cache['ts'] = _t.time()" dans _geo_background_fetch, injecter _save_geo_cache(_geo_cache)
# On capture l'indentation pour la reutiliser.
pattern = re.compile(r'^([ \t]+)_geo_cache\["ts"\]\s*=\s*_t\.time\(\)\s*\n', re.M)

def _inject(m):
    indent = m.group(1)
    return m.group(0) + indent + "_save_geo_cache(_geo_cache)\n"

src3, n = pattern.subn(_inject, src2)
if n < 2:
    print("[ERR] N'a pas trouve les 2 emplacements _geo_cache[ts] = _t.time() (trouve " + str(n) + ")")
    sys.exit(1)

# Validation AST
try:
    ast.parse(src3)
except SyntaxError as e:
    print("[ERR] ERR_AST: " + str(e))
    # Dump 20 lignes autour pour diagnostic
    if e.lineno:
        ls = src3.splitlines()
        a = max(0, e.lineno - 10)
        b = min(len(ls), e.lineno + 10)
        for i in range(a, b):
            print(f"{i+1:5d}|{ls[i]}")
    sys.exit(1)

with io.open(TARGET, "w", encoding="utf-8", newline="\n") as f:
    f.write(src3)

print("[OK] " + MARKER + " applique, " + str(n) + " save_geo_cache injectes")
'@

$pyCode = $pyCode.Replace("__TARGET__", $target.Replace("\","\\"))
Set-Content -Path $helper -Value $pyCode -Encoding UTF8

try {
    & py -3.13 $helper
    if ($LASTEXITCODE -ne 0) {
        throw "Helper Python a echoue (exit $LASTEXITCODE)"
    }

    # Double validation AST cote PowerShell
    & py -3.13 -c "import ast; ast.parse(open(r'$target', encoding='utf-8-sig').read()); print('[AST-OK]')"
    if ($LASTEXITCODE -ne 0) {
        throw "Validation AST finale KO"
    }
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
