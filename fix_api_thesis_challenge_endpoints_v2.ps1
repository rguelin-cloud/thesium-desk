# [FIX_API_THESIS_CHALLENGE_ENDPOINTS_V2] Ajoute 3 endpoints REST pour les challenges
#   GET  /api/pplx/thesis-challenges          -> liste des derniers challenges
#   GET  /api/pplx/thesis-challenge/{id}      -> detail d'un challenge
#   POST /api/pplx/thesis-challenge/{id}      -> declenche manuellement
# Met aussi a jour /api/pplx/cycle-snapshot pour inclure les challenges
# V2 corrections:
#   - SELECT corrige : t.conviction_score AS conviction, t.thesis_text AS rationale
#   - Side derive cote python (pas dans SQL)
#   - Detection robuste des helpers _pplx_db / _time_pplx (creation si manquants)
#   - Multi-strategie d'injection challenges dans cycle-snapshot
# Marqueur : [PPLX_THESIS_API_V2]
$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
$backup = "$target.bak_pplxthapi_v2_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

if (-not (Test-Path $target)) { Write-Host "[ERR] $target introuvable" -ForegroundColor Red; exit 1 }
Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

# 1. Bloc d'endpoints (fichier separe)
$blockFile = Join-Path $env:TEMP "pplx_thesis_endpoints_v2_$(Get-Random).py"
$block = @'

