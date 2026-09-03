# [FIX_API_THESIS_CHALLENGE_ENDPOINTS_V3] Ajoute 3 endpoints REST pour les challenges
# V3 : injection plus propre dans cycle-snapshot (sans double virgule)
# Marqueur : [PPLX_THESIS_API_V3]
$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
$backup = "$target.bak_pplxthapi_v3_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

if (-not (Test-Path $target)) { Write-Host "[ERR] $target introuvable" -ForegroundColor Red; exit 1 }
Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

# 1. Bloc d'endpoints (fichier separe)
$blockFile = Join-Path $env:TEMP "pplx_thesis_endpoints_v3_$(Get-Random).py"
$block = @'

# [PPLX_THESIS_API_V3] Endpoints pour les challenges Perplexity sur theses
def _pplx_thesis_derive_side(action):
    """Derive LONG/SHORT/HOLD a partir de proposed_action."""
    import re as _re
    if not action:
        return "HOLD"
    if _re.search(r"\b(BUY|LONG|INCREASE|ACCUMULATE|ADD|OVERWEIGHT)\b", action, _re.I):
        return "LONG"
    if _re.search(r"\b(SELL|SHORT|REDUCE|TRIM|UNDERWEIGHT|EXIT|CLOSE)\b", action, _re.I):
        return "SHORT"
    return "HOLD"


def _pplx_thesis_recent_for_snapshot():
    """Retourne les 20 derniers thesis challenges (pour cycle-snapshot)."""
    import sqlite3 as _s3
    from pathlib import Path as _P
    _db = _P(__file__).resolve().parent / "thesium.db"
    cx = _s3.connect(str(_db), timeout=10)
    cx.row_factory = _s3.Row
    try:
        rows = cx.execute(
            "SELECT thesis_id, ticker, side, conviction, challenge_score, "
            "verdict, alternative_thesis, ts "
            "FROM thesis_challenge_context ORDER BY ts DESC LIMIT 20"
        ).fetchall()
    except Exception:
        rows = []
    finally:
        cx.close()
    return [dict(r) for r in rows]


@app.get("/api/pplx/thesis-challenges")
def pplx_thesis_challenges_list(limit: int = 50):
    """Liste les derniers challenges Perplexity de theses."""
    import sqlite3 as _sql3, time as _t
    from pathlib import Path as _P
    _db = _P(__file__).resolve().parent / "thesium.db"
    cx = _sql3.connect(str(_db), timeout=10)
    cx.row_factory = _sql3.Row
    try:
        rows = cx.execute(
            "SELECT thesis_id, ticker, side, conviction, challenge_score, verdict, "
            "confidence_in_challenge, alternative_thesis, model, ts, source_thesis_summary "
            "FROM thesis_challenge_context ORDER BY ts DESC LIMIT ?",
            (limit,)
        ).fetchall()
    finally:
        cx.close()
    now = _t.time()
    out = []
    for r in rows:
        d = dict(r)
        d["age_hours"] = round((now - d["ts"]) / 3600.0, 2) if d["ts"] else None
        out.append(d)
    return {"count": len(out), "items": out}


@app.get("/api/pplx/thesis-challenge/{thesis_id}")
def pplx_thesis_challenge_detail(thesis_id: int):
    """Detail complet d'un challenge."""
    import sqlite3 as _sql3, time as _t, json as _j
    from pathlib import Path as _P
    _db = _P(__file__).resolve().parent / "thesium.db"
    cx = _sql3.connect(str(_db), timeout=10)
    cx.row_factory = _sql3.Row
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
            try:
                d[k] = _j.loads(d[k])
            except Exception:
                pass
    if d.get("ts"):
        d["age_hours"] = round((_t.time() - d["ts"]) / 3600.0, 2)
    return d


@app.post("/api/pplx/thesis-challenge/{thesis_id}")
def pplx_thesis_challenge_trigger(thesis_id: int):
    """Declenche manuellement le challenge d'une these."""
    import sqlite3 as _sql3
    from pathlib import Path as _P
    _db = _P(__file__).resolve().parent / "thesium.db"
    cx = _sql3.connect(str(_db), timeout=10)
    cx.row_factory = _sql3.Row
    try:
        row = cx.execute(
            "SELECT t.id, t.agent_type, "
            "t.conviction_score AS conviction, t.thesis_text AS rationale, "
            "t.proposed_action, t.horizon, t.key_drivers, t.status, t.created_at, "
            "i.ticker, i.name, i.sector, i.asset_class "
            "FROM theses t JOIN instruments i ON i.id = t.instrument_id "
            "WHERE t.id = ?",
            (thesis_id,)
        ).fetchone()
    finally:
        cx.close()
    if not row:
        from fastapi import HTTPException as _HE
        raise _HE(status_code=404, detail="These " + str(thesis_id) + " introuvable")
    thesis_dict = dict(row)
    thesis_dict["side"] = _pplx_thesis_derive_side(thesis_dict.get("proposed_action"))
    try:
        from pplx_thesis_agent import challenge_one
        data = challenge_one(thesis_dict)
        if not data:
            from fastapi import HTTPException as _HE
            raise _HE(status_code=502, detail="Challenge Perplexity a echoue")
        return {"thesis_id": thesis_id, "challenge": data}
    except ImportError:
        from fastapi import HTTPException as _HE
        raise _HE(status_code=500, detail="pplx_thesis_agent non installe")
