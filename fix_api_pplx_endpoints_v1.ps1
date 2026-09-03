# [FIX_API_PPLX_ENDPOINTS_V1] Ajoute les endpoints REST pour exposer les donnees Perplexity
# Endpoints crees:
#   GET /api/pplx/crypto              -> liste tous les cryptos avec narrative
#   GET /api/pplx/crypto/{ticker}     -> detail d'un crypto (BTC, ETH, LINK)
#   GET /api/pplx/quality             -> liste tous les equities avec quality
#   GET /api/pplx/quality/{ticker}    -> detail d'un equity
#   GET /api/pplx/cycle-snapshot      -> snapshot global pour le panel UI
# Marqueur : [PPLX_API_ENDPOINTS_V1]
$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
$backup = "$target.bak_pplxapi_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

if (-not (Test-Path $target)) { Write-Host "[ERR] $target introuvable" -ForegroundColor Red; exit 1 }
Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

# 1. Ecrire le bloc Python a injecter dans un fichier separe (pas d'echappement complique)
$blockFile = Join-Path $env:TEMP "pplx_endpoints_block_$(Get-Random).py"
$block = @'

# [PPLX_API_ENDPOINTS_V1]
# Endpoints REST pour exposer les donnees Perplexity (CryptoAgent + FactorAgent)
import json as _json_pplx
import time as _time_pplx
from pathlib import Path as _Path_pplx
import sqlite3 as _sqlite_pplx

def _pplx_db():
    db = _Path_pplx(__file__).resolve().parent / "thesium.db"
    cx = _sqlite_pplx.connect(str(db), timeout=10)
    cx.row_factory = _sqlite_pplx.Row
    return cx

def _pplx_parse_json(s):
    if not s:
        return None
    try:
        return _json_pplx.loads(s)
    except Exception:
        return s


@app.get("/api/pplx/crypto")
def pplx_crypto_list():
    """Liste tous les cryptos avec leur narrative Perplexity."""
    cx = _pplx_db()
    try:
        rows = cx.execute(
            "SELECT ticker, narrative_score, sentiment, narratives, trading_thesis, "
            "citations, model, ts FROM crypto_context ORDER BY narrative_score DESC"
        ).fetchall()
    finally:
        cx.close()
    now = _time_pplx.time()
    out = []
    for r in rows:
        d = dict(r)
        d["narratives"] = _pplx_parse_json(d["narratives"])
        d["citations"] = _pplx_parse_json(d["citations"])
        d["age_hours"] = round((now - d["ts"]) / 3600.0, 2) if d["ts"] else None
        out.append(d)
    return {"count": len(out), "items": out}


@app.get("/api/pplx/crypto/{ticker}")
def pplx_crypto_detail(ticker: str):
    """Detail crypto pour un ticker (BTC, ETH, LINK)."""
    cx = _pplx_db()
    try:
        row = cx.execute(
            "SELECT * FROM crypto_context WHERE upper(ticker) = ?",
            (ticker.upper(),)
        ).fetchone()
    finally:
        cx.close()
    if not row:
        from fastapi import HTTPException as _HE
        raise _HE(status_code=404, detail="crypto_context manquant pour " + ticker)
    d = dict(row)
    for k in ("narratives", "citations"):
        if k in d:
            d[k] = _pplx_parse_json(d[k])
    if d.get("ts"):
        d["age_hours"] = round((_time_pplx.time() - d["ts"]) / 3600.0, 2)
    return d


@app.get("/api/pplx/quality")
def pplx_quality_list():
    """Liste tous les equities avec leur score qualite Perplexity."""
    cx = _pplx_db()
    try:
        rows = cx.execute(
            "SELECT ticker, quality_score, earnings_trend, management_quality, "
            "moat_strength, balance_sheet_health, red_flags, positive_catalysts, "
            "citations, model, ts FROM factor_quality_context ORDER BY quality_score DESC"
        ).fetchall()
    finally:
        cx.close()
    now = _time_pplx.time()
    out = []
    for r in rows:
        d = dict(r)
        d["red_flags"] = _pplx_parse_json(d["red_flags"]) or []
        d["positive_catalysts"] = _pplx_parse_json(d["positive_catalysts"]) or []
        d["citations"] = _pplx_parse_json(d["citations"]) or []
        d["red_flags_count"] = len(d["red_flags"]) if isinstance(d["red_flags"], list) else 0
        d["age_hours"] = round((now - d["ts"]) / 3600.0, 2) if d["ts"] else None
        out.append(d)
    return {"count": len(out), "items": out}