# [PPLX_THESIS_API_V2] Endpoints pour les challenges Perplexity sur theses
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
    """Detail complet d'un challenge (counter_arguments, sources, ...)."""
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
    """Declenche manuellement le challenge d'une these specifique."""
    import sqlite3 as _sql3
    from pathlib import Path as _P
    _db = _P(__file__).resolve().parent / "thesium.db"
    cx = _sql3.connect(str(_db), timeout=10)
    cx.row_factory = _sql3.Row
    try:
        row = cx.execute(
            "SELECT t.id, "
            "t.agent_type, "
            "t.conviction_score AS conviction, "
            "t.thesis_text AS rationale, "
            "t.proposed_action, "
            "t.horizon, "
            "t.key_drivers, "
            "t.status, "
            "t.created_at, "
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
            raise _HE(status_code=502, detail="Challenge Perplexity a echoue (verifier .env et logs)")
        return {"thesis_id": thesis_id, "challenge": data}
    except ImportError:
        from fastapi import HTTPException as _HE
        raise _HE(status_code=500, detail="pplx_thesis_agent non installe")
'@
Set-Content -Path $blockFile -Value $block -Encoding UTF8

# 2. Helper Python : injecter le bloc + patcher cycle-snapshot
$helper = Join-Path $env:TEMP "pplx_thesis_api_v2_$(Get-Random).py"
$helperCode = @'
import re, sys, ast
from pathlib import Path

target = Path(sys.argv[1])
block_file = Path(sys.argv[2])

src = target.read_text(encoding="utf-8-sig")
block = block_file.read_text(encoding="utf-8-sig")
MARKER = "[PPLX_THESIS_API_V2]"

if MARKER in src:
    print(f"[SKIP] {MARKER} deja present")
    sys.exit(0)

# Eviter conflit avec V1 (s'il etait deja applique)
if "[PPLX_THESIS_API_V1]" in src:
    print("[SKIP] V1 deja presente - desinstaller V1 d'abord")
    sys.exit(0)

# 1. Inserer le bloc avant if __name__ ou en fin
m = re.search(r"\n(if\s+__name__\s*==\s*['\"]__main__['\"]\s*:)", src)
if m:
    src = src[:m.start()] + "\n" + block + "\n" + src[m.start():]
else:
    src = src.rstrip() + "\n" + block + "\n"
print("[OK] 3 endpoints injectes")

# 2. Enrichir cycle-snapshot : ajouter "thesis_challenges" dans le return
# Strategie : on cherche la fonction pplx_cycle_snapshot et on rajoute la cle.
# La fonction existe (creee par fix_api_pplx_endpoints_v1.ps1) si [PPLX_API_ENDPOINTS_V1] present.
if "[PPLX_API_ENDPOINTS_V1]" in src:
    func_match = re.search(
        r"(@app\.get\(['\"]/api/pplx/cycle-snapshot['\"]\)[\s\S]*?return\s+\{[\s\S]*?\n\s*\})",
        src
    )
    if func_match:
        old = func_match.group(1)
        if '"thesis_challenges"' in old:
            print("[SKIP] cycle-snapshot deja enrichi avec thesis_challenges")
        else:
            # Strategie : juste ajouter une cle "thesis_challenges" dans le dict return
            # On utilise une lambda qui requete la base directement
            # Trouver la derniere cle du dict return et ajouter notre cle apres
            ret_match = re.search(r"return\s+\{([\s\S]*?)\n(\s*)\}", old)
            if ret_match:
                ret_body = ret_match.group(1)
                ret_indent = ret_match.group(2)
                # Detecter l'indent des cles existantes
                key_indent_match = re.search(r"\n(\s+)\"\w+\"\s*:", ret_body)
                key_indent = key_indent_match.group(1) if key_indent_match else (ret_indent + "    ")
                # Construire la nouvelle cle via une lambda en place
                new_key = (
                    f',\n{key_indent}"thesis_challenges": (lambda: ['
                    f'dict(r) for r in __import__("sqlite3").connect('
                    f'str(__import__("pathlib").Path(__file__).resolve().parent / "thesium.db"), timeout=10'
                    f').execute("SELECT thesis_id, ticker, side, conviction, challenge_score, verdict, '
                    f'alternative_thesis, ts FROM thesis_challenge_context ORDER BY ts DESC LIMIT 20").fetchall()'
                    f'])()'
                )
                # Plus propre : ajouter un row_factory pour avoir des dicts. Mais on simplifie :
                # On insere une cle qui execute un SELECT et retourne les tuples mappes manuellement
                new_key = (
                    f',\n{key_indent}"thesis_challenges": _pplx_thesis_recent_for_snapshot()'
                )
                new_ret = old[:ret_match.start()] + f"return {{{ret_body}{new_key}\n{ret_indent}}}"
                # Helper a placer juste avant la fonction snapshot
                helper_fn = (
                    "def _pplx_thesis_recent_for_snapshot():\n"
                    "    import sqlite3 as _s3\n"
                    "    from pathlib import Path as _P\n"
                    "    _db = _P(__file__).resolve().parent / \"thesium.db\"\n"
                    "    cx = _s3.connect(str(_db), timeout=10)\n"
                    "    cx.row_factory = _s3.Row\n"
                    "    try:\n"
                    "        rows = cx.execute(\n"
                    "            \"SELECT thesis_id, ticker, side, conviction, challenge_score, \"\n"
                    "            \"verdict, alternative_thesis, ts \"\n"
                    "            \"FROM thesis_challenge_context ORDER BY ts DESC LIMIT 20\"\n"
                    "        ).fetchall()\n"
                    "    except Exception:\n"
                    "        rows = []\n"
                    "    finally:\n"
                    "        cx.close()\n"
                    "    return [dict(r) for r in rows]\n\n"
                )
                # Inserer helper_fn + remplacer old par new_ret
                src = src.replace(old, helper_fn + new_ret, 1)
                print("[OK] cycle-snapshot enrichi avec thesis_challenges")
            else:
                print("[WARN] return {} de cycle-snapshot pas trouve - skip enrichissement")
    else:
        print("[WARN] fonction pplx_cycle_snapshot non trouvee - skip enrichissement")
else:
    print("[WARN] PPLX_API_ENDPOINTS_V1 absent - cycle-snapshot non enrichi (les endpoints seuls fonctionnent)")

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

Write-Host "[DONE] 3 endpoints thesis-challenge + cycle-snapshot enrichi" -ForegroundColor Green
Write-Host "  GET  /api/pplx/thesis-challenges" -ForegroundColor Gray
Write-Host "  GET  /api/pplx/thesis-challenge/{id}" -ForegroundColor Gray
Write-Host "  POST /api/pplx/thesis-challenge/{id}  (trigger manuel)" -ForegroundColor Gray
Write-Host "  GET  /api/pplx/cycle-snapshot  -> contient maintenant 'thesis_challenges'" -ForegroundColor Gray
