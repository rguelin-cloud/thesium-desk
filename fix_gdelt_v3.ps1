# [GDELT_FIX_V3] Corrige le throttling 429 + sequentialise les requetes
# Idempotent. Restaure le backup au besoin, valide AST avant ecriture.

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$src  = Join-Path $root "data_geopolitical.py"

if (-not (Test-Path $src)) { throw "Fichier introuvable : $src" }

# Backup horodate
$bak = Join-Path $root ("data_geopolitical.py.bak_v3_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
Copy-Item $src $bak -Force
Write-Host "[BACKUP] $bak" -ForegroundColor Cyan

# Verification AST initiale
$preCheck = py -3.13 -c "import ast; ast.parse(open(r'$src',encoding='utf-8-sig').read()); print('AST_OK')"
if ($preCheck -notmatch "AST_OK") {
    Write-Host "[ERR] Fichier initialement invalide. Stop." -ForegroundColor Red
    exit 1
}

$pyPatch = @'
import re, sys, io, ast
from datetime import datetime

src = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_geopolitical.py"

with io.open(src, "r", encoding="utf-8-sig") as f:
    content = f.read()

if "[GDELT_FIX_V3]" in content:
    print("SKIP_ALREADY_PATCHED")
    sys.exit(0)

changes = []

# --- Patch A : sur 429, mettre a jour _gdelt_last_call POUR forcer le throttle suivant ---
# Avant: si 429 et attempt < max-1, on fait juste "continue" sans MAJ timestamp
# => prochaine iteration ne respecte pas le min_delay grandissant
# Apres: on MAJ _gdelt_last_call AVANT continue pour que le delai s'applique

old_a = (
    'if resp.status_code == 429:\n'
    '                    print(f"[GDELT] 429 rate limit (attempt {attempt+1}/{max_retries}) for: {q[:60]}")\n'
    '                    # Don\'t update last_call timestamp \u2014 the request was rejected\n'
    '                    if attempt < max_retries - 1:\n'
    '                        continue  # Will retry with longer delay\n'
    '                    else:\n'
    '                        print(f"[GDELT] All retries exhausted for: {q[:60]}")\n'
    '                        return {}'
)
new_a = (
    'if resp.status_code == 429:\n'
    '                    # [GDELT_FIX_V3] On MAJ le timestamp pour forcer le throttle plus long au prochain essai\n'
    '                    _gdelt_last_call = _time.time()\n'
    '                    print(f"[GDELT] 429 rate limit (attempt {attempt+1}/{max_retries}) for: {q[:60]}")\n'
    '                    if attempt < max_retries - 1:\n'
    '                        continue\n'
    '                    else:\n'
    '                        print(f"[GDELT] All retries exhausted for: {q[:60]}")\n'
    '                        return {}'
)

# Comme ce bloc utilise des guillemets/dashes, on cherche par regex tolerante
pat_a = re.compile(
    r'if resp\.status_code == 429:\s*\n'
    r'\s*print\(f"\[GDELT\] 429 rate limit \(attempt \{attempt\+1\}/\{max_retries\}\) for: \{q\[:60\]\}"\)\s*\n'
    r"\s*# Don't update last_call timestamp.*?\n"
    r'\s*if attempt < max_retries - 1:\s*\n'
    r'\s*continue.*?\n'
    r'\s*else:\s*\n'
    r'\s*print\(f"\[GDELT\] All retries exhausted for: \{q\[:60\]\}"\)\s*\n'
    r'\s*return \{\}'
)
m = pat_a.search(content)
if m:
    content = content[:m.start()] + new_a + content[m.end():]
    changes.append("A:429-timestamp-update")
else:
    print("WARN_PATCH_A_NOT_FOUND")

# --- Patch B : augmenter min_delay de base : 6/11/16 -> 8/16/25 ---
old_b = "min_delay = 6.0 + (attempt * 5.0)"
new_b = "min_delay = 8.0 + (attempt * 8.0)  # [GDELT_FIX_V3] 8s/16s/24s entre essais"
if old_b in content:
    content = content.replace(old_b, new_b, 1)
    changes.append("B:min_delay-8/16/24")
else:
    print("WARN_PATCH_B_NOT_FOUND")

# --- Patch C : sur Timeout, MAJ aussi _gdelt_last_call pour eviter retry trop rapproche ---
# On cherche le bloc except Timeout
pat_c = re.compile(
    r'except requests\.exceptions\.Timeout:\s*\n'
    r'\s*print\(f"\[GDELT\] Timeout \(attempt \{attempt\+1\}\) for: \{q\[:60\]\}"\)\s*\n'
    r'\s*if attempt < max_retries - 1:\s*\n'
    r'\s*continue'
)
new_c = (
    'except requests.exceptions.Timeout:\n'
    '                print(f"[GDELT] Timeout (attempt {attempt+1}) for: {q[:60]}")\n'
    '                _gdelt_last_call = _time.time()  # [GDELT_FIX_V3] espace les retry post-timeout\n'
    '                if attempt < max_retries - 1:\n'
    '                    continue'
)
m = pat_c.search(content)
if m:
    content = content[:m.start()] + new_c + content[m.end():]
    changes.append("C:timeout-timestamp-update")
else:
    print("WARN_PATCH_C_NOT_FOUND")

# --- Marqueur en tete (apres docstring du module) ---
stamp = "# [GDELT_FIX_V3] applied " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " - " + ",".join(changes)
m = re.match(r'^("""[\s\S]*?""")', content)
if m:
    content = content[:m.end()] + "\n" + stamp + "\n" + content[m.end():]
else:
    content = stamp + "\n" + content

# --- Validation AST avant ecriture ---
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

$pyFile = Join-Path $env:TEMP "patch_gdelt_v3.py"
[System.IO.File]::WriteAllText($pyFile, $pyPatch, (New-Object System.Text.UTF8Encoding $false))

$result = py -3.13 $pyFile
Remove-Item $pyFile -Force

Write-Host ""
if ($result -match "OK_PATCHED") {
    Write-Host "[OK] Patch V3 applique : $result" -ForegroundColor Green
} elseif ($result -match "SKIP_ALREADY_PATCHED") {
    Write-Host "[SKIP] Deja patche" -ForegroundColor Yellow
} else {
    Write-Host "[ERR] $result" -ForegroundColor Red
    Write-Host "Restauration depuis $bak ..." -ForegroundColor Yellow
    Copy-Item $bak $src -Force
    exit 1
}

# Double check AST
$finalCheck = py -3.13 -c "import ast; ast.parse(open(r'$src',encoding='utf-8-sig').read()); print('AST_FINAL_OK')"
if ($finalCheck -match "AST_FINAL_OK") {
    Write-Host "[OK] Verification AST finale : OK" -ForegroundColor Green
} else {
    Write-Host "[ERR] AST final KO : $finalCheck" -ForegroundColor Red
    Copy-Item $bak $src -Force
    Write-Host "[ROLLBACK] Fichier restaure depuis $bak" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Resume des changements :" -ForegroundColor Cyan
Write-Host "  A) Sur 429 : _gdelt_last_call MAJ pour vrai backoff progressif"
Write-Host "  B) Delais min : 8s / 16s / 24s entre essais (au lieu de 6/11/16)"
Write-Host "  C) Sur Timeout : _gdelt_last_call MAJ aussi"
Write-Host ""
Write-Host "Redemarre uvicorn :" -ForegroundColor Yellow
Write-Host "  py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000"
