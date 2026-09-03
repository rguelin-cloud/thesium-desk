#requires -Version 5.1
<#
.SYNOPSIS
  1) Rollback : restaure index.html depuis le dernier backup .bak_pplx_move_*
  2) Patch JS : ajoute du JS qui déplace #pplx-insights-panel dans #tab-today
     au DOMContentLoaded — propre, pas de manipulation HTML risquée.
  3) Patch CSS : adapte le panel au mode sombre via variables CSS.

  Idempotent : marker [PPLX_PANEL_JS_MOVE_V1] dans app.js, [PPLX_PANEL_DARK_CSS_V1] dans index.html
#>
$ErrorActionPreference = 'Stop'
$root  = 'C:\Users\RichardGUELIN\Prod\ThesiumDesk'
$html  = Join-Path $root 'index.html'
$js    = Join-Path $root 'app.js'

# ---- 1) ROLLBACK ----
Write-Host "[STEP 1] Rollback index.html depuis backup..." -ForegroundColor Cyan
$backup = Get-ChildItem -Path $root -Filter 'index.html.bak_pplx_move_*' |
          Sort-Object LastWriteTime -Descending |
          Select-Object -First 1
if (-not $backup) {
  Write-Host "[ERR] Aucun backup pplx_move trouvé." -ForegroundColor Red
  exit 1
}
Copy-Item $backup.FullName $html -Force
Write-Host "[OK] index.html restauré depuis $($backup.Name)" -ForegroundColor Green

# ---- 2) PATCH JS : déplacement runtime ----
Write-Host ""
Write-Host "[STEP 2] Injection du JS de déplacement runtime dans app.js..." -ForegroundColor Cyan

$jsTimestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$jsBackup = "$js.bak_pplx_jsmove_$jsTimestamp"

$helper = Join-Path $env:TEMP "pplx_jsmove_$(Get-Random).py"
$pyCode = @'
import sys, shutil
from pathlib import Path

JS = Path(sys.argv[1])
BAK = Path(sys.argv[2])
txt = JS.read_text(encoding="utf-8-sig", errors="strict")

MARKER = "[PPLX_PANEL_JS_MOVE_V1]"
if MARKER in txt:
    print(f"[SKIP] Marker {MARKER} déjà présent dans app.js.")
    sys.exit(0)

shutil.copy2(JS, BAK)
print(f"[OK] Backup app.js: {BAK.name}")

block = """

// === [PPLX_PANEL_JS_MOVE_V1] ===
// Déplace #pplx-insights-panel dans <section id="tab-today"> au chargement,
// pour qu'il s'affiche sous "Recent Activity" et suive l'état actif/inactif de l'onglet.
(function pplxPanelMoveIntoToday(){
  function doMove(){
    try {
      var panel = document.getElementById('pplx-insights-panel');
      var today = document.getElementById('tab-today');
      if (!panel || !today) {
        return false;
      }
      // Déjà dans Today ? rien à faire
      if (panel.parentElement === today) {
        return true;
      }
      today.appendChild(panel);
      console.log('[pplx] panel déplacé dans tab-today');
      return true;
    } catch (e) {
      console.warn('[pplx] erreur déplacement panel:', e);
      return false;
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', doMove);
  } else {
    doMove();
  }
  // Sécurité : retry après 500ms si le panel est injecté tardivement
  setTimeout(doMove, 500);
  setTimeout(doMove, 2000);
})();
// === FIN [PPLX_PANEL_JS_MOVE_V1] ===

"""

new_txt = txt.rstrip() + block
JS.write_text(new_txt, encoding="utf-8")
print(f"[OK] Block JS ajouté ({len(block)} chars). Total: {len(new_txt)} chars.")
'@
Set-Content -Path $helper -Value $pyCode -Encoding UTF8
& py -3.13 $helper $js $jsBackup
$ec = $LASTEXITCODE
Remove-Item $helper -Force -ErrorAction SilentlyContinue
if ($ec -ne 0) {
  Write-Host "[FAIL] Helper JS exited $ec" -ForegroundColor Red
  exit $ec
}

# ---- 3) PATCH CSS : mode sombre ----
Write-Host ""
Write-Host "[STEP 3] Patch CSS mode sombre dans index.html..." -ForegroundColor Cyan

$htmlTimestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$htmlBackup = "$html.bak_pplx_dark_$htmlTimestamp"

