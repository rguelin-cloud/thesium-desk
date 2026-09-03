# =====================================================================
# fix_double_utf8_ui.ps1
# Repare le double-encodage UTF-8 dans les fichiers HTML/JS/CSS de l'UI
# Cause : Ã© au lieu de e accent aigu = encode latin-1 puis re-encode utf-8
# Solution : pour chaque fichier, decode bytes en latin-1, re-encode en utf-8
# =====================================================================

$ErrorActionPreference = "Stop"
$Root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
Set-Location $Root

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  FIX DOUBLE-UTF8 UI" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "$Root\_backups_ui_utf8_$ts"
New-Item -ItemType Directory -Path $backupDir | Out-Null
Write-Host "[1/3] Backup dir : $backupDir" -ForegroundColor Green

$py = @'
import sys
import shutil
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
BK   = Path(sys.argv[1])

# Sequences caracteristiques du double-encodage UTF-8 (latin-1 view de l'UTF-8 reel)
# Ã© = e accent aigu, Ã¨ = e accent grave, Ã  = a accent grave, etc.
DOUBLE_MARKERS = [
    "Ã©", "Ã¨", "Ã ", "Ã§", "Ãª", "Ã®", "Ã´", "Ã»", "Ã¢", "Ã¯", "Ã¹",
    "Ã‰", "Ã€", "Ãˆ", "Ã‡", "Ã‚", "Ã”", "Ã›",
    "Â°", "Â§", "â€™", "â€œ", "â€\u009d", "â€\u0093", "â€\u0094",
]

EXTS = {".html", ".htm", ".js", ".css", ".json", ".md"}

# Cherche dans ThesiumDesk (recursif, mais skip backups et dossiers cachees)
SKIP_DIRS = {"_backups", "__pycache__", ".git", "node_modules", "venv", ".venv"}

candidates = []
for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    if path.suffix.lower() not in EXTS:
        continue
    # Skip backups
    if any(part.startswith("_backup") or part in SKIP_DIRS for part in path.parts):
        continue
    candidates.append(path)

print(f"Fichiers candidats (extensions {EXTS}) : {len(candidates)}")
print()

affected = []
for p in candidates:
    try:
        raw = p.read_bytes()
        # Decode en UTF-8 - si echec on skip
        try:
            txt = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        # Cherche markers
        hits = sum(txt.count(m) for m in DOUBLE_MARKERS)
        if hits > 0:
            affected.append((p, hits, txt))
    except Exception as e:
        print(f"  SKIP {p.relative_to(ROOT)} : {e}")

if not affected:
    print("[OK] Aucun fichier avec double-encodage detecte")
    sys.exit(0)

print(f"Fichiers AVEC double-encodage : {len(affected)}")
print()
for p, hits, _ in affected:
    print(f"  {hits:>5} occurrences  ->  {p.relative_to(ROOT)}")
print()

# =====================================================================
# Reparation
# =====================================================================
print("=" * 60)
print("Reparation : decode latin-1 -> re-encode utf-8")
print("=" * 60)

for p, hits, txt in affected:
    rel = p.relative_to(ROOT)
    # Backup
    bk_path = BK / rel
    bk_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, bk_path)

    # Reparation : on prend le texte UTF-8 actuel, on l'encode en latin-1
    # (ca recupere les bytes originaux UTF-8), puis on decode en UTF-8.
    try:
        fixed_bytes = txt.encode("latin-1")
        fixed_txt   = fixed_bytes.decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError) as e:
        print(f"  KO {rel} : {e} (skip)")
        continue

    # Verifier qu'on a bien reduit les markers (sinon le fichier mixe)
    remaining = sum(fixed_txt.count(m) for m in DOUBLE_MARKERS)
    if remaining > 0:
        # Peut-etre du quadruple-encodage : retenter
        try:
            fixed_bytes2 = fixed_txt.encode("latin-1")
            fixed_txt2   = fixed_bytes2.decode("utf-8")
            remaining2 = sum(fixed_txt2.count(m) for m in DOUBLE_MARKERS)
            if remaining2 < remaining:
                fixed_txt = fixed_txt2
                remaining = remaining2
                note = " (quadruple corrige)"
            else:
                note = " (partiel)"
        except Exception:
            note = " (partiel)"
    else:
        note = ""

    p.write_text(fixed_txt, encoding="utf-8")
    print(f"  OK {rel}  {hits} -> {remaining}{note}")

print()
print("Backups dans :", BK)
'@

$tmp = "$env:TEMP\_fix_ui.py"
$py | Set-Content -Path $tmp -Encoding UTF8

Write-Host ""
Write-Host "[2/3] Detection et reparation..." -ForegroundColor Yellow
py $tmp $backupDir

# =====================================================================
# Verification HTTP
# =====================================================================
Write-Host ""
Write-Host "[3/3] Verification HTTP (echantillon)..." -ForegroundColor Yellow
$verify = @'
import sys, urllib.request, re
try:
    req = urllib.request.Request("http://127.0.0.1:8000/", headers={"Cache-Control":"no-cache"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        ct = resp.headers.get("Content-Type", "?")
        body = resp.read().decode("utf-8", errors="replace")
    print(f"  GET /  ->  Content-Type: {ct}")
    # Cherche marker
    markers = ["Ã©", "Ã¨", "Ã "]
    hits = sum(body.count(m) for m in markers)
    print(f"  Markers double-utf8 dans le HTML servi : {hits}")
    # Cherche un mot avec accent OK
    ok_words = re.findall(r"[A-Za-z]*[éèàçêîôûâïùÉÀÈÇÂÔÛ][A-Za-z]*", body)
    print(f"  Mots avec accents corrects detectes : {len(ok_words)}")
    if ok_words:
        print(f"     exemples : {', '.join(ok_words[:8])}")
except Exception as e:
    print(f"  KO verif HTTP : {e}")
'@
$tmpV = "$env:TEMP\_verif_ui.py"
$verify | Set-Content -Path $tmpV -Encoding UTF8
py $tmpV

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  TERMINE - prochaine etape :" -ForegroundColor Cyan
Write-Host "  1. Ctrl+Shift+R dans le navigateur (HARD reload)" -ForegroundColor Cyan
Write-Host "  2. Verifie : PORTFOLIO IDEAL avec E accent aigu correct" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
