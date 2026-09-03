# =====================================================================
# fix_utf8_and_btc_v2.ps1
# v2 : patch UTF-8 robuste + patch PCA pour BTC gap-fill initial
# =====================================================================

$ErrorActionPreference = "Stop"
$Root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
Set-Location $Root

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  FIX UTF-8 UI + BTC GAP-FILL  (v2)" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "$Root\_backups_v2_$ts"
New-Item -ItemType Directory -Path $backupDir | Out-Null
Copy-Item "$Root\api_server_with_static.py"           "$backupDir\" -Force
Copy-Item "$Root\portfolio_construction_agent.py"     "$backupDir\" -Force
Write-Host "[1/4] Backup OK : $backupDir" -ForegroundColor Green

# ---------------------------------------------------------------------
# 2. Patch UTF-8 robuste
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[2/4] Patch UTF-8 StaticFiles..." -ForegroundColor Yellow

$utf8Script = @'
import re
from pathlib import Path

api = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server_with_static.py")
src = api.read_text(encoding="utf-8", errors="ignore")
original = src

if "class UTF8StaticFiles" in src:
    print("  [utf8] Deja patche, skip")
else:
    # Affiche la ligne mount existante (peu importe son format)
    mount_pat = re.compile(r'^(.*app\.mount\([^\n]*StaticFiles[^\n]*\).*)$', re.MULTILINE)
    matches = list(mount_pat.finditer(src))
    if not matches:
        print("  [utf8] AUCUN mount trouve - dump des 5 lignes contenant 'mount' :")
        for ln_no, line in enumerate(src.splitlines(), 1):
            if "mount" in line.lower():
                print(f"     L{ln_no}: {line.strip()[:120]}")
    else:
        for m in matches:
            ln = src[:m.start()].count("\n") + 1
            print(f"  [utf8] Ligne mount detectee L{ln} : {m.group(1).strip()[:120]}")

        # Recupere la 1ere occurrence
        m = matches[0]
        line_orig = m.group(1)
        ln = src[:m.start()].count("\n") + 1

        # Remplace 'StaticFiles' par 'UTF8StaticFiles' dans cette ligne
        new_line = line_orig.replace("StaticFiles(", "UTF8StaticFiles(")

        # Trouve l'endroit ou injecter la sous-classe : juste avant app.mount
        utf8_class = '''
# ---------- UTF-8 StaticFiles patch ----------
from starlette.staticfiles import StaticFiles as _StaticFiles_UTF8
class UTF8StaticFiles(_StaticFiles_UTF8):
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if hasattr(resp, "media_type") and resp.media_type:
            mt = resp.media_type.lower()
            if mt.startswith("text/") or mt in (
                "application/javascript", "application/json", "application/xml"):
                ct = resp.headers.get("content-type") or ""
                if "charset" not in ct:
                    resp.headers["content-type"] = f"{resp.media_type}; charset=utf-8"
        return resp
# ----------------------------------------------
'''

        src = src.replace(line_orig, utf8_class + "\n" + new_line, 1)
        print("  [utf8] Injection OK")

if src != original:
    api.write_text(src, encoding="utf-8")
    print("  [utf8] Fichier reecrit")
else:
    print("  [utf8] Pas de changement")
'@

$tmpPy1 = "$env:TEMP\_utf8_v2.py"
$utf8Script | Set-Content -Path $tmpPy1 -Encoding UTF8
py $tmpPy1

# ---------------------------------------------------------------------
# 3. Patch PCA : BTC gap-fill initial
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[3/4] Diagnostic PCA pour identifier le filtre BTC..." -ForegroundColor Yellow

$pcaInspect = @'
import re
from pathlib import Path

pca = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py")
src = pca.read_text(encoding="utf-8", errors="ignore")
lines = src.splitlines()

# Trouve la fonction principale : build_targets, propose_orders, _build, run
print("  [pca] Fonctions detectees :")
for ln, line in enumerate(lines, 1):
    if re.match(r"^\s*def\s+\w+", line):
        print(f"     L{ln:>4}  {line.strip()[:90]}")

# Cherche les requetes SQL et les filtres
print()
print("  [pca] Requetes SQL pour positions / targets :")
for ln, line in enumerate(lines, 1):
    if re.search(r"(SELECT|FROM|WHERE).{0,50}(portfolio_positions|portfolio_targets|theses)", line, re.IGNORECASE):
        print(f"     L{ln:>4}  {line.strip()[:90]}")
'@

$tmpPy2 = "$env:TEMP\_pca_inspect.py"
$pcaInspect | Set-Content -Path $tmpPy2 -Encoding UTF8
py $tmpPy2

# ---------------------------------------------------------------------
# 4. Resume
# ---------------------------------------------------------------------
Write-Host ""
Write-Host "[4/4] Resume" -ForegroundColor Yellow
Write-Host "  Backup        : $backupDir" -ForegroundColor Gray
Write-Host "  Patch UTF-8   : applique (sauf si deja en place)" -ForegroundColor Gray
Write-Host ""
Write-Host "  ETAPE SUIVANTE :" -ForegroundColor Cyan
Write-Host "    1. Redemarre uvicorn (Ctrl+C puis relance)" -ForegroundColor Gray
Write-Host "    2. Verifie l'UI dans le navigateur (les Ã© doivent disparaitre)" -ForegroundColor Gray
Write-Host "    3. Envoie la sortie du diagnostic PCA ci-dessus pour qu'on patch BTC gap-fill" -ForegroundColor Gray
Write-Host ""
