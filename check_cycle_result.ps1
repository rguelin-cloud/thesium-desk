# =====================================================================
# check_cycle_result.ps1
# Verifie le resultat du dernier cycle :
# 1. Les 3 ordres pending - inclut-il BTC ?
# 2. Pourquoi pas de logs [score_R] ?
# 3. Bonne table pour 'cycles' ?
# =====================================================================

$ErrorActionPreference = "Continue"
$Root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
Set-Location $Root

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  CHECK CYCLE RESULT - BTC + R + tables" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

$py = @'
import sqlite3
import json
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB   = ROOT / "thesium.db"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

# =====================================================================
# 1. Tables liees aux cycles
# =====================================================================
print("=" * 60)
print("1. Tables 'cycle' ou 'memo' ou 'reconciliation'")
print("=" * 60)
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for r in cur.fetchall():
    name = r["name"]
    if any(k in name.lower() for k in ("cycle", "memo", "reconcil", "log")):
        cur.execute(f"SELECT COUNT(*) FROM {name}")
        n = cur.fetchone()[0]
        print(f"  {name:<40} {n:>6} rows")

# =====================================================================
# 2. Ordres pending - aujourd'hui apres 09:13
# =====================================================================
print()
print("=" * 60)
print("2. Ordres pending_validation (cree apres 09:13 = nouveau cycle)")
print("=" * 60)
cur.execute("""
    SELECT o.id, i.ticker, o.side, o.quantity, o.order_type, o.status, o.created_at
    FROM orders o
    JOIN instruments i ON i.id = o.instrument_id
    WHERE o.status='pending_validation'
      AND o.created_at >= '2026-05-25 09:13:00'
    ORDER BY o.created_at DESC, o.id DESC
""")
rows = cur.fetchall()
if not rows:
    print("  (aucun ordre nouveau)")
else:
    print(f"  {'ID':<6} {'Ticker':<8} {'Side':<6} {'Qty':>14} {'Type':<8} {'Created':<20}")
    print("  " + "-" * 70)
    for r in rows:
        print(f"  {r['id']:<6} {r['ticker']:<8} {r['side']:<6} {r['quantity']:>14.6f} {r['order_type']:<8} {r['created_at']}")

print()
print("BTC pending TOUS confondus :")
cur.execute("""
    SELECT o.id, o.side, o.quantity, o.status, o.created_at
    FROM orders o JOIN instruments i ON i.id = o.instrument_id
    WHERE i.ticker='BTC' AND o.status='pending_validation'
    ORDER BY o.created_at DESC LIMIT 5
""")
btc = cur.fetchall()
if not btc:
    print("  AUCUN BTC pending - probleme dans le Reconciler")
else:
    for r in btc:
        print(f"  #{r['id']}  {r['side']}  qty={r['quantity']:.6f}  {r['status']}  {r['created_at']}")

# =====================================================================
# 3. cycle_reconciliation_log - dernier cycle
# =====================================================================
print()
print("=" * 60)
print("3. cycle_reconciliation_log - dernier cycle")
print("=" * 60)

# Nom des colonnes
cur.execute("PRAGMA table_info(cycle_reconciliation_log)")
cols = [c["name"] for c in cur.fetchall()]
print(f"  cols : {cols}")

# Trouver cycle_id le plus recent
cur.execute("SELECT DISTINCT cycle_id FROM cycle_reconciliation_log ORDER BY id DESC LIMIT 1")
last_cycle = cur.fetchone()
if last_cycle:
    cid = last_cycle["cycle_id"]
    print(f"\n  Dernier cycle_id : {cid}")
    cur.execute(f"SELECT * FROM cycle_reconciliation_log WHERE cycle_id=? ORDER BY id", (cid,))
    rec_rows = cur.fetchall()
    print(f"  {len(rec_rows)} actions dans ce cycle")
    print()
    for r in rec_rows:
        d = dict(r)
        # Format compact
        ticker = d.get("ticker", "?")
        action = d.get("action_type") or d.get("action") or "?"
        decision = d.get("decision") or "?"
        print(f"    {ticker:<8} {action:<20} decision={decision}")
        details = d.get("details") or d.get("notes")
        if details:
            print(f"      details: {details[:200]}")

# =====================================================================
# 4. Verifier params_json enable_realized actuel
# =====================================================================
print()
print("=" * 60)
print("4. target_construction_config.params_json actuel")
print("=" * 60)
cur.execute("SELECT params_json, updated_at FROM target_construction_config WHERE id=1")
r = cur.fetchone()
if r:
    params = json.loads(r["params_json"])
    print(f"  updated_at : {r['updated_at']}")
    for k in ("enable_realized", "enable_macro", "enable_diversif", "enable_vol_penalty",
              "w_conviction", "w_realized", "w_macro", "w_diversif"):
        print(f"    {k:<22} = {params.get(k)}")

# =====================================================================
# 5. portfolio_construction_agent appele dans le cycle ?
# =====================================================================
print()
print("=" * 60)
print("5. run_construction_agent dans le code")
print("=" * 60)
# Quelle fonction appelle run_construction_agent ?
for py_file in ROOT.glob("*.py"):
    try:
        txt = py_file.read_text(encoding="utf-8", errors="ignore")
        if "run_construction_agent" in txt and py_file.name != "portfolio_construction_agent.py":
            lines = txt.splitlines()
            for i, line in enumerate(lines):
                if "run_construction_agent" in line:
                    print(f"  {py_file.name}:L{i+1}  {line.strip()[:100]}")
    except:
        pass

# =====================================================================
# 6. Theses du dernier cycle - agents qui ont tourne
# =====================================================================
print()
print("=" * 60)
print("6. Theses du dernier cycle (par agent)")
print("=" * 60)
cur.execute("""
    SELECT cycle_id, agent_type, COUNT(*) as n, MAX(created_at) as last
    FROM theses
    WHERE created_at >= '2026-05-25 09:13:00'
    GROUP BY cycle_id, agent_type
    ORDER BY cycle_id DESC, agent_type
""")
for r in cur.fetchall():
    print(f"  {r['cycle_id']:<25} {r['agent_type']:<28} n={r['n']:>3}  last={r['last']}")

# =====================================================================
# 7. portfolio_targets_history - dernier snapshot
# =====================================================================
print()
print("=" * 60)
print("7. portfolio_targets_history - dernier snapshot")
print("=" * 60)
cur.execute("SELECT DISTINCT snapshot_id, created_at FROM portfolio_targets_history ORDER BY created_at DESC LIMIT 3")
for snap in cur.fetchall():
    sid = snap["snapshot_id"]
    print(f"\n  Snapshot {sid} ({snap['created_at']}) :")
    cur.execute("""
        SELECT ticker, target_weight_pct, score
        FROM portfolio_targets_history
        WHERE snapshot_id=?
        ORDER BY target_weight_pct DESC
    """, (sid,))
    for r in cur.fetchall():
        sc = f"{r['score']:.4f}" if r['score'] is not None else "NULL"
        print(f"    {r['ticker']:<8}  tgt={r['target_weight_pct']:>6.2f}%  score={sc}")

con.close()
'@

$tmp = "$env:TEMP\_check_cycle.py"
$py | Set-Content -Path $tmp -Encoding UTF8
py $tmp

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  TERMINE" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
