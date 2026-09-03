# [DIAG_CYCLE_STRUCTURE_V1] Verifie la structure de la table cycles + endpoints /api/cycle/*
# Sortie utilisee pour calibrer les patches verrou.
from __future__ import annotations
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = ROOT / "api_server.py"
DB = ROOT / "thesium.db"

src = API.read_text(encoding="utf-8-sig")

print("=" * 80)
print("STRUCTURE CYCLE")
print("=" * 80)

# 1. Tables cycle
print("\n--- Tables 'cycle' en DB ---")
cx = sqlite3.connect(str(DB), timeout=10)
cx.row_factory = sqlite3.Row
try:
    rows = cx.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%cycle%'"
    ).fetchall()
    for r in rows:
        t = r["name"]
        cols = cx.execute(f"PRAGMA table_info({t})").fetchall()
        print(f"\nTable {t}:")
        for c in cols:
            print(f"  {c['name']:25} {c['type']:15} default={c['dflt_value']}")
        cnt = cx.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
        print(f"  ({cnt} rows)")

        # 3 derniers
        col_names = [c["name"] for c in cols]
        order = "id"
        for c in ("created_at", "started_at", "ts", "id"):
            if c in col_names:
                order = c
                break
        last = cx.execute(f"SELECT * FROM {t} ORDER BY {order} DESC LIMIT 3").fetchall()
        for row in last:
            d = dict(row)
            short = {k: (str(v)[:50] if v else v) for k, v in list(d.items())[:6]}
            print(f"  {short}")
finally:
    cx.close()

# 2. Endpoints /api/cycle/*
print("\n--- Endpoints /api/cycle/* dans api_server.py ---")
for m in re.finditer(r"@app\.(get|post)\(['\"]([^'\"]*cycle[^'\"]*)['\"]\)\s*\n(?:async\s+)?def\s+(\w+)\(([^)]*)\)", src):
    print(f"  {m.group(1).upper():5} {m.group(2):30} -> def {m.group(3)}({m.group(4)[:60]})")

# 3. Fonction du POST /api/cycle/run : extraire les 50 premieres lignes
print("\n--- Corps de la fonction POST /api/cycle/run ---")
m = re.search(r"@app\.post\(['\"]([^'\"]*cycle/run[^'\"]*)['\"]\)\s*\n(?:async\s+)?def\s+(\w+)\([^)]*\):(.+?)(?=\n@app\.|\nclass\s|\Z)", src, re.DOTALL)
if m:
    body = m.group(3)
    for i, line in enumerate(body.splitlines()[:40], 1):
        print(f"  {i:3} {line}")
else:
    print("  (endpoint /api/cycle/run non trouve - chercher manuellement)")
    # Fallback : chercher 'cycle/run' brut
    for m in re.finditer(r"cycle/run", src):
        line_no = src[: m.start()].count("\n") + 1
        line = src.splitlines()[line_no - 1].strip()
        print(f"  L{line_no}: {line[:120]}")
