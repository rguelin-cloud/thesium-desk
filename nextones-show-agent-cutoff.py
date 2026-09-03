# nextones-show-agent-cutoff.py
# Affiche les sections cles du portfolio_construction_agent.py pour comprendre :
# - le slice [:3] L944 (sur quoi il s'applique - asset_class ? bucket ?)
# - comment min_score_inclusion est applique
# - le contexte des theses pour XLB et XLI (score reel sur le run)
# ASCII pur.

import sqlite3
import os
import sys
import json

AGENT_FILE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py"
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

# 1) Code autour de L944 (slice [:3])
print("=" * 70)
print("CODE AGENT autour de L944 (lignes 900-970)")
print("=" * 70)
if not os.path.exists(AGENT_FILE):
    print(f"introuvable: {AGENT_FILE}")
    sys.exit(1)

with open(AGENT_FILE, "r", encoding="utf-8-sig") as f:
    lines = f.read().splitlines()

START, END = 880, 980
for i in range(START - 1, min(END, len(lines))):
    print(f"L{i+1:>4}: {lines[i]}")
print()

# 2) Code autour de min_score_inclusion (L86 et L936)
print("=" * 70)
print("CODE autour de min_score_inclusion (L920-960)")
print("=" * 70)
for i in range(925 - 1, 960):
    if i < len(lines):
        print(f"L{i+1:>4}: {lines[i]}")
print()

# 3) Definitions de S, rows
print("=" * 70)
print("Recherche : definition de 'rows' et 'S' dans le scope build/include")
print("=" * 70)
import re
# Lignes contenant "rows = " ou "x[\"S\"]" autour de L944
for i, l in enumerate(lines, 1):
    if 800 <= i <= 950:
        if re.search(r"\brows\s*=", l) or re.search(r"\"S\"\s*:", l) or re.search(r"'S'\s*:", l) or "rows.append" in l:
            print(f"L{i:>4}: {l}")
print()

# 4) Thresholds appliques avant le slice
print("=" * 70)
print("Filtres / threshold avant le slice [:3]")
print("=" * 70)
for i in range(880, 944):
    if i < len(lines):
        l = lines[i]
        if any(k in l.lower() for k in ["if ", "filter", "skip", "continue", "exclude", "drop", "threshold", "min_score"]):
            print(f"L{i+1:>4}: {l}")
print()

# 5) DB - rechercher des theses recentes pour XLB/XLI (donnees du run construction)
print("=" * 70)
print("Theses recentes pour XLB / XLI / XLE / XLK")
print("=" * 70)
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

# Schema theses
cols = cur.execute("PRAGMA table_info(theses)").fetchall()
th_cols = [c['name'] for c in cols]
print(f"colonnes theses : {th_cols}")
print()

# Trouver col ticker dans theses
t_col = None
for c in ["ticker", "instrument_ticker", "symbol", "instrument_id"]:
    if c in th_cols: t_col = c; break

ts_col = None
for c in ["created_at", "ts", "updated_at"]:
    if c in th_cols: ts_col = c; break

if t_col and t_col != "instrument_id":
    for tk in ["XLB", "XLI", "XLE", "XLK"]:
        rows = cur.execute(
            f"SELECT * FROM theses WHERE {t_col} = ? ORDER BY {ts_col} DESC LIMIT 3",
            (tk,)
        ).fetchall()
        print(f"--- {tk} ---")
        if not rows:
            print("  (aucune these)")
        for r in rows:
            d = dict(r)
            # afficher seulement les champs utiles
            interesting = {k: v for k, v in d.items() if k in ["id", "stance", "conviction", "score", "agent", "created_at", t_col]}
            print(f"  {interesting}")
elif t_col == "instrument_id":
    # Resoudre via instruments
    for tk in ["XLB", "XLI", "XLE", "XLK"]:
        r_i = cur.execute("SELECT id FROM instruments WHERE ticker = ?", (tk,)).fetchone()
        if not r_i:
            print(f"  {tk}: pas dans instruments"); continue
        iid = r_i["id"]
        rows = cur.execute(
            f"SELECT * FROM theses WHERE instrument_id = ? ORDER BY {ts_col} DESC LIMIT 5",
            (iid,)
        ).fetchall()
        print(f"--- {tk} (iid={iid}) ---")
        if not rows:
            print("  (aucune these)")
        for r in rows:
            d = dict(r)
            for k in ["id", "stance", "conviction", "score", "agent", "created_at"]:
                if k in d:
                    print(f"    {k}={d[k]}")
            print()
print()

# 6) micro_theses, ou autres tables qui pourraient contenir le score S
print("=" * 70)
print("Tables possibles pour score S")
print("=" * 70)
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
for t in tables:
    name = t["name"]
    if any(k in name.lower() for k in ["thesis", "thes", "score", "micro", "construction"]):
        cols2 = cur.execute(f"PRAGMA table_info({name})").fetchall()
        cn = [c['name'] for c in cols2]
        print(f"  {name}: {cn}")

con.close()
print()
print("Done.")
