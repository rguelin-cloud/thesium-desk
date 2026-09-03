# [FIX_RUN_AGENTS_THESIS_CHALLENGE_V2] Patche run_agents_endpoint pour challenger les top-N theses
# apres chaque cycle reussi.
# V2 : detection d'indentation plus robuste (pas dependante de "conn = db()")
# Marqueur : [THESIS_CHALLENGE_V2]
$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
$backup = "$target.bak_thesisch_v2_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

if (-not (Test-Path $target)) { Write-Host "[ERR] $target introuvable" -ForegroundColor Red; exit 1 }
Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

$helper = Join-Path $env:TEMP "thesis_challenge_patch_v2_$(Get-Random).py"
$helperCode = @'
import re, sys, ast
from pathlib import Path

target = Path(sys.argv[1])
src = target.read_text(encoding="utf-8-sig")
MARKER = "[THESIS_CHALLENGE_V2]"

# Skip si V1 ou V2 deja la
if MARKER in src or "[THESIS_CHALLENGE_V1]" in src:
    print(f"[SKIP] marker challenge deja present (V1 ou V2)")
    sys.exit(0)

# Localiser la fonction run_agents_endpoint
needle = "def run_agents_endpoint"
idx = src.find(needle)
if idx < 0:
    print("[ERR] def run_agents_endpoint introuvable")
    sys.exit(2)

# Trouver la fin de la fonction = prochain "\n@app." ou "\ndef " au meme niveau d'indent
# Strategie simple : prochain "@app." apres run_agents_endpoint
next_route = src.find("\n@app.", idx + len(needle))
if next_route < 0:
    next_route = len(src)

func_body = src[idx:next_route]

# Detecter l'indentation des statements dans la fonction
# On cherche la 1ere ligne indentee apres la signature
sig_end = func_body.find(":\n")
if sig_end < 0:
    print("[ERR] Signature de fonction mal formee")
    sys.exit(3)
after_sig = func_body[sig_end+2:]
indent_match = re.match(r"(\s+)\S", after_sig)
if not indent_match:
    print("[ERR] Indent corps non detectee")
    sys.exit(4)
indent = indent_match.group(1)
# Si plus de 8 espaces, c'est probablement docstring : essayer la ligne suivante
if len(indent) > 12:
    lines = after_sig.split("\n")
    for ln in lines[1:]:
        if ln.strip() and not ln.lstrip().startswith(('"""', "'''")):
            m2 = re.match(r"(\s+)\S", ln)
            if m2:
                indent = m2.group(1)
                break

print(f"[DEBUG] Indentation detectee: {len(indent)} espaces")

# Trouver le bloc "return" final (dernier return au niveau de la fonction)
# Pattern : \n<indent>return <quelque chose>
return_pattern = re.compile(rf"\n{re.escape(indent)}return\s", re.MULTILINE)
returns = list(return_pattern.finditer(func_body))
if not returns:
    # Plan B : essayer return sans espace apres (ex: "return{")
    return_pattern2 = re.compile(rf"\n{re.escape(indent)}return\b", re.MULTILINE)
    returns = list(return_pattern2.finditer(func_body))
    if not returns:
        print(f"[ERR] Aucun return trouve a l'indentation '{indent}' ({len(indent)} espaces)")
        # Debug : afficher les 10 premieres lignes indentees
        for i, line in enumerate(func_body.split("\n")[:30]):
            print(f"  L{i}: '{line[:80]}'")
        sys.exit(5)

last_return = returns[-1]
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
