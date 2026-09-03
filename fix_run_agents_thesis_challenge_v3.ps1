# [FIX_RUN_AGENTS_THESIS_CHALLENGE_V3] Patche run_agents_endpoint pour challenger les top-N theses
# V3 : recherche tous les "return" dans la fonction (a toute indentation),
#      prend le dernier au niveau le plus a gauche (4 espaces = niveau fonction).
# Marqueur : [THESIS_CHALLENGE_V3]
$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
$backup = "$target.bak_thesisch_v3_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

if (-not (Test-Path $target)) { Write-Host "[ERR] $target introuvable" -ForegroundColor Red; exit 1 }
Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

$helper = Join-Path $env:TEMP "thesis_challenge_patch_v3_$(Get-Random).py"
$helperCode = @'
import re, sys, ast
from pathlib import Path

target = Path(sys.argv[1])
src = target.read_text(encoding="utf-8-sig")
MARKER = "[THESIS_CHALLENGE_V3]"

# Skip si V1, V2 ou V3 deja la
for old in ("[THESIS_CHALLENGE_V1]", "[THESIS_CHALLENGE_V2]", "[THESIS_CHALLENGE_V3]"):
    if old in src:
        print(f"[SKIP] {old} deja present")
        sys.exit(0)

# Localiser la fonction run_agents_endpoint
needle_re = re.compile(r"^def\s+run_agents_endpoint\s*\(", re.MULTILINE)
m = needle_re.search(src)
if not m:
    print("[ERR] def run_agents_endpoint introuvable")
    sys.exit(2)
idx = m.start()

# Trouver la fin = prochain "def " ou "@app." au debut de ligne, ou EOF
end_re = re.compile(r"^(?:def\s|@app\.|class\s)", re.MULTILINE)
end_match = end_re.search(src, idx + 4)
next_route = end_match.start() if end_match else len(src)

func_body = src[idx:next_route]
print(f"[DEBUG] Fonction run_agents_endpoint : {len(func_body)} chars, lignes {src[:idx].count(chr(10))}-{src[:next_route].count(chr(10))}")

# Trouver TOUS les returns dans la fonction, capturer leur indentation
# Pattern : debut de ligne, espaces, "return" suivi d'espace ou fin de ligne
return_re = re.compile(r"^(\s+)return\b", re.MULTILINE)
returns = list(return_re.finditer(func_body))
if not returns:
    print("[ERR] Aucun return trouve dans run_agents_endpoint")
    sys.exit(3)

# Trouver l'indentation minimale (= niveau fonction body)
min_indent = min(len(r.group(1)) for r in returns)
print(f"[DEBUG] {len(returns)} returns trouves, indent min={min_indent}")

# Filtrer : ne garder que les returns au niveau de la fonction (indent min)
top_level_returns = [r for r in returns if len(r.group(1)) == min_indent]
print(f"[DEBUG] {len(top_level_returns)} returns au niveau fonction")

# Prendre le DERNIER (= return final de la fonction)
last_return = top_level_returns[-1]
indent = last_return.group(1)
abs_return_pos = idx + last_return.start()

# Skip le saut de ligne initial si present
if src[abs_return_pos] == "\n":
    abs_return_pos += 1

# Verifier qu'on est bien sur le return
preview = src[abs_return_pos:abs_return_pos+80].replace("\n", "\\n")
print(f"[DEBUG] Insertion juste AVANT : '{preview}'")

# Bloc a inserer
challenge_block = f'''{indent}# {MARKER} Challenge des top-N theses par Perplexity (tolerant)
{indent}try:
{indent}    from pplx_thesis_agent import challenge_top_n as _challenge_top_n
{indent}    _challenge_result = _challenge_top_n(n=5)
{indent}    print(f"[THESIS-CHALLENGE] {{_challenge_result.get('ok',0)}} OK / {{_challenge_result.get('failed',0)}} FAIL en {{_challenge_result.get('elapsed_s',0)}}s")
{indent}except ImportError:
{indent}    print("[THESIS-CHALLENGE] pplx_thesis_agent non installe - skip")
{indent}except Exception as _ce:
{indent}    print(f"[THESIS-CHALLENGE] Erreur (skip): {{_ce}}")
'''

src = src[:abs_return_pos] + challenge_block + src[abs_return_pos:]

# Validation AST
try:
    ast.parse(src)
except SyntaxError as e:
    print(f"[AST-FAIL] ligne {e.lineno}: {e.msg}")
    lines = src.splitlines()
    start = max(0, e.lineno - 5)
    end = min(len(lines), e.lineno + 5)
    for i in range(start, end):
        print(f"  L{i+1}: {lines[i]}")
    sys.exit(5)

target.write_text(src, encoding="utf-8")
print(f"[OK] {MARKER} applique - challenge top-5 auto apres run-agents")
print("[AST-OK]")
'@

Set-Content -Path $helper -Value $helperCode -Encoding UTF8
py -3.13 $helper $target
$rc = $LASTEXITCODE
Remove-Item $helper -Force -ErrorAction SilentlyContinue

if ($rc -ne 0) {
    Write-Host "[ROLLBACK] Restoration depuis $backup" -ForegroundColor Yellow
    Copy-Item $backup $target -Force
    exit $rc
}

Write-Host "[DONE] run_agents_endpoint challenge automatiquement les top-5 theses apres execution" -ForegroundColor Green
