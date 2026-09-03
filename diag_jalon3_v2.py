# =====================================================================
# diag_jalon3_v2.py
# Diagnostic pre-Jalon 3 - sans i.exchange (lit le vrai schema)
# =====================================================================
import sqlite3, re
from pathlib import Path

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 70)
print("  DIAGNOSTIC JALON 3  (v2)")
print("=" * 70)

# ---------------------------------------------------------------------
# 0. Vrai schema 'instruments' (pour eviter de redeviner les colonnes)
# ---------------------------------------------------------------------
print()
print("[0] Schema 'instruments'")
print("-" * 70)
cur.execute("PRAGMA table_info(instruments)")
inst_cols = [c['name'] for c in cur.fetchall()]
print(f"  Colonnes : {inst_cols}")

# ---------------------------------------------------------------------
# 1. Couverture prix (deja vue, on confirme rapide)
# ---------------------------------------------------------------------
print()
print("[1] Recap couverture (deja connu : 44j actions / 63j crypto)")

# ---------------------------------------------------------------------
# 2. BTC en detail - select dynamique sur colonnes existantes
# ---------------------------------------------------------------------
print()
print("[2] BTC complet")
print("-" * 70)
cur.execute("SELECT * FROM instruments WHERE ticker='BTC'")
btc_inst = cur.fetchone()
if btc_inst:
    for k in btc_inst.keys():
        print(f"  {k:<20} = {btc_inst[k]}")
else:
    print("  Pas de BTC dans instruments")

print()
print("  Position BTC :")
cur.execute("""
    SELECT pp.*, pt.target_weight_pct, pt.active AS tgt_active, pt.source AS tgt_source
      FROM instruments i
 LEFT JOIN portfolio_positions pp ON pp.instrument_id=i.id
 LEFT JOIN portfolio_targets   pt ON pt.ticker=i.ticker AND pt.active=1
     WHERE i.ticker='BTC'
""")
btc_pos = cur.fetchone()
if btc_pos:
    for k in btc_pos.keys():
        print(f"    {k:<20} = {btc_pos[k]}")

print()
print("  3 derniers prix BTC :")
cur.execute("""
    SELECT date, open, high, low, close, volume
      FROM prices p JOIN instruments i ON i.id=p.instrument_id
     WHERE i.ticker='BTC' ORDER BY date DESC LIMIT 3
""")
for r in cur.fetchall():
    print(f"    {r['date']}  O={r['open']:.2f}  H={r['high']:.2f}  "
          f"L={r['low']:.2f}  C={r['close']:.2f}  V={r['volume']:.0f}")

# ---------------------------------------------------------------------
# 3. Pourquoi BTC qty=0 ? Tracer le dernier ordre BTC
# ---------------------------------------------------------------------
print()
print("[3] Ordres BTC (historique)")
print("-" * 70)
cur.execute("""
    SELECT o.id, o.side, o.quantity, o.limit_price, o.status,
           o.rejection_reason,
           datetime(o.created_at,'localtime') AS created
      FROM orders o JOIN instruments i ON i.id=o.instrument_id
     WHERE i.ticker='BTC' ORDER BY o.id DESC LIMIT 10
""")
rows = cur.fetchall()
if rows:
    for r in rows:
        reason = (r['rejection_reason'] or "")[:50]
        print(f"  #{r['id']:>4}  {r['side']:<4}  qty={r['quantity']:<10}  "
              f"px={r['limit_price'] or 0:>10.2f}  status={r['status']:<22}  "
              f"created={r['created']}  {reason}")
else:
    print("  Aucun ordre BTC jamais cree")

# ---------------------------------------------------------------------
# 4. Composante R dans portfolio_construction_agent.py
# ---------------------------------------------------------------------
print()
print("[4] Composante R dans portfolio_construction_agent.py")
print("-" * 70)
pca_path = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py")
if pca_path.exists():
    src = pca_path.read_text(encoding="utf-8", errors="ignore")
    nb_lines = src.count("\n")
    print(f"  Fichier OK ({nb_lines} lignes)")
    patterns = [r"realized.{0,20}sharpe", r"sharpe.{0,20}realized",
                r"component.{0,5}r\b", r"score_R", r"\[score_R\]"]
    found = False
    for p in patterns:
        for m in re.finditer(p, src, re.IGNORECASE):
            ln = src[:m.start()].count("\n") + 1
            line = src.splitlines()[ln-1].strip()[:80]
            print(f"  L{ln:<4} {line}")
            found = True
    if not found:
        print("  Aucune trace de composante R - a implementer")

    print()
    print("  Ponderations / pondaration trouvees :")
    for m in list(re.finditer(r"(weight_|w_|score_|component_).{0,30}=\s*[0-9.]+", src))[:15]:
        ln = src[:m.start()].count("\n") + 1
        line = src.splitlines()[ln-1].strip()[:80]
        print(f"    L{ln:<4} {line}")

# ---------------------------------------------------------------------
# 5. Dependances
# ---------------------------------------------------------------------
print()
print("[5] Dependances Python")
print("-" * 70)
for mod in ["yfinance", "pandas", "numpy"]:
    try:
        m = __import__(mod)
        print(f"  {mod:<15} OK  (version {getattr(m,'__version__','?')})")
    except ImportError:
        print(f"  {mod:<15} MANQUANT  (py -m pip install {mod})")

con.close()
print()
print("=" * 70)
print("  Diagnostic termine")
print("=" * 70)
