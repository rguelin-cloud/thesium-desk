# diag_utf8_ui.py
# Diagnostique le mojibake UTF-8 cote backend/UI

import sqlite3
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

db = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
con = sqlite3.connect(db)
cur = con.cursor()

print("=" * 70)
print("1. Lignes mojibakees dans cycle_reconciliation_log (Ã©, Ã¨, Ã , etc.)")
print("=" * 70)
cur.execute("""
    SELECT cycle_id, ticker, action, reason
    FROM cycle_reconciliation_log
    WHERE reason LIKE '%Ã%' OR reason LIKE '%Â%'
    ORDER BY created_at DESC
    LIMIT 10
""")
mojibake_rows = cur.fetchall()
print(f"  Trouve : {len(mojibake_rows)} lignes mojibakees")
for r in mojibake_rows[:5]:
    print(f"  cycle={r[0]} ticker={r[1]} action={r[2]}")
    print(f"    reason={r[3][:100]}")

print()
print("=" * 70)
print("2. Lignes correctes (accents propres)")
print("=" * 70)
cur.execute("""
    SELECT cycle_id, ticker, action, reason
    FROM cycle_reconciliation_log
    WHERE (reason LIKE '%é%' OR reason LIKE '%è%' OR reason LIKE '%à%')
      AND reason NOT LIKE '%Ã%'
    ORDER BY created_at DESC
    LIMIT 5
""")
clean_rows = cur.fetchall()
print(f"  Trouve : {len(clean_rows)} lignes correctes")
for r in clean_rows[:3]:
    print(f"  cycle={r[0]} ticker={r[1]} reason={r[3][:100]}")

print()
print("=" * 70)
print("3. Theses thesis_text avec mojibake")
print("=" * 70)
cur.execute("""
    SELECT id, thesis_text FROM theses
    WHERE thesis_text LIKE '%Ã%' OR thesis_text LIKE '%Â%'
    ORDER BY id DESC LIMIT 3
""")
for r in cur.fetchall():
    print(f"  id={r[0]} : {r[1][:120]}")

print()
print("=" * 70)
print("4. Recherche fichiers serveur Python avec encoding")
print("=" * 70)
root = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
candidates = ["api_server_with_static.py", "api_server.py", "execution_engine.py",
              "reconciler.py", "order_reconciler.py"]
for fname in candidates:
    p = root / fname
    if p.exists():
        content = p.read_text(encoding="utf-8-sig", errors="replace")
        lines = content.split("\n")
        for i, line in enumerate(lines):
            # Chercher JSONResponse, FileResponse, Response, json.dumps, headers
            if any(k in line for k in ["JSONResponse", "FileResponse", "json.dumps",
                                       'content_type', 'media_type', 'application/json',
                                       'text/html', 'charset']):
                if not line.strip().startswith("#"):
                    print(f"  {fname} L{i+1:5d}: {line.rstrip()[:130]}")

print()
print("=" * 70)
print("5. Fichiers HTML/JS UI - chercher charset declaration")
print("=" * 70)
import os
ui_files = []
for ext in ["*.html", "*.js"]:
    ui_files.extend(root.rglob(ext))
ui_files = [f for f in ui_files if "node_modules" not in str(f) and "_backups" not in str(f)]
print(f"  Files trouves : {len(ui_files)}")
for f in ui_files[:20]:
    try:
        content = f.read_text(encoding="utf-8-sig", errors="replace")
        has_charset = "charset" in content.lower()[:500]
        has_mojibake = "Ã©" in content or "Ã¨" in content
        rel = f.relative_to(root)
        print(f"  {rel}  charset_in_head={has_charset}  has_mojibake={has_mojibake}")
    except Exception as e:
        print(f"  {f} read error: {e}")

con.close()