@app.get("/api/pplx/quality/{ticker}")
def pplx_quality_detail(ticker: str):
    """Detail qualite pour un equity."""
    cx = _pplx_db()
    try:
        row = cx.execute(
            "SELECT * FROM factor_quality_context WHERE upper(ticker) = ?",
            (ticker.upper(),)
        ).fetchone()
    finally:
        cx.close()
    if not row:
        from fastapi import HTTPException as _HE
        raise _HE(status_code=404, detail="factor_quality_context manquant pour " + ticker)
    d = dict(row)
    for k in ("red_flags", "positive_catalysts", "citations"):
        if k in d:
            d[k] = _pplx_parse_json(d[k])
    if d.get("ts"):
        d["age_hours"] = round((_time_pplx.time() - d["ts"]) / 3600.0, 2)
    return d


@app.get("/api/pplx/cycle-snapshot")
def pplx_cycle_snapshot():
    """Snapshot global pour le panel UI Perplexity Insights."""
    cx = _pplx_db()
    try:
        cryptos = cx.execute(
            "SELECT ticker, narrative_score, sentiment, ts FROM crypto_context ORDER BY narrative_score DESC"
        ).fetchall()
        equities = cx.execute(
            "SELECT ticker, quality_score, earnings_trend, moat_strength, red_flags, ts "
            "FROM factor_quality_context ORDER BY quality_score DESC"
        ).fetchall()
        audit = cx.execute(
            "SELECT agent, COUNT(*) as calls, ROUND(SUM(COALESCE(cost_usd,0)),4) as cost_usd_total "
            "FROM pplx_audit GROUP BY agent ORDER BY agent"
        ).fetchall()
    finally:
        cx.close()
    now = _time_pplx.time()
    crypto_items = []
    for r in cryptos:
        d = dict(r)
        d["age_hours"] = round((now - d["ts"]) / 3600.0, 2) if d["ts"] else None
        crypto_items.append(d)
    equity_items = []
    for r in equities:
        rf = _pplx_parse_json(r["red_flags"]) or []
        equity_items.append({
            "ticker": r["ticker"],
            "quality_score": r["quality_score"],
            "earnings_trend": r["earnings_trend"],
            "moat_strength": r["moat_strength"],
            "red_flags_count": len(rf) if isinstance(rf, list) else 0,
            "age_hours": round((now - r["ts"]) / 3600.0, 2) if r["ts"] else None,
        })
    return {
        "generated_at": _time_pplx.strftime("%Y-%m-%d %H:%M:%S"),
        "crypto": crypto_items,
        "equity": equity_items,
        "audit": [dict(r) for r in audit],
    }
'@
Set-Content -Path $blockFile -Value $block -Encoding UTF8

# 2. Helper Python : injecter le bloc dans api_server.py + validation AST
$helper = Join-Path $env:TEMP "pplx_api_patch_$(Get-Random).py"
$helperCode = @'
import re, sys, ast
from pathlib import Path

target = Path(sys.argv[1])
block_file = Path(sys.argv[2])

src = target.read_text(encoding="utf-8-sig")
block = block_file.read_text(encoding="utf-8-sig")
MARKER = "[PPLX_API_ENDPOINTS_V1]"

if MARKER in src:
    print(f"[SKIP] {MARKER} deja present")
    sys.exit(0)

# Inserer avant le if __name__ == "__main__"
m = re.search(r"\n(if\s+__name__\s*==\s*['\"]__main__['\"]\s*:)", src)
if m:
    src = src[:m.start()] + "\n" + block + "\n" + src[m.start():]
else:
    src = src.rstrip() + "\n" + block + "\n"

# Validation AST
try:
    ast.parse(src)
except SyntaxError as e:
    print(f"[AST-FAIL] ligne {e.lineno}: {e.msg}")
    sys.exit(3)

target.write_text(src, encoding="utf-8")
print(f"[OK] {MARKER} applique - 5 endpoints PPLX ajoutes")
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

Write-Host "[DONE] 5 endpoints PPLX disponibles:" -ForegroundColor Green
Write-Host "  GET /api/pplx/crypto" -ForegroundColor Gray
Write-Host "  GET /api/pplx/crypto/{ticker}" -ForegroundColor Gray
Write-Host "  GET /api/pplx/quality" -ForegroundColor Gray
Write-Host "  GET /api/pplx/quality/{ticker}" -ForegroundColor Gray
Write-Host "  GET /api/pplx/cycle-snapshot" -ForegroundColor Gray
