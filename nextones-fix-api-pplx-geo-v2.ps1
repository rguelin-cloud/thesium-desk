# nextones-fix-api-pplx-geo-v2.ps1
# CORRECTION : cible le BON fichier api_server.py (92k chars)
# + nettoie le bloc parasite dans api_server_with_static.py
# Marker idempotent : [PPLX_GEO_API_V1]

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$target = Join-Path $root "api_server.py"
$stray = Join-Path $root "api_server_with_static.py"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak_geo_api_$ts"
$strayBackup = "$stray.bak_geo_clean_$ts"

if (-not (Test-Path $target)) {
    Write-Host "[KO] $target introuvable" -ForegroundColor Red
    exit 1
}

Write-Host "[1/6] Backup api_server.py -> $backup"
Copy-Item $target $backup -Force

# Comptage AVANT
$src = Get-Content $target -Raw -Encoding UTF8
$nbRoutesBefore = ([regex]::Matches($src, '@app\.(get|post|put|delete)\(')).Count
$nbDefBefore = ([regex]::Matches($src, '(?m)^def\s+\w+|^async\s+def\s+\w+')).Count
Write-Host "[2/6] AVANT api_server.py : $nbDefBefore fonctions, $nbRoutesBefore routes"

# Helper Python qui injecte le bloc + enrichit cycle-snapshot
$helper = Join-Path $env:TEMP "patch_pplx_geo_v2_$ts.py"
$helperContent = @'
# -*- coding: utf-8 -*-
import re, sys
from pathlib import Path

target = Path(sys.argv[1])
raw = target.read_text(encoding="utf-8-sig")

MARKER_START = "# === [PPLX_GEO_API_V1] BEGIN ==="
MARKER_END   = "# === [PPLX_GEO_API_V1] END ==="
SNAP_START   = "# === [PPLX_GEO_SNAPSHOT_ENRICH_V1] BEGIN ==="
SNAP_END     = "# === [PPLX_GEO_SNAPSHOT_ENRICH_V1] END ==="

# Détermine la variable DB_PATH (cherche dans le fichier)
m_db = re.search(r'(DB_PATH|DATABASE_PATH|DB_FILE|DBPATH)\s*=\s*', raw)
db_var = m_db.group(1) if m_db else "DB_PATH"
print(f"[i] DB variable détectée : {db_var}")

BLOCK = '''
# === [PPLX_GEO_API_V1] BEGIN ===
# GeoAgent Perplexity : endpoint /api/pplx/geo + helpers
# Lecture pplx_geo_context (snapshot 4h) + mapping inverse book_exposure

def _pplx_geo_load_snapshot():
    import sqlite3, json
    try:
        con = sqlite3.connect(__DB__)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
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
        keys0 = rows[0].keys()
        for r in rows:
            def _jload(col):
                if col not in keys0:
                    return []
                v = r[col]
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
                "mechanism": r["mechanism"] if "mechanism" in keys0 else "",
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
    import sqlite3
    try:
        con = sqlite3.connect(__DB__)
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
'''.replace("__DB__", db_var)

# Supprime ancien bloc s'il existe
pattern = re.compile(re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END), re.DOTALL)
raw = pattern.sub("", raw)

# Append à la fin
raw = raw.rstrip() + "\n\n" + BLOCK.strip() + "\n"

# --- Enrichissement cycle-snapshot ---
# Supprime ancien block enrich
raw = re.sub(re.escape(SNAP_START) + r".*?" + re.escape(SNAP_END), "", raw, flags=re.DOTALL)

