# nextones-find-etf-coverage.py
# 1) Affiche tous les agents qui generent des theses + leur liste de tickers
# 2) Verifie si un agent couvre les ETF sectoriels (XLE/XLK/XLI/XLB)
# 3) Calcule le score S theorique pour XLB/XLI/XLE/XLK avec les memes regles que l'agent
# 4) Cherche un fichier 'factor_agent' ou 'sector_agent' pour voir s'il filtre par asset_class
# ASCII pur.

import sqlite3
import os
import sys
import json
import re

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

# 1) Liste des agents recents avec leur couverture de tickers (dernieres 24h)
print("=" * 70)
print("AGENTS RECENTS - couverture de tickers (theses cree depuis 1j)")
print("=" * 70)
rows = cur.execute(
    "SELECT t.agent_type, i.ticker, i.asset_class, COUNT(*) AS n "
    "FROM theses t JOIN instruments i ON i.id = t.instrument_id "
    "WHERE t.created_at >= datetime('now', '-1 day') "
    "GROUP BY t.agent_type, i.ticker, i.asset_class "
    "ORDER BY t.agent_type, i.asset_class, i.ticker"
).fetchall()

by_agent = {}
for r in rows:
    a = r["agent_type"]
    by_agent.setdefault(a, []).append((r["ticker"], r["asset_class"], r["n"]))

for agent, items in by_agent.items():
    classes = sorted(set(x[1] for x in items))
    print(f"\n--- {agent} ({len(items)} tickers, classes: {classes}) ---")
    for tk, ac, n in items[:30]:
        print(f"    {tk:<8} {ac:<10} n={n}")
print()

# 2) Verifier presence ETF dans les theses tous agents confondus
print("=" * 70)
print("Couverture ETF XLE/XLK/XLI/XLB - tous agents")
print("=" * 70)
for tk in ["XLE", "XLK", "XLI", "XLB"]:
    rows = cur.execute(
        "SELECT t.agent_type, t.conviction_score, t.created_at "
        "FROM theses t JOIN instruments i ON i.id = t.instrument_id "
        "WHERE i.ticker = ? ORDER BY t.created_at DESC LIMIT 5",
        (tk,)
    ).fetchall()
    if rows:
        print(f"  {tk}:")
        for r in rows:
            print(f"    agent={r['agent_type']:<25} conviction={r['conviction_score']} at={r['created_at']}")
    else:
        print(f"  {tk}: AUCUNE these toute date")
print()

# 3) Calcul du score S theorique pour XLB/XLI/XLE/XLK
print("=" * 70)
print("CALCUL SCORE S theorique pour XLB/XLI/XLE/XLK")
print("=" * 70)
# Config
cfg_row = cur.execute("SELECT params_json FROM target_construction_config LIMIT 1").fetchone()
cfg = json.loads(cfg_row["params_json"])
print(f"min_score_inclusion = {cfg['min_score_inclusion']}")
print(f"w_conviction={cfg['w_conviction']} w_realized={cfg['w_realized']} "
      f"w_macro={cfg['w_macro']} w_diversif={cfg['w_diversif']}")
print(f"enable_realized={cfg['enable_realized']} enable_macro={cfg['enable_macro']} "
      f"enable_diversif={cfg['enable_diversif']} enable_vol_penalty={cfg['enable_vol_penalty']}")
print(f"halflife={cfg['conviction_halflife_days']} lookback={cfg['conviction_lookback_days']}")
print()

# Pour comprendre vraiment, on doit aller voir la fonction compute_avg_conviction
# Mais on peut au moins voir conviction_score des theses recentes
for tk in ["XLB", "XLI", "XLE", "XLK", "AAPL", "BTC"]:
    r_i = cur.execute("SELECT id FROM instruments WHERE ticker = ?", (tk,)).fetchone()
    if not r_i: continue
    iid = r_i["id"]
    rows = cur.execute(
        "SELECT conviction_score, created_at FROM theses "
        "WHERE instrument_id = ? AND created_at >= datetime('now', ?) "
        "ORDER BY created_at DESC",
        (iid, f"-{cfg['conviction_lookback_days']} days")
    ).fetchall()
    convs = [r["conviction_score"] for r in rows if r["conviction_score"] is not None]
    if convs:
        avg = sum(convs) / len(convs)
        print(f"  {tk:<8} n_theses={len(convs)} avg_conviction={avg:.4f} sample={convs[:3]}")
    else:
        print(f"  {tk:<8} n_theses=0 (aucune these dans le lookback)")
print()

# 4) Cherche les agents dans le code et leur liste d'instruments
print("=" * 70)
print("FICHIERS AGENTS - filtre par asset_class")
print("=" * 70)
agent_files = []
for root, dirs, files in os.walk(ROOT):
    # Skip backups et venv
    if "venv" in root.lower() or ".bak" in root or "backup" in root.lower() or "__pycache__" in root:
        continue
    for f in files:
        if f.endswith(".py") and ("agent" in f.lower()):
            agent_files.append(os.path.join(root, f))

print(f"Fichiers agents trouves : {len(agent_files)}")
for fp in agent_files[:30]:
    print(f"  {os.path.relpath(fp, ROOT)}")
print()

# Inspecter les patterns asset_class et SELECT instruments dans chaque agent
print("=" * 70)
print("Filtres asset_class par fichier agent")
print("=" * 70)
for fp in agent_files:
    try:
        with open(fp, "r", encoding="utf-8-sig") as f:
            src = f.read()
    except Exception:
        continue
    # Patterns interessants
    hits = []
    for pat in [
        r"asset_class\s*[=!<>]+\s*['\"][a-z]+['\"]",
        r"WHERE\s+asset_class\s*=",
        r"asset_class\s+IN",
        r"asset_class\s*==\s*['\"]equity['\"]",
        r"asset_class\s*==\s*['\"]etf['\"]",
        r"asset_class\s*==\s*['\"]crypto['\"]",
        r"if\s+.*asset_class",
    ]:
        for m in re.finditer(pat, src, re.IGNORECASE):
            hits.append(m.group(0)[:80])
    if hits:
        print(f"\n--- {os.path.basename(fp)} ---")
        for h in hits[:5]:
            print(f"    {h}")

con.close()
print()
print("Done.")
