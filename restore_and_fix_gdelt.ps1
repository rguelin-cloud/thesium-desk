# [GDELT_TIMEOUT_FIX_V2] Restaure depuis backup + applique patch via Python
# Plus sur que le V1 (qui cassait les triple-quotes de la docstring)

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$src  = Join-Path $root "data_geopolitical.py"

# --- Etape 1 : retrouver le dernier backup .bak_YYYYMMDD_HHmmss ---
$backups = Get-ChildItem -Path $root -Filter "data_geopolitical.py.bak_*" |
           Sort-Object LastWriteTime -Descending
if ($backups.Count -eq 0) {
    Write-Host "[ERR] Aucun backup trouve. Verifier manuellement." -ForegroundColor Red
    exit 1
}
$latest = $backups[0].FullName
Write-Host "[BACKUP] Restauration depuis : $latest" -ForegroundColor Cyan
Copy-Item $latest $src -Force

# --- Etape 2 : verifier que le fichier restaure est syntaxiquement valide ---
$check = py -3.13 -c "import ast; ast.parse(open(r'$src',encoding='utf-8-sig').read()); print('AST_OK')"
if ($check -notmatch "AST_OK") {
    Write-Host "[ERR] Backup lui-meme invalide. Stop." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Backup restaure et valide" -ForegroundColor Green

# --- Etape 3 : ecrire un script Python qui fait le patch proprement ---
$pyPatch = @'
import re, sys, io, ast
from datetime import datetime

src = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_geopolitical.py"

with io.open(src, "r", encoding="utf-8-sig") as f:
    content = f.read()

# Marqueur d'idempotence
if "[GDELT_TIMEOUT_FIX_V2]" in content:
    print("SKIP_ALREADY_PATCHED")
    sys.exit(0)

# Patch 1 : timeout=20 -> timeout=45 + UA
old_pat = re.compile(
    r"resp\s*=\s*requests\.get\(GDELT_GKG_API,\s*params=params,\s*timeout=20\)"
)
new_line = (
    'resp = requests.get(GDELT_GKG_API, params=params, timeout=45, '
    'headers={"User-Agent": "NEXTONES-thesium/1.0"})'
)

if not old_pat.search(content):
    print("ERR_PATTERN_NOT_FOUND")
    sys.exit(2)

content = old_pat.sub(new_line, content, count=1)

# Ajout du marqueur en tete (apres la docstring du module)
stamp = "# [GDELT_TIMEOUT_FIX_V2] applied " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
# On insere apres la fin de la docstring du module si elle existe
m = re.match(r'^("""[\s\S]*?""")', content)
if m:
    content = content[:m.end()] + "\n" + stamp + "\n" + content[m.end():]
else:
    content = stamp + "\n" + content

# Validation AST avant ecriture
try:
    ast.parse(content)
except SyntaxError as e:
    print("ERR_AST:", e)
    sys.exit(3)

with io.open(src, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)

print("OK_PATCHED")
'@

$pyFile = Join-Path $env:TEMP "patch_gdelt.py"
[System.IO.File]::WriteAllText($pyFile, $pyPatch, (New-Object System.Text.UTF8Encoding $false))

$result = py -3.13 $pyFile
Remove-Item $pyFile -Force

Write-Host ""
if ($result -match "OK_PATCHED") {
    Write-Host "[OK] Patch applique : timeout 20 -> 45s + User-Agent" -ForegroundColor Green
} elseif ($result -match "SKIP_ALREADY_PATCHED") {
    Write-Host "[SKIP] Deja patche" -ForegroundColor Yellow
} else {
    Write-Host "[ERR] $result" -ForegroundColor Red
    exit 1
}

# --- Etape 4 : double-check AST final ---
$finalCheck = py -3.13 -c "import ast; ast.parse(open(r'$src',encoding='utf-8-sig').read()); print('AST_FINAL_OK')"
if ($finalCheck -match "AST_FINAL_OK") {
    Write-Host "[OK] Verification AST finale : OK" -ForegroundColor Green
} else {
    Write-Host "[ERR] AST final KO : $finalCheck" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Relance uvicorn :" -ForegroundColor Yellow
Write-Host "  py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000"
