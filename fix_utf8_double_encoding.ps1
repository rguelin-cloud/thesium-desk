# fix_utf8_double_encoding.ps1
# Corrige le double-encoding UTF-8 (c3 83 c2 a9 -> c3 a9 pour 'é', etc.)
# dans execution_engine.py et les reasons en DB
# Strategie : detecter les bytes UTF-8 mojibakes (UTF-8 d'un texte deja en UTF-8 lu comme Latin-1)
# et inverser : decode('utf-8').encode('latin-1').decode('utf-8')

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"

Write-Host "=== FIX UTF-8 DOUBLE ENCODING ===" -ForegroundColor Cyan
Write-Host ""

# ----- ETAPE 1 : Backup execution_engine.py -----
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$ee = "$root\execution_engine.py"
$ee_backup = "$ee.bak.utf8fix.$ts"
Copy-Item $ee $ee_backup -Force
Write-Host "[OK] Backup execution_engine : $ee_backup" -ForegroundColor Green

# ----- ETAPE 2 : Repair execution_engine.py via Python -----
$py_ee = @'
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

target = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"

# Lecture bytes raw
with open(target, "rb") as f:
    raw = f.read()

print(f"[INFO] Taille originale : {len(raw)} bytes")

# Strategie : raw est UTF-8. On le decode UTF-8 -> on obtient des chars dont
# certains sont du Latin-1 "vu" comme UTF-8 (e.g. "Ã©" au lieu de "é").
# Pour fixer : on prend ces chars, on les encode latin-1 (donne les bytes UTF-8 originaux),
# on re-decode UTF-8 -> on recupere "é".

text = raw.decode("utf-8", errors="strict")

# Detection : les sequences Ã suivies d'un char latin-1 caracteristique
# (Ã©, Ã¨, Ã , Ãª, Ã®, Ã´, Ã¹, Ãª, ÃŠ etc.)
# Plus simple : tenter le re-decode global ligne par ligne et appliquer si plus court

import re

# Patterns connus de double-encoding UTF-8 -> char attendu
fixes = {
    "Ã©": "é", "Ã¨": "è", "Ã ": "à", "Ãª": "ê", "Ã®": "î", "Ã´": "ô",
    "Ã¹": "ù", "Ã¢": "â", "Ã»": "û", "Ã¯": "ï", "Ã«": "ë", "Ã¶": "ö",
    "Ã§": "ç", "Ã±": "ñ", "Ã€": "À", "Ã‰": "É", "Ãˆ": "È", "ÃŠ": "Ê",
    "Ã‡": "Ç", "Ã”": "Ô", "Ã™": "Ù", "Ã›": "Û", "Ã€": "À",
    "â€™": "'", "â€œ": "\"", "â€": "\"", "â€"": "-", "â€"": "-",
    "â€¦": "...", "â€¢": "•",
    # Cas double-encoding sur 4 bytes (c3 83 c2 a9 -> c3 a9 = é)
    # Quand on relit en utf-8, ca donne "Ã\x83Â©" qui s'affiche comme "Ã©" en latin-1
    # mais en utf-8 strict ca peut donner d'autres formes
}

# Compter occurrences avant
counts_before = {}
for moji, fixed in fixes.items():
    n = text.count(moji)
    if n > 0:
        counts_before[moji] = n

print(f"[INFO] Occurrences mojibakes avant fix :")
for m, n in sorted(counts_before.items(), key=lambda x: -x[1]):
    print(f"  '{m}' -> '{fixes[m]}' : {n}")

# Appliquer les fixes - ordre important : longs avant courts
fixed_text = text
for moji, fixed in sorted(fixes.items(), key=lambda x: -len(x[0])):
    fixed_text = fixed_text.replace(moji, fixed)

# Verif AST
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
remaining = sum(raw_after.count(m.encode("utf-8")) for m in counts_before.keys())
print(f"[INFO] Sequences mojibakes residuelles : {remaining}")
'@

$tmp = "$env:TEMP\fix_ee_utf8.py"
[System.IO.File]::WriteAllText($tmp, $py_ee, (New-Object System.Text.UTF8Encoding $false))
& py -3.13 $tmp
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERR] Repair execution_engine.py echoue, restauration backup" -ForegroundColor Red
    Copy-Item $ee_backup $ee -Force
    exit 1
}

Write-Host ""

# ----- ETAPE 3 : Repair DB - cycle_reconciliation_log.reason -----
Write-Host "=== FIX DB cycle_reconciliation_log.reason ===" -ForegroundColor Cyan

$py_db = @'
import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

db = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
con = sqlite3.connect(db)
cur = con.cursor()

fixes = {
    "Ã©": "é", "Ã¨": "è", "Ã ": "à", "Ãª": "ê", "Ã®": "î", "Ã´": "ô",
    "Ã¹": "ù", "Ã¢": "â", "Ã»": "û", "Ã¯": "ï", "Ã«": "ë", "Ã¶": "ö",
    "Ã§": "ç", "Ã±": "ñ", "Ã€": "À", "Ã‰": "É", "Ãˆ": "È", "ÃŠ": "Ê",
    "Ã‡": "Ç", "Ã”": "Ô", "Ã™": "Ù", "Ã›": "Û",
    "â€™": "'", "â€¦": "...", "â€¢": "•",
}

# Recuperer toutes les reasons contenant un mojibake
cur.execute("SELECT id, reason FROM cycle_reconciliation_log WHERE reason IS NOT NULL")
rows = cur.fetchall()

fixed_count = 0
for row_id, reason in rows:
    needs_fix = any(m in reason for m in fixes.keys())
    if needs_fix:
        new_reason = reason
        for moji, fixed in sorted(fixes.items(), key=lambda x: -len(x[0])):
            new_reason = new_reason.replace(moji, fixed)
        if new_reason != reason:
            cur.execute("UPDATE cycle_reconciliation_log SET reason=? WHERE id=?",
                       (new_reason, row_id))
            fixed_count += 1

con.commit()
print(f"[OK] {fixed_count} lignes corrigees dans cycle_reconciliation_log")

# Sample apres fix
cur.execute("""
    SELECT cycle_id, ticker, reason FROM cycle_reconciliation_log
    WHERE cycle_id = '20260525-104013'
    ORDER BY id
""")
print()
print("[INFO] Sample apres fix :")
for r in cur.fetchall():
    print(f"  {r[0]} {r[1]:6s} : {r[2][:100]}")

con.close()
'@

$tmp2 = "$env:TEMP\fix_db_utf8.py"
[System.IO.File]::WriteAllText($tmp2, $py_db, (New-Object System.Text.UTF8Encoding $false))
& py -3.13 $tmp2

Write-Host ""
Write-Host "=== TERMINE ===" -ForegroundColor Green
Write-Host "Etapes suivantes :" -ForegroundColor Cyan
Write-Host "  1. Tuer uvicorn" -ForegroundColor White
Write-Host "  2. Relancer uvicorn" -ForegroundColor White
Write-Host "  3. Rafraichir UI (Ctrl+F5)" -ForegroundColor White
Write-Host "  4. Verifier dans UI que 'Ordre net émis' s'affiche bien" -ForegroundColor White
