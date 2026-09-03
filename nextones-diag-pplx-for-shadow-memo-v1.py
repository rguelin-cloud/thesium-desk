# -*- coding: utf-8 -*-
"""
Diag prereq Jalon 9.5b LLM Memo Shadow :
  1. Confirm presence pplx_client.py et signature de la fonction principale
     (ex: ask_pplx, chat, query...)
  2. Confirm presence pplx_factor_agent.py / pplx_thesis_agent.py pour pattern reference
  3. Lister fichiers shadow_*.py existants (engine, perf_rolling, hook, backfill)
  4. Confirmer column recommendation_memo dans shadow_perf_rolling (PRAGMA)
"""
import os
import sqlite3

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

print("=" * 70)
print("[1] Fichiers pplx_*.py + shadow_*.py dans", ROOT)
print("=" * 70)
files = sorted(os.listdir(ROOT))
for f in files:
    fl = f.lower()
    if fl.startswith("pplx_") and fl.endswith(".py"):
        size = os.path.getsize(os.path.join(ROOT, f))
        print("  PPLX     | {:50s} {:>8} bytes".format(f, size))
    if fl.startswith("shadow_") and fl.endswith(".py"):
        size = os.path.getsize(os.path.join(ROOT, f))
        print("  SHADOW   | {:50s} {:>8} bytes".format(f, size))

print()
print("=" * 70)
print("[2] Signature pplx_client.py (def ...)")
print("=" * 70)
client = os.path.join(ROOT, "pplx_client.py")
if os.path.exists(client):
    with open(client, "r", encoding="utf-8-sig", errors="replace") as f:
        for i, line in enumerate(f, 1):
            s = line.strip()
            if s.startswith("def ") or s.startswith("class ") or s.startswith("async def "):
                print("  L{:5d} | {}".format(i, s))
else:
    print("  [ERR] pplx_client.py introuvable")

print()
print("=" * 70)
print("[3] Pattern d'appel dans pplx_factor_agent.py (1eres 40 lignes utiles)")
print("=" * 70)
fa = os.path.join(ROOT, "pplx_factor_agent.py")
if os.path.exists(fa):
    with open(fa, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.readlines()
    # Cherche imports + 1er appel client
    shown = 0
    for i, line in enumerate(lines, 1):
        if "pplx_client" in line or "ask_pplx" in line or "from pplx" in line or "import pplx" in line or ".ask(" in line or ".chat(" in line or ".query(" in line:
            print("  L{:5d} | {}".format(i, line.rstrip()))
            shown += 1
            if shown > 25: break
else:
    print("  [WARN] pplx_factor_agent.py absent")

print()
print("=" * 70)
print("[4] Schema shadow_perf_rolling (PRAGMA table_info)")
print("=" * 70)
conn = sqlite3.connect(DB, timeout=10.0)
try:
    cur = conn.execute("PRAGMA table_info(shadow_perf_rolling)")
    for row in cur.fetchall():
        cid, name, ctype, notnull, dflt, pk = row
        print("  {:3d} {:30s} {:15s} notnull={} pk={}".format(cid, name, ctype, notnull, pk))
    print()
    cur = conn.execute("SELECT COUNT(*) FROM shadow_perf_rolling")
    print("  Total rows:", cur.fetchone()[0])
    cur = conn.execute("SELECT COUNT(*) FROM shadow_perf_rolling WHERE recommendation_memo IS NOT NULL")
    print("  Rows avec memo:", cur.fetchone()[0])
finally:
    conn.close()

print()
print("DONE")
