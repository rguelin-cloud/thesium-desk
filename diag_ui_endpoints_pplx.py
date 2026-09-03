# [DIAG_UI_PPLX_V1] Verifie quels endpoints API exposent les donnees Perplexity
# et donc ce qui est visible (ou pas) dans l'UI suite a Crypto + Factor agents.
#
# Repond a: "y a t il des changements dans l'UI suite a nos 2 ajouts ?"
from __future__ import annotations
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = ROOT / "api_server.py"
STATIC = ROOT / "static"
DB = ROOT / "thesium.db"

print("=" * 80)
print("DIAG UI / API - Exposition des donnees Perplexity")
print("=" * 80)

src = API.read_text(encoding="utf-8-sig")

# ---------------------------------------------------------------------------
# 1. Tables Perplexity dans la DB
# ---------------------------------------------------------------------------
print("\n--- Tables Perplexity en DB ---")
cx = sqlite3.connect(str(DB), timeout=10)
cx.row_factory = sqlite3.Row
try:
    rows = cx.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND "
        "(name LIKE '%pplx%' OR name LIKE 'crypto_context%' OR name LIKE 'factor_quality%')"
    ).fetchall()
    pplx_tables = [r["name"] for r in rows]
    for t in pplx_tables:
        cnt = cx.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
        print(f"  {t}: {cnt} rows")
finally:
    cx.close()

# ---------------------------------------------------------------------------
# 2. Endpoints qui touchent aux tables Perplexity
# ---------------------------------------------------------------------------
print("\n--- Endpoints API exposant Perplexity ---")
keywords = ["crypto_context", "factor_quality_context", "pplx_cache", "pplx_audit", "narrative", "quality_narrative"]
hits = {}
for m in re.finditer(r"@app\.(get|post|delete|put)\(['\"]([^'\"]+)['\"]\)", src):
    method = m.group(1).upper()
    route = m.group(2)
    # Capture la fonction qui suit
    after = src[m.end(): m.end() + 3000]
    func_match = re.search(r"def\s+(\w+)\([^)]*\):(.+?)(?=\n@app\.|\nclass |\Z)", after, re.DOTALL)
    if not func_match:
        continue
    body = func_match.group(2)
    for kw in keywords:
        if kw in body:
            hits.setdefault((method, route), set()).add(kw)

if hits:
    for (method, route), kws in hits.items():
        print(f"  {method:5} {route}  ->  {sorted(kws)}")
else:
    print("  AUCUN endpoint ne lit les tables Perplexity directement")

# ---------------------------------------------------------------------------
# 3. /api/agents/run + factor_scores : que renvoie-t-il ?
# ---------------------------------------------------------------------------
print("\n--- Endpoints agents (FactorAgent expose quality_narrative ?) ---")
for m in re.finditer(r"@app\.(get|post)\(['\"]([^'\"]*agent[^'\"]*)['\"]\)", src):
    print(f"  {m.group(1).upper():5} {m.group(2)}")

# ---------------------------------------------------------------------------
# 4. Fichiers UI / HTML / JS qui parlent de crypto / quality / pplx
# ---------------------------------------------------------------------------
print("\n--- Fichiers UI (HTML/JS) mentionnant crypto/quality/pplx/narrative ---")
if STATIC.exists():
    for ext in ("*.html", "*.js", "*.css"):
        for f in STATIC.rglob(ext):
            try:
                txt = f.read_text(encoding="utf-8-sig", errors="ignore")
            except Exception:
                continue
            kws = []
            for kw in ("crypto_context", "factor_quality", "quality_narrative", "pplx", "narrative_score", "red_flags"):
                if kw in txt:
                    kws.append(kw)
            if kws:
                print(f"  {f.relative_to(ROOT)}  ->  {kws}")
else:
    print("  (dossier static introuvable)")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("""
Si AUCUN endpoint ne lit crypto_context / factor_quality_context, et
AUCUN fichier UI ne reference ces tables, alors :

  L'UI n'a PAS change visuellement apres Crypto + Factor agents.

Les donnees Perplexity influencent SEULEMENT les scores internes:
  - FactorAgent : quality_score mixe inv-vol et narrative -> impact sur ranking
  - CryptoAgent : narrative_score peut moduler conviction crypto

Pour rendre visible dans l'UI, il faudrait ajouter:
  - GET /api/pplx/crypto/{ticker}   -> renvoie narrative + sources
  - GET /api/pplx/quality/{ticker}  -> renvoie quality + red_flags + catalysts
  - Un panel "Perplexity Insights" cote front avec badges sources et tendances
""")
