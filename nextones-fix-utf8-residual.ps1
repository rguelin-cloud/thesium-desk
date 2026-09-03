# Fix résidus mojibake ciblés : â— → ● et Â· → ·
# Idempotent. Backup automatique.

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"

# Lance un helper Python pour appliquer le fix (évite les pièges PowerShell+UTF-8)
$helper = @'
# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
TS = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d_%H%M%S")

# Mapping résiduel : seulement ces 2 séquences ciblées
RESIDUAL_MAP = {
    "\u00e2\u2014": "\u25cf",   # â— -> ●
    "\u00c2\u00b7": "\u00b7",   # Â· -> ·
}

TARGETS = [
    ROOT / "index.html",
    ROOT / "app.js",
    ROOT / "static" / "index.html",
    ROOT / "static" / "app.js",
]

print(f"=== Fix résidus mojibake (ciblé) - TS={TS} ===\n")

total_fixed = 0
for p in TARGETS:
    if not p.exists():
        continue
    raw = p.read_bytes()
    has_bom = raw.startswith(b'\xef\xbb\xbf')
    if has_bom:
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        print(f"  [SKIP] {p.name}: decode error {e}")
        continue

    before = {k: text.count(k) for k in RESIDUAL_MAP}
    if sum(before.values()) == 0:
        print(f"  [PROPRE] {p.relative_to(ROOT)}")
        continue

    # Backup
    bak = p.with_name(p.name + f".bak_resid_{TS}")
    bak.write_bytes((b'\xef\xbb\xbf' if has_bom else b'') + raw)

    # Sort by length desc
    for src in sorted(RESIDUAL_MAP.keys(), key=len, reverse=True):
        text = text.replace(src, RESIDUAL_MAP[src])

    after = {k: text.count(k) for k in RESIDUAL_MAP}
    p.write_text(text, encoding="utf-8", newline="\n")
    total_fixed += 1
    rel = p.relative_to(ROOT)
    print(f"  [FIX] {rel}")
    for k, v in before.items():
        if v > 0:
            print(f"     {repr(k)} : {v} -> {after[k]}")

print(f"\n=== {total_fixed} fichier(s) corrigé(s) ===")

# Validation : recompter
print("\n=== Validation finale ===")
for p in TARGETS:
    if not p.exists():
        continue
    text = p.read_text(encoding="utf-8")
    residual = sum(text.count(k) for k in RESIDUAL_MAP)
    rel = p.relative_to(ROOT)
    print(f"  {rel}: {residual} résidus")
'@

$pyFile = Join-Path $env:TEMP "nextones_fix_residual.py"
$helper | Out-File -FilePath $pyFile -Encoding UTF8 -NoNewline

Write-Host "Helper écrit : $pyFile"
Write-Host ""
py -3.13 $pyFile $ts

Write-Host ""
Write-Host "=== Vérification globale (recherche tous résidus) ==="
$residuals = @("â—", "Â·", "â¿", "Ã©", "Ã‰")
foreach ($r in $residuals) {
    foreach ($f in @("index.html", "app.js", "static\index.html", "static\app.js")) {
        $full = Join-Path $root $f
        if (Test-Path $full) {
            $content = Get-Content -Raw -Path $full -Encoding UTF8
            $count = ([regex]::Matches($content, [regex]::Escape($r))).Count
            if ($count -gt 0) {
                Write-Host "  $f : '$r' x $count" -ForegroundColor Yellow
            }
        }
    }
}
Write-Host ""
Write-Host "=== Terminé. Rafraîchis le navigateur (Ctrl+Shift+R) pour voir le résultat ==="
