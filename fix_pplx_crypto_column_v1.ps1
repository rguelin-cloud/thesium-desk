# [FIX_PPLX_CRYPTO_COLUMN_V1] Reecrit les 3 endpoints PPLX crypto pour matcher le vrai schema crypto_context
# Schema reel : symbol, narrative_score, social_sentiment, current_narratives, regulatory_status,
#               onchain_signals, smart_money_positioning, key_catalysts_30d, red_flags,
#               thesis_short, citations, model, ts
# Strategie : remplacer les 3 fonctions complètes par leur version corrigée.
# Marqueur : [PPLX_CRYPTO_COL_FIX_V1]
$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
$backup = "$target.bak_pplxcol_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

if (-not (Test-Path $target)) { Write-Host "[ERR] $target introuvable" -ForegroundColor Red; exit 1 }
Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

# 1. Ecrire les 3 fonctions corrigees dans un fichier separe (pas d'echappement)
$replaceFile = Join-Path $env:TEMP "pplx_crypto_replace_$(Get-Random).py"
$replaceBlock = @'
@app.get("/api/pplx/crypto")
def pplx_crypto_list():
    """Liste tous les cryptos avec leur narrative Perplexity (schema reel: symbol, social_sentiment, ...)."""
    cx = _pplx_db()
    try:
        rows = cx.execute(
            "SELECT symbol AS ticker, narrative_score, social_sentiment AS sentiment, "
            "current_narratives AS narratives, thesis_short AS trading_thesis, "
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
    """Detail crypto pour un symbol (BTC, ETH, LINK)."""
    cx = _pplx_db()
    try:
        row = cx.execute(
            "SELECT *, symbol AS ticker, social_sentiment AS sentiment, "
            "current_narratives AS narratives, thesis_short AS trading_thesis "
            "FROM crypto_context WHERE upper(symbol) = ?",
            (ticker.upper(),)
        ).fetchone()
    finally:
        cx.close()
    if not row:
        from fastapi import HTTPException as _HE
        raise _HE(status_code=404, detail="crypto_context manquant pour " + ticker)
    d = dict(row)
    # Parser tous les champs JSON connus
    for k in ("narratives", "current_narratives", "citations", "onchain_signals",
              "key_catalysts_30d", "red_flags", "regulatory_status"):
        if k in d and d[k]:
            d[k] = _pplx_parse_json(d[k])
    if d.get("ts"):
        d["age_hours"] = round((_time_pplx.time() - d["ts"]) / 3600.0, 2)
    return d
'@
Set-Content -Path $replaceFile -Value $replaceBlock -Encoding UTF8

# 2. Bloc de remplacement pour pplx_cycle_snapshot
$snapshotFile = Join-Path $env:TEMP "pplx_snapshot_replace_$(Get-Random).py"
$snapshotBlock = @'
@app.get("/api/pplx/cycle-snapshot")
def pplx_cycle_snapshot():
    """Snapshot global pour le panel UI Perplexity Insights."""
    cx = _pplx_db()
    try:
        cryptos = cx.execute(
            "SELECT symbol AS ticker, narrative_score, social_sentiment AS sentiment, ts "
            "FROM crypto_context ORDER BY narrative_score DESC"
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
Set-Content -Path $snapshotFile -Value $snapshotBlock -Encoding UTF8

# 3. Helper Python : remplace les 3 fonctions par regex sur signature
$helper = Join-Path $env:TEMP "pplx_crypto_col_patch_$(Get-Random).py"
$helperCode = @'
import re, sys, ast
from pathlib import Path

target = Path(sys.argv[1])
replace_file = Path(sys.argv[2])
snapshot_file = Path(sys.argv[3])

src = target.read_text(encoding="utf-8-sig")
MARKER = "[PPLX_CRYPTO_COL_FIX_V1]"

if MARKER in src:
    print(f"[SKIP] {MARKER} deja present")
    sys.exit(0)

replace_block = replace_file.read_text(encoding="utf-8-sig").strip()
snapshot_block = snapshot_file.read_text(encoding="utf-8-sig").strip()

original = src

# 1. Remplacer les 2 endpoints crypto (list + detail) en un seul bloc
# On cherche du decorateur "/api/pplx/crypto" jusqu'au decorateur "/api/pplx/quality"
pattern_crypto = re.compile(
    r"@app\.get\(['\"]/api/pplx/crypto['\"]\).*?(?=@app\.get\(['\"]/api/pplx/quality['\"]\))",
    re.DOTALL
)
m_crypto = pattern_crypto.search(src)
if not m_crypto:
    print("[ERR] Bloc crypto list+detail introuvable")
    sys.exit(2)

src = src[:m_crypto.start()] + replace_block + "\n\n\n" + src[m_crypto.end():]
print("[OK] Bloc crypto list+detail remplace")

# 2. Remplacer pplx_cycle_snapshot
pattern_snapshot = re.compile(
    r"@app\.get\(['\"]/api/pplx/cycle-snapshot['\"]\).*?(?=\n(?:@app\.|class\s|def\s+(?!_)|if\s+__name__|\Z))",
    re.DOTALL
)
m_snap = pattern_snapshot.search(src)
if not m_snap:
    print("[ERR] Bloc cycle-snapshot introuvable")
    sys.exit(3)

src = src[:m_snap.start()] + snapshot_block + "\n" + src[m_snap.end():]
print("[OK] Bloc cycle-snapshot remplace")

# 3. Marqueur d'idempotence
src = src.replace(
    "# [PPLX_API_ENDPOINTS_V1]",
    f"# [PPLX_API_ENDPOINTS_V1] {MARKER}",
    1
)

if src == original:
    print("[ERR] Aucune modification")
    sys.exit(4)

# 4. Validation AST
try:
    ast.parse(src)
except SyntaxError as e:
    print(f"[AST-FAIL] ligne {e.lineno}: {e.msg}")
    sys.exit(5)

target.write_text(src, encoding="utf-8")
print(f"[OK] {MARKER} applique")
print("[AST-OK]")
'@

Set-Content -Path $helper -Value $helperCode -Encoding UTF8
py -3.13 $helper $target $replaceFile $snapshotFile
$rc = $LASTEXITCODE
Remove-Item $replaceFile -Force -ErrorAction SilentlyContinue
Remove-Item $snapshotFile -Force -ErrorAction SilentlyContinue
Remove-Item $helper -Force -ErrorAction SilentlyContinue

if ($rc -ne 0) {
    Write-Host "[ROLLBACK] Restoration depuis $backup" -ForegroundColor Yellow
    Copy-Item $backup $target -Force
    exit $rc
}

Write-Host "[DONE] Endpoints crypto corriges. Restart uvicorn et tester:" -ForegroundColor Green
Write-Host "  GET /api/pplx/crypto" -ForegroundColor Gray
Write-Host "  GET /api/pplx/crypto/BTC" -ForegroundColor Gray
Write-Host "  GET /api/pplx/cycle-snapshot" -ForegroundColor Gray
