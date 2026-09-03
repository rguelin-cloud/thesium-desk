# [FIX_API_THESIS_CHALLENGE_ENDPOINTS_V1] Ajoute 3 endpoints REST pour les challenges
#   GET  /api/pplx/thesis-challenges          -> liste des derniers challenges
#   GET  /api/pplx/thesis-challenge/{id}      -> detail d'un challenge
#   POST /api/pplx/thesis-challenge/{id}      -> declenche manuellement le challenge d'une these
# Met aussi a jour /api/pplx/cycle-snapshot pour inclure les challenges
# Marqueur : [PPLX_THESIS_API_V1]
$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
$backup = "$target.bak_pplxthapi_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

if (-not (Test-Path $target)) { Write-Host "[ERR] $target introuvable" -ForegroundColor Red; exit 1 }
Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

# 1. Bloc d'endpoints (fichier separe)
$blockFile = Join-Path $env:TEMP "pplx_thesis_endpoints_$(Get-Random).py"
$block = @'

# [PPLX_THESIS_API_V1] Endpoints pour les challenges Perplexity sur theses
@app.get("/api/pplx/thesis-challenges")
def pplx_thesis_challenges_list(limit: int = 50):
    """Liste les derniers challenges Perplexity de theses."""
    cx = _pplx_db()
    try:
        rows = cx.execute(
            "SELECT thesis_id, ticker, side, conviction, challenge_score, verdict, "
            "confidence_in_challenge, alternative_thesis, model, ts, source_thesis_summary "
            "FROM thesis_challenge_context ORDER BY ts DESC LIMIT ?",
            (limit,)
        ).fetchall()
    finally:
        cx.close()
    now = _time_pplx.time()
    out = []
    for r in rows:
        d = dict(r)
        d["age_hours"] = round((now - d["ts"]) / 3600.0, 2) if d["ts"] else None
        out.append(d)
    return {"count": len(out), "items": out}


@app.get("/api/pplx/thesis-challenge/{thesis_id}")
def pplx_thesis_challenge_detail(thesis_id: int):
    """Detail complet d'un challenge (counter_arguments, sources, ...)."""
    cx = _pplx_db()
    try:
        row = cx.execute(
            "SELECT * FROM thesis_challenge_context WHERE thesis_id = ?",
            (thesis_id,)
        ).fetchone()
    finally:
        cx.close()
    if not row:
        from fastapi import HTTPException as _HE
        raise _HE(status_code=404, detail="Aucun challenge stocke pour la these " + str(thesis_id))
    d = dict(row)
    for k in ("counter_arguments", "supporting_facts_against", "blind_spots", "citations"):
        if d.get(k):
            d[k] = _pplx_parse_json(d[k])
    if d.get("ts"):
        d["age_hours"] = round((_time_pplx.time() - d["ts"]) / 3600.0, 2)
    return d


@app.post("/api/pplx/thesis-challenge/{thesis_id}")
def pplx_thesis_challenge_trigger(thesis_id: int):
    """Declenche manuellement le challenge d'une these specifique."""
    cx = _pplx_db()
    try:
        row = cx.execute(
            "SELECT t.id, i.ticker, t.proposed_action AS side, t.conviction, "
            "t.rationale, t.agent_type "
            "FROM theses t LEFT JOIN instruments i ON i.id = t.instrument_id "
            "WHERE t.id = ?",
            (thesis_id,)
        ).fetchone()
    finally:
        cx.close()
    if not row:
        from fastapi import HTTPException as _HE
        raise _HE(status_code=404, detail="These " + str(thesis_id) + " introuvable")
    try:
        from pplx_thesis_agent import challenge_one
        data = challenge_one(dict(row))
        if not data:
            from fastapi import HTTPException as _HE
            raise _HE(status_code=502, detail="Challenge Perplexity a echoue (verifier .env et logs)")
        return {"thesis_id": thesis_id, "challenge": data}
    except ImportError:
        from fastapi import HTTPException as _HE
        raise _HE(status_code=500, detail="pplx_thesis_agent non installe")
'@
Set-Content -Path $blockFile -Value $block -Encoding UTF8

# 2. Helper Python : injecter le bloc + patcher cycle-snapshot
$helper = Join-Path $env:TEMP "pplx_thesis_api_$(Get-Random).py"
$helperCode = @'
import re, sys, ast
from pathlib import Path

target = Path(sys.argv[1])
block_file = Path(sys.argv[2])

