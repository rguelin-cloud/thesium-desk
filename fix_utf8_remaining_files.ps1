# fix_utf8_remaining_files.ps1
# Fix UTF-8 double-encoding dans les fichiers Python restants :
# - execution_engine_v6_5.py (backup avec mojibake)
# - execution_engine_v6_4_backup.py (clean en theorie, on verifie)
# - api_server_with_static.py (commentaires mojibakes)
# - tous les autres .py du root qui contiennent du mojibake

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"

Write-Host "=== FIX UTF-8 fichiers Python restants ===" -ForegroundColor Cyan
Write-Host ""

$py = @'
import sys
import io
import ast
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
    "\u00c3\u20ac\u0022": "\u2014",
    "\u00c3\u20ac": "\u2014",
}

root = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

# Scanner tous les .py du root (pas les _backups, pas les sous-dossiers)
candidates = []
for p in root.glob("*.py"):
    name = p.name
    # Skip nos propres scripts de diag/fix
    if name.startswith("diag_") or name.startswith("fix_") or name.startswith("verif_"):
        continue
    if name.startswith("find_") or name.startswith("check_") or name.startswith("trace_"):
        continue
    if name.startswith("show_") or name.startswith("reset_"):
        continue
    candidates.append(p)

print(f"[INFO] {len(candidates)} fichiers candidats")
print()

import datetime
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = root / "_backups_utf8"
backup_dir.mkdir(exist_ok=True)

fixed_files = []
skipped_files = []

for target in candidates:
    try:
        with open(target, "rb") as f:
            raw = f.read()
        # Detecter BOM
        if raw[:3] == b"\xef\xbb\xbf":
            raw_no_bom = raw[3:]
            had_bom = True
        else:
            raw_no_bom = raw
            had_bom = False
        text = raw_no_bom.decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        print(f"[ERR] {target.name} : impossible de decoder UTF-8 ({e})")
        skipped_files.append(target.name)
        continue
    except Exception as e:
        print(f"[ERR] {target.name} : {e}")
        skipped_files.append(target.name)
        continue
    
    # Compter mojibakes
    counts = {}
    for moji in fixes:
        n = text.count(moji)
        if n > 0:
            counts[moji] = n
    
    if not counts:
        continue
    
    total = sum(counts.values())
    print(f"[FIX] {target.name} : {total} sequences mojibakes")
    
    # Backup
    backup = backup_dir / f"{target.name}.bak.{ts}"
    with open(backup, "wb") as f:
        f.write(raw)
    
    # Apply
    fixed_text = text
    for moji in sorted(fixes.keys(), key=lambda x: -len(x)):
        fixed_text = fixed_text.replace(moji, fixes[moji])
    
    # AST check (sur .py)
    try:
        ast.parse(fixed_text)
    except SyntaxError as e:
        print(f"  [SKIP] AST invalide apres fix : {e}")
        skipped_files.append(target.name)
        continue
    
    # Ecriture utf-8 sans BOM
    with open(target, "wb") as f:
        f.write(fixed_text.encode("utf-8"))
    
    new_size = len(fixed_text.encode("utf-8"))
    print(f"  [OK] {total} fix, {new_size} bytes (BOM={'oui->non' if had_bom else 'aucun'})")
    fixed_files.append((target.name, total))

print()
print("=" * 60)
print(f"BILAN : {len(fixed_files)} fichiers corriges, {len(skipped_files)} skip")
print("=" * 60)
for name, n in fixed_files:
    print(f"  OK  {name:50s} {n:4d} fix")
for name in skipped_files:
    print(f"  -   {name:50s} SKIP")
print()
print(f"Backups dans {backup_dir}")
'@

$tmp = "$env:TEMP\fix_utf8_remaining.py"
[System.IO.File]::WriteAllText($tmp, $py, (New-Object System.Text.UTF8Encoding $false))
& py -3.13 $tmp

Write-Host ""
Write-Host "=== TERMINE ===" -ForegroundColor Green
