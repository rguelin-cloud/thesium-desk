# Lit :
#   - target_construction_config (table)
#   - Le code reconciler : seuil exact de Drop "Portfolio deja a la cible"
#   - PortfolioConstructionAgent : comment il calcule les target_weight_pct

import sqlite3
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"

print("=" * 80)
print("[1] target_construction_config (table)")
print("=" * 80)
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()
rows = cur.execute("SELECT * FROM target_construction_config").fetchall()
for r in rows:
    print("  " + " | ".join(f"{k}={r[k]}" for k in r.keys()))

print()
print("=" * 80)
print("[2] risk_config (table)")
print("=" * 80)
try:
    rows = cur.execute("SELECT * FROM risk_config").fetchall()
    for r in rows:
        print("  " + " | ".join(f"{k}={r[k]}" for k in r.keys()))
except Exception as e:
    print(f"  {e}")

print()
print("=" * 80)
print("[3] Cherche le seuil 'Portfolio deja a la cible' dans le code")
print("=" * 80)
import glob
files = glob.glob(str(ROOT / "*.py"))
hit = None
for f in files:
    try:
        txt = Path(f).read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        continue
    if "Portfolio" in txt and "cible" in txt:
        for i, line in enumerate(txt.splitlines(), 1):
            if "cible" in line or "Portfolio dej" in line or "Portfolio d\u00e9j" in line:
                print(f"\n  -- {Path(f).name} L{i} --")
                # Affiche 15 lignes de contexte
                lines = txt.splitlines()
                for j in range(max(0, i-12), min(len(lines), i+3)):
                    marker = " >>" if j == i-1 else "   "
                    print(f"  {marker} L{j+1:>4}: {lines[j].rstrip()[:200]}")
                hit = f
                break
    if hit:
        break

print()
print("=" * 80)
print("[4] Cherche le calcul du target_weight_pct dans PortfolioConstructionAgent")
print("=" * 80)
for f in files:
    name = Path(f).name.lower()
    if "construction" in name or "portfolio_construction" in name:
        print(f"\n  -- {Path(f).name} --")
        txt = Path(f).read_text(encoding="utf-8-sig", errors="replace")
        # Cherche lignes avec target_weight ou MAX_WEIGHT ou cap
        for i, line in enumerate(txt.splitlines(), 1):
            s = line.strip().lower()
            if any(k in s for k in ["target_weight", "max_weight", "max_per_position",
                                     "n_positions", "max_positions", "cap",
                                     "weight_pct", "default_weight", "base_weight",
                                     "kelly"]):
                if not line.strip().startswith("#"):
                    print(f"    L{i:>4}: {line.rstrip()[:200]}")

print()
print("=" * 80)
print("[5] Sum des target_weight_pct + Sum des current weight_pct")
print("=" * 80)
r = cur.execute("SELECT SUM(target_weight_pct) as s FROM portfolio_targets WHERE active=1").fetchone()
print(f"  Sum target_weight_pct (active) : {r['s']}")
r = cur.execute("SELECT SUM(weight_pct) as s FROM portfolio_positions").fetchone()
print(f"  Sum weight_pct (positions)     : {r['s']}")
r = cur.execute("SELECT COUNT(*) as n FROM portfolio_targets WHERE active=1").fetchone()
print(f"  N targets actifs               : {r['n']}")
r = cur.execute("SELECT COUNT(*) as n FROM portfolio_positions").fetchone()
print(f"  N positions ouvertes           : {r['n']}")

con.close()
print("\n[DONE]")
