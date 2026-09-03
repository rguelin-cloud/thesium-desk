# fix_utf8_double_encoding_v2.ps1
# Version ASCII-safe : patterns construits via codepoints Python (\uXXXX)
# pour eviter les corruptions PowerShell -> heredoc -> Python

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"

Write-Host "=== FIX UTF-8 DOUBLE ENCODING V2 ===" -ForegroundColor Cyan
Write-Host ""

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$ee = "$root\execution_engine.py"
$ee_backup = "$ee.bak.utf8fix.$ts"
Copy-Item $ee $ee_backup -Force
Write-Host "[OK] Backup execution_engine : $ee_backup" -ForegroundColor Green

# Script Python : on construit les patterns avec \uXXXX pour rester pur ASCII
$py = @'
import sys
import io
import os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Tous les patterns construits via codepoints, donc le source Python est pur ASCII
# fixes : moji_seq (codepoints exacts) -> char clean
fixes = {
    "\u00c3\u00a9": "\u00e9",       # Ãé -> é
    "\u00c3\u00a8": "\u00e8",       # Ãè -> è
    "\u00c3\u00a0": "\u00e0",       # Ãa -> à
    "\u00c3\u00aa": "\u00ea",       # Ãê -> ê
    "\u00c3\u00ae": "\u00ee",       # Ãî -> î
    "\u00c3\u00b4": "\u00f4",       # Ãô -> ô
    "\u00c3\u00b9": "\u00f9",       # Ãù -> ù
    "\u00c3\u00a2": "\u00e2",       # Ãâ -> â
    "\u00c3\u00bb": "\u00fb",       # Ãû -> û
    "\u00c3\u00af": "\u00ef",       # Ãï -> ï
    "\u00c3\u00ab": "\u00eb",       # Ãë -> ë
    "\u00c3\u00b6": "\u00f6",       # Ãö -> ö
    "\u00c3\u00a7": "\u00e7",       # Ãç -> ç
    "\u00c3\u00b1": "\u00f1",       # Ãñ -> ñ
    "\u00c3\u0080": "\u00c0",       # ÃA -> À
    "\u00c3\u0089": "\u00c9",       # ÃE -> É
    "\u00c3\u0088": "\u00c8",       # ÃE -> È
    "\u00c3\u008a": "\u00ca",       # ÃE -> Ê
    "\u00c3\u0087": "\u00c7",       # ÃC -> Ç
    "\u00c3\u0094": "\u00d4",       # ÃO -> Ô
    "\u00c3\u0099": "\u00d9",       # ÃU -> Ù
    "\u00c3\u009b": "\u00db",       # ÃU -> Û
    # Cas Windows-1252 etiquette : "â\u20ac\u2122" -> apostrophe droite
    "\u00e2\u20ac\u2122": "\u2019",   # right single quote
    "\u00e2\u20ac\u201c": "\u2013",   # en-dash
    "\u00e2\u20ac\u201d": "\u2014",   # em-dash
    "\u00e2\u20ac\u00a6": "\u2026",   # ellipsis
}

target = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"
with open(target, "rb") as f:
    raw = f.read()
print(f"[INFO] Taille originale : {len(raw)} bytes")

text = raw.decode("utf-8", errors="strict")

# Compter avant
counts_before = {}
for moji in fixes:
    n = text.count(moji)
    if n > 0:
        counts_before[moji] = n

print("[INFO] Occurrences mojibakes avant fix :")
total_before = 0
for m, n in sorted(counts_before.items(), key=lambda x: -x[1]):
    rep = fixes[m]
    print(f"  {' '.join(f'U+{ord(c):04X}' for c in m)} -> U+{ord(rep):04X} : {n}")
    total_before += n
print(f"[INFO] Total a corriger : {total_before}")

# Appliquer : ordre par longueur descendante
fixed_text = text
for moji in sorted(fixes.keys(), key=lambda x: -len(x)):
    fixed_text = fixed_text.replace(moji, fixes[moji])

# AST check
import ast
try:
    ast.parse(fixed_text)
    print("[OK] AST valide apres fix")
except SyntaxError as e:
    print(f"[ERR] AST invalide : {e}")
    sys.exit(1)

# Ecriture utf-8 sans BOM
with open(target, "wb") as f:
    f.write(fixed_text.encode("utf-8"))

