#!/usr/bin/env python3
# Trouve OU sont les 10 ordres pending affiches dans l'UI
# et COMMENT [RISK_V2_WIRED] est cable (proposition vs validation)

import sqlite3, re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 78)
print("OU SONT LES 10 ORDRES PENDING ?")
print("=" * 78)

# 1) toutes les tables potentielles
print("\n[1] Tables contenant 'order' ou 'propos' ou 'trade'")
print("-" * 78)
cur.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND (name LIKE '%order%' OR name LIKE '%propos%' OR name LIKE '%trade%' OR name LIKE '%pending%')
    ORDER BY name
""")
tables = [r[0] for r in cur.fetchall()]
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    n = cur.fetchone()[0]
    cur.execute(f"PRAGMA table_info({t})")
    cols = [c[1] for c in cur.fetchall()]
    print(f"  {t:35s}  {n:>5} rows  cols={cols}")

# 2) Cherche les 10 BUY recents dans toutes ces tables
print("\n[2] Recherche BUY recents (29/05) dans chaque table")
print("-" * 78)
for t in tables:
    cur.execute(f"PRAGMA table_info({t})")
    cols = [c[1] for c in cur.fetchall()]
    if not cols:
        continue
    # cherche une colonne date
    date_col = next((c for c in ("created_at", "ts", "timestamp", "date", "created") if c in cols), None)
    if not date_col:
        continue
    try:
        cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {date_col} LIKE '2026-05-29%'")
        n = cur.fetchone()[0]
        if n > 0:
            print(f"\n  --- {t} : {n} entrees du 29/05 ---")
            cur.execute(f"SELECT * FROM {t} WHERE {date_col} LIKE '2026-05-29%' ORDER BY {date_col} DESC LIMIT 12")
            for r in cur.fetchall():
                d = dict(r)
                # affiche cles principales
                key_fields = {k: v for k, v in d.items() if k in ("id", "instrument_id", "symbol", "ticker", "side", "qty", "quantity", "status", "risk_check_result", date_col)}
                # tronque les valeurs longues
                line = " ".join(f"{k}={str(v)[:30]}" for k, v in key_fields.items())
                print(f"    {line}")
    except Exception as e:
        print(f"  {t}: err {e}")

# 3) Cherche les IDs 4895-4907 partout
print("\n[3] Recherche IDs 4895-4907 dans toutes tables avec colonne id")
print("-" * 78)
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
all_tables = [r[0] for r in cur.fetchall()]
for t in all_tables:
    try:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [c[1] for c in cur.fetchall()]
        if "id" not in cols:
            continue
        cur.execute(f"SELECT COUNT(*) FROM {t} WHERE id BETWEEN 4895 AND 4907")
        n = cur.fetchone()[0]
        if n > 0:
            print(f"  {t}: {n} rows avec id 4895-4907")
    except Exception:
        pass

# 4) Max id de orders
print("\n[4] Range des IDs sur orders")
print("-" * 78)
try:
    cur.execute("SELECT MIN(id) AS mn, MAX(id) AS mx, COUNT(*) AS n FROM orders")
    r = cur.fetchone()
    print(f"  orders: min={r['mn']}, max={r['mx']}, count={r['n']}")
    # 10 derniers
    cur.execute("SELECT id, instrument_id, side, quantity, status, risk_check_result, created_at FROM orders ORDER BY id DESC LIMIT 15")
    print(f"\n  15 derniers ordres:")
    for r in cur.fetchall():
        rc = str(r['risk_check_result'])[:50] if r['risk_check_result'] else "None"
        print(f"    #{r['id']:>5} inst={r['instrument_id']:>3} {r['side']:<5} qty={str(r['quantity']):<10} status={r['status']:<12} created={r['created_at']} rc={rc}")
except Exception as e:
    print(f"  err: {e}")

# 5) Inspect execution_engine.py L1180-1230 (le gate wired)
print("\n[5] Contexte wired [RISK_V2_WIRED] L1180-1235 dans execution_engine.py")
print("-" * 78)
p = ROOT / "execution_engine.py"
content = p.read_text(encoding="utf-8-sig", errors="replace")
lines = content.splitlines()
for i in range(1175, 1240):
    if i < len(lines):
        print(f"  L{i+1}: {lines[i].rstrip()[:130]}")

# 6) Cherche la def de create_and_execute_order pour voir d'OU elle est appelee
print("\n[6] Definition create_and_execute_order + appelants")
print("-" * 78)
m = re.search(r"def create_and_execute_order\([^)]*\)", content)
if m:
    ln = content[:m.start()].count("\n") + 1
    print(f"  Definie a L{ln}: {m.group()[:100]}")

# Cherche les appels a cette fonction
for py in ROOT.glob("*.py"):
    if py.name.startswith("nextones-"):
        continue
    try:
        c = py.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        continue
    for m in re.finditer(r"create_and_execute_order\(", c):
        ln = c[:m.start()].count("\n") + 1
        start = c.rfind("\n", 0, m.start()) + 1
        end = c.find("\n", m.end())
        print(f"  appel: {py.name}:L{ln}  {c[start:end].strip()[:120]}")

conn.close()
print("\n" + "=" * 78)
