# nextones-fix-api-pplx-geo-endpoints.ps1
# Ajoute GET /api/pplx/geo + enrichit /api/pplx/cycle-snapshot avec geo_risks + book_exposure
# Marker idempotent : [PPLX_GEO_API_V1]

$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server_with_static.py"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak_geo_api_$ts"

if (-not (Test-Path $target)) {
    Write-Host "[KO] Fichier introuvable : $target" -ForegroundColor Red
    exit 1
}

Write-Host "[1/5] Backup -> $backup"
Copy-Item $target $backup -Force

# Lecture du contenu source pour comptage tags AVANT
$src = Get-Content $target -Raw -Encoding UTF8
$nbDefBefore = ([regex]::Matches($src, '(?m)^def\s+\w+|^async\s+def\s+\w+')).Count
$nbRoutesBefore = ([regex]::Matches($src, '@app\.(get|post|put|delete)\(')).Count
Write-Host "[2/5] AVANT : $nbDefBefore fonctions, $nbRoutesBefore routes"

# Vérif marker existant
if ($src -match '\[PPLX_GEO_API_V1\]') {
    Write-Host "[i] Marker [PPLX_GEO_API_V1] déjà présent. Patch idempotent : on remplace le bloc." -ForegroundColor Yellow
}

# Helper Python qui injecte le bloc
$helper = Join-Path $env:TEMP "patch_pplx_geo_api_$ts.py"
$helperContent = @'
# -*- coding: utf-8 -*-
import re, sys, io
from pathlib import Path

target = Path(sys.argv[1])
raw = target.read_text(encoding="utf-8-sig")

MARKER_START = "# === [PPLX_GEO_API_V1] BEGIN ==="
MARKER_END   = "# === [PPLX_GEO_API_V1] END ==="

BLOCK = '''
# === [PPLX_GEO_API_V1] BEGIN ===
# GeoAgent Perplexity : endpoints /api/pplx/geo + enrichissement cycle-snapshot
# Lecture pplx_geo_context (snapshot 4h) + mapping inverse book_exposure

def _pplx_geo_load_snapshot():
    """Charge le snapshot complet pplx_geo_context. Retourne None si table absente."""
    import sqlite3, json
    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        # Vérif table
        row = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pplx_geo_context'"
        ).fetchone()
        if not row:
            con.close()
            return None
        rows = cur.execute(
            "SELECT * FROM pplx_geo_context ORDER BY severity DESC"
        ).fetchall()
        con.close()
        if not rows:
            return None
        risks = []
        header = {
            "global_score": rows[0]["global_score"],
            "regime": rows[0]["regime"],
            "summary": rows[0]["summary"],
            "model": rows[0]["model"],
            "generated_at": rows[0]["generated_at"],
        }
        for r in rows:
            def _jload(col):
                v = r[col] if col in r.keys() else None
                if not v:
                    return []
                try:
                    return json.loads(v)
                except Exception:
                    return []
            risks.append({
                "risk_id": r["risk_id"],
                "title": r["title"],
                "region": r["region"],
                "severity": r["severity"],
                "horizon": r["horizon"],
                "type": r["type"],
                "narrative": r["narrative"],
                "catalysts": _jload("catalysts_json"),
                "sectors": _jload("sectors_json"),
                "tickers": _jload("tickers_json"),
                "mechanism": r["mechanism"] if "mechanism" in r.keys() else "",
                "sources": _jload("sources_json"),
            })
        return {"header": header, "risks": risks}
    except Exception as e:
        try:
            con.close()
        except Exception:
            pass
        return {"_error": str(e)}


def _pplx_geo_book_exposure(risks):
    """Mapping inverse : pour chaque ticker actif du book, liste les risques + score d'exposition."""
    import sqlite3
    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        positions = cur.execute("""
            SELECT i.ticker, p.weight_pct, p.quantity
            FROM portfolio_positions p
            JOIN instruments i ON i.id = p.instrument_id
            WHERE p.quantity != 0
        """).fetchall()
        con.close()
    except Exception:
        return []

    out = []
    for p in positions:
        ticker = p["ticker"]
        weight = float(p["weight_pct"] or 0.0)
        matched = []
        raw_score = 0
        for r in risks:
            tks = r.get("tickers") or []
            if ticker in tks:
                matched.append({
                    "risk_id": r["risk_id"],
                    "title": r["title"],
                    "severity": r["severity"],
                    "horizon": r["horizon"],
                    "type": r["type"],
                })
                raw_score += int(r["severity"] or 0)
        if not matched:
            continue
        out.append({
            "ticker": ticker,
            "weight_pct": round(weight, 4),
            "risks": matched,
            "exposure_score": raw_score,
            "exposure_score_weighted": round(raw_score * (weight / 100.0), 4),
        })
    out.sort(key=lambda x: x["exposure_score_weighted"], reverse=True)
    return out


@app.get("/api/pplx/geo")
def api_pplx_geo():
    """Snapshot géopolitique complet + book_exposure."""
    from fastapi.responses import JSONResponse
    snap = _pplx_geo_load_snapshot()
    if snap is None:
        return JSONResponse({"available": False, "reason": "no_snapshot"}, status_code=200)
    if isinstance(snap, dict) and snap.get("_error"):
        return JSONResponse({"available": False, "reason": "db_error", "error": snap["_error"]}, status_code=200)
    exposure = _pplx_geo_book_exposure(snap["risks"])
    return {
        "available": True,
        "header": snap["header"],
        "risks": snap["risks"],
        "book_exposure": exposure,
    }
# === [PPLX_GEO_API_V1] END ===
'''

