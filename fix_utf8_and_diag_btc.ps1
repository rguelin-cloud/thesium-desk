# =====================================================================
# fix_utf8_and_diag_btc.ps1
# Combo : Fix UI UTF-8 + Diagnostic pourquoi BTC n'est jamais propose
# =====================================================================

$ErrorActionPreference = "Stop"
$Root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
Set-Location $Root

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  FIX UTF-8 UI + DIAG BTC" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------
# 1. Backup api_server_with_static.py
# ---------------------------------------------------------------------
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "$Root\_backups_utf8_$ts"
New-Item -ItemType Directory -Path $backupDir | Out-Null
Copy-Item "$Root\api_server_with_static.py" "$backupDir\" -Force
Write-Host "[1/3] Backup OK : $backupDir" -ForegroundColor Green

# ---------------------------------------------------------------------
# 2. Patch UTF-8 : sous-classer StaticFiles
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[2/3] Patch UTF-8 StaticFiles + Diag BTC..." -ForegroundColor Yellow

$patchScript = @'
import re
from pathlib import Path

api = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server_with_static.py")
src = api.read_text(encoding="utf-8", errors="ignore")
original = src

# --- A. Si deja patche, skip
if "class UTF8StaticFiles" in src:
    print("  [utf8_patch] Deja patche, skip")
else:
    # --- B. Ajouter une sous-classe avant le mount
    # On l'injecte juste avant la ligne 'app.mount("/", StaticFiles(...))'
    mount_re = re.compile(r'app\.mount\("/", StaticFiles\(directory=([^)]+)\), name="static"\)')
    m = mount_re.search(src)
    if not m:
        print("  [utf8_patch] Pattern mount introuvable - patch impossible")
    else:
        directory_expr = m.group(1)

        utf8_class = '''
# ---------- UTF-8 StaticFiles patch ----------
from starlette.staticfiles import StaticFiles as _StaticFiles
from starlette.responses import Response as _Response

class UTF8StaticFiles(_StaticFiles):
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if hasattr(resp, "media_type") and resp.media_type:
            mt = resp.media_type.lower()
            if mt.startswith("text/") or mt in ("application/javascript",
                                                  "application/json",
                                                  "application/xml"):
                if "charset" not in (resp.headers.get("content-type") or ""):
                    resp.headers["content-type"] = f"{resp.media_type}; charset=utf-8"
        return resp
# ----------------------------------------------
'''

        # Injecte la classe juste avant le mount
        new_mount = f'app.mount("/", UTF8StaticFiles(directory={directory_expr}), name="static")'
        src = src.replace(m.group(0), utf8_class.rstrip() + "\n\n" + new_mount)
        print("  [utf8_patch] Sous-classe UTF8StaticFiles injectee")

if src != original:
    api.write_text(src, encoding="utf-8")
    print("  [utf8_patch] Ecrit")
else:
    print("  [utf8_patch] Aucun changement")

# --- C. Diagnostic BTC dans portfolio_construction_agent.py
print()
print("  [diag_btc] Recherche du filtrage des tickers dans PCA...")
pca = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py")
psrc = pca.read_text(encoding="utf-8", errors="ignore")

# Cherche : filtres, where, asset_class, get_eligible, get_candidates
patterns = [
    (r"def\s+get_eligible[^(]*\([^)]*\)",     "def get_eligible"),
    (r"def\s+get_candidates[^(]*\([^)]*\)",   "def get_candidates"),
    (r"def\s+build_targets[^(]*\([^)]*\)",    "def build_targets"),
    (r"def\s+propose[^(]*\([^)]*\)",          "def propose"),
    (r"asset_class\s*[!=]=\s*['\"][^'\"]+['\"]", "asset_class filter"),
    (r"WHERE[^;]*asset_class",                "SQL where asset_class"),
    (r"ticker\s+IN\s*\([^)]+\)",              "ticker IN (..)"),
    (r"BTC",                                  "BTC mention"),
    (r"crypto",                               "crypto mention"),
]
for p, label in patterns:
    for m in re.finditer(p, psrc, re.IGNORECASE):
        ln = psrc[:m.start()].count("\n") + 1
        line = psrc.splitlines()[ln-1].strip()[:90]
        print(f"  L{ln:<5} [{label}] {line}")

# --- D. Verifier qu'il existe des theses pour BTC
print()
print("  [diag_btc] Theses BTC dans la base ?")
import sqlite3
con = sqlite3.connect(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
con.row_factory = sqlite3.Row
cur = con.cursor()
cur.execute("""
    SELECT t.id, t.agent_type, t.conviction_score, t.proposed_action,
           t.status, datetime(t.created_at,'localtime') AS created
      FROM theses t JOIN instruments i ON i.id=t.instrument_id
     WHERE i.ticker='BTC' ORDER BY t.id DESC LIMIT 10
""")
btc_theses = cur.fetchall()
print(f"  -> {len(btc_theses)} theses BTC trouvees")
for t in btc_theses:
    print(f"     #{t['id']} agent={t['agent_type']:<20} conv={t['conviction_score']} "
          f"action={t['proposed_action']:<10} status={t['status']:<10} created={t['created']}")

# --- E. Liste agents actifs (qui auraient du produire des theses BTC)
print()
print("  [diag_btc] Repartition des theses par agent (toutes confondues) :")
cur.execute("""
    SELECT agent_type, COUNT(*) AS nb,
           datetime(MAX(created_at),'localtime') AS last_run
      FROM theses
     GROUP BY agent_type
     ORDER BY nb DESC
""")
for r in cur.fetchall():
    print(f"     {r['agent_type']:<25} {r['nb']:>4} theses   last={r['last_run']}")

con.close()
'@

$tmpPy = "$env:TEMP\_patch_utf8_diag_btc.py"
$patchScript | Set-Content -Path $tmpPy -Encoding UTF8
py $tmpPy

# ---------------------------------------------------------------------
# 3. Resume
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[3/3] Resume" -ForegroundColor Yellow
Write-Host "  - Backup api_server_with_static.py : $backupDir" -ForegroundColor Gray
Write-Host "  - Patch UTF-8 applique"                          -ForegroundColor Gray
Write-Host "  - Diag BTC affiche ci-dessus"                    -ForegroundColor Gray
Write-Host ""
Write-Host "  ETAPE SUIVANTE : redemarre uvicorn pour appliquer le patch UTF-8" -ForegroundColor Cyan
Write-Host "    -> Ctrl+C dans la fenetre uvicorn, puis relance la meme commande" -ForegroundColor Gray
Write-Host ""
