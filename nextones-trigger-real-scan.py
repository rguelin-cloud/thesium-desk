# -*- coding: utf-8 -*-
"""
[TRIGGER_REAL_SCAN_V1]
Declenche directement un scan REEL (dry_run=False) qui insere les candidats en DB.
Puis affiche le contenu de universe_candidates apres.
"""
import sys, traceback, sqlite3
from pathlib import Path
ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"
sys.path.insert(0, str(ROOT))

import universe_expansion_agent as uea

print("=" * 60)
print("Scan REEL (dry_run=False, top_n=5)")
print("=" * 60)
try:
    res = uea.run_scan(top_n=5, dry_run=False)
    print()
    print(f"Resultat : {res}")
except Exception as e:
    print(f"[EXC] {type(e).__name__}: {e}")
    traceback.print_exc()

print()
print("=" * 60)
print("Contenu universe_candidates apres scan :")
print("=" * 60)
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.execute(
    """SELECT id, ticker, asset_class, score, sharpe_90d, momentum_12m_minus_1m,
              max_correl_existing, suggested_cap_pct, status, rationale_source, created_at
       FROM universe_candidates ORDER BY id DESC LIMIT 10"""
)
rows = cur.fetchall()
print(f"  {len(rows)} ligne(s)")
for r in rows:
    print()
    print(f"  [#{r['id']}] {r['ticker']} ({r['asset_class']}) status={r['status']}")
    print(f"    score={r['score']}  sharpe90j={r['sharpe_90d']}  mom12-1={r['momentum_12m_minus_1m']}")
    print(f"    cap_pct={r['suggested_cap_pct']}  corr_max={r['max_correl_existing']}")
    print(f"    rationale_source={r['rationale_source']}  created={r['created_at']}")
con.close()
