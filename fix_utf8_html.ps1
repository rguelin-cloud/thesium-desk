# fix_utf8_html.ps1
# Repare le double-encoding UTF-8 dans index.html (et autres fichiers UI/HTML/JS)
# Memes patterns que execution_engine

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"

Write-Host "=== FIX UTF-8 dans index.html + UI ===" -ForegroundColor Cyan
Write-Host ""

# Backup index.html
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$idx = "$root\index.html"
$idx_backup = "$idx.bak.utf8fix.$ts"
Copy-Item $idx $idx_backup -Force
Write-Host "[OK] Backup : $idx_backup" -ForegroundColor Green

$py = @'
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

fixes = {
    "\u00c3\u00a9": "\u00e9",  "\u00c3\u00a8": "\u00e8",  "\u00c3\u00a0": "\u00e0",
    "\u00c3\u00aa": "\u00ea",  "\u00c3\u00ae": "\u00ee",  "\u00c3\u00b4": "\u00f4",
    "\u00c3\u00b9": "\u00f9",  "\u00c3\u00a2": "\u00e2",  "\u00c3\u00bb": "\u00fb",
    "\u00c3\u00af": "\u00ef",  "\u00c3\u00ab": "\u00eb",  "\u00c3\u00b6": "\u00f6",
    "\u00c3\u00a7": "\u00e7",  "\u00c3\u00b1": "\u00f1",
    "\u00c3\u0080": "\u00c0",  "\u00c3\u0089": "\u00c9",  "\u00c3\u0088": "\u00c8",
    "\u00c3\u008a": "\u00ca",  "\u00c3\u0087": "\u00c7",  "\u00c3\u0094": "\u00d4",
    "\u00c3\u0099": "\u00d9",  "\u00c3\u009b": "\u00db",
    "\u00e2\u20ac\u2122": "\u2019", "\u00e2\u20ac\u201c": "\u2013",
    "\u00e2\u20ac\u201d": "\u2014", "\u00e2\u20ac\u00a6": "\u2026",
    # Cas vus dans l'UI : "Ã\u20ac\"" et "Ã€\"" sont des em-dash double-encodes specifiques
    "\u00c3\u20ac\u0022": "\u2014",  # Ã€" (vu dans capture) -> em-dash
    "\u00c3\u20ac": "\u2014",        # variant
}

root = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
targets = [
    root / "index.html",
    root / "ui_panel_patch.html",
    root / "app.js",
]

for target in targets:
    if not target.exists():
        print(f"[SKIP] {target.name} introuvable")
        continue
    
    with open(target, "rb") as f:
        raw = f.read()
    
    text = raw.decode("utf-8", errors="strict")
    
    counts = {}
    for moji in fixes:
        n = text.count(moji)
        if n > 0:
            counts[moji] = n
    
    if not counts:
        print(f"[OK] {target.name} : aucun mojibake")
        continue
    
    print(f"\n[INFO] {target.name} - sequences mojibakes :")
    total = 0
    for m, n in sorted(counts.items(), key=lambda x: -x[1]):
        rep = fixes[m]
        moji_repr = ' '.join(f'U+{ord(c):04X}' for c in m)
        print(f"  {moji_repr} -> U+{ord(rep):04X} : {n}")
        total += n
    print(f"[INFO] Total : {total}")
    
    fixed_text = text
    for moji in sorted(fixes.keys(), key=lambda x: -len(x)):
        fixed_text = fixed_text.replace(moji, fixes[moji])
    
    with open(target, "wb") as f:
        f.write(fixed_text.encode("utf-8"))
    
    new_size = len(fixed_text.encode("utf-8"))
    print(f"[OK] {target.name} reecrit ({new_size} bytes, gain {len(raw)-new_size})")
    
    # Verif post-fix
    with open(target, "rb") as f:
        raw_after = f.read()
    text_after = raw_after.decode("utf-8", errors="replace")
    remaining = 0
    for moji in counts:
        remaining += text_after.count(moji)
    print(f"[INFO] Sequences residuelles : {remaining}")
    
    # Sample lignes critiques
    for line_no, line in enumerate(text_after.split("\n"), 1):
        if "PORTFOLIO" in line.upper() and ("30 DAYS" in line.upper() or "IDEAL" in line.upper() or "ID\u00c9AL" in line):
            print(f"  L{line_no}: {line.strip()[:140]}")

print("\n[OK] Termine")
'@

$tmp = "$env:TEMP\fix_html_utf8.py"
[System.IO.File]::WriteAllText($tmp, $py, (New-Object System.Text.UTF8Encoding $false))
& py -3.13 $tmp

Write-Host ""
Write-Host "=== TERMINE ===" -ForegroundColor Green
Write-Host "Ctrl+F5 dans le navigateur (vider cache + reload)" -ForegroundColor White
