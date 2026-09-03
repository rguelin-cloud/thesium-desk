# -*- coding: utf-8 -*-
"""
Diag carte Convergence Engine :
(a) variables CSS du theme (clair/sombre) presentes dans index.html / style.css
(b) structure reelle de buckets_json pour 2 tickers (1 forced_exit, 1 strong)
"""
import os, sys, re, io, sqlite3, json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(BASE, "thesium.db")
INDEX = os.path.join(BASE, "index.html")

# (a) Variables CSS
print("=" * 60)
print("(a) VARIABLES CSS THEME")
print("=" * 60)
with open(INDEX, "r", encoding="utf-8-sig") as f:
    html = f.read()

# :root + [data-theme] + .light-mode etc
print("\n[ROOT VARS]")
for m in re.finditer(r':root\s*\{([^}]+)\}', html, re.DOTALL):
    block = m.group(1)
    for v in re.finditer(r'(--[a-z0-9-]+)\s*:\s*([^;]+);', block, re.IGNORECASE):
        print(f"  {v.group(1)} : {v.group(2).strip()}")

print("\n[LIGHT THEME OVERRIDES]")
for m in re.finditer(r'(\[data-theme="light"\]|\.light-mode|body\.light|html\.light)\s*\{([^}]+)\}', html, re.DOTALL):
    selector = m.group(1)
    print(f"  Selector: {selector}")
    for v in re.finditer(r'(--[a-z0-9-]+)\s*:\s*([^;]+);', m.group(2), re.IGNORECASE):
        print(f"    {v.group(1)} : {v.group(2).strip()}")

# attribut data-theme actuel
print("\n[ATTRIBUT data-theme dans html ou body]")
for m in re.finditer(r'<(html|body)[^>]*data-theme\s*=\s*"([^"]+)"', html, re.IGNORECASE):
    print(f"  {m.group(1)} -> {m.group(2)}")

# Theme toggle
print("\n[THEME TOGGLE LOGIC]")
# chercher .theme-toggle, setTheme, localStorage theme
for kw in ["theme-toggle", "setTheme", "data-theme", "themeToggle"]:
    cnt = html.count(kw)
    print(f"  '{kw}' : {cnt} occurences dans index.html")

# (b) Structure buckets_json
print("\n" + "=" * 60)
print("(b) STRUCTURE buckets_json")
print("=" * 60)

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Dernier cycle
cur.execute("SELECT cycle_id FROM convergence_snapshots ORDER BY rowid DESC LIMIT 1")
row = cur.fetchone()
if not row:
    print("PAS DE SNAPSHOT")
    sys.exit(0)
cycle_id = row[0]
print(f"cycle_id : {cycle_id}")

# 1 forced_exit + 1 strong + 1 drift
for label, where in [
    ("FORCED_EXIT", "forced_exit = 1"),
    ("DRIFT", "drift = 1"),
    ("STRONG", "sizing_multiplier >= 1.0 AND n_aligned >= 3"),
    ("NEUTRAL", "forced_exit = 0 AND drift = 0 AND n_aligned < 3"),
]:
    cur.execute(f"""
        SELECT ticker, direction_consensus, n_aligned, n_present, convergence_pct,
               sizing_multiplier, forced_exit, drift, is_crypto, buckets_json
        FROM convergence_snapshots
        WHERE cycle_id = ? AND {where}
        LIMIT 1
    """, (cycle_id,))
    r = cur.fetchone()
    if not r:
        print(f"\n[{label}] aucun")
        continue
    print(f"\n[{label}] {r[0]}  dir={r[1]}  n={r[2]}/{r[3]}  pct={r[4]}  sizing={r[5]}  fe={r[6]}  drift={r[7]}  crypto={r[8]}")
    try:
        buckets = json.loads(r[9]) if r[9] else {}
    except Exception as e:
        print(f"  ERREUR PARSE : {e}")
        print(f"  raw: {r[9][:300]}")
        continue
    print(f"  buckets keys: {list(buckets.keys())}")
    for k, v in buckets.items():
        print(f"    {k} = {json.dumps(v, ensure_ascii=False)[:200]}")

conn.close()
print("\n[DONE]")
