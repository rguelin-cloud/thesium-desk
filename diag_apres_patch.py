# =====================================================================
# diag_apres_patch.py
# Verifie en 1 passe :
#  - patch crypto (execution_engine L1441)
#  - patch UTF-8 (api_server_with_static)
#  - patch realized_score (PCA L272)
#  - BTC dans portfolio_targets ET portfolio_targets_history
#  - Pourquoi BTC absent du cycle 10:50
# =====================================================================
import sqlite3, re
from pathlib import Path
import urllib.request

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

print("=" * 80)
print("  DIAG APRES PATCHS - BTC + UTF-8")
print("=" * 80)

# ---------------------------------------------------------------------
# 1. Patch crypto applique ?
# ---------------------------------------------------------------------
print()
print("[1] execution_engine.py - patch crypto")
print("-" * 80)
ee = (ROOT / "execution_engine.py").read_text(encoding="utf-8", errors="ignore")
if "# Jalon 3 - qty fractionnaire crypto" in ee:
    print("  PATCH PRESENT")
    # Affiche le bloc patche
    lines = ee.splitlines()
    for i, ln in enumerate(lines, 1):
        if "Jalon 3 - qty fractionnaire" in ln:
            for j in range(max(0,i-3), min(len(lines), i+18)):
                print(f"    L{j+1}  {lines[j]}")
            break
else:
    print("  PATCH ABSENT - le ps1 n'a pas applique le replace")
    # Affiche la zone L1441-1455 pour voir l'etat actuel
    lines = ee.splitlines()
    for i in range(1438, 1460):
        if i < len(lines):
            print(f"    L{i+1}  {lines[i]}")

# ---------------------------------------------------------------------
# 2. Patch UTF-8 applique ?
# ---------------------------------------------------------------------
print()
print("[2] api_server_with_static.py - patch UTF-8")
print("-" * 80)
api = (ROOT / "api_server_with_static.py").read_text(encoding="utf-8", errors="ignore")
if "class UTF8StaticFiles" in api:
    print("  PATCH PRESENT dans le fichier")
    # Trouve la ligne mount
    for ln, line in enumerate(api.splitlines(), 1):
        if "app.mount" in line and "Static" in line:
            print(f"    L{ln}  {line.strip()[:120]}")
else:
    print("  PATCH ABSENT")

# ---------------------------------------------------------------------
# 3. Test HTTP : verifie Content-Type retourne par le serveur
# ---------------------------------------------------------------------
print()
print("[3] Test HTTP Content-Type sur /index.html ou /")
print("-" * 80)
for url in ["http://127.0.0.1:8000/", "http://127.0.0.1:8000/index.html"]:
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=3) as resp:
            ct = resp.headers.get("Content-Type", "?")
            print(f"  {url}  ->  Content-Type: {ct}")
            if "charset=utf-8" in ct.lower():
                print(f"    OK - charset=utf-8 present")
            else:
                print(f"    KO - charset manquant (UTF-8 pas force)")
    except Exception as e:
        print(f"  {url}  ->  erreur: {e}")

# ---------------------------------------------------------------------
# 4. Patch realized_score applique ?
# ---------------------------------------------------------------------
print()
print("[4] portfolio_construction_agent.py - patch realized R")
print("-" * 80)
pca = (ROOT / "portfolio_construction_agent.py").read_text(encoding="utf-8", errors="ignore")
if "# Jalon 3 - Sharpe annualise" in pca:
    print("  PATCH PRESENT")
elif "Stub Jalon 3" in pca:
    print("  STUB ENCORE LA - patch realized_score pas applique")
else:
    print("  Etat indetermine - inspect manuel L272")

# ---------------------------------------------------------------------
# 5. DB : enable_realized
# ---------------------------------------------------------------------
print()
print("[5] DB target_construction_config")
print("-" * 80)
con = sqlite3.connect(ROOT / "thesium.db")
con.row_factory = sqlite3.Row
cur = con.cursor()
try:
    cur.execute("SELECT * FROM target_construction_config WHERE id=1")
    cfg = cur.fetchone()
    if cfg:
        for k in cfg.keys():
            if "enable" in k.lower() or k in ("id",):
                print(f"  {k:<25} = {cfg[k]}")
except Exception as e:
    print(f"  Erreur : {e}")

# ---------------------------------------------------------------------
# 6. BTC : portfolio_targets vs portfolio_targets_history
# ---------------------------------------------------------------------
print()
print("[6] BTC dans portfolio_targets (actif) ET history (dernier snap)")
print("-" * 80)
cur.execute("SELECT ticker, target_weight_pct, active, score, snapshot_id, updated_at FROM portfolio_targets WHERE ticker='BTC'")
r = cur.fetchone()
if r:
    print(f"  portfolio_targets : tgt={r['target_weight_pct']}%  active={r['active']}  "
          f"score={r['score']}  snap={r['snapshot_id']}  updated={r['updated_at']}")
else:
    print("  ABSENT de portfolio_targets")

try:
    cur.execute("""
        SELECT snapshot_id, ticker, target_weight_pct, score, datetime(created_at,'localtime') AS created
          FROM portfolio_targets_history
         ORDER BY id DESC LIMIT 30
    """)
    history = cur.fetchall()
    print()
    print(f"  Last 30 entries portfolio_targets_history :")
    snaps = {}
    for h in history:
        snaps.setdefault(h["snapshot_id"], []).append(h)
    for snap, items in list(snaps.items())[:3]:
        print(f"  Snapshot {snap} ({items[0]['created']}) :")
        tickers = [it["ticker"] for it in items]
        print(f"    Tickers ({len(tickers)}) : {tickers}")
        btc_here = any(it["ticker"] == "BTC" for it in items)
        print(f"    BTC present : {btc_here}")
except Exception as e:
    print(f"  Erreur history : {e}")

# ---------------------------------------------------------------------
# 7. Dernier cycle - actions de reconciliation
# ---------------------------------------------------------------------
print()
print("[7] Dernier cycle reconciliation (BTC mentionne ?)")
print("-" * 80)
cur.execute("""
    SELECT cycle_id, COUNT(*) AS n, MAX(datetime(created_at,'localtime')) AS last
      FROM cycle_reconciliation_log
     GROUP BY cycle_id ORDER BY MAX(id) DESC LIMIT 3
""")
for cyc in cur.fetchall():
    print(f"  Cycle {cyc['cycle_id']} : {cyc['n']} actions, last={cyc['last']}")
    cur.execute("""
        SELECT ticker, action, reason FROM cycle_reconciliation_log
         WHERE cycle_id=? ORDER BY id
    """, (cyc["cycle_id"],))
    for r in cur.fetchall():
        if r["ticker"] == "BTC":
            print(f"     BTC -> {r['action']:<12} {r['reason'][:80]}")
    # Check si BTC absent
    cur.execute("SELECT COUNT(*) AS n FROM cycle_reconciliation_log WHERE cycle_id=? AND ticker='BTC'", (cyc["cycle_id"],))
    n_btc = cur.fetchone()["n"]
    if n_btc == 0:
        print(f"     BTC ABSENT de ce cycle")

con.close()

print()
print("=" * 80)
print("  FIN DIAG")
print("=" * 80)
