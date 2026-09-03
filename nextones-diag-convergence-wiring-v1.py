# -*- coding: utf-8 -*-
"""
[DIAG_CONVERGENCE_WIRING_V1]

Verifie le wiring complet du patch CONVERGENCE_SIZING_V1 :
  1. Marker present dans portfolio_construction_agent.py ?
  2. Helper apply_convergence_sizing defini ?
  3. Bloc d'injection avant apply_caps_floors ?
  4. apply_caps_floors utilise scaled_alloc ?
  5. Comment /api/construction/run appelle run_construction_agent ?
     -> cycle_id est-il passe ?
  6. Snapshots convergence presents en DB ? combien par cycle ?

Lance :
  py -3.13 nextones-diag-convergence-wiring-v1.py
"""
import sys
import io
import os
import sqlite3
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

PCA = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py"
API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

print("=" * 70)
print("1. INSPECTION portfolio_construction_agent.py")
print("=" * 70)
with open(PCA, "r", encoding="utf-8-sig") as f:
    pca_content = f.read()

checks = {
    "Marker [CONVERGENCE_SIZING_V1]": "# [CONVERGENCE_SIZING_V1]" in pca_content,
    "Helper def apply_convergence_sizing": "def apply_convergence_sizing(" in pca_content,
    "Call apply_convergence_sizing(": "apply_convergence_sizing(conn, cycle_id, raw_alloc)" in pca_content,
    "apply_caps_floors(scaled_alloc": "apply_caps_floors(scaled_alloc" in pca_content,
    "apply_caps_floors(raw_alloc (ancien)": "apply_caps_floors(raw_alloc" in pca_content,
}
for k, v in checks.items():
    print(f"  [{'OK' if v else 'KO'}] {k}")

# Snippet autour de l'injection
print("\n--- Extrait autour de l'injection ---")
m = re.search(r"raw_alloc = softmax_allocate.*?capped_alloc, cap_log = apply_caps_floors.*?\n",
              pca_content, re.DOTALL)
if m:
    snippet = m.group(0)
    for ln in snippet.split("\n"):
        print(f"    {ln}")

print("\n" + "=" * 70)
print("2. INSPECTION api_server.py - endpoint /api/construction/run")
print("=" * 70)
with open(API, "r", encoding="utf-8-sig") as f:
    api_content = f.read()

# Cherche l'endpoint construction/run
m = re.search(r"@app\.(post|get)\([\"']/api/construction/run[\"'].*?(?=@app\.|def \w+\(.*\):\n(?!\s))",
              api_content, re.DOTALL)
if not m:
    # Fallback : cherche juste la string
    idx = api_content.find('"/api/construction/run"')
    if idx == -1:
        idx = api_content.find("'/api/construction/run'")
    if idx != -1:
        # Extrait 60 lignes apres
        lines = api_content[idx:].split("\n")[:60]
        print("--- Endpoint trouve, 60 lignes ---")
        for ln in lines:
            print(f"    {ln}")
    else:
        print("[KO] Endpoint /api/construction/run introuvable")
else:
    print("--- Endpoint /api/construction/run ---")
    for ln in m.group(0).split("\n"):
        print(f"    {ln}")

# Verifie si cycle_id est passe a run_construction_agent
print("\n--- Tous les appels run_construction_agent() dans api_server.py ---")
for i, ln in enumerate(api_content.split("\n"), 1):
    if "run_construction_agent" in ln:
        print(f"  L{i}: {ln.rstrip()}")

print("\n" + "=" * 70)
print("3. DB convergence_snapshots")
print("=" * 70)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# Cycles avec snapshots convergence
cur = conn.execute("""
    SELECT cycle_id, COUNT(*) as n, 
           SUM(CASE WHEN forced_exit=1 THEN 1 ELSE 0 END) as fe,
           SUM(CASE WHEN drift=1 THEN 1 ELSE 0 END) as dr,
           MAX(created_at) as latest
    FROM convergence_snapshots
    GROUP BY cycle_id
    ORDER BY latest DESC
    LIMIT 10
""")
print(f"\n{'CYCLE_ID':<25} {'N':>4} {'FE':>4} {'DR':>4}  CREATED")
print("-" * 70)
for r in cur.fetchall():
    print(f"  {r['cycle_id']:<25} {r['n']:>4} {r['fe']:>4} {r['dr']:>4}  {r['latest']}")

# Dernier cycle id en cycles table
print("\n--- Derniers cycles connus (table cycles) ---")
try:
    cur = conn.execute("SELECT id, created_at FROM cycles ORDER BY created_at DESC LIMIT 5")
    for r in cur.fetchall():
        print(f"  {r['id']}  {r['created_at']}")
except Exception as e:
    print(f"  (table cycles : {e})")

# Verifie sizing_multiplier sur cycle latest
print("\n--- Detail sizing_multiplier sur le dernier cycle ---")
cur = conn.execute("""
    SELECT ticker, sizing_multiplier, regime, forced_exit, drift
    FROM convergence_snapshots
    WHERE cycle_id = (SELECT cycle_id FROM convergence_snapshots ORDER BY created_at DESC LIMIT 1)
    ORDER BY sizing_multiplier ASC, ticker ASC
""")
print(f"\n{'TICKER':<8} {'MULT':>6} {'REGIME':<16} {'FE':>3} {'DR':>3}")
print("-" * 50)
for r in cur.fetchall():
    print(f"  {r['ticker']:<6} {r['sizing_multiplier']:>6.3f}  {r['regime']:<16} {r['forced_exit']:>3} {r['drift']:>3}")

# Snapshot snap-20260609T100504-c5f0aa : a-t-il un cycle_id rattache ?
print("\n--- Le dernier snapshot construction (snap-20260609T100504-c5f0aa) ---")
try:
    cur = conn.execute("""
        SELECT DISTINCT cycle_id FROM portfolio_targets_history
        WHERE snapshot_id = ?
    """, ("snap-20260609T100504-c5f0aa",))
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"  cycle_id rattache : {r['cycle_id']!r}")
    else:
        print("  Aucune ligne en portfolio_targets_history pour ce snapshot")
except Exception as e:
    print(f"  (erreur : {e})")

conn.close()
print("\n[OK] Diag termine.")
