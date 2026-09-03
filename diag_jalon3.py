# =====================================================================
# diag_jalon3.py
# Diagnostic pre-Jalon 3 : prix, BTC, composante R
# =====================================================================
import sqlite3
from pathlib import Path

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 70)
print("  DIAGNOSTIC JALON 3")
print("=" * 70)

# ---------------------------------------------------------------------
# 1. Schema prices
# ---------------------------------------------------------------------
print()
print("[1] Schema table 'prices'")
print("-" * 70)
cur.execute("PRAGMA table_info(prices)")
for c in cur.fetchall():
    print(f"  {c['name']:<20}  {c['type']:<15}  nullable={not c['notnull']}")

# ---------------------------------------------------------------------
# 2. Couverture historique des prix par instrument
# ---------------------------------------------------------------------
print()
print("[2] Couverture prix par instrument (jours dispo, plage de dates)")
print("-" * 70)
cur.execute("""
    SELECT i.ticker,
           COUNT(p.date) AS nb_days,
           MIN(p.date)   AS first_date,
           MAX(p.date)   AS last_date
      FROM instruments i
 LEFT JOIN prices p ON p.instrument_id = i.id
     GROUP BY i.id
     ORDER BY i.ticker
""")
print(f"  {'Ticker':<8} {'Jours':>6}  {'First':<12}  {'Last':<12}")
for r in cur.fetchall():
    print(f"  {r['ticker']:<8} {r['nb_days'] or 0:>6}  "
          f"{r['first_date'] or '-':<12}  {r['last_date'] or '-':<12}")

# ---------------------------------------------------------------------
# 3. Etat BTC en detail
# ---------------------------------------------------------------------
print()
print("[3] BTC en detail")
print("-" * 70)
cur.execute("""
    SELECT i.id, i.ticker, i.name, i.asset_class, i.exchange,
           pp.quantity, pp.current_price, pp.weight_pct,
           pt.target_weight_pct AS tgt
      FROM instruments i
 LEFT JOIN portfolio_positions pp ON pp.instrument_id = i.id
 LEFT JOIN portfolio_targets pt   ON pt.ticker = i.ticker AND pt.active=1
     WHERE i.ticker = 'BTC'
""")
btc = cur.fetchone()
if btc:
    for k in btc.keys():
        print(f"  {k:<20} = {btc[k]}")
else:
    print("  Pas de BTC dans instruments")

print()
cur.execute("""
    SELECT date, close FROM prices p
      JOIN instruments i ON i.id=p.instrument_id
     WHERE i.ticker='BTC' ORDER BY date DESC LIMIT 5
""")
print("  5 derniers prix BTC :")
for r in cur.fetchall():
    print(f"    {r['date']}  close={r['close']}")

# ---------------------------------------------------------------------
# 4. Chercher composante R dans le code
# ---------------------------------------------------------------------
print()
print("[4] Composante R - recherche dans portfolio_construction_agent.py")
print("-" * 70)
import re
pca_path = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py")
if pca_path.exists():
    src = pca_path.read_text(encoding="utf-8", errors="ignore")
    nb_lines = src.count("\n")
    print(f"  Fichier OK ({nb_lines} lignes)")
    # Cherche mentions de R, sharpe, realized, returns
    patterns = [
        r"realized.{0,20}sharpe",
        r"sharpe.{0,20}realized",
        r"component.{0,5}r\b",
        r"score_R",
        r"\[score_R\]",
        r"weights?\s*=\s*\{[^}]*['\"]R['\"]",
    ]
    found_any = False
    for p in patterns:
        for m in re.finditer(p, src, re.IGNORECASE):
            line_no = src[:m.start()].count("\n") + 1
            snippet = src.splitlines()[line_no-1].strip()[:80]
            print(f"  L{line_no:<4} [{p[:30]}]  {snippet}")
            found_any = True
    if not found_any:
        print("  Aucune trace de composante R (a implementer)")

    # Cherche les ponderations de score actuelles
    print()
    print("  Ponderations score actuelles :")
    for m in re.finditer(r"(weight_|w_|score_).{0,20}=\s*[0-9.]+", src):
        line_no = src[:m.start()].count("\n") + 1
        snippet = src.splitlines()[line_no-1].strip()[:80]
        print(f"    L{line_no:<4} {snippet}")
else:
    print(f"  KO : {pca_path} introuvable")

# ---------------------------------------------------------------------
# 5. yfinance dispo ?
# ---------------------------------------------------------------------
print()
print("[5] Dependances Python")
print("-" * 70)
for mod in ["yfinance", "pandas", "numpy"]:
    try:
        __import__(mod)
        print(f"  {mod:<15} OK")
    except ImportError:
        print(f"  {mod:<15} MANQUANT (pip install {mod})")

con.close()
print()
print("=" * 70)
print("  Diagnostic termine")
print("=" * 70)
