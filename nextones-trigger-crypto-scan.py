# -*- coding: utf-8 -*-
"""
[TRIGGER_CRYPTO_SCAN_V2]
Lance un scan REEL avec top_n=20 pour avoir crypto + ETFs.
A executer APRES avoir applique le throttle CoinGecko :
  py -3.13 .\\nextones-add-cg-throttle.py

Verifie a l'execution que le marker [CG_THROTTLE_V2] est present
dans universe_expansion_agent.py et avertit sinon.
"""
import sys
import time
import traceback
import sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"
AGENT = ROOT / "universe_expansion_agent.py"
sys.path.insert(0, str(ROOT))

# Pre-check : marker du throttle present ?
THROTTLE_MARK = "[CG_THROTTLE_V2]"
try:
    raw = AGENT.read_text(encoding="utf-8-sig", errors="replace")
    has_throttle = THROTTLE_MARK in raw
except Exception:
    has_throttle = False

print("=" * 60)
print(f"Pre-check throttle : {THROTTLE_MARK} = {'OUI' if has_throttle else 'NON'}")
if not has_throttle:
    print("[WARN] Le patch throttle n'est PAS applique. CoinGecko risque de retourner 429.")
    print("       Lance d'abord :")
    print("       py -3.13 .\\nextones-add-cg-throttle.py")
    print("       puis relance ce script.")
print("=" * 60)

import universe_expansion_agent as uea
import importlib
importlib.reload(uea)

TOP_N = 20
print()
print("=" * 60)
print(f"Scan REEL top_n={TOP_N} dry_run=False — debut {time.strftime('%H:%M:%S')}")
print("=" * 60)
t0 = time.time()
try:
    res = uea.run_scan(top_n=TOP_N, dry_run=False)
    elapsed = time.time() - t0
    print()
    print(f"Termine en {elapsed:.1f}s")
    print(f"Resultat : {res}")
except Exception as e:
    print(f"[EXC] {type(e).__name__}: {e}")
    traceback.print_exc()

print()
print("=" * 60)
print("Tous les candidats pending dans universe_candidates :")
print("=" * 60)
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.execute(
    """SELECT id, ticker, asset_class, score, sharpe_90d, momentum_12m_minus_1m,
              max_correl_existing, suggested_cap_pct, status, rationale_source, created_at
       FROM universe_candidates
       WHERE status='pending'
       ORDER BY score DESC"""
)
rows = cur.fetchall()
print(f"  {len(rows)} candidat(s) pending")
for r in rows:
    print()
    print(f"  [#{r['id']}] {r['ticker']:8s} ({r['asset_class']:7s}) score={r['score']:.3f}  "
          f"sharpe={r['sharpe_90d']:.2f}  mom12-1={r['momentum_12m_minus_1m']:.3f}  "
          f"cap={r['suggested_cap_pct']*100:.1f}%  corr_max={r['max_correl_existing']:.3f}")
con.close()

print()
print("=" * 60)
print("Si des doublons sont apparus, lance :")
print("  py -3.13 .\\nextones-dedupe-universe-candidates.py")
print("=" * 60)
