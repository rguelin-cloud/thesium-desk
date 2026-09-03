# nextones-diag-api-and-locks.py
# Diagnostique etat API + verrous DB
# 1) Ping racine + /api/healthz
# 2) Test simple read sur DB (verifier le lock)
# 3) Liste dernieres entrees event_log pour voir si un cycle execute-cycle est en cours
# ASCII pur.

import sqlite3
import os
import sys
import json
import urllib.request
import urllib.error
import time

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
BASE = "http://127.0.0.1:8000"

# 1) Ping
print("=" * 70)
print("PING API")
print("=" * 70)
for path in ["/", "/api/healthz", "/api/health", "/api/status"]:
    url = BASE + path
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read()[:300].decode("utf-8", errors="replace")
            print(f"  GET {path:<20} HTTP {resp.status} body={body[:120]}")
    except urllib.error.HTTPError as e:
        print(f"  GET {path:<20} HTTP {e.code}")
    except Exception as e:
        print(f"  GET {path:<20} ERR {type(e).__name__}: {e}")
print()

# 2) Test lock DB - SELECT simple puis UPDATE volatile
print("=" * 70)
print("TEST LOCK DB")
print("=" * 70)
if not os.path.exists(DB):
    print(f"  DB introuvable : {DB}")
    sys.exit(1)

# Lecture
try:
    con = sqlite3.connect(DB, timeout=2)
    cur = con.cursor()
    r = cur.execute("SELECT COUNT(*) FROM theses").fetchone()
    print(f"  SELECT OK -> {r[0]} theses")
    # Test UPDATE rapide sur ligne neutre
    try:
        # PRAGMA pour voir si la DB est accessible en write
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("ROLLBACK")
        print("  BEGIN IMMEDIATE + ROLLBACK = OK (pas de lock write)")
    except sqlite3.OperationalError as e:
        print(f"  BEGIN IMMEDIATE FAIL : {e}")
    con.close()
except sqlite3.OperationalError as e:
    print(f"  SELECT FAIL : {e}")
print()

# 3) Dernieres entrees event_log (15 min)
print("=" * 70)
print("event_log dernieres 15 minutes")
print("=" * 70)
try:
    con = sqlite3.connect(DB, timeout=2)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = cur.execute(
        "SELECT id, event_type, agent, entity_id, created_at "
        "FROM event_log WHERE created_at >= datetime('now', '-15 minutes') "
        "ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    if not rows:
        print("  (aucun event recent)")
    for r in rows:
        print(f"  L{r['id']:>5} {r['created_at']} {r['agent']:<25} {r['event_type']:<35} ent={r['entity_id']}")
    con.close()
except sqlite3.OperationalError as e:
    print(f"  ERR : {e}")
print()

# 4) Compter ordres recents
print("=" * 70)
print("orders recents (15 min)")
print("=" * 70)
try:
    con = sqlite3.connect(DB, timeout=2)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = cur.execute(
        "SELECT id, instrument_id, side, quantity, status, created_at "
        "FROM orders WHERE created_at >= datetime('now', '-15 minutes') "
        "ORDER BY id DESC LIMIT 30"
    ).fetchall()
    if not rows:
        print("  (aucun ordre recent)")
    for r in rows:
        print(f"  id={r['id']:<4} instr={r['instrument_id']:<3} {r['side']:<5} qty={r['quantity']:<14} {r['status']:<10} at={r['created_at']}")
    con.close()
except sqlite3.OperationalError as e:
    print(f"  ERR : {e}")
print()

# 5) Cycles recents
print("=" * 70)
print("cycles_daily dernieres 24h")
print("=" * 70)
try:
    con = sqlite3.connect(DB, timeout=2)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cols = cur.execute("PRAGMA table_info(cycles_daily)").fetchall()
    col_names = [c['name'] for c in cols]
    print(f"  colonnes : {col_names}")
    # Detection col date
    tcol = None
    for c in ["created_at", "ts", "cycle_date", "date", "run_at"]:
        if c in col_names: tcol = c; break
    if tcol:
        rows = cur.execute(
            f"SELECT * FROM cycles_daily ORDER BY {tcol} DESC LIMIT 5"
        ).fetchall()
        for r in rows:
            d = dict(r)
            # Compact
            s = " | ".join(f"{k}={str(v)[:30]}" for k, v in d.items() if v is not None)
            print(f"    {s}")
    con.close()
except sqlite3.OperationalError as e:
    print(f"  ERR : {e}")

print()
print("Done.")
