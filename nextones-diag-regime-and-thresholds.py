# Confirme :
#   1. Le regime actuel (BUILD / MAINTAIN / REBALANCE) du dernier snapshot
#   2. Valeur exacte de DRIFT_TOLERANCE_PCT, MIN_TRADE_WEIGHT_PCT, BUILD_TARGET_OVERRIDE_CONV, BUILD_MIN_SIZE_OVERRIDE_CONV
#   3. Que fait apply_regime_to_proposals (ceiling target x1.10 / x1.50)
#   4. NAV actuel

import sqlite3
from pathlib import Path
import re
import glob

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

print("=" * 80)
print("[1] Regime actuel (dernier snapshot)")
print("=" * 80)
DB = ROOT / "thesium.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

# regime_log
try:
    rows = cur.execute("SELECT * FROM regime_log ORDER BY rowid DESC LIMIT 5").fetchall()
    for r in rows:
        print("  " + " | ".join(f"{k}={r[k]}" for k in r.keys()))
except Exception as e:
    print(f"  {e}")

# portfolio_targets_history pour regime
print("\n  portfolio_targets_history (regime):")
try:
    rows = cur.execute("""SELECT DISTINCT regime, snapshot_id, MAX(created_at) as last
                          FROM portfolio_targets_history
                          GROUP BY snapshot_id ORDER BY last DESC LIMIT 5""").fetchall()
    for r in rows:
        print("  " + " | ".join(f"{k}={r[k]}" for k in r.keys()))
except Exception as e:
    print(f"  {e}")

# cycles_daily
print("\n  cycles_daily :")
try:
    rows = cur.execute("SELECT * FROM cycles_daily ORDER BY rowid DESC LIMIT 3").fetchall()
    for r in rows:
        print("  " + " | ".join(f"{k}={r[k]}" for k in r.keys()))
except Exception as e:
    print(f"  {e}")

print()
print("=" * 80)
print("[2] NAV / cash actuel (portfolio_state)")
print("=" * 80)
try:
    rows = cur.execute("SELECT * FROM portfolio_state ORDER BY rowid DESC LIMIT 3").fetchall()
    for r in rows:
        print("  " + " | ".join(f"{k}={r[k]}" for k in r.keys()))
except Exception as e:
    print(f"  {e}")

print()
print("=" * 80)
print("[3] Constantes execution_engine : DRIFT_TOLERANCE, MIN_TRADE, BUILD_*")
print("=" * 80)
for fname in ["execution_engine.py", "execution_engine_v6_5.py"]:
    f = ROOT / fname
    if not f.exists():
        continue
    print(f"\n  -- {fname} --")
    txt = f.read_text(encoding="utf-8-sig", errors="replace")
    for i, line in enumerate(txt.splitlines(), 1):
        if any(k in line for k in [
            "DRIFT_TOLERANCE_PCT",
            "MIN_TRADE_WEIGHT_PCT",
            "BUILD_TARGET_OVERRIDE_CONV",
            "BUILD_MIN_SIZE_OVERRIDE_CONV",
            "DRIFT_TOLERANCE =",
            "self.DRIFT",
            "self.MIN_TRADE",
            "self.BUILD",
        ]):
            # Filtre commentaires
            s = line.strip()
            if not s.startswith("#"):
                print(f"    L{i:>4}: {line.rstrip()[:200]}")

print()
print("=" * 80)
print("[4] apply_regime_to_proposals (ceiling x1.10/x1.50)")
print("=" * 80)
for fname in ["execution_engine.py", "execution_engine_v6_5.py", "portfolio_construction_agent.py", "portfolio_construction_agent_jalon2.py"]:
    f = ROOT / fname
    if not f.exists():
        continue
    txt = f.read_text(encoding="utf-8-sig", errors="replace")
    if "apply_regime_to_proposals" in txt:
        print(f"\n  -- {fname} --")
        lines = txt.splitlines()
        for i, line in enumerate(lines, 1):
            if "def apply_regime_to_proposals" in line or "ceiling" in line.lower() or "1.10" in line or "1.50" in line:
                print(f"    L{i:>4}: {line.rstrip()[:200]}")

print()
print("=" * 80)
print("[5] Comment le regime est decidé ?")
print("=" * 80)
for fname in ["portfolio_construction_agent.py", "portfolio_construction_agent_jalon2.py"]:
    f = ROOT / fname
    if not f.exists():
        continue
    txt = f.read_text(encoding="utf-8-sig", errors="replace")
    lines = txt.splitlines()
    # Cherche detection regime
    for i, line in enumerate(lines, 1):
        if re.search(r'(detect|determine|compute|infer|select).{0,20}regime', line, re.I):
            print(f"\n  -- {fname} L{i} --")
            for j in range(max(0, i-2), min(len(lines), i+30)):
                marker = " >>" if j == i-1 else "   "
                print(f"  {marker} L{j+1:>4}: {lines[j].rstrip()[:200]}")
            break
        if re.search(r'regime\s*=\s*["\']', line):
            print(f"    L{i:>4}: {line.rstrip()[:200]}")

con.close()
print("\n[DONE]")