# Remove existing block if present
pattern = re.compile(re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END), re.DOTALL)
raw = pattern.sub("", raw)

# Append block at end (safe : we use app from module scope)
raw = raw.rstrip() + "\n\n" + BLOCK.strip() + "\n"

# --- Enrichissement cycle-snapshot ---
# On cherche la fonction qui implémente /api/pplx/cycle-snapshot
# Pattern attendu (selon session précédente) : @app.get("/api/pplx/cycle-snapshot")
SNAP_MARKER_START = "# === [PPLX_GEO_SNAPSHOT_ENRICH_V1] BEGIN ==="
SNAP_MARKER_END   = "# === [PPLX_GEO_SNAPSHOT_ENRICH_V1] END ==="

# Remove old enrich block
raw = re.sub(re.escape(SNAP_MARKER_START) + r".*?" + re.escape(SNAP_MARKER_END), "", raw, flags=re.DOTALL)

# Trouve la fonction cycle-snapshot et son return final
# Stratégie : trouver "@app.get(\"/api/pplx/cycle-snapshot\")" puis le bloc def juste après
m = re.search(r'@app\.get\(["\']\/api\/pplx\/cycle-snapshot["\']\)\s*\ndef\s+(\w+)\s*\([^)]*\)\s*:', raw)
if m:
    func_name = m.group(1)
    # On localise la prochaine occurrence de "return " dans cette fonction
    start = m.end()
    # Recherche du return de plus haut niveau (4 espaces) ou d'une nouvelle fonction
    next_def = re.search(r'\n(?:@app\.|def\s+|async\s+def\s+)', raw[start:])
    end = start + (next_def.start() if next_def else len(raw) - start)
    body = raw[start:end]

    # Construit le bloc d'injection AVANT le return
    inject = '''
    # === [PPLX_GEO_SNAPSHOT_ENRICH_V1] BEGIN ===
    try:
        _geo_snap = _pplx_geo_load_snapshot()
        if _geo_snap and not _geo_snap.get("_error"):
            _geo_exposure = _pplx_geo_book_exposure(_geo_snap["risks"])
            # Top 5 condensé
            _geo_top = []
            for _r in _geo_snap["risks"][:5]:
                _geo_top.append({
                    "risk_id": _r["risk_id"],
                    "title": _r["title"],
                    "severity": _r["severity"],
                    "horizon": _r["horizon"],
                    "type": _r["type"],
                    "tickers": _r["tickers"],
                })
            snap_payload_geo = {
                "geo_global_score": _geo_snap["header"]["global_score"],
                "geo_regime": _geo_snap["header"]["regime"],
                "geo_summary": _geo_snap["header"]["summary"],
                "geo_generated_at": _geo_snap["header"]["generated_at"],
                "geo_risks": _geo_top,
                "geo_book_exposure": _geo_exposure[:10],
            }
        else:
            snap_payload_geo = {"geo_available": False}
    except Exception as _e:
        snap_payload_geo = {"geo_available": False, "geo_error": str(_e)}
    # === [PPLX_GEO_SNAPSHOT_ENRICH_V1] END ===
'''

    # Insère avant le premier return de la fonction
    return_match = re.search(r'\n(    return\s+)', body)
    if return_match:
        # Modifie le return pour merge le dict
        # On suppose un return d'un dict. On enrichit le dict avec ** snap_payload_geo si possible.
        # Sécurité : on cherche le pattern "return {" ou "return dict("
        body_new = body[:return_match.start()] + inject + body[return_match.start():]
        # Tente d'injecter dans le dict de retour
        # Pattern : "return {" sur une ligne
        body_new2 = re.sub(
            r'(\n    return\s*\{)',
            r'\1\n        **snap_payload_geo,',
            body_new,
            count=1,
        )
        if body_new2 == body_new:
            # Fallback : si return d'une variable, on ajoute un update avant
            body_new2 = re.sub(
                r'(\n    return\s+)(\w+)(\s*\n)',
                r'\1{**\2, **snap_payload_geo}\3',
                body_new,
                count=1,
            )
        raw = raw[:start] + body_new2 + raw[end:]
        print(f"[i] cycle-snapshot enrichi (func={func_name})")
    else:
        print("[!] cycle-snapshot : aucun return trouvé dans la fonction, enrichissement skipped")
