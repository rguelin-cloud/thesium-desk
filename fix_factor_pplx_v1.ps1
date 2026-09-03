# [FACTOR_PPLX_V1] Patch FactorAgent (agents.py) pour mixer Perplexity quality score.
# - Import pplx_factor_agent.get_quality_context
# - Mix 50% quality_inv_vol + 50% (narrative_score/10) si dispo
# - Penalite red_flags: -1 par flag, max -3
# - Si snapshot absent: fallback 100% comportement existant (zero regression)
# - Ajoute champs traceables: quality_inv_vol, quality_narrative, red_flags_count
# Idempotent, AST valide, rollback auto.

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$target = Join-Path $root "agents.py"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak_factorpplx_$ts"

Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

$helper = Join-Path $env:TEMP "factor_pplx_$ts.py"

$pyCode = @'
import io, re, sys, ast

TARGET = r"__TARGET__"
MARKER = "[FACTOR_PPLX_V1]"

with io.open(TARGET, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER in src:
    print("[SKIP] Patch deja applique")
    sys.exit(0)

# 1) Ajouter import en haut du fichier (apres les imports stdlib)
# On insere juste apres "import math" qui est probablement deja la
import_block = '''
# ''' + MARKER + ''' Import optionnel du contexte qualite Perplexity (tolerant a l'absence)
try:
    from pplx_factor_agent import get_quality_context as _pplx_get_quality
except Exception:
    _pplx_get_quality = None
'''

# Inserer avant la premiere "class " ou "def " toplevel
m = re.search(r"^(class |def )", src, re.M)
if not m:
    print("[ERR] Impossible de trouver point d'insertion pour imports")
    sys.exit(1)
src2 = src[:m.start()] + import_block + "\n" + src[m.start():]

# 2) Trouver la ligne quality_score = 10 / (1 + math.exp((vol_20 - 0.30) * 12))
# Capturer son indentation, ajouter juste apres le bloc Perplexity mix.
old_quality = "quality_score = 10 / (1 + math.exp((vol_20 - 0.30) * 12))"
if old_quality not in src2:
    print("[ERR] quality_score formula introuvable")
    sys.exit(1)

# Detecter l'indentation locale (lignes qui contiennent cette formule)
lines = src2.splitlines(keepends=True)
target_indent = None
for i, ln in enumerate(lines):
    if old_quality in ln:
        # Extraire l'indentation
        target_indent = ln[:len(ln) - len(ln.lstrip())]
        break

if target_indent is None:
    print("[ERR] Indentation indeterminable")
    sys.exit(1)

ind = target_indent
mix_block = (
    f"{ind}quality_inv_vol = quality_score  # snapshot avant mix Perplexity\n"
    f"{ind}# {MARKER} Mix Perplexity quality if available\n"
    f"{ind}quality_narrative = None\n"
    f"{ind}red_flags_count = 0\n"
    f"{ind}if _pplx_get_quality is not None:\n"
    f"{ind}    try:\n"
    f"{ind}        _pq = _pplx_get_quality(inst['ticker'])\n"
    f"{ind}        if _pq and _pq.get('quality_score') is not None:\n"
    f"{ind}            quality_narrative = float(_pq['quality_score']) / 10.0  # 0-100 -> 0-10\n"
    f"{ind}            red_flags_count = len(_pq.get('red_flags') or [])\n"
    f"{ind}            # Mix 50/50 quality\n"
    f"{ind}            quality_score = 0.5 * quality_inv_vol + 0.5 * quality_narrative\n"
    f"{ind}            # Penalite red flags (max -3)\n"
    f"{ind}            quality_score = max(0.0, quality_score - min(red_flags_count, 3))\n"
    f"{ind}    except Exception as _e:\n"
    f"{ind}        print(f\"[FactorAgent] PPLX quality fetch echec pour {{inst['ticker']}}: {{_e}}\")\n"
)

# Inserer mix_block juste apres la ligne quality_score = ...
src3 = src2.replace(
    old_quality + "\n",
    old_quality + "\n" + mix_block,
    1
)

# 3) Etendre le dict factor_scores.append({...}) pour exposer les nouveaux champs.
# On cherche "factor_scores.append({" et on injecte les 3 nouveaux champs avant la fermeture "})"
# Plus simple : remplacer la ligne "ticker": inst["ticker"], par une version qui ajoute aussi quality_narrative.
old_append_marker = '"ticker": inst["ticker"],'
if old_append_marker in src3:
    new_append_marker = (
        '"ticker": inst["ticker"],\n'
        + ind + '    "quality_inv_vol": round(quality_inv_vol, 2),\n'
        + ind + '    "quality_narrative": round(quality_narrative, 2) if quality_narrative is not None else None,\n'
        + ind + '    "red_flags_count": red_flags_count,'
    )
    src3 = src3.replace(old_append_marker, new_append_marker, 1)

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

print("[OK] " + MARKER + " applique sur FactorAgent")
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
