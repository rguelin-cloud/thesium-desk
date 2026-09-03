#!/usr/bin/env python3
# nextones-fix-risk-v2-db-lock.py
# Fix Option A : timeout 30s + busy_timeout 30000ms sur la connexion risk_pretrade
# Marker idempotent : [RISK_V2_DBLOCK_FIX_V1]
#
# Cible : risk_pretrade.py:L50-53 (def _conn)
# Avant :
#   def _conn(db_path: str) -> sqlite3.Connection:
#       c = sqlite3.connect(db_path)
#       c.row_factory = sqlite3.Row
#       return c
# Apres :
#   def _conn(db_path: str) -> sqlite3.Connection:  # [RISK_V2_DBLOCK_FIX_V1]
#       c = sqlite3.connect(db_path, timeout=30.0)
#       c.row_factory = sqlite3.Row
#       try:
#           c.execute("PRAGMA busy_timeout=30000")
#       except Exception:
#           pass
#       return c

import shutil, sys, sqlite3, json, traceback
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
TARGET = ROOT / "risk_pretrade.py"
DB = ROOT / "thesium.db"
TS = datetime.now().strftime("%Y%m%dT%H%M%S")
BACKUP_DIR = ROOT / f"_backups_risk_v2_dblock_{TS}"
MARKER = "[RISK_V2_DBLOCK_FIX_V1]"

def ok(s):    print(f"  OK   {s}")
def info(s):  print(f"  INFO {s}")
def warn(s):  print(f"  WARN {s}")
def fatal(s):
    print(f"  FATAL {s}")
    sys.exit(1)

print("=" * 78)
print(f" RISK V2 DB LOCK FIX - marker {MARKER}")
print("=" * 78)

# 1) Backup
print("\n[1] Backup horodate")
print("-" * 78)
BACKUP_DIR.mkdir(exist_ok=True)
backup_file = BACKUP_DIR / "risk_pretrade.py"
shutil.copy2(TARGET, backup_file)
ok(f"backup -> {backup_file}")

# 2) Read source utf-8-sig
print("\n[2] Lecture source")
print("-" * 78)
src = TARGET.read_text(encoding="utf-8-sig", errors="replace")
print(f"  Length: {len(src)} chars")

# Idempotence check
if MARKER in src:
    info(f"Marker {MARKER} deja present - skip patch")
    sys.exit(0)

# 3) Apply patch
print("\n[3] Application patch")
print("-" * 78)
OLD = (
    "def _conn(db_path: str) -> sqlite3.Connection:\n"
    "    c = sqlite3.connect(db_path)\n"
    "    c.row_factory = sqlite3.Row\n"
    "    return c\n"
)
NEW = (
    f"def _conn(db_path: str) -> sqlite3.Connection:  # {MARKER}\n"
    "    c = sqlite3.connect(db_path, timeout=30.0)\n"
    "    c.row_factory = sqlite3.Row\n"
    "    try:\n"
    "        c.execute(\"PRAGMA busy_timeout=30000\")\n"
    "    except Exception:\n"
    "        pass\n"
    "    return c\n"
)
if OLD not in src:
    fatal(f"Bloc OLD non trouve dans {TARGET} - structure changee ?")
new_src = src.replace(OLD, NEW, 1)
if MARKER not in new_src:
    fatal("Marker absent apres replace - aborting")
TARGET.write_text(new_src, encoding="utf-8")  # sans BOM
ok(f"Patch applique - marker present {new_src.count(MARKER)}x")

# 4) Validation counts
print("\n[4] Validation tags")
print("-" * 78)
n_marker = new_src.count(MARKER)
n_busy = new_src.count("busy_timeout")
n_connect_old = new_src.count("sqlite3.connect(db_path)")
n_connect_new = new_src.count("sqlite3.connect(db_path, timeout=30.0)")
print(f"  Marker {MARKER}            : {n_marker}")
print(f"  Mentions busy_timeout           : {n_busy}")
print(f"  Restes connect(db_path) seul    : {n_connect_old}")
print(f"  connect(db_path, timeout=30.0)  : {n_connect_new}")
if n_marker != 1 or n_connect_new != 1:
    warn("Compte inattendu - verifie manuellement")
else:
    ok("Compte coherent")

# 5) Smoke test - import + appel direct
print("\n[5] Smoke test - run_pretrade_checks AAPL 1 200 BUY")
print("-" * 78)
sys.path.insert(0, str(ROOT))
# force reimport
for mod in list(sys.modules):
    if mod.startswith("risk_pretrade"):
        del sys.modules[mod]
try:
    from risk_pretrade import run_pretrade_checks
    res = run_pretrade_checks("AAPL", 1.0, 200.0, "BUY", db_path=str(DB))
    print(f"  passed     : {res.get('passed')}")
    print(f"  blocked_by : {res.get('blocked_by')}")
    print(f"  marker     : {res.get('marker')}")
    ok("Smoke test OK")
except Exception as e:
    warn(f"Smoke test FAIL : {type(e).__name__}: {e}")
    traceback.print_exc()

# 6) Verifie insert dans risk_pretrade_log
print("\n[6] Verifie insert dans risk_pretrade_log")
print("-" * 78)
conn = sqlite3.connect(str(DB), timeout=5.0)
conn.row_factory = sqlite3.Row
n_before = conn.execute("SELECT COUNT(*) FROM risk_pretrade_log").fetchone()[0]
print(f"  Total entrees risk_pretrade_log : {n_before}")
last = conn.execute("SELECT id, ts, symbol, side, qty, passed FROM risk_pretrade_log ORDER BY id DESC LIMIT 3").fetchall()
for r in last:
    print(f"    #{r['id']:>3} ts={r['ts']} sym={r['symbol']} {r['side']} qty={r['qty']} passed={r['passed']}")
conn.close()

print("\n" + "=" * 78)
print(" FIX TERMINE")
print("=" * 78)
print(f"""
PROCHAINES ETAPES :
  1) Le fix prend effet AU PROCHAIN cycle (uvicorn n'a pas besoin de redemarrer
     car risk_pretrade.py est importe a la volee dans le hook L1199).
  2) Toutefois, par securite, redemarre uvicorn pour purger un eventuel cache :
       py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000
  3) Au prochain Run Decision Cycle, verifie :
     SELECT id, ts, symbol, side, passed, blocked_by
     FROM risk_pretrade_log
     WHERE ts LIKE '2026-05-%%' ORDER BY id DESC LIMIT 15;
  4) Verifie aussi que les warnings 'database is locked' disparaissent dans
     orders.risk_check_result du prochain cycle.
""")
