# Comprendre pourquoi PortfolioConstructionAgent en mode MAINTAIN (budget 70%)
# distribue seulement 26% sur 10 tickers (2.5% chacun).
#
# Hypotheses :
#   A) Le softmax normalise mal -> sum != budget
#   B) Le budget est applique mais ensuite cappe par max_weight_pct
#   C) Le scoring filtre les tickers (min_score_inclusion=0.3 -> exclus)
#   D) Erreur de calcul dans la fonction softmax_allocate
#
# Verifie :
#   1. target_universe (caps par ticker)
#   2. Derniere construction snapshot : score, target avant cap, target apres cap
#   3. Code softmax / allocate_budget

import sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 80)
print("[1] target_universe : caps par ticker")
print("=" * 80)
rows = cur.execute("""SELECT ticker, asset_class, sector,
                             max_weight_pct, min_weight_pct
                      FROM target_universe ORDER BY ticker""").fetchall()
for r in rows:
    print("  " + " | ".join(f"{k}={r[k]}" for k in r.keys()))

print()
print("=" * 80)
print("[2] portfolio_targets_history : dernier snapshot complet")
print("=" * 80)
# Trouver le dernier snapshot
r = cur.execute("""SELECT snapshot_id, regime, MAX(created_at) as last
                   FROM portfolio_targets_history
                   GROUP BY snapshot_id ORDER BY last DESC LIMIT 1""").fetchone()
if r:
    sid = r["snapshot_id"]
    print(f"  Dernier snapshot : {sid} ({r['regime']}, {r['last']})")
    print()
    # Verifier les colonnes dispo
    cols = [c[1] for c in cur.execute("PRAGMA table_info(portfolio_targets_history)").fetchall()]
    print(f"  Colonnes : {cols}")
    print()
    rows = cur.execute("""SELECT * FROM portfolio_targets_history WHERE snapshot_id=?
                          ORDER BY target_weight_pct DESC""", (sid,)).fetchall()
    for r in rows:
        # Print les colonnes utiles
        d = dict(r)
        print(f"  {d.get('ticker', '?'):<8} "
              f"target={d.get('target_weight_pct', 0):>6.2f}% "
              f"prev={d.get('prev_target_weight_pct', 0):>6.2f}% "
              f"regime={d.get('regime', '?'):<10} "
              f"incl={d.get('included', '?')} "
              f"cap/floor={d.get('cap_floor_applied', '')}")
        # components_json
        comp = d.get('components_json', '')
        if comp:
            print(f"           components: {str(comp)[:180]}")

    print(f"\n  Sum target weights : {sum(r['target_weight_pct'] or 0 for r in rows):.2f}%")
    print(f"  N tickers : {len(rows)}")

print()
print("=" * 80)
print("[3] target_construction_config params_json detaille")
print("=" * 80)
import json
r = cur.execute("SELECT params_json FROM target_construction_config WHERE id=1").fetchone()
if r:
    cfg = json.loads(r["params_json"])
    for k, v in cfg.items():
        print(f"  {k:<32} = {v}")

print()
print("=" * 80)
print("[4] Code : fonction d'allocation (softmax / budget) - portfolio_construction_agent.py")
print("=" * 80)
f = ROOT / "portfolio_construction_agent.py"
txt = f.read_text(encoding="utf-8-sig", errors="replace")
lines = txt.splitlines()

# Cherche softmax_allocate ou allocate_budget ou raw_alloc
for kw in ["def softmax_allocate", "def allocate_budget", "def _allocate", "raw_alloc =",
           "softmax(", "budget =", "* budget"]:
    for i, line in enumerate(lines, 1):
        if kw in line:
            # Affiche 25 lignes apres
            print(f"\n  -- L{i} : '{kw}' --")
            for j in range(i-1, min(len(lines), i+25)):
                print(f"    L{j+1:>4}: {lines[j].rstrip()[:200]}")
            break

con.close()
print("\n[DONE]")
