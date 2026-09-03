#requires -Version 5.1
<#
.SYNOPSIS
  Remplace le bloc CSS [PPLX_PANEL_DARK_CSS_V1] (mauvais fallbacks) par
  [PPLX_PANEL_DARK_CSS_V2] qui utilise les vraies variables du thème Hydra Teal :
    --color-surface, --color-surface-2, --color-text, --color-text-muted,
    --color-border, --color-divider, --color-surface-offset, --color-primary

  Idempotent : si V2 déjà présent, skip. Si V1 présent, remplacé.
#>
$ErrorActionPreference = 'Stop'
$root = 'C:\Users\RichardGUELIN\Prod\ThesiumDesk'
$html = Join-Path $root 'index.html'

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = "$html.bak_pplx_dark_v2_$timestamp"

$helper = Join-Path $env:TEMP "pplx_dark_v2_$(Get-Random).py"

$pyCode = @'
import sys, shutil, re
from pathlib import Path

HTML = Path(sys.argv[1])
BAK  = Path(sys.argv[2])
txt = HTML.read_text(encoding="utf-8-sig", errors="strict")

MARKER_V1 = "[PPLX_PANEL_DARK_CSS_V1]"
MARKER_V2 = "[PPLX_PANEL_DARK_CSS_V2]"

if MARKER_V2 in txt:
    print(f"[SKIP] {MARKER_V2} déjà présent.")
    sys.exit(0)

shutil.copy2(HTML, BAK)
print(f"[OK] Backup: {BAK.name}")

# Nouveau bloc CSS — utilise les vraies variables du thème
new_block = """<style>
/* === [PPLX_PANEL_DARK_CSS_V2] — Aligné sur le thème Hydra Teal (light/dark) === */
#pplx-insights-panel {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg, 0.5rem);
  color: var(--color-text);
  padding: var(--space-5, 1.25rem);
  margin: var(--space-5, 1.25rem) 0;
  box-shadow: var(--shadow-sm);
}
#pplx-insights-panel header,
#pplx-insights-panel > header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3, 0.75rem);
}
#pplx-insights-panel h2,
#pplx-insights-panel h3,
#pplx-insights-panel h4 {
  color: var(--color-text);
  margin: 0;
}
#pplx-insights-panel small,
#pplx-insights-panel .pplx-muted,
#pplx-insights-panel .pplx-age,
#pplx-insights-panel .pplx-ts {
  color: var(--color-text-muted);
}
#pplx-insights-panel table {
  width: 100%;
  border-collapse: collapse;
  background: transparent;
  color: var(--color-text);
  font-size: var(--text-sm);
}
#pplx-insights-panel th {
  background: var(--color-surface-offset);
  color: var(--color-text-muted);
  border-bottom: 1px solid var(--color-divider);
  text-align: left;
  font-weight: 600;
  padding: var(--space-2, 0.5rem) var(--space-3, 0.75rem);
  text-transform: uppercase;
  font-size: var(--text-xs);
  letter-spacing: 0.02em;
}
#pplx-insights-panel td {
  border-bottom: 1px solid var(--color-divider);
  padding: var(--space-2, 0.5rem) var(--space-3, 0.75rem);
}
#pplx-insights-panel tr:hover td {
  background: var(--color-surface-2);
}
#pplx-insights-panel button {
  background: var(--color-surface-2);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm, 0.25rem);
  padding: var(--space-1, 0.25rem) var(--space-3, 0.75rem);
  cursor: pointer;
  font-size: var(--text-sm);
  transition: background var(--transition-interactive, 180ms);
}
#pplx-insights-panel button:hover {
  background: var(--color-surface-offset);
  border-color: var(--color-primary);
}
#pplx-insights-panel a {
  color: var(--color-primary);
  text-decoration: none;
}
#pplx-insights-panel a:hover {
  text-decoration: underline;
}
/* Sections internes (Crypto, Equity, Thesis) */
#pplx-insights-panel h3 {
  margin-top: var(--space-4, 1rem);
  font-size: var(--text-lg);
}
#pplx-insights-panel h3:first-of-type {
  margin-top: 0;
}
/* Audit ligne du bas (texte verbeux gris) */
#pplx-insights-panel .pplx-audit,
#pplx-insights-panel [class*="audit"] {
  color: var(--color-text-faint);
  font-size: var(--text-xs);
  margin-top: var(--space-3, 0.75rem);
  word-break: break-word;
}
/* Modal détail challenge */
#pplx-detail-modal,
.pplx-detail-modal {
  background: oklch(0 0 0 / 0.6) !important;
}
#pplx-detail-content,
.pplx-detail-content {
  background: var(--color-surface);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg, 0.5rem);
  box-shadow: var(--shadow-panel);
}
#pplx-detail-content h2,
#pplx-detail-content h3,
.pplx-detail-content h2,
.pplx-detail-content h3 {
  color: var(--color-text);
}
/* === FIN [PPLX_PANEL_DARK_CSS_V2] === */
</style>
"""

# 1) Supprime l'ancien bloc V1 s'il existe
v1_pattern = re.compile(
    r"<style>\s*\n?\s*/\*\s*===\s*\[PPLX_PANEL_DARK_CSS_V1\].*?===\s*FIN\s*\[PPLX_PANEL_DARK_CSS_V1\]\s*===\s*\*/\s*\n?\s*</style>\s*",
    re.DOTALL
)
m = v1_pattern.search(txt)
if m:
    print(f"[INFO] Suppression de V1 ({m.end()-m.start()} chars) à offset {m.start()}")
    txt = txt[:m.start()] + txt[m.end():]
else:
    print("[INFO] V1 non trouvé (ok si premier passage post-rollback ou déjà nettoyé).")

# 2) Injecte V2 juste avant </head>
m = re.search(r"</head>", txt)
if not m:
    print("[ERR] </head> introuvable")
    sys.exit(1)
new_txt = txt[:m.start()] + new_block + "\n" + txt[m.start():]
HTML.write_text(new_txt, encoding="utf-8")
print(f"[OK] V2 injecté avant </head>. Taille finale: {len(new_txt)} chars.")
'@

Set-Content -Path $helper -Value $pyCode -Encoding UTF8

Write-Host "[STEP] Application du patch CSS V2..." -ForegroundColor Cyan
& py -3.13 $helper $html $backup
$ec = $LASTEXITCODE
Remove-Item $helper -Force -ErrorAction SilentlyContinue

if ($ec -ne 0) {
  Write-Host "[FAIL] Patch exited $ec" -ForegroundColor Red
  if (Test-Path $backup) {
    $bak  = (Get-Item $backup).LastWriteTimeUtc
    $cur  = (Get-Item $html).LastWriteTimeUtc
    if ($cur -gt $bak) {
      Copy-Item $backup $html -Force
      Write-Host "[OK] Restoré depuis backup." -ForegroundColor Yellow
    }
  }
  exit $ec
}

Write-Host ""
Write-Host "[DONE] Patch CSS V2 appliqué." -ForegroundColor Green
Write-Host "       Marker [PPLX_PANEL_DARK_CSS_V2] inséré." -ForegroundColor Green
Write-Host "       Ctrl+F5 sur l'UI : le panel doit maintenant suivre le mode sombre." -ForegroundColor Green
