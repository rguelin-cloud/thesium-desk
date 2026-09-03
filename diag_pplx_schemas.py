# [DIAG_PPLX_SCHEMAS_V1] Verifie les vraies colonnes des tables crypto_context et factor_quality_context
# + capture la signature exacte de run_agents_endpoint dans api_server.py
from __future__ import annotations
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "thesium.db"
API = ROOT / "api_server.py"

print("=" * 80)
print("SCHEMAS PPLX + SIGNATURE run_agents_endpoint")
print("=" * 80)

# 1. Schema crypto_context
cx = sqlite3.connect(str(DB), timeout=10)
cx.row_factory = sqlite3.Row
try:
    for t in ("crypto_context", "factor_quality_context"):
        print(f"\n--- Table {t} ---")
        try:
            cols = cx.execute(f"PRAGMA table_info({t})").fetchall()
            for c in cols:
                print(f"  {c['name']:25} {c['type']:15} default={c['dflt_value']}")
            # 1 row exemple
            row = cx.execute(f"SELECT * FROM {t} LIMIT 1").fetchone()
            if row:
                print("\n  Exemple ligne:")
                for k in row.keys():
                    v = row[k]
                    s = str(v)[:80] if v else v
                    print(f"    {k}: {s}")
        except Exception as e:
            print(f"  ERREUR: {e}")
finally:
    cx.close()

# 2. Signature exacte de run_agents_endpoint
print("\n--- Decorateur + signature run_agents_endpoint ---")
src = API.read_text(encoding="utf-8-sig")
# Chercher la ligne avec "def run_agents_endpoint"
m = re.search(r"def\s+run_agents_endpoint", src)
if m:
    line_no = src[: m.start()].count("\n") + 1
    # Afficher les 5 lignes avant + 3 apres
    lines = src.splitlines()
    start = max(0, line_no - 6)
    end = min(len(lines), line_no + 3)
    for i in range(start, end):
        marker = " >> " if i == line_no - 1 else "    "
        print(f"{marker}L{i+1:5}: {lines[i]}")
else:
    print("run_agents_endpoint NON TROUVE !")
    # Chercher autres patterns
    for m in re.finditer(r"def\s+\w*run\w*\(", src):
        line_no = src[: m.start()].count("\n") + 1
        print(f"  L{line_no}: {src.splitlines()[line_no-1].strip()}")

# 3. Chercher /api/run-agents
print("\n--- Tous les decorateurs /api/run-agents ---")
for m in re.finditer(r"@app\.[a-z]+\([^)]*run-agents[^)]*\)", src):
    line_no = src[: m.start()].count("\n") + 1
    print(f"  L{line_no}: {m.group(0)}")
    # Afficher les 3 lignes suivantes
    lines = src.splitlines()
    for i in range(line_no, min(len(lines), line_no + 4)):
        print(f"         L{i+1}: {lines[i]}")
