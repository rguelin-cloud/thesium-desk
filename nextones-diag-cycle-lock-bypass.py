# Localise le verrou "1 cycle par jour" et propose un bypass minimal :
# - soit supprime l'entree de verrou dans event_log/cycles_daily
# - soit reset le compteur

import sqlite3
from pathlib import Path
import re

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

today = "2026-05-29"

print("=" * 70)
print("[1] event_log : aujourd'hui")
print("=" * 70)
try:
    cols = [c[1] for c in cur.execute("PRAGMA table_info(event_log)").fetchall()]
    print(f"  cols: {cols}")
    rows = cur.execute(f"SELECT * FROM event_log WHERE created_at LIKE '{today}%' ORDER BY rowid DESC LIMIT 20").fetchall()
    if not rows:
        rows = cur.execute(f"SELECT * FROM event_log ORDER BY rowid DESC LIMIT 10").fetchall()
    for r in rows:
        print("  " + " | ".join(f"{k}={str(r[k])[:50]}" for k in r.keys()))
except Exception as e:
    print(f"  {e}")

print()
print("=" * 70)
print("[2] cycles_daily : tout")
print("=" * 70)
try:
    rows = cur.execute("SELECT * FROM cycles_daily ORDER BY rowid DESC LIMIT 5").fetchall()
    if not rows:
        print("  (vide)")
    for r in rows:
        print("  " + " | ".join(f"{k}={r[k]}" for k in r.keys()))
except Exception as e:
    print(f"  {e}")

print()
print("=" * 70)
print("[3] Recherche du code 'verrou' / 'lock' / 'deja lance' dans api_server.py")
print("=" * 70)
api = ROOT / "api_server.py"
txt = api.read_text(encoding="utf-8-sig", errors="replace")
lines = txt.splitlines()
patterns = [
    r"deja\s+lance",
    r"d[ée]j[àa]\s+lanc",
    r"already\s+run",
    r"cycle.*lock",
    r"lock.*cycle",
    r"once.*per.*day",
    r"1.*par.*jour",
    r"cycle_id.*=.*today",
    r"RUN_CYCLE_LOCK",
    r"\[CYCLE_LOCK",
    r"raise.*HTTPException.*400",
    r"raise.*HTTPException.*409",
]
hits = []
for i, line in enumerate(lines, 1):
    for pat in patterns:
        if re.search(pat, line, re.I):
            hits.append(i)
            break

for i in sorted(set(hits))[:30]:
    print(f"\n  -- L{i} --")
    for j in range(max(0, i-5), min(len(lines), i+8)):
        marker = " >>" if j == i-1 else "   "
        print(f"  {marker} L{j+1:>4}: {lines[j].rstrip()[:200]}")

print()
print("=" * 70)
print("[4] Cherche endpoint /api/.../run_cycle ou /decision/run")
print("=" * 70)
for i, line in enumerate(lines, 1):
    if re.search(r'@app\.(post|get).*("|\').*(decision|run|cycle)', line, re.I):
        for j in range(i-1, min(len(lines), i+25)):
            marker = " >>" if j == i-1 else "   "
            print(f"  {marker} L{j+1:>4}: {lines[j].rstrip()[:200]}")
        print()

con.close()
print("\n[DONE]")
