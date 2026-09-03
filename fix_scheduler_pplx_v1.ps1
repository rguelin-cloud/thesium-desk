# [SCHEDULER_PPLX_V1] Ajoute deux jobs au scheduler APScheduler dans api_server.py:
#   refresh_pplx_crypto   (toutes les 4h)
#   refresh_pplx_factor   (toutes les 24h)
# Idempotent, AST valide, rollback auto.

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$target = Join-Path $root "api_server.py"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak_schedpplx_$ts"

Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

$helper = Join-Path $env:TEMP "sched_pplx_$ts.py"

$pyCode = @'
import io, re, sys, ast

TARGET = r"__TARGET__"
MARKER = "[SCHEDULER_PPLX_V1]"

with io.open(TARGET, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER in src:
    print("[SKIP] Patch deja applique")
    sys.exit(0)

# 1) Trouver la ligne contenant scheduler.add_job(refresh_geo, ...)
# Et inserer juste apres deux nouveaux jobs + leurs fonctions wrappers.
marker_line = "scheduler.add_job(refresh_geo,"
if marker_line not in src:
    print("[ERR] Ligne marker scheduler.add_job(refresh_geo introuvable")
    sys.exit(1)

# On detecte l'indentation de la ligne marker
lines = src.splitlines(keepends=True)
idx_marker = None
indent_marker = ""
for i, ln in enumerate(lines):
    if marker_line in ln:
        idx_marker = i
        indent_marker = ln[:len(ln) - len(ln.lstrip())]
        break

if idx_marker is None:
    print("[ERR] idx_marker non trouve")
    sys.exit(1)

# 2) Ajouter les wrappers refresh_pplx_crypto et refresh_pplx_factor
# Juste avant scheduler.add_job lines (apres les autres def refresh_*).
# On trouve la position du def refresh_geo() pour s'aligner
geo_def_match = re.search(r"(\s*def refresh_geo\(\):\s*\n(?:\s+.*\n)+?(?=\s*scheduler\.add_job|\n\s*#))", src)

# Plus robuste: on trouve "def refresh_geo(" et on prend tout le bloc indente apres.
def_pattern = re.compile(r"^([ \t]+)def refresh_geo\(\):\s*\n", re.M)
m = def_pattern.search(src)
if not m:
    print("[ERR] def refresh_geo introuvable")
    sys.exit(1)
indent_def = m.group(1)

# Trouver fin du bloc refresh_geo (ligne non-indentee de plus que indent_def+4 ou ligne vide suivie de def/scheduler)
start_def = m.end()
# Lire jusqu'a ce qu'on trouve une ligne au meme niveau d'indentation (commence par indent_def + caractere non-espace)
end_def = start_def
src_lines = src.splitlines(keepends=True)
# Trouver la ligne ou commence le def
running_idx = src[:start_def].count("\n")
inner_indent = indent_def + "    "
for j in range(running_idx, len(src_lines)):
    ln = src_lines[j]
    if ln.strip() == "":
        continue
    if not ln.startswith(inner_indent) and not ln.startswith(indent_def + "\t"):
        # Premiere ligne hors du corps -> on s'arrete avant elle
        end_def = sum(len(x) for x in src_lines[:j])
        break
else:
    end_def = len(src)

new_defs = f'''
{indent_def}def refresh_pplx_crypto():
{indent_def}    """{MARKER} Refresh contexte Perplexity pour cryptos."""
{indent_def}    try:
{indent_def}        print("[scheduler] Refreshing Perplexity crypto contexts...")
{indent_def}        from pplx_crypto_agent import refresh_all_crypto_contexts
{indent_def}        refresh_all_crypto_contexts(ttl_hours=4)
{indent_def}    except Exception as e:
{indent_def}        print(f"[scheduler] PPLX crypto refresh error: {{e}}")

{indent_def}def refresh_pplx_factor():
{indent_def}    """{MARKER} Refresh contexte Perplexity qualite pour equities."""
{indent_def}    try:
{indent_def}        print("[scheduler] Refreshing Perplexity factor quality contexts...")
{indent_def}        from pplx_factor_agent import refresh_all_quality_contexts
{indent_def}        refresh_all_quality_contexts(ttl_hours=24)
{indent_def}    except Exception as e:
{indent_def}        print(f"[scheduler] PPLX factor refresh error: {{e}}")

'''

src2 = src[:end_def] + new_defs + src[end_def:]

# 3) Ajouter les add_job apres celui de refresh_geo
new_add_jobs = (
    indent_marker + "scheduler.add_job(refresh_pplx_crypto, 'interval', hours=4,  id='refresh_pplx_crypto', next_run_time=_now + _td(minutes=2))\n"
    + indent_marker + "scheduler.add_job(refresh_pplx_factor, 'interval', hours=24, id='refresh_pplx_factor', next_run_time=_now + _td(minutes=5))\n"
)

# On trouve la fin de la ligne add_job(refresh_geo, ...) dans src2 (decalee par new_defs)
geo_addjob_match = re.search(r"scheduler\.add_job\(refresh_geo,[^\n]*\n", src2)
if not geo_addjob_match:
    print("[ERR] scheduler.add_job(refresh_geo introuvable apres patch")
    sys.exit(1)
insert_pos = geo_addjob_match.end()
src3 = src2[:insert_pos] + new_add_jobs + src2[insert_pos:]

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

print("[OK] " + MARKER + " applique: refresh_pplx_crypto (4h) + refresh_pplx_factor (24h)")
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
