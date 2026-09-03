# Diag plus profond :
# 1) Liste TOUTES les tables replay_* existantes (et leur DDL)
# 2) Tente CREATE TABLE replay_orders ligne par ligne pour identifier le coupable exact
# 3) Liste les methodes publiques de ReplayOrchestrator
import os, sqlite3, sys, inspect

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(PROD_DIR, "thesium.db")
sys.path.insert(0, PROD_DIR)

print("=" * 70)
print("DIAG DEEPER : tables replay_* + executescript step-by-step + methods")
print("=" * 70)

conn = sqlite3.connect(DB, timeout=10.0)
cur = conn.cursor()

print("\n--- Tables 'replay_*' dans la DB ---")
rows = cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'replay_%' ORDER BY name"
).fetchall()
for r in rows:
    print(f"  {r[0]}")

print("\n--- DDL exact replay_orders (si existe) ---")
row = cur.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='replay_orders'"
).fetchone()
if row:
    print(row[0])
    print("\n  PRAGMA table_info :")
    for r in cur.execute("PRAGMA table_info(replay_orders)").fetchall():
        print(f"    {r[1]:<25s} {r[2]}")
else:
    print("  (n'existe pas)")

print("\n--- DDL exact replay_fills (si existe) ---")
row = cur.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='replay_fills'"
).fetchone()
if row:
    print(row[0])
else:
    print("  (n'existe pas)")

print("\n--- DDL exact replay_positions (si existe) ---")
row = cur.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='replay_positions'"
).fetchone()
if row:
    print(row[0])
else:
    print("  (n'existe pas)")

print("\n--- DDL exact replay_nav_history (si existe) ---")
row = cur.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='replay_nav_history'"
).fetchone()
if row:
    print(row[0])
else:
    print("  (n'existe pas)")

# Tente CREATE TABLE replay_orders en isolation
print("\n--- TEST : tentative CREATE TABLE replay_orders dans un test isolé ---")
test_sql = """
CREATE TABLE IF NOT EXISTS replay_orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES replay_runs(run_id),
    cycle_id_replay INTEGER NOT NULL REFERENCES replay_cycles(cycle_id),
    day_t           TEXT NOT NULL,
    cycle_id_prod   TEXT,
    ticker          TEXT NOT NULL,
    side            TEXT NOT NULL,
    qty             REAL NOT NULL,
    qty_target      REAL,
    qty_current     REAL,
    target_weight_pct REAL,
    status          TEXT NOT NULL,
    fill_price      REAL,
    slippage_bps    REAL,
    price_close_t   REAL,
    nav_before      REAL,
    risk_check_json TEXT,
    rejection_reason TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
)
"""
try:
    cur.execute(test_sql)
    print("  CREATE TABLE replay_orders : OK")
except Exception as e:
    print(f"  FAIL : {type(e).__name__}: {e}")

# Tente CREATE INDEX
print("\n--- TEST : CREATE INDEX idx_replay_orders_cycle ---")
try:
    cur.execute("CREATE INDEX IF NOT EXISTS idx_replay_orders_cycle ON replay_orders(cycle_id_replay)")
    print("  CREATE INDEX : OK")
except Exception as e:
    print(f"  FAIL : {type(e).__name__}: {e}")

conn.rollback()
conn.close()

print("\n--- Methodes publiques de ReplayOrchestrator ---")
from replay_orchestrator import ReplayOrchestrator
methods = [m for m in dir(ReplayOrchestrator) if not m.startswith('_')]
for m in methods:
    attr = getattr(ReplayOrchestrator, m)
    if callable(attr):
        try:
            sig = inspect.signature(attr)
            print(f"  {m}{sig}")
        except (ValueError, TypeError):
            print(f"  {m} (no signature)")
