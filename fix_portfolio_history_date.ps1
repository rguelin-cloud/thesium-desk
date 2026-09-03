# fix_portfolio_history_date.ps1
# Fix le warning "portfolio_history.date NOT NULL" lors du reset
# Strategie : trouver le code qui INSERT dans portfolio_history sans date
# et ajouter date=DATE('now') ou similaire

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"

Write-Host "=== FIX portfolio_history.date NOT NULL ===" -ForegroundColor Cyan
Write-Host ""

$py = @'
import sys
import io
import re
import sqlite3
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 1. Inspecter le schema
db = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
con = sqlite3.connect(db)
cur = con.cursor()

print("[INFO] Schema portfolio_history :")
cur.execute("PRAGMA table_info(portfolio_history)")
for r in cur.fetchall():
    print(f"  {r}")

print()
print("[INFO] Sample lignes existantes :")
cur.execute("SELECT * FROM portfolio_history ORDER BY id DESC LIMIT 3")
cols = [d[0] for d in cur.description]
print(f"  cols : {cols}")
for r in cur.fetchall():
    print(f"  {dict(zip(cols, r))}")

print()
print("[INFO] Count lignes :")
cur.execute("SELECT COUNT(*) FROM portfolio_history")
print(f"  total = {cur.fetchone()[0]}")

con.close()

# 2. Chercher INSERT INTO portfolio_history dans le code
print()
print("[INFO] Recherche INSERT INTO portfolio_history dans le code Python :")
root = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
for py_file in root.glob("*.py"):
    if "_backups" in str(py_file):
        continue
    if py_file.name.startswith(("diag_", "fix_", "verif_", "find_", "check_", "trace_", "show_", "reset_")):
        continue
    try:
        content = py_file.read_text(encoding="utf-8-sig")
    except Exception:
        continue
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if "portfolio_history" in line.lower() and "insert" in content[max(0,i*100-500):i*100+200].lower():
            # Voir 5 lignes avant + 5 apres pour contexte
            if "insert" in line.lower() or "portfolio_history" in line.lower():
                ctx_start = max(0, i-3)
                ctx_end = min(len(lines), i+10)
                snippet = "\n".join(lines[ctx_start:ctx_end])
                if "INSERT" in snippet.upper() and "portfolio_history" in snippet.lower():
                    print(f"\n  --- {py_file.name} autour L{i+1} ---")
                    for j in range(ctx_start, ctx_end):
                        marker = ">>> " if j == i else "    "
                        print(f"  L{j+1:5d}{marker}{lines[j].rstrip()[:120]}")
                    break
'@

$tmp = "$env:TEMP\diag_portfolio_history.py"
[System.IO.File]::WriteAllText($tmp, $py, (New-Object System.Text.UTF8Encoding $false))
& py -3.13 $tmp
