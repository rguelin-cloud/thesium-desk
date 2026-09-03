# [FIX_RUN_AGENTS_THESIS_CHALLENGE_V1] Patche run_agents_endpoint pour challenger les top-N theses
# apres chaque cycle reussi (apres le verrou).
# Marqueur : [THESIS_CHALLENGE_V1]
$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
$backup = "$target.bak_thesisch_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

if (-not (Test-Path $target)) { Write-Host "[ERR] $target introuvable" -ForegroundColor Red; exit 1 }
Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

$helper = Join-Path $env:TEMP "thesis_challenge_patch_$(Get-Random).py"
$helperCode = @'
import re, sys, ast
from pathlib import Path

target = Path(sys.argv[1])
src = target.read_text(encoding="utf-8-sig")
MARKER = "[THESIS_CHALLENGE_V1]"

if MARKER in src:
    print(f"[SKIP] {MARKER} deja present")
    sys.exit(0)

# Localiser le `return` de run_agents_endpoint (le dernier return avant la prochaine route)
# Strategie : trouver "def run_agents_endpoint" puis chercher le 1er "return" suffisamment loin
needle = "def run_agents_endpoint"
idx = src.find(needle)
if idx < 0:
    print("[ERR] def run_agents_endpoint introuvable")
    sys.exit(2)

# Chercher le prochain "@app." apres run_agents_endpoint pour delimiter la fonction
next_route = src.find("\n@app.", idx)
if next_route < 0:
    next_route = len(src)

func_body = src[idx:next_route]

# Detecter indentation
indent_match = re.search(r"\n(    +)conn = db\(\)", func_body)
if not indent_match:
    print("[ERR] Indent corps non trouvee")
    sys.exit(3)
indent = indent_match.group(1)

# Trouver le bloc "return" final (dernier "return" avant la prochaine route)
return_pattern = re.compile(rf"\n{re.escape(indent)}return\s+", re.MULTILINE)
returns = list(return_pattern.finditer(func_body))
if not returns:
    print("[ERR] Aucun return dans run_agents_endpoint")
    sys.exit(4)

last_return = returns[-1]
# Position absolue du return dans src
abs_return_pos = idx + last_return.start() + 1  # +1 pour skip le \n initial

# Bloc a inserer juste AVANT le return final
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
    start = max(0, e.lineno - 3)
    end = min(len(lines), e.lineno + 3)
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
