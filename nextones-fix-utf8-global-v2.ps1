# nextones-fix-utf8-global-v2.ps1
# Corrige le double-encoding UTF-8 sur :
#   - index.html, app.js, *.html, *.js, *.css  (tous)
#   - api_server.py, api_server_with_static.py, execution_engine.py, execution_engine_v6_5.py
# Exclut explicitement :
#   - _backups_*/ folders
#   - .bak_* files
#   - nextones-diag-utf8*, diag_utf8* (faux positifs)
#   - node_modules, .venv, __pycache__

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"

$helper = Join-Path $env:TEMP "fix_utf8_v2_$ts.py"
$helperContent = @'
# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
TS = sys.argv[2]

SIGNATURES = [
    "Ã©", "Ã¨", "Ã ", "Ã®", "Ã´", "Ã»", "Ã§",
    "Ã‰", "Ãˆ", "Ã€",
    "â€™", "â€\"", "â€¦", "â€¢",
    "ðŸ", "â¿",
]

def is_mojibake(text):
    return any(sig in text for sig in SIGNATURES)

def fix_mojibake(text):
    try:
        fixed = text.encode("latin-1", errors="strict").decode("utf-8", errors="strict")
        if not is_mojibake(fixed):
            return fixed, 1
        # 2e passe si triple-encoding
        try:
            fixed2 = fixed.encode("latin-1", errors="strict").decode("utf-8", errors="strict")
            if not is_mojibake(fixed2):
                return fixed2, 2
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        return fixed, 1
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text, 0

# Cible explicite : extensions ET fichiers Python autorisés
HTML_JS_CSS_EXT = {".html", ".js", ".css"}
ALLOWED_PY_FILES = {
    "api_server.py",
    "api_server_with_static.py",
    "execution_engine.py",
    "execution_engine_v6_5.py",
}

# Patterns d'exclusion
def should_skip(p: Path) -> tuple[bool, str]:
    name = p.name
    parts = set(p.parts)
    # Backup folders
    if any(part.startswith("_backups_") for part in p.parts):
        return True, "in _backups_*"
    # Backup files
    if ".bak_" in name or name.endswith(".bak"):
        return True, ".bak file"
    # Outils diag UTF8 (faux positifs)
    if "diag_utf8" in name or "diag-utf8" in name:
        return True, "diag_utf8 (false positive)"
    if "fix_utf8" in name or "fix-utf8" in name:
        return True, "fix_utf8 helper"
    # Le script de diag actuel
    if "nextones-diag-utf8" in name:
        return True, "current diag script"
    # node_modules, venv
    if "node_modules" in parts or ".venv" in parts or "__pycache__" in parts:
        return True, "vendor folder"
    return False, ""

# Collecte fichiers
candidates = []
for ext in HTML_JS_CSS_EXT:
    for p in ROOT.rglob(f"*{ext}"):
        skip, reason = should_skip(p)
        if skip:
            continue
        candidates.append(p)

for fname in ALLOWED_PY_FILES:
    p = ROOT / fname
    if p.exists():
        skip, reason = should_skip(p)
        if not skip:
            candidates.append(p)

print(f"=== {len(candidates)} fichiers à examiner ===\n")

total = 0
fixed_count = 0
skipped = 0
errors = []

for p in candidates:
    total += 1
    try:
        raw_bytes = p.read_bytes()
    except Exception as e:
        errors.append((p, f"read_bytes: {e}"))
        continue
    has_bom = raw_bytes.startswith(b'\xef\xbb\xbf')
    if has_bom:
        raw_bytes = raw_bytes[3:]
    try:
        text = raw_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        errors.append((p, f"decode utf-8: {e}"))
        continue
    if not is_mojibake(text):
        skipped += 1
        continue
    before_hits = sum(text.count(sig) for sig in SIGNATURES)
    # Backup
    backup_path = p.with_name(p.name + f".bak_utf8_{TS}")
    backup_path.write_bytes((b'\xef\xbb\xbf' if has_bom else b'') + raw_bytes)
    # Fix
    fixed_text, n_pass = fix_mojibake(text)
    after_hits = sum(fixed_text.count(sig) for sig in SIGNATURES)
    # Écrit sans BOM
    p.write_text(fixed_text, encoding="utf-8", newline="\n")
    fixed_count += 1
    rel = p.relative_to(ROOT)
    status = "OK" if after_hits == 0 else f"residual {after_hits}"
    print(f"  [pass={n_pass}] {rel} : {before_hits} -> {after_hits} mojibake ({status})")

print(f"\n=== RESUME ===")
print(f"  Examinés : {total}")
print(f"  Corrigés : {fixed_count}")
print(f"  Propres (skip) : {skipped}")
if errors:
    print(f"  Erreurs : {len(errors)}")
    for p, e in errors:
        print(f"    {p.relative_to(ROOT)}: {e}")
'@

Set-Content -Path $helper -Value $helperContent -Encoding UTF8

Write-Host "[1/2] Helper -> $helper"
Write-Host "[2/2] Exécution..."
Write-Host ""

py -3.13 $helper $root $ts

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[KO] Helper a echoue" -ForegroundColor Red
    exit 1
}

# Validation syntaxe des .py modifiés
Write-Host ""
Write-Host "[VALIDATION] Syntaxe Python..."
foreach ($f in @("api_server.py", "api_server_with_static.py", "execution_engine.py", "execution_engine_v6_5.py")) {
    $full = Join-Path $root $f
    if (Test-Path $full) {
        py -3.13 -c "import ast; ast.parse(open(r'$full', encoding='utf-8').read()); print('  [OK] $f')"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  [KO] $f - syntaxe cassée par le fix UTF-8" -ForegroundColor Red
            # Auto-restore
            $bak = Get-ChildItem "$root\$f.bak_utf8_$ts" -ErrorAction SilentlyContinue
            if ($bak) {
                Copy-Item $bak.FullName $full -Force
                Write-Host "    Restauré depuis $($bak.Name)" -ForegroundColor Yellow
            }
        }
    }
}

Write-Host ""
Write-Host "=== TERMINE ===" -ForegroundColor Green
Write-Host ""
Write-Host "1. Redemarre l'API (les .py corriges doivent etre rechargees)"
Write-Host "2. Hard refresh navigateur (Ctrl+F5)"
