"""
Diag : pourquoi AAPL et SOL ont target_weight_pct != 0 alors que
       convergence_snapshots dit forced_exit=1 ?

5 autres forced_exit (AMZN, BTC, ETH, GOOGL, LINK) sont bien a 0.
=> filtre forced_exit applique de facon selective. Pourquoi ?

Pistes :
  1. sizing_multiplier NULL pour AAPL/SOL dans le dernier snapshot ?
  2. AAPL/SOL non-presents dans le mult_map au moment du calcul ?
  3. Ordre des etapes : apply_convergence_sizing applique APRES un re-add ?

ASCII pur.
"""
import sqlite3

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

# 1. Dernier cycle_id convergence
last_cid = cur.execute(
    "SELECT cycle_id FROM convergence_snapshots "
    "ORDER BY rowid DESC LIMIT 1"
).fetchone()
if last_cid:
    cid = last_cid["cycle_id"]
else:
    cid = None
print("Dernier cycle_id convergence :", cid)

# 2. Snapshot complet AAPL + SOL + comparaison ETH/BTC (qui marchent)
print("\n=== convergence_snapshots : AAPL, SOL, ETH, BTC, AMZN, GOOGL, LINK ===")
rows = cur.execute(
    "SELECT ticker, sizing_multiplier, direction_consensus, "
    "       forced_exit, drift, convergence_pct, n_aligned, n_present, "
    "       is_crypto, created_at "
    "FROM convergence_snapshots "
    "WHERE cycle_id = ? "
    "  AND ticker IN ('AAPL','SOL','ETH','BTC','AMZN','GOOGL','LINK','HYPE','ZEC') "
    "ORDER BY ticker",
    (cid,)
).fetchall()

print("ticker | sizing_mult | dir_cons | forced | drift | conv% | n_a/n_p | crypto")
print("-" * 80)
for r in rows:
    print("{:6} | {:11} | {:8} | {:6} | {:5} | {:5} | {}/{} | {}".format(
        r["ticker"],
        str(r["sizing_multiplier"]),
        r["direction_consensus"] or "",
        r["forced_exit"],
        r["drift"],
        r["convergence_pct"],
        r["n_aligned"],
        r["n_present"],
        r["is_crypto"],
    ))

# 3. portfolio_targets pour AAPL + SOL
print("\n=== portfolio_targets : AAPL, SOL ===")
rows = cur.execute(
    "SELECT ticker, target_weight_pct, updated_at, "
    "       conviction_score, macro_factor, vol_factor "
    "FROM portfolio_targets "
    "WHERE ticker IN ('AAPL','SOL','ETH','BTC','AMZN','GOOGL','LINK') "
    "ORDER BY ticker"
).fetchall()
for r in rows:
    cols = list(r.keys())
    print("  " + r["ticker"] + " :")
    for c in cols[1:]:
        print("    {} = {}".format(c, r[c]))

# 4. Y a-t-il des doublons de ticker dans convergence_snapshots ?
print("\n=== Doublons AAPL/SOL dans convergence_snapshots du cycle ===")
dup = cur.execute(
    "SELECT ticker, COUNT(*) AS n FROM convergence_snapshots "
    "WHERE cycle_id = ? GROUP BY ticker HAVING n > 1",
    (cid,)
).fetchall()
if dup:
    for r in dup:
        print("  DOUBLON :", r["ticker"], "x", r["n"])
else:
    print("  Pas de doublon dans ce cycle.")

# 5. Tous les forced_exit du dernier cycle
print("\n=== Tous les forced_exit du dernier cycle ===")
rows = cur.execute(
    "SELECT ticker, sizing_multiplier, direction_consensus, forced_exit "
    "FROM convergence_snapshots "
    "WHERE cycle_id = ? AND forced_exit = 1 "
    "ORDER BY ticker",
    (cid,)
).fetchall()
for r in rows:
    print("  {} mult={} dir={}".format(
        r["ticker"], r["sizing_multiplier"], r["direction_consensus"]))

# 6. Verifier targets pour ces forced_exit
print("\n=== Cross-check target_weight_pct vs forced_exit ===")
forced_tickers = [r["ticker"] for r in rows]
if forced_tickers:
    placeholders = ",".join("?" * len(forced_tickers))
    targets = cur.execute(
        "SELECT ticker, target_weight_pct FROM portfolio_targets "
        "WHERE ticker IN (" + placeholders + ")",
        forced_tickers
    ).fetchall()
    tmap = {t["ticker"]: t["target_weight_pct"] for t in targets}
    for tk in forced_tickers:
        v = tmap.get(tk, "<absent>")
        status = "[OK] zero" if v == 0 else "[FAIL] not zero"
        print("  {} target={} {}".format(tk, v, status))

# 7. Voir le mult de cycle precedent (sans regime)
print("\n=== AAPL/SOL sur les 3 derniers cycles ===")
rows = cur.execute(
    "SELECT cycle_id, ticker, sizing_multiplier, forced_exit, created_at "
    "FROM convergence_snapshots "
    "WHERE ticker IN ('AAPL','SOL') "
    "ORDER BY rowid DESC LIMIT 10"
).fetchall()
for r in rows:
    print("  {} | {} | mult={} | forced={} | {}".format(
        r["cycle_id"][:25], r["ticker"], r["sizing_multiplier"],
        r["forced_exit"], r["created_at"]))

con.close()
print("\n[DONE]")
