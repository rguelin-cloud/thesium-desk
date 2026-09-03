# -*- coding: utf-8 -*-
"""
Diag : pourquoi le regime reste MAINTAIN depuis 2 jours ?

On regarde :
  1. Historique complet du regime_log : combien de jours en MAINTAIN, transitions
  2. Inputs du regime : volatilite calculee, indicateurs marche
  3. Code source : ou est la fonction qui decide du regime, quels sont les seuils
  4. Verifier si les prix marche sont a jour (sinon volatilite = 0)
  5. Construction config : params actuels
"""
import sqlite3
import os
import json
import re

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 80)
print("1. HISTORIQUE COMPLET REGIME (50 derniers cycles)")
print("=" * 80)
rows = cur.execute("""
    SELECT cycle_id, regime, invested_pct, nav, cash, n_positions,
           n_proposals_in, n_proposals_attenuated, n_sell_capped, n_buy_capped,
           notes, created_at
    FROM regime_log
    ORDER BY id DESC
    LIMIT 50
""").fetchall()
print(f"  {len(rows)} entrees")
prev_regime = None
transitions = []
for r in rows:
    marker = ""
    if prev_regime and prev_regime != r["regime"]:
        marker = f"  <-- TRANSITION {r['regime']} -> {prev_regime}"
        transitions.append((r["created_at"], r["regime"], prev_regime))
    prev_regime = r["regime"]
    print(f"  {r['created_at']} cycle={r['cycle_id']:<22} regime={r['regime']:<12} "
          f"inv%={r['invested_pct']:>6.2f} nav={r['nav']:>10.0f} props_in={r['n_proposals_in']:>3} "
          f"capped={r['n_sell_capped']+r['n_buy_capped']:>2}{marker}")

print()
print(f"  Transitions detectees : {len(transitions)}")
for t in transitions:
    print(f"    {t[0]} : {t[1]} -> {t[2]}")

print()
print("=" * 80)
print("2. DISTRIBUTION DES REGIMES SUR L'HISTORIQUE")
print("=" * 80)
rows = cur.execute("""
    SELECT regime, COUNT(*) AS n, MIN(created_at) AS first, MAX(created_at) AS last
    FROM regime_log
    GROUP BY regime
    ORDER BY n DESC
""").fetchall()
for r in rows:
    print(f"  {r['regime']:<15} n={r['n']:<4} de {r['first']} a {r['last']}")

print()
print("=" * 80)
print("3. CONFIG construction (params_json) actuel")
print("=" * 80)
row = cur.execute("""
    SELECT params_json, updated_at FROM target_construction_config
    ORDER BY id DESC LIMIT 1
""").fetchone()
if row:
    print(f"  updated_at = {row['updated_at']}")
    try:
        params = json.loads(row["params_json"])
        for k, v in params.items():
            if isinstance(v, dict):
                print(f"  {k} :")
                for k2, v2 in v.items():
                    print(f"    {k2} = {v2}")
            else:
                print(f"  {k} = {v}")
    except Exception as e:
        print(f"  ERREUR parsing : {e}")
        print(f"  Raw: {row['params_json'][:500]}")

print()
print("=" * 80)
print("4. INSTRUMENTS PRICE FRESHNESS")
print("=" * 80)
# Verifier les derniers prix par instrument
TABLES = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
if "prices" in TABLES:
    p_cols = [r["name"] for r in cur.execute("PRAGMA table_info(prices)").fetchall()]
    print(f"  cols prices : {p_cols}")
    ts_col = None
    for cand in ("date", "ts", "timestamp", "created_at", "as_of"):
        if cand in p_cols:
            ts_col = cand
            break
    if ts_col:
        rows = cur.execute(f"""
            SELECT MAX({ts_col}) AS last_ts, COUNT(*) AS n_rows
            FROM prices
        """).fetchone()
        print(f"  Dernier prix : {rows['last_ts']}  total={rows['n_rows']} lignes")
        # Par ticker
        if "ticker" in p_cols:
            rows = cur.execute(f"""
                SELECT ticker, MAX({ts_col}) AS last_ts, COUNT(*) AS n
                FROM prices
                GROUP BY ticker
                ORDER BY last_ts DESC
                LIMIT 30
            """).fetchall()
            print(f"  Freshness par ticker (top 30) :")
            for r in rows:
                print(f"    {r['ticker']:<10} last={r['last_ts']:<25} n={r['n']}")

print()
print("=" * 80)
print("5. CODE : ou est la logique de decision du regime ?")
print("=" * 80)
# Chercher dans les fichiers Python
py_files = []
for root, _, files in os.walk(ROOT):
    if any(skip in root for skip in (".git", "__pycache__", "venv", ".bak")):
        continue
    for f in files:
        if f.endswith(".py") and not f.startswith("nextones-"):
            py_files.append(os.path.join(root, f))
print(f"  {len(py_files)} fichiers .py a scanner")

# Mots cles
patterns = [
    (r"regime\s*=\s*['\"](MAINTAIN|RISK_ON|RISK_OFF|EXPANSION|DEFENSIVE)", "assignation regime"),
    (r"def\s+(\w*regime\w*)\s*\(", "fonction regime"),
    (r"def\s+(\w*decide\w*regime\w*|\w*classify\w*regime\w*|\w*detect\w*regime\w*)", "decide regime"),
    (r"volatility\s*[><]\s*[\d\.]+", "comparaison volatility"),
    (r"vix\s*[><]\s*[\d\.]+", "comparaison vix"),
]
hits = {}
for pf in py_files:
    try:
        with open(pf, "r", encoding="utf-8-sig", errors="ignore") as f:
            content = f.read()
    except Exception:
        continue
    fname = os.path.basename(pf)
    for pat, label in patterns:
        for m in re.finditer(pat, content, re.IGNORECASE):
            hits.setdefault(label, []).append((fname, m.group(0)[:80]))

for label, items in hits.items():
    print(f"\n  [{label}]")
    seen = set()
    for fname, snippet in items:
        key = (fname, snippet[:50])
        if key in seen:
            continue
        seen.add(key)
        print(f"    {fname:<40} : {snippet}")

print()
print("=" * 80)
print("6. RECHERCHE FONCTION decide_regime / classify_regime / get_regime")
print("=" * 80)
for pf in py_files:
    try:
        with open(pf, "r", encoding="utf-8-sig", errors="ignore") as f:
            content = f.read()
    except Exception:
        continue
    fname = os.path.basename(pf)
    # Cherche def ...regime...
    for m in re.finditer(r"def\s+(\w*regime\w*)\s*\(([^)]*)\)", content, re.IGNORECASE):
        func_name = m.group(1)
        # Extraire les 50 lignes suivantes
        start = m.start()
        excerpt = content[start:start+2500]
        # Garder jusqu'au prochain 'def ' au meme niveau
        next_def = re.search(r"\n(def |class )", excerpt[10:])
        if next_def:
            excerpt = excerpt[:next_def.start() + 10]
        print(f"\n  {fname} -> def {func_name}({m.group(2)[:50]}...)")
        for i, line in enumerate(excerpt.splitlines()[:60]):
            print(f"    {i:3} | {line}")
        print(f"    [...]")

con.close()
print()
print("=" * 80)
print("FIN DU DIAG")
print("=" * 80)
