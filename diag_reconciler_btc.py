# =====================================================================
# diag_reconciler_btc.py
# Trace POURQUOI BTC n'a jamais d'ordre BUY initial
# Cherche dans execution_engine.py la logique reconciler vs positions
# =====================================================================
import re, sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"

# ---------------------------------------------------------------------
# 1. Verifier dans DB : BTC est-il dans portfolio_targets ?
# ---------------------------------------------------------------------
print("=" * 80)
print("  DIAG RECONCILER BTC")
print("=" * 80)
print()
print("[1] BTC dans portfolio_targets")
print("-" * 80)
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()
cur.execute("""
    SELECT * FROM portfolio_targets WHERE ticker='BTC' ORDER BY id DESC LIMIT 5
""")
rows = cur.fetchall()
for r in rows:
    print("  " + "  ".join(f"{k}={r[k]}" for k in r.keys()))

# ---------------------------------------------------------------------
# 2. Latest run du PCA - BTC dans portfolio_targets_history ?
# ---------------------------------------------------------------------
print()
print("[2] BTC dans portfolio_targets_history (5 dernieres entrees)")
print("-" * 80)
try:
    cur.execute("""
        SELECT snapshot_id, ticker, target_weight_pct, score,
               datetime(created_at,'localtime') AS created
          FROM portfolio_targets_history
         WHERE ticker='BTC' ORDER BY id DESC LIMIT 5
    """)
    for r in cur.fetchall():
        print(f"  snap={r['snapshot_id']:<25} tgt={r['target_weight_pct']:>5.2f}% "
              f"score={r['score']:>6.3f if r['score'] else 0} created={r['created']}")
except Exception as e:
    print(f"  Erreur: {e}")

# ---------------------------------------------------------------------
# 3. execution_engine.py - chercher la logique de generation d'ordres
# ---------------------------------------------------------------------
print()
print("[3] execution_engine.py - logique de generation d'ordres")
print("-" * 80)
ee_path = ROOT / "execution_engine.py"
if not ee_path.exists():
    print("  Fichier introuvable, tente execution_engine_v6_5.py")
    ee_path = ROOT / "execution_engine_v6_5.py"

src = ee_path.read_text(encoding="utf-8", errors="ignore")
lines = src.splitlines()
print(f"  Fichier : {ee_path.name} ({len(lines)} lignes)")

# Cherche : where target join positions, LEFT JOIN, INNER JOIN, target_weight, current_weight
print()
print("  [3a] Requetes SQL portfolio_targets / portfolio_positions :")
for ln, line in enumerate(lines, 1):
    if re.search(r"FROM\s+portfolio_(targets|positions)", line, re.IGNORECASE):
        print(f"    L{ln:>4}  {line.strip()[:100]}")
    elif re.search(r"(LEFT|INNER)\s+JOIN\s+portfolio_", line, re.IGNORECASE):
        print(f"    L{ln:>4}  {line.strip()[:100]}")

print()
print("  [3b] Mentions BTC / crypto / qty=0 / target_weight :")
patterns = [
    (r"\bBTC\b",                "BTC"),
    (r"crypto",                 "crypto"),
    (r"qty\s*[=<>!]+\s*0",      "qty vs 0"),
    (r"quantity\s*[=<>!]+\s*0", "quantity vs 0"),
    (r"current_weight",         "current_weight"),
    (r"current_qty",            "current_qty"),
    (r"weight_pct\s*-",         "weight_pct -"),
    (r"target_weight",          "target_weight"),
    (r"INSERT INTO orders",     "INSERT orders"),
]
for p, label in patterns:
    for m in re.finditer(p, src, re.IGNORECASE):
        ln = src[:m.start()].count("\n") + 1
        line = lines[ln-1].strip()[:90]
        print(f"    L{ln:>4} [{label:<18}] {line}")

# ---------------------------------------------------------------------
# 4. Cherche la fonction principale de l'execution_engine
# ---------------------------------------------------------------------
print()
print("[4] Fonctions detectees dans execution_engine.py")
print("-" * 80)
for ln, line in enumerate(lines, 1):
    if re.match(r"^def\s+\w+", line):
        print(f"  L{ln:>4}  {line.strip()[:90]}")

con.close()
print()
print("=" * 80)
print("  FIN DIAG")
print("=" * 80)
