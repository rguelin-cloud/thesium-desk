#requires -Version 5.1
<#
.SYNOPSIS
  Déplace le panel Perplexity Insights de la fin du <body> vers l'intérieur de
  <section id="tab-today">, juste avant son </section> de fermeture.

  Idempotent : si le marker [PPLX_PANEL_MOVED_TO_TODAY] est déjà présent, ne fait rien.

  Préserve : le modal <div ... pplx-detail-content ...> (overlay) reste en dehors.

.NOTES
  - Backup créé : index.html.bak_pplx_move_yyyyMMdd_HHmmss
  - Valide la structure HTML par comptage des balises avant/après.
#>
$ErrorActionPreference = 'Stop'
$root  = 'C:\Users\RichardGUELIN\Prod\ThesiumDesk'
$html  = Join-Path $root 'index.html'

if (-not (Test-Path $html)) {
  Write-Host "[ERR] index.html introuvable: $html" -ForegroundColor Red
  exit 1
}

# Helper Python pour la manipulation (regex/AST-like)
$helper = Join-Path $env:TEMP "pplx_move_helper_$(Get-Random).py"
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = "$html.bak_pplx_move_$timestamp"

$pyCode = @'
"""
Déplace le bloc Perplexity Insights (panel + (V2 thesis challenges)) depuis
la fin du <body> vers l'intérieur de <section id="tab-today"> (avant son </section>).

Le modal <div id="pplx-detail-modal"> (ou similaire pplx-detail-content) est PRESERVÉ
au même endroit (c'est un overlay, doit rester hors flow d'onglet).
"""
import re, sys, shutil
from pathlib import Path

SRC = Path(sys.argv[1])
BAK = Path(sys.argv[2])

txt = SRC.read_text(encoding="utf-8-sig", errors="strict")

# Idempotence
if "[PPLX_PANEL_MOVED_TO_TODAY]" in txt:
    print("[SKIP] Marker [PPLX_PANEL_MOVED_TO_TODAY] déjà présent, rien à faire.")
    sys.exit(0)

# 1) Backup
shutil.copy2(SRC, BAK)
print(f"[OK] Backup: {BAK.name}")

# 2) Localiser le bloc à déplacer
#    Début : commentaire <!-- [PPLX_PANEL_V1_HTML] ... -->
#    Fin   : juste avant le bloc modal "pplx-detail-modal" ou "pplx-detail-content"
#            (ou avant </body> s'il n'y a pas de modal)
start_marker = "<!-- [PPLX_PANEL_V1_HTML]"
start = txt.find(start_marker)
if start < 0:
    print("[ERR] Marker [PPLX_PANEL_V1_HTML] introuvable.")
    sys.exit(2)

# Cherche la fin : on prend tout jusqu'au <div id="pplx-detail-modal"> ou similaire
# ou jusqu'à </body> si rien
end_candidates = []
for needle in ['<div id="pplx-detail-modal"',
               '<div id="pplx-thesis-detail-modal"',
               '<div class="pplx-detail-modal"',
               '<div id="pplx-detail-content"',  # parfois directement le content
               '</body>']:
    pos = txt.find(needle, start)
    if pos > 0:
        end_candidates.append((pos, needle))
end_candidates.sort()
if not end_candidates:
    print("[ERR] Impossible de déterminer la fin du bloc à déplacer.")
    sys.exit(3)
end, end_marker = end_candidates[0]

# Si la fin est </body>, on prend tout sauf </body>
block = txt[start:end].rstrip()
print(f"[INFO] Bloc à déplacer : offsets {start}..{end} ({end - start} chars), fin marker='{end_marker}'")
print(f"[INFO] Bloc commence par: {block[:80]!r}")
print(f"[INFO] Bloc finit par   : {block[-80:]!r}")

# 3) Localiser le </section> de fermeture de <section id="tab-today">
m = re.search(r'<section\s+class="tab-content active"\s+id="tab-today"[^>]*>', txt)
if not m:
    m = re.search(r'<section[^>]*id="tab-today"[^>]*>', txt)
if not m:
    print("[ERR] <section id='tab-today'> introuvable.")
    sys.exit(4)

today_open_end = m.end()