m = re.search(r'@app\.get\(\s*["\']\/api\/pplx\/cycle-snapshot["\']\s*\)\s*\n(?:async\s+)?def\s+(\w+)\s*\([^)]*\)\s*:', raw)
if m:
    func_name = m.group(1)
    start = m.end()
    # Cherche la fin de la fonction = prochaine ligne commençant par @app., def, async def (en début de ligne)
    next_def = re.search(r'\n(?:@app\.|def\s+|async\s+def\s+)', raw[start:])
    end = start + (next_def.start() if next_def else len(raw) - start)
    body = raw[start:end]

    inject = '''
    # === [PPLX_GEO_SNAPSHOT_ENRICH_V1] BEGIN ===
    try:
        _geo_snap = _pplx_geo_load_snapshot()
        if _geo_snap and not _geo_snap.get("_error"):
            _geo_exposure = _pplx_geo_book_exposure(_geo_snap["risks"])
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
                "geo_available": True,
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

    # Cherche le return
    ret_match = re.search(r'\n(    return\s+)', body)
    if ret_match:
        body_new = body[:ret_match.start()] + inject + body[ret_match.start():]
        # Tente d'injecter dans le dict return { ... }
        body_new2 = re.sub(
            r'(\n    return\s*\{)',
            r'\1\n        **snap_payload_geo,',
            body_new,
            count=1,
        )
        if body_new2 == body_new:
            # Fallback : return VAR -> return {**VAR, **snap_payload_geo}
            body_new2 = re.sub(
                r'(\n    return\s+)([\w\.\[\]\"\']+)(\s*[\n\r])',
                r'\1{**\2, **snap_payload_geo}\3',
                body_new,
                count=1,
            )
        raw = raw[:start] + body_new2 + raw[end:]
        print(f"[OK] cycle-snapshot enrichi (func={func_name})")
    else:
        print(f"[!] cycle-snapshot func={func_name} : aucun return trouvé. Skipped.")
else:
    print("[!] /api/pplx/cycle-snapshot introuvable dans api_server.py")

target.write_text(raw, encoding="utf-8", newline="\n")
print("[OK] Fichier écrit")
'@

Set-Content -Path $helper -Value $helperContent -Encoding UTF8
Write-Host "[3/6] Helper -> $helper"

py -3.13 $helper $target
if ($LASTEXITCODE -ne 0) {
    Write-Host "[KO] Helper a échoué. Restore." -ForegroundColor Red
    Copy-Item $backup $target -Force
    exit 1
}

# Comptage APRES
$src2 = Get-Content $target -Raw -Encoding UTF8
$nbRoutesAfter = ([regex]::Matches($src2, '@app\.(get|post|put|delete)\(')).Count
$nbDefAfter = ([regex]::Matches($src2, '(?m)^def\s+\w+|^async\s+def\s+\w+')).Count
Write-Host "[4/6] APRES api_server.py : $nbDefAfter fonctions, $nbRoutesAfter routes"
Write-Host "    Delta : +$($nbDefAfter - $nbDefBefore) fonctions, +$($nbRoutesAfter - $nbRoutesBefore) routes"

if ($nbRoutesAfter -lt $nbRoutesBefore + 1) {
    Write-Host "[KO] Pas de nouvelle route. Restore." -ForegroundColor Red
    Copy-Item $backup $target -Force
    exit 1
}

# Vérif présence markers
$hasGeoApi = $src2.Contains("[PPLX_GEO_API_V1]")
$hasGeoSnap = $src2.Contains("[PPLX_GEO_SNAPSHOT_ENRICH_V1]")
Write-Host "    Marker [PPLX_GEO_API_V1] : $hasGeoApi"
Write-Host "    Marker [PPLX_GEO_SNAPSHOT_ENRICH_V1] : $hasGeoSnap"

# Validation syntaxe
Write-Host "[5/6] Validation syntaxe Python..."
py -3.13 -c "import ast; ast.parse(open(r'$target', encoding='utf-8').read()); print('[OK] syntaxe valide')"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[KO] Erreur syntaxe. Restore." -ForegroundColor Red
    Copy-Item $backup $target -Force
    exit 1
}

# Nettoyage du bloc parasite dans api_server_with_static.py
Write-Host "[6/6] Nettoyage bloc parasite dans api_server_with_static.py..."
if (Test-Path $stray) {
    Copy-Item $stray $strayBackup -Force
    $strayContent = Get-Content $stray -Raw -Encoding UTF8
    if ($strayContent.Contains("[PPLX_GEO_API_V1]")) {
        # Retire le bloc parasite
        $cleanScript = @"
import re
from pathlib import Path
p = Path(r'$stray')
s = p.read_text(encoding='utf-8-sig')
pat = re.compile(re.escape('# === [PPLX_GEO_API_V1] BEGIN ===') + r'.*?' + re.escape('# === [PPLX_GEO_API_V1] END ==='), re.DOTALL)
s2 = pat.sub('', s).rstrip() + '\n'
p.write_text(s2, encoding='utf-8', newline='\n')
print('[OK] Bloc parasite supprimé de api_server_with_static.py')
"@
        $cleanFile = Join-Path $env:TEMP "clean_stray_$ts.py"
        Set-Content -Path $cleanFile -Value $cleanScript -Encoding UTF8
        py -3.13 $cleanFile
        # Re-validate syntaxe
        py -3.13 -c "import ast; ast.parse(open(r'$stray', encoding='utf-8').read()); print('[OK] api_server_with_static.py syntaxe OK')"
    } else {
        Write-Host "    Aucun bloc parasite, skip."
    }
}

Write-Host ""
Write-Host "=== PATCH OK ===" -ForegroundColor Green
Write-Host "Backup api_server.py : $backup"
Write-Host "Backup api_server_with_static.py : $strayBackup"
Write-Host ""
Write-Host "Prochaines etapes :"
Write-Host "  1. Redemarre l'API : py -3.13 -m uvicorn api_server:app --host 0.0.0.0 --port 8000"
Write-Host "     (ou la commande habituelle si differente)"
Write-Host "  2. Test geo : curl http://localhost:8000/api/pplx/geo"
Write-Host "  3. Test snapshot enrichi : curl http://localhost:8000/api/pplx/cycle-snapshot"