'@
Set-Content -Path $blockFile -Value $block -Encoding UTF8

# 2. Helper Python : inject + patch cycle-snapshot proprement
$helper = Join-Path $env:TEMP "pplx_thesis_api_v3_$(Get-Random).py"
$helperCode = @'
import re, sys, ast
from pathlib import Path

target = Path(sys.argv[1])
block_file = Path(sys.argv[2])

src = target.read_text(encoding="utf-8-sig")
block = block_file.read_text(encoding="utf-8-sig")
MARKER = "[PPLX_THESIS_API_V3]"

# Skip si une version deja la
for v in ("[PPLX_THESIS_API_V1]", "[PPLX_THESIS_API_V2]", "[PPLX_THESIS_API_V3]"):
    if v in src:
        print(f"[SKIP] {v} deja present")
        sys.exit(0)

# 1. Inserer le bloc des endpoints avant if __name__ ou en fin
m = re.search(r"\n(if\s+__name__\s*==\s*['\"]__main__['\"]\s*:)", src)
if m:
    src = src[:m.start()] + "\n" + block + "\n" + src[m.start():]
else:
    src = src.rstrip() + "\n" + block + "\n"
print("[OK] 3 endpoints + helpers injectes")

# 2. Enrichir cycle-snapshot avec thesis_challenges
# Strategie : trouver le dict return de pplx_cycle_snapshot et ajouter une cle
# On recherche la fonction
snap_match = re.search(
    r'(@app\.get\(["\\\']/api/pplx/cycle-snapshot["\\\']\)[\s\S]*?def\s+\w+\([^)]*\):[\s\S]*?return\s+\{[\s\S]*?\n(\s*)\})',
    src
)
if not snap_match:
    print("[WARN] cycle-snapshot fonction non trouvee - skip enrichissement")
else:
    full_block = snap_match.group(1)
    close_indent = snap_match.group(2)

    if '"thesis_challenges"' in full_block:
        print("[SKIP] cycle-snapshot deja enrichi avec thesis_challenges")
    else:
        # Trouver le dict return precisemment
        ret_re = re.search(r'(return\s+\{)([\s\S]*?)(\n' + re.escape(close_indent) + r'\})', full_block)
        if not ret_re:
            print("[WARN] Impossible de parser le return {} - skip enrichissement")
        else:
            ret_open = ret_re.group(1)
            ret_body = ret_re.group(2)
            ret_close = ret_re.group(3)

            # Detecter l'indent des cles
            key_match = re.search(r'\n(\s+)"[^"]+"\s*:', ret_body)
            key_indent = key_match.group(1) if key_match else (close_indent + "    ")

            # Nettoyer le ret_body : enlever virgule trailing eventuelle
            ret_body_stripped = ret_body.rstrip()
            # S'assurer qu'il finit par , (sinon ajouter)
            if not ret_body_stripped.rstrip().endswith(","):
                ret_body_new = ret_body_stripped + ","
            else:
                ret_body_new = ret_body_stripped

            # Ajouter notre cle
            ret_body_new += f'\n{key_indent}"thesis_challenges": _pplx_thesis_recent_for_snapshot()'

            new_ret = ret_open + ret_body_new + ret_close
            new_full_block = full_block.replace(ret_re.group(0), new_ret, 1)
            src = src.replace(full_block, new_full_block, 1)
            print("[OK] cycle-snapshot enrichi avec thesis_challenges")

# 3. Validation AST
try:
    ast.parse(src)
except SyntaxError as e:
    print(f"[AST-FAIL] ligne {e.lineno}: {e.msg}")
    lines = src.splitlines()
    start = max(0, e.lineno - 5)
    end = min(len(lines), e.lineno + 5)
    for i in range(start, end):
        print(f"  L{i+1}: {lines[i]}")
    sys.exit(3)

target.write_text(src, encoding="utf-8")
print(f"[OK] {MARKER} applique - endpoints + cycle-snapshot enrichi")
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

Write-Host "[DONE] 3 endpoints + cycle-snapshot enrichi" -ForegroundColor Green
Write-Host "  GET  /api/pplx/thesis-challenges" -ForegroundColor Gray
Write-Host "  GET  /api/pplx/thesis-challenge/{id}" -ForegroundColor Gray
Write-Host "  POST /api/pplx/thesis-challenge/{id}" -ForegroundColor Gray