src = target.read_text(encoding="utf-8-sig")
block = block_file.read_text(encoding="utf-8-sig")
MARKER = "[PPLX_THESIS_API_V1]"

if MARKER in src:
    print(f"[SKIP] {MARKER} deja present")
    sys.exit(0)

# 1. Inserer le bloc avant if __name__ ou en fin
m = re.search(r"\n(if\s+__name__\s*==\s*['\"]__main__['\"]\s*:)", src)
if m:
    src = src[:m.start()] + "\n" + block + "\n" + src[m.start():]
else:
    src = src.rstrip() + "\n" + block + "\n"

# 2. Enrichir cycle-snapshot : ajouter "challenges" dans le return
# On cherche le dict return de pplx_cycle_snapshot et on ajoute la cle 'challenges'
snap_match = re.search(
    r'def pplx_cycle_snapshot\(\).*?return \{(.*?)\}\s*\n',
    src,
    re.DOTALL
)
if snap_match:
    return_dict_content = snap_match.group(1)
    if '"challenges"' not in return_dict_content:
        # Recuperer les challenges en debut de fonction (avant le return)
        # On insere juste avant le 'return {'
        ret_start = snap_match.start() + snap_match.group(0).rfind("return {")
        insert_query = (
            "        challenges_rows = []\n"
            "        try:\n"
            "            challenges_rows = cx.execute(\n"
            "                \"SELECT thesis_id, ticker, side, conviction, challenge_score, verdict, ts \"\n"
            "                \"FROM thesis_challenge_context ORDER BY ts DESC LIMIT 20\"\n"
            "            ).fetchall()\n"
            "        except Exception:\n"
            "            pass\n"
        )
        # Inserer juste avant le 'finally:' de la fonction
        # Plus simple : reecrire la fonction. On la cherche entierement.
        full_match = re.search(
            r"(@app\.get\(['\"]/api/pplx/cycle-snapshot['\"]\)[\s\S]*?return\s*\{[\s\S]*?\}\s*\n)",
            src
        )
        if full_match:
            old = full_match.group(1)
            # Inserer challenges_rows juste avant 'finally:'
            new = old.replace(
                "    finally:\n        cx.close()",
                "        challenges_rows = []\n"
                "        try:\n"
                "            challenges_rows = cx.execute(\n"
                "                \"SELECT thesis_id, ticker, side, conviction, challenge_score, verdict, ts \"\n"
                "                \"FROM thesis_challenge_context ORDER BY ts DESC LIMIT 20\"\n"
                "            ).fetchall()\n"
                "        except Exception:\n"
                "            pass\n"
                "    finally:\n        cx.close()"
            )
            # Inserer la cle "challenges" dans le return
            new = new.replace(
                '"audit": [dict(r) for r in audit],',
                '"audit": [dict(r) for r in audit],\n'
                '        "challenges": [dict(r) for r in challenges_rows],'
            )
            src = src.replace(old, new, 1)
            print("[OK] cycle-snapshot enrichi avec 'challenges'")

# 3. Validation AST
try:
    ast.parse(src)
except SyntaxError as e:
    print(f"[AST-FAIL] ligne {e.lineno}: {e.msg}")
    lines = src.splitlines()
    start = max(0, e.lineno - 3)
    end = min(len(lines), e.lineno + 3)
    for i in range(start, end):
        print(f"  L{i+1}: {lines[i]}")
    sys.exit(3)

target.write_text(src, encoding="utf-8")
print(f"[OK] {MARKER} applique - 3 endpoints + cycle-snapshot enrichi")
print("[AST-OK]")
'@

Set-Content -Path $helper -Value $helperCode -Encoding UTF8
py -3.13 $helper $target $blockFile
$rc = $LASTEXITCODE
Remove-Item $blockFile -Force -ErrorAction SilentlyContinue
Remove-Item $helper -Force -ErrorAction SilentlyContinue

if ($rc -ne 0) {
    Write-Host "[ROLLBACK] Restoration depuis $backup" -ForegroundColor Yellow
    Copy-Item $backup $target -Force
    exit $rc
}

Write-Host "[DONE] 3 endpoints thesis-challenge disponibles + cycle-snapshot enrichi" -ForegroundColor Green
Write-Host "  GET  /api/pplx/thesis-challenges" -ForegroundColor Gray
Write-Host "  GET  /api/pplx/thesis-challenge/{id}" -ForegroundColor Gray
Write-Host "  POST /api/pplx/thesis-challenge/{id}  (trigger manuel)" -ForegroundColor Gray