else:
    print("[!] /api/pplx/cycle-snapshot introuvable : enrichissement skipped (endpoint geo seul ajouté)")

# Écriture sans BOM
target.write_text(raw, encoding="utf-8", newline="\n")
print("[OK] Patch écrit")
'@

Set-Content -Path $helper -Value $helperContent -Encoding UTF8
Write-Host "[3/5] Helper Python -> $helper"

py -3.13 $helper $target
if ($LASTEXITCODE -ne 0) {
    Write-Host "[KO] Helper a échoué. Restore backup." -ForegroundColor Red
    Copy-Item $backup $target -Force
    exit 1
}

# Comptage tags APRES
$src2 = Get-Content $target -Raw -Encoding UTF8
$nbDefAfter = ([regex]::Matches($src2, '(?m)^def\s+\w+|^async\s+def\s+\w+')).Count
$nbRoutesAfter = ([regex]::Matches($src2, '@app\.(get|post|put|delete)\(')).Count
Write-Host "[4/5] APRES : $nbDefAfter fonctions, $nbRoutesAfter routes"

$diffDef = $nbDefAfter - $nbDefBefore
$diffRoutes = $nbRoutesAfter - $nbRoutesBefore
Write-Host "    Delta : +$diffDef fonctions, +$diffRoutes routes"

if ($diffRoutes -lt 1) {
    Write-Host "[KO] Aucune nouvelle route détectée. Restore backup." -ForegroundColor Red
    Copy-Item $backup $target -Force
    exit 1
}

# Validation syntaxe Python
Write-Host "[5/5] Validation syntaxe Python..."
py -3.13 -c "import ast, sys; ast.parse(open(r'$target', encoding='utf-8').read()); print('[OK] syntaxe valide')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[KO] Erreur syntaxe Python. Restore backup." -ForegroundColor Red
    Copy-Item $backup $target -Force
    exit 1
}

Write-Host ""
Write-Host "=== PATCH OK ===" -ForegroundColor Green
Write-Host "Backup : $backup"
Write-Host ""
Write-Host "Prochaines étapes :"
Write-Host "  1. Redémarre l'API : py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000"
Write-Host "  2. Test : curl http://localhost:8000/api/pplx/geo | py -3.13 -m json.tool"
Write-Host "  3. Test : curl http://localhost:8000/api/pplx/cycle-snapshot | py -3.13 -m json.tool | findstr geo"
