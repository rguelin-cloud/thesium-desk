# [GDELT_FIX_V4] Capture ConnectionError + Connection:close + delai 30s sur reset TCP
# Idempotent, AST valide, rollback auto

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$src  = Join-Path $root "data_geopolitical.py"
if (-not (Test-Path $src)) { throw "Fichier introuvable : $src" }

$bak = Join-Path $root ("data_geopolitical.py.bak_v4_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
Copy-Item $src $bak -Force
Write-Host "[BACKUP] $bak" -ForegroundColor Cyan

$preCheck = py -3.13 -c "import ast; ast.parse(open(r'$src',encoding='utf-8-sig').read()); print('AST_OK')"
if ($preCheck -notmatch "AST_OK") { Write-Host "[ERR] AST initial KO" -ForegroundColor Red; exit 1 }

$pyPatch = @'
import re, sys, io, ast
from datetime import datetime

src = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_geopolitical.py"

with io.open(src, "r", encoding="utf-8-sig") as f:
    content = f.read()

if "[GDELT_FIX_V4]" in content:
    print("SKIP_ALREADY_PATCHED")
    sys.exit(0)

changes = []

# --- Patch 1 : remplacer le requests.get par un appel via Session avec Connection:close
old1 = 'resp = requests.get(GDELT_GKG_API, params=params, timeout=45, headers={"User-Agent": "NEXTONES-thesium/1.0"})'
new1 = (
    '# [GDELT_FIX_V4] Session jetable + Connection:close pour eviter le pool TLS qui se fait killer\n'
    '                _sess = requests.Session()\n'
    '                _sess.headers.update({"User-Agent": "NEXTONES-thesium/1.0", "Connection": "close"})\n'
    '                try:\n'
    '                    resp = _sess.get(GDELT_GKG_API, params=params, timeout=45)\n'
    '                finally:\n'
    '                    _sess.close()'
)
if old1 in content:
    content = content.replace(old1, new1, 1)
    changes.append("1:session-close")
else:
    print("WARN_PATCH_1_NOT_FOUND")

# --- Patch 2 : ajouter except ConnectionError APRES except Timeout
# On cherche le bloc Timeout et on ajoute ConnectionError juste derriere
pat2 = re.compile(
    r"(except requests\.exceptions\.Timeout:\s*\n"
    r"\s*print\(f\"\[GDELT\] Timeout \(attempt \{attempt\+1\}\) for: \{q\[:60\]\}\"\)\s*\n"
    r"\s*_gdelt_last_call = _time\.time\(\)[^\n]*\n"
    r"\s*if attempt < max_retries - 1:\s*\n"
    r"\s*continue)"
)
m = pat2.search(content)
if m:
    inject = (
        m.group(1) + "\n"
        '            except (requests.exceptions.ConnectionError, ConnectionResetError) as _ce:  # [GDELT_FIX_V4]\n'
        '                print(f"[GDELT] ConnectionReset (attempt {attempt+1}) for: {q[:60]} - {type(_ce).__name__}")\n'
        '                _gdelt_last_call = _time.time() + 30.0  # pause longue 30s avant retry\n'
        '                if attempt < max_retries - 1:\n'
        '                    continue'
    )
    content = content[:m.start()] + inject + content[m.end():]
    changes.append("2:catch-connection-error")
else:
    # Tentative plus laxe si V3 n'avait pas pris
    pat2b = re.compile(
        r"(except requests\.exceptions\.Timeout:\s*\n"
        r"\s*print\(f\"\[GDELT\] Timeout \(attempt \{attempt\+1\}\) for: \{q\[:60\]\}\"\)\s*\n"
        r"\s*if attempt < max_retries - 1:\s*\n"
        r"\s*continue)"
    )
    m2 = pat2b.search(content)
    if m2:
        inject = (
            m2.group(1) + "\n"
            '            except (requests.exceptions.ConnectionError, ConnectionResetError) as _ce:  # [GDELT_FIX_V4]\n'
            '                print(f"[GDELT] ConnectionReset (attempt {attempt+1}) for: {q[:60]} - {type(_ce).__name__}")\n'
            '                _gdelt_last_call = _time.time() + 30.0\n'
            '                if attempt < max_retries - 1:\n'
            '                    continue'
        )
        content = content[:m2.start()] + inject + content[m2.end():]
        changes.append("2b:catch-connection-error-fallback")
    else:
        print("WARN_PATCH_2_NOT_FOUND")

# --- Patch 3 : delai mini bumpe a 10/20/30s pour aerer
old3 = "min_delay = 8.0 + (attempt * 8.0)"
new3 = "min_delay = 10.0 + (attempt * 10.0)  # [GDELT_FIX_V4] 10/20/30s entre essais"
if old3 in content:
    content = content.replace(old3, new3, 1)
    changes.append("3:min-delay-10-20-30")
else:
    # Si V3 n'a pas pris, on cible la version originale
    old3b = "min_delay = 6.0 + (attempt * 5.0)"
    new3b = "min_delay = 10.0 + (attempt * 10.0)  # [GDELT_FIX_V4] 10/20/30s"
    if old3b in content:
        content = content.replace(old3b, new3b, 1)
        changes.append("3b:min-delay-from-orig")

# --- Marqueur de tete
stamp = "# [GDELT_FIX_V4] applied " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " - " + ",".join(changes)
m = re.match(r'^("""[\s\S]*?""")', content)
if m:
    content = content[:m.end()] + "\n" + stamp + "\n" + content[m.end():]
else:
    content = stamp + "\n" + content

# Validation AST
try:
    ast.parse(content)
except SyntaxError as e:
    print("ERR_AST:", e)
    sys.exit(3)

if not changes:
    print("ERR_NO_CHANGES")
    sys.exit(4)

with io.open(src, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)

print("OK_PATCHED:" + ",".join(changes))
'@

$pyFile = Join-Path $env:TEMP "patch_gdelt_v4.py"
[System.IO.File]::WriteAllText($pyFile, $pyPatch, (New-Object System.Text.UTF8Encoding $false))

$result = py -3.13 $pyFile
Remove-Item $pyFile -Force

Write-Host ""
if ($result -match "OK_PATCHED") {
    Write-Host "[OK] V4 applique : $result" -ForegroundColor Green
} elseif ($result -match "SKIP_ALREADY_PATCHED") {
    Write-Host "[SKIP] Deja patche" -ForegroundColor Yellow
} else {
    Write-Host "[ERR] $result" -ForegroundColor Red
    Copy-Item $bak $src -Force
    Write-Host "[ROLLBACK] depuis $bak" -ForegroundColor Yellow
    exit 1
}

$finalCheck = py -3.13 -c "import ast; ast.parse(open(r'$src',encoding='utf-8-sig').read()); print('AST_FINAL_OK')"
if ($finalCheck -notmatch "AST_FINAL_OK") {
    Write-Host "[ERR] AST final KO : $finalCheck" -ForegroundColor Red
    Copy-Item $bak $src -Force
    exit 1
}
Write-Host "[OK] AST final valide" -ForegroundColor Green

Write-Host ""
Write-Host "Changements :" -ForegroundColor Cyan
Write-Host "  1) Session jetable + Connection:close (evite pool TLS killed)"
Write-Host "  2) Catch ConnectionError / ConnectionResetError + delai 30s"
Write-Host "  3) Throttle de base 10/20/30s entre essais"
Write-Host ""
Write-Host "Redemarre uvicorn :" -ForegroundColor Yellow
Write-Host "  py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000"
