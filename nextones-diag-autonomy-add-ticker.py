#!/usr/bin/env python3
# Verifie si l'app peut autonome AJOUTER un ticker au portefeuille
# 1. Comment est defini l'univers investissable (table, source) ?
# 2. Y a-t-il un agent / processus qui PROPOSE des nouveaux tickers ?
# 3. Comment un ticker passe de "decouvert" a "tradable" ?
# 4. Le scheduler appelle-t-il une fonction d'expansion d'univers ?

from pathlib import Path
import sqlite3, re

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 78)
print("DIAG : Autonomie ajout ticker au portefeuille")
print("=" * 78)

# 1) Tables liees a l'univers
print("\n[1] Tables univers / instruments / watchlist")
print("-" * 78)
cur.execute("""
    SELECT name FROM sqlite_master WHERE type='table'
    AND (name LIKE '%instrument%' OR name LIKE '%univers%' OR name LIKE '%watchlist%'
         OR name LIKE '%target%' OR name LIKE '%screening%' OR name LIKE '%candidate%'
         OR name LIKE '%discover%' OR name LIKE '%universe%')
    ORDER BY name
""")
for (t,) in cur.fetchall():
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    n = cur.fetchone()[0]
    cur.execute(f"PRAGMA table_info({t})")
    cols = [c[1] for c in cur.fetchall()]
    print(f"  {t:35s} {n:>5} rows  cols={cols[:10]}")

# 2) Schema instruments + dernier ajoute
print("\n[2] Schema instruments + 5 plus recents")
print("-" * 78)
cur.execute("PRAGMA table_info(instruments)")
for c in cur.fetchall():
    print(f"  {c[1]:25s} {c[2]}")
date_col = None
cur.execute("PRAGMA table_info(instruments)")
cols = [c[1] for c in cur.fetchall()]
for c in ("created_at", "added_at", "date_added", "updated_at"):
    if c in cols:
        date_col = c
        break
if date_col:
    cur.execute(f"SELECT id, ticker, name, asset_class, {date_col} FROM instruments ORDER BY {date_col} DESC LIMIT 5")
    print(f"\n  5 plus recents (par {date_col}):")
    for r in cur.fetchall():
        print(f"    #{r['id']:>3} {r['ticker']:<8} {r['name'][:30]:<30} {r['asset_class']:<8} {r[date_col]}")
else:
    cur.execute("SELECT id, ticker, name, asset_class FROM instruments ORDER BY id DESC LIMIT 5")
    print("\n  5 derniers par id:")
    for r in cur.fetchall():
        print(f"    #{r['id']:>3} {r['ticker']:<8} {r['name'][:30]:<30} {r['asset_class']}")

# 3) target_construction_config : config univers
print("\n[3] target_construction_config (config univers)")
print("-" * 78)
cur.execute("SELECT * FROM target_construction_config LIMIT 1")
r = cur.fetchone()
if r:
    for k in r.keys():
        v = str(r[k])
        if len(v) > 100:
            v = v[:100] + "..."
        print(f"  {k:35s} : {v}")

# 4) target_universe : la liste effective
print("\n[4] target_universe (univers effectif)")
print("-" * 78)
try:
    cur.execute("SELECT * FROM target_universe ORDER BY symbol LIMIT 30")
    rows = cur.fetchall()
    if rows:
        print(f"  cols: {list(rows[0].keys())}")
        for r in rows:
            print(f"    {dict(r)}")
    else:
        print("  vide")
except Exception as e:
    print(f"  err: {e}")

# 5) Cherche dans le code Python les patterns d'ajout autonome
print("\n[5] Code Python : patterns 'add_instrument' / 'screening' / 'discover' / 'universe_expand'")
print("-" * 78)
patterns = [
    r"INSERT INTO instruments",
    r"add_instrument",
    r"discover_ticker",
    r"add_to_universe",
    r"expand_universe",
    r"screening",
    r"new_ticker",
    r"propose_instrument",
    r"add_candidate",
    r"watchlist",
]
for py in ROOT.glob("*.py"):
    if py.name.startswith("nextones-diag-") or py.name.startswith("nextones-fix-") or py.name.startswith("nextones-show-"):
        continue
    try:
        content = py.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        continue
    matches_in_file = []
    for pat in patterns:
        for m in re.finditer(pat, content, re.IGNORECASE):
            ln = content[:m.start()].count("\n") + 1
            start = content.rfind("\n", 0, m.start()) + 1
            end = content.find("\n", m.end())
            line = content[start:end].strip()
            matches_in_file.append((pat, ln, line[:120]))
    if matches_in_file:
        print(f"\n  --- {py.name} ---")
        seen = set()
        for pat, ln, line in matches_in_file:
            key = (ln, line[:60])
            if key in seen:
                continue
            seen.add(key)
            print(f"    L{ln} [{pat}] {line}")

# 6) Scheduler : taches recurrentes liees a l'univers
print("\n[6] Scheduler.py : taches recurrentes")
print("-" * 78)
sched = ROOT / "scheduler.py"
if sched.exists():
    src = sched.read_text(encoding="utf-8-sig", errors="replace")
    for i, ln in enumerate(src.splitlines(), 1):
        if re.search(r"(add_job|schedule|cron|interval|every).*?(univers|instrument|screening|discover|expand|candidate)", ln, re.IGNORECASE):
            print(f"  L{i}: {ln.rstrip()[:130]}")

# 7) Stats positions actuelles vs univers
print("\n[7] Positions actives vs total instruments")
print("-" * 78)
try:
    cur.execute("SELECT COUNT(*) AS n FROM positions WHERE quantity > 0")
    pos = cur.fetchone()['n']
except Exception:
    pos = 'N/A'
cur.execute("SELECT COUNT(*) AS n FROM instruments")
total = cur.fetchone()['n']
print(f"  Instruments total : {total}")
print(f"  Positions actives : {pos}")

conn.close()
print("\n" + "=" * 78)