$helper2 = Join-Path $env:TEMP "pplx_dark_$(Get-Random).py"
$pyCode2 = @'
import sys, shutil, re
from pathlib import Path

HTML = Path(sys.argv[1])
BAK = Path(sys.argv[2])
txt = HTML.read_text(encoding="utf-8-sig", errors="strict")

MARKER = "[PPLX_PANEL_DARK_CSS_V1]"
if MARKER in txt:
    print(f"[SKIP] Marker {MARKER} déjà présent.")
    sys.exit(0)

shutil.copy2(HTML, BAK)
print(f"[OK] Backup: {BAK.name}")

css_block = """
<style>
/* === [PPLX_PANEL_DARK_CSS_V1] — Mode sombre pour le panel Perplexity Insights === */
#pplx-insights-panel {
  background: var(--card-bg, var(--bg-secondary, #fafafa)) !important;
  border: 1px solid var(--border-color, var(--border, #e0e0e0)) !important;
  color: var(--text-primary, var(--text, #333)) !important;
}
#pplx-insights-panel header h2,
#pplx-insights-panel header h3,
#pplx-insights-panel h2,
#pplx-insights-panel h3,
#pplx-insights-panel h4 {
  color: var(--text-primary, var(--text, #222)) !important;
}
#pplx-insights-panel table {
  background: transparent !important;
  color: var(--text-primary, var(--text, #333)) !important;
}
#pplx-insights-panel th {
  background: var(--table-header-bg, var(--bg-tertiary, #f0f0f0)) !important;
  color: var(--text-secondary, var(--text-muted, #666)) !important;
  border-bottom: 1px solid var(--border-color, var(--border, #ddd)) !important;
}
#pplx-insights-panel td {
  border-bottom: 1px solid var(--border-color, var(--border, #eee)) !important;
}
#pplx-insights-panel tr:hover td {
  background: var(--row-hover, var(--bg-tertiary, #f5f5f5)) !important;
}
#pplx-insights-panel button {
  background: var(--btn-bg, var(--accent, #fff)) !important;
  color: var(--btn-text, var(--text-primary, #333)) !important;
  border: 1px solid var(--border-color, var(--border, #ccc)) !important;
}
#pplx-insights-panel a {
  color: var(--link-color, var(--accent, #0066cc)) !important;
}
/* Modal détail */
#pplx-detail-modal,
.pplx-detail-modal {
  background: rgba(0,0,0,0.6) !important;
}
#pplx-detail-content,
.pplx-detail-content {
  background: var(--card-bg, var(--bg-secondary, #fff)) !important;
  color: var(--text-primary, var(--text, #333)) !important;
  border: 1px solid var(--border-color, var(--border, #ccc)) !important;
}
/* === FIN [PPLX_PANEL_DARK_CSS_V1] === */
</style>
"""

# Insertion juste avant </head>
m = re.search(r"</head>", txt)
if not m:
    print("[ERR] </head> introuvable")
    sys.exit(1)
new_txt = txt[:m.start()] + css_block + "\n" + txt[m.start():]
HTML.write_text(new_txt, encoding="utf-8")
print(f"[OK] CSS bloc injecté avant </head>. Taille: {len(new_txt)} chars.")
'@
Set-Content -Path $helper2 -Value $pyCode2 -Encoding UTF8
& py -3.13 $helper2 $html $htmlBackup
$ec2 = $LASTEXITCODE
Remove-Item $helper2 -Force -ErrorAction SilentlyContinue
if ($ec2 -ne 0) {
  Write-Host "[FAIL] Helper CSS exited $ec2" -ForegroundColor Red
  exit $ec2
}

Write-Host ""
Write-Host "[DONE] Patches appliqués." -ForegroundColor Green
Write-Host "       1. Rollback HTML  : OK"  -ForegroundColor Green
Write-Host "       2. JS move runtime: ajoute [PPLX_PANEL_JS_MOVE_V1] dans app.js" -ForegroundColor Green
Write-Host "       3. CSS dark mode  : ajoute [PPLX_PANEL_DARK_CSS_V1] avant </head>" -ForegroundColor Green
Write-Host ""
Write-Host "Recharge l'UI avec Ctrl+F5 :"
Write-Host "  - Tous les onglets doivent re-fonctionner"
Write-Host "  - Sur Today, le panel Perplexity Insights apparaît en bas"
Write-Host "  - Mode sombre : les couleurs s'adaptent"