print(f"[OK] Fichier reecrit ({len(fixed_text.encode('utf-8'))} bytes)")

# Verif post-fix
with open(target, "rb") as f:
    raw_after = f.read()
remaining = 0
for moji in counts_before:
    remaining += raw_after.decode("utf-8", errors="replace").count(moji)
print(f"[INFO] Sequences mojibakes residuelles : {remaining}")

# Verif visuel : sample de la ligne L688
text_after = raw_after.decode("utf-8")
for i, line in enumerate(text_after.split("\n"), 1):
    if "Ordre net" in line and "qty_net" in line:
        print(f"[CHECK] L{i}: {line.strip()[:120]}")
        break
'@

$tmp = "$env:TEMP\fix_ee_utf8_v2.py"
[System.IO.File]::WriteAllText($tmp, $py, (New-Object System.Text.UTF8Encoding $false))
& py -3.13 $tmp
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERR] Repair execution_engine.py echoue, restauration backup" -ForegroundColor Red
    Copy-Item $ee_backup $ee -Force
    exit 1
}

Write-Host ""
Write-Host "=== FIX DB cycle_reconciliation_log.reason ===" -ForegroundColor Cyan

$py_db = @'
import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

fixes = {
    "\u00c3\u00a9": "\u00e9", "\u00c3\u00a8": "\u00e8", "\u00c3\u00a0": "\u00e0",
    "\u00c3\u00aa": "\u00ea", "\u00c3\u00ae": "\u00ee", "\u00c3\u00b4": "\u00f4",
    "\u00c3\u00b9": "\u00f9", "\u00c3\u00a2": "\u00e2", "\u00c3\u00bb": "\u00fb",
    "\u00c3\u00af": "\u00ef", "\u00c3\u00ab": "\u00eb", "\u00c3\u00b6": "\u00f6",
    "\u00c3\u00a7": "\u00e7", "\u00c3\u00b1": "\u00f1",
    "\u00c3\u0080": "\u00c0", "\u00c3\u0089": "\u00c9", "\u00c3\u0088": "\u00c8",
    "\u00c3\u008a": "\u00ca", "\u00c3\u0087": "\u00c7", "\u00c3\u0094": "\u00d4",
    "\u00c3\u0099": "\u00d9", "\u00c3\u009b": "\u00db",
    "\u00e2\u20ac\u2122": "\u2019", "\u00e2\u20ac\u201c": "\u2013",
    "\u00e2\u20ac\u201d": "\u2014", "\u00e2\u20ac\u00a6": "\u2026",
}

db = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
con = sqlite3.connect(db)
cur = con.cursor()

cur.execute("SELECT id, reason FROM cycle_reconciliation_log WHERE reason IS NOT NULL")
rows = cur.fetchall()
fixed_count = 0
for row_id, reason in rows:
    if any(m in reason for m in fixes):
        new_reason = reason
        for moji in sorted(fixes.keys(), key=lambda x: -len(x)):
            new_reason = new_reason.replace(moji, fixes[moji])
        if new_reason != reason:
            cur.execute("UPDATE cycle_reconciliation_log SET reason=? WHERE id=?",
                       (new_reason, row_id))
            fixed_count += 1
con.commit()
print(f"[OK] {fixed_count} lignes corrigees dans cycle_reconciliation_log")

# Sample
cur.execute("""
    SELECT cycle_id, ticker, reason FROM cycle_reconciliation_log
    WHERE cycle_id = '20260525-104013'
    ORDER BY id LIMIT 5
""")
print()
print("[INFO] Sample apres fix :")
for r in cur.fetchall():
    print(f"  {r[0]} {r[1]:6s} : {r[2][:100]}")

con.close()
'@

$tmp2 = "$env:TEMP\fix_db_utf8_v2.py"
[System.IO.File]::WriteAllText($tmp2, $py_db, (New-Object System.Text.UTF8Encoding $false))
& py -3.13 $tmp2

Write-Host ""
Write-Host "=== TERMINE ===" -ForegroundColor Green
Write-Host "  1. Ctrl+C uvicorn" -ForegroundColor White
Write-Host "  2. Relancer uvicorn" -ForegroundColor White
Write-Host "  3. Ctrl+F5 UI" -ForegroundColor White
