#!/usr/bin/env python3
# Pourquoi risk_v2 n'a pas tourne sur les ordres 135-144 ?
# 1) instruments.ticker pour ids 1-17 (NULL => skip)
# 2) full risk_check_result d'un ordre (regarde warnings + risk_v2 key)
# 3) Test import risk_pretrade isole
# 4) Test direct run_pretrade_checks("AAPL", 64, 200, "BUY") avec DB path

import sqlite3, json, traceback
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 78)
print("DIAG SILENT SKIP risk_v2 sur ordres 135-144")
print("=" * 78)

# 1) instruments.ticker mapping
print("\n[1] instruments id->ticker pour ordres 135-144")
print("-" * 78)
cur.execute("SELECT id, ticker, name, asset_class FROM instruments WHERE id BETWEEN 1 AND 20 ORDER BY id")
for r in cur.fetchall():
    print(f"  id={r['id']:>3}  ticker={r['ticker']!r:<15}  name={r['name']}  class={r['asset_class']}")

# 2) full risk_check_result pour un ordre (137 = AAPL)
print("\n[2] FULL risk_check_result pour ordre #137 (AAPL)")
print("-" * 78)
cur.execute("SELECT id, instrument_id, risk_check_result FROM orders WHERE id = 137")
r = cur.fetchone()
print(f"  Ordre #{r['id']} inst={r['instrument_id']}")
rc = r['risk_check_result']
print(f"  Length: {len(rc) if rc else 0} chars")
print(f"  Raw:")
print(rc)
print()
try:
    parsed = json.loads(rc)
    print(f"  Keys: {list(parsed.keys())}")
    print(f"  risk_v2 present? {'risk_v2' in parsed}")
    print(f"  warnings: {parsed.get('warnings')}")
except Exception as e:
    print(f"  JSON parse error: {e}")

# 3) Test import risk_pretrade
print("\n[3] Test import risk_pretrade")
print("-" * 78)
import sys
sys.path.insert(0, str(ROOT))
try:
    from risk_pretrade import run_pretrade_checks
    print("  OK import risk_pretrade.run_pretrade_checks")
    print(f"  Signature OK")
except Exception as e:
    print(f"  FAIL import: {type(e).__name__}: {e}")
    traceback.print_exc()

# 4) Test direct appel pour AAPL/64/200/BUY
print("\n[4] Test direct run_pretrade_checks('AAPL', 64, 200, 'BUY')")
print("-" * 78)
try:
    from risk_pretrade import run_pretrade_checks
    res = run_pretrade_checks("AAPL", 64, 200, "BUY", db_path=str(DB))
    print(f"  Result keys: {list(res.keys()) if isinstance(res, dict) else type(res)}")
    print(f"  Full result:")
    print(json.dumps(res, indent=2, default=str)[:2000])
except Exception as e:
    print(f"  FAIL: {type(e).__name__}: {e}")
    traceback.print_exc()

# 5) Combien d'ordres ont 'risk_v2' dans leur risk_check_result toutes dates ?
print("\n[5] Combien d'ordres ont 'risk_v2' dans risk_check_result")
print("-" * 78)
cur.execute("SELECT COUNT(*) AS n FROM orders WHERE risk_check_result LIKE '%risk_v2%'")
print(f"  Total ordres avec risk_v2 inclus: {cur.fetchone()['n']}")
cur.execute("SELECT COUNT(*) AS n FROM orders WHERE risk_check_result LIKE '%[RISK_V2]%' OR risk_check_result LIKE '%RISK_V2%'")
print(f"  Total avec marker [RISK_V2]: {cur.fetchone()['n']}")

# 6) status REAL des ordres 135-144 (filled?) - confirme
print("\n[6] Status ordres 135-144")
print("-" * 78)
cur.execute("SELECT id, status, validated_at, validated_by FROM orders WHERE id BETWEEN 135 AND 144")
for r in cur.fetchall():
    print(f"  #{r['id']}  status={r['status']}  validated_at={r['validated_at']}  by={r['validated_by']}")

conn.close()
print("\n" + "=" * 78)