# Trouve le </section> correspondant — il faut compter les <section> imbriqués
# (mais ici les tab-content ne sont pas imbriqués, donc le 1er </section> après suffit)
# Pour être robuste : on cherche le prochain <section> ouvrant ET la prochaine fermeture
depth = 1
pos = today_open_end
close_idx = -1
while pos < len(txt) and depth > 0:
    next_open  = txt.find('<section', pos)
    next_close = txt.find('</section>', pos)
    if next_close < 0:
        break
    if next_open >= 0 and next_open < next_close:
        depth += 1
        pos = next_open + len('<section')
    else:
        depth -= 1
        if depth == 0:
            close_idx = next_close
            break
        pos = next_close + len('</section>')

if close_idx < 0:
    print("[ERR] </section> de fermeture de tab-today introuvable.")
    sys.exit(5)

print(f"[INFO] tab-today : ouverture @ {m.start()}..{m.end()}, fermeture </section> @ {close_idx}")

# 4) Effectuer le déplacement
#    On insère le bloc avant </section> de tab-today, et on retire le bloc original.
move_marker = "\n  <!-- [PPLX_PANEL_MOVED_TO_TODAY] Bloc déplacé depuis la fin du body -->\n"
insert_block = move_marker + block + "\n"

# Important : si on insère AVANT de retirer, les offsets changent.
# On fait : retirer d'abord (le bloc original est PLUS LOIN dans le fichier que tab-today),
# puis insérer avec offset recalculé. Mais le close_idx vient AVANT start.
# Vérifions :
if close_idx >= start:
    print(f"[ERR] close_idx ({close_idx}) >= start du bloc ({start}). Cas inattendu.")
    sys.exit(6)

# Donc : insérer en close_idx, puis adjuster start/end pour le retrait
inserted_len = len(insert_block)
new_txt = txt[:close_idx] + insert_block + txt[close_idx:]
# Recalcul des offsets du bloc à retirer
new_start = start + inserted_len
new_end   = end   + inserted_len
new_txt   = new_txt[:new_start] + new_txt[new_end:]

# 5) Validation rapide : compter les balises <section>, </section>, <div>, </div>
def count(txt, tag):
    return len(re.findall(re.escape(tag), txt, re.IGNORECASE))

before_section_open  = count(txt,    '<section')
before_section_close = count(txt,    '</section>')
after_section_open   = count(new_txt,'<section')
after_section_close  = count(new_txt,'</section>')

print(f"[CHECK] <section>  : avant={before_section_open}  après={after_section_open}")
print(f"[CHECK] </section> : avant={before_section_close} après={after_section_close}")
print(f"[CHECK] taille     : avant={len(txt)}  après={len(new_txt)}  diff={len(new_txt)-len(txt)}")

if (before_section_open != after_section_open or
    before_section_close != after_section_close):
    print("[ERR] Le nombre de balises <section> a changé après déplacement, abort.")
    sys.exit(7)

# 6) Écrire en UTF-8 sans BOM
SRC.write_text(new_txt, encoding="utf-8")
print(f"[OK] index.html mis à jour ({len(new_txt)} chars).")
print(f"[OK] Marker [PPLX_PANEL_MOVED_TO_TODAY] inséré dans tab-today.")
'@

Set-Content -Path $helper -Value $pyCode -Encoding UTF8

Write-Host "[STEP] Exécution du helper Python..." -ForegroundColor Cyan
& py -3.13 $helper $html $backup
$ec = $LASTEXITCODE

Remove-Item $helper -Force -ErrorAction SilentlyContinue

if ($ec -ne 0) {
  Write-Host "[FAIL] Helper exited with code $ec. Restauration backup si modifié." -ForegroundColor Red
  if (Test-Path $backup) {
    # Restore seulement si index.html a été touché
    $bak  = (Get-Item $backup).LastWriteTimeUtc
    $cur  = (Get-Item $html).LastWriteTimeUtc
    if ($cur -gt $bak) {
      Copy-Item $backup $html -Force
      Write-Host "[OK] index.html restauré depuis backup." -ForegroundColor Yellow
    }
  }
  exit $ec
}

Write-Host ""
Write-Host "[DONE] Patch appliqué." -ForegroundColor Green
Write-Host "       Recharge l'UI avec Ctrl+F5 et va sur l'onglet Today." -ForegroundColor Green
Write-Host "       Le panel Perplexity Insights doit maintenant être visible sous Recent Activity." -ForegroundColor Green
