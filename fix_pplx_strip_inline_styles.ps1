#requires -Version 5.1
<#
.SYNOPSIS
  Retire les attributs style="..." en dur sur les éléments du panel Perplexity Insights
  (#pplx-insights-panel et descendants nommés) pour que le CSS V2 prenne le contrôle.

  Idempotent via marker [PPLX_PANEL_INLINE_STRIP_V1].
#>
$ErrorActionPreference = 'Stop'
$root = 'C:\Users\RichardGUELIN\Prod\ThesiumDesk'
$html = Join-Path $root 'index.html'

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = "$html.bak_inline_strip_$timestamp"

$helper = Join-Path $env:TEMP "pplx_strip_$(Get-Random).py"
$pyCode = @'
import sys, shutil, re
from pathlib import Path

HTML = Path(sys.argv[1])
BAK  = Path(sys.argv[2])
txt = HTML.read_text(encoding="utf-8-sig", errors="strict")

MARKER = "[PPLX_PANEL_INLINE_STRIP_V1]"
if MARKER in txt:
    print(f"[SKIP] {MARKER} déjà présent.")
    sys.exit(0)

shutil.copy2(HTML, BAK)
print(f"[OK] Backup: {BAK.name}")

# Trouve la zone du panel : du marker [PPLX_PANEL_V1_HTML] jusqu'à la fin du body
start = txt.find("<!-- [PPLX_PANEL_V1_HTML]")
if start < 0:
    print("[ERR] [PPLX_PANEL_V1_HTML] introuvable")
    sys.exit(1)

end = txt.find("</body>", start)
if end < 0:
    end = len(txt)

zone = txt[start:end]
print(f"[INFO] Zone panel: {len(zone)} chars (offsets {start}..{end})")

# Compte les attributs style="..." dans la zone AVANT
style_count_before = len(re.findall(r'\bstyle\s*=\s*"[^"]*"', zone))
print(f"[INFO] Attributs style=\"...\" avant: {style_count_before}")

# Retire tous les style="..." dans la zone, mais préserve quelques cas critiques :
#  - display:none (pour les éléments cachés type modal)
#  - position:fixed/absolute (pour les overlays modaux)
def should_keep(style_value):
    sv = style_value.lower()
    # Préserve les styles qui contiennent display:none ou position:fixed/absolute (modal/overlay)
    keep_keywords = ['display:none', 'display: none', 'position:fixed', 'position: fixed',
                     'position:absolute', 'position: absolute', 'z-index']
    return any(k in sv for k in keep_keywords)

def strip_style(m):
    val = m.group(1)
    if should_keep(val):
        return m.group(0)  # garde
    return ''  # retire l'attribut entier

# Pattern : style="..." avec espace optionnel autour de =
zone_new = re.sub(r'\s*\bstyle\s*=\s*"([^"]*)"', strip_style, zone)

# Nettoie les doubles espaces résiduels dans les tags
zone_new = re.sub(r'<(\w+)\s{2,}', r'<\1 ', zone_new)
zone_new = re.sub(r'\s+>', '>', zone_new)

style_count_after = len(re.findall(r'\bstyle\s*=\s*"[^"]*"', zone_new))
print(f"[INFO] Attributs style=\"...\" après : {style_count_after}")
print(f"[INFO] Retirés: {style_count_before - style_count_after}")

# Ajoute un commentaire-marker au début de la zone
marker_line = f"<!-- {MARKER} inline styles retirés pour que CSS V2 prenne effet -->\n"
zone_new = marker_line + zone_new

# Reconstruit le fichier
new_txt = txt[:start] + zone_new + txt[end:]

# Validation rapide : structure HTML intacte
def cnt(t, pat):
    return len(re.findall(pat, t))

checks = [
    ('<section', cnt(txt, r'<section\b'), cnt(new_txt, r'<section\b')),
    ('</section>', cnt(txt, r'</section>'), cnt(new_txt, r'</section>')),
    ('<div', cnt(txt, r'<div\b'), cnt(new_txt, r'<div\b')),
    ('</div>', cnt(txt, r'</div>'), cnt(new_txt, r'</div>')),
    ('<body', cnt(txt, r'<body\b'), cnt(new_txt, r'<body\b')),
    ('</body>', cnt(txt, r'</body>'), cnt(new_txt, r'</body>')),
]
print()
print(f"{'TAG':12} {'AVANT':>6} {'APRES':>6}")
for tag, a, b in checks:
    flag = "  <==" if a != b else ""
    print(f"{tag:12} {a:>6} {b:>6}{flag}")
    if a != b:
        print(f"[ERR] Comptage tags changé pour {tag}, abort.")
        sys.exit(2)

HTML.write_text(new_txt, encoding="utf-8")
print(f"[OK] index.html mis à jour ({len(new_txt)} chars).")
'@

Set-Content -Path $helper -Value $pyCode -Encoding UTF8

Write-Host "[STEP] Stripping des styles inline du panel pplx..." -ForegroundColor Cyan
& py -3.13 $helper $html $backup
$ec = $LASTEXITCODE
Remove-Item $helper -Force -ErrorAction SilentlyContinue

if ($ec -ne 0) {
  Write-Host "[FAIL] Patch exited $ec" -ForegroundColor Red
  if (Test-Path $backup) {
    $bak = (Get-Item $backup).LastWriteTimeUtc
    $cur = (Get-Item $html).LastWriteTimeUtc
    if ($cur -gt $bak) {
      Copy-Item $backup $html -Force
      Write-Host "[OK] Restoré depuis backup." -ForegroundColor Yellow
    }
  }
  exit $ec
}

Write-Host ""
Write-Host "[DONE] Inline styles retirés." -ForegroundColor Green
Write-Host "       Le CSS V2 ([PPLX_PANEL_DARK_CSS_V2]) doit maintenant s'appliquer." -ForegroundColor Green
Write-Host "       Ctrl+F5 et regarde en mode sombre." -ForegroundColor Green
