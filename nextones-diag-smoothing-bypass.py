"""
Diag : confirmer que smoothing_max_delta_pct=2.0 est responsable
       du clamp AAPL et SOL.

Hypothese : smoothing applique apres apply_convergence_sizing
            sans bypass forced_exit -> AAPL/SOL clampes a (prev - 2.0).

1. Lire le bloc smoothing dans jalon2 (autour de L1100-1130)
2. Lire portfolio_targets_history pour AAPL/SOL/AMZN/BTC -> valeurs J-1
3. Calculer si target_actuelle == max(0, target_prev - 2.0)
4. Verifier si forced_exit est passe au smoothing

ASCII pur.
"""
import os
import re
import sqlite3

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
JALON2 = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent_jalon2.py"

# 1. Bloc smoothing dans jalon2
print("=== Bloc smoothing dans jalon2 ===")
with open(JALON2, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()

print("Total lignes :", len(lines))

# Chercher smoothing_max_delta_pct
print("\n--- Occurrences smoothing_max_delta_pct ---")
for i, l in enumerate(lines, 1):
    if "smoothing_max_delta_pct" in l or "smoothing" in l.lower():
        print("  L{}: {}".format(i, l.rstrip()))

# Bloc autour de L1115 (UPDATE portfolio_targets)
print("\n--- L1100-1130 (UPDATE portfolio_targets) ---")
start = 1100
end = 1135
for i in range(start, min(end, len(lines)) + 1):
    print("  L{}: {}".format(i, lines[i-1].rstrip()))

# Chercher apply_convergence_sizing
print("\n--- Bloc apply_convergence_sizing ---")
for i, l in enumerate(lines, 1):
    if "def apply_convergence_sizing" in l or "apply_convergence_sizing(" in l:
        print("  L{}: {}".format(i, l.rstrip()))

# Chercher "forced_exit" dans jalon2
print("\n--- Occurrences forced_exit dans jalon2 ---")
for i, l in enumerate(lines, 1):
    if "forced_exit" in l:
        print("  L{}: {}".format(i, l.rstrip()[:120]))

# 2. portfolio_targets_history pour AAPL, SOL, AMZN, BTC, ETH, GOOGL, LINK
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("\n\n=== portfolio_targets_history (5 dernieres pour chaque ticker) ===")
for tk in ["AAPL", "SOL", "AMZN", "BTC", "ETH", "GOOGL", "LINK"]:
    print("\n--- " + tk + " ---")
    try:
        rows = cur.execute(
            "SELECT * FROM portfolio_targets_history WHERE ticker = ? "
            "ORDER BY id DESC LIMIT 5",
            (tk,)
        ).fetchall()
        if not rows:
            print("  (aucun)")
        else:
            cols = list(rows[0].keys())
            for r in rows:
                vals = []
                for c in cols:
                    if c in ("ticker",):
                        continue
                    v = r[c]
                    if isinstance(v, str) and len(v) > 30:
                        v = v[:30] + "..."
                    vals.append("{}={}".format(c, v))
                print("  " + " | ".join(vals))
    except Exception as e:
        print("  Erreur :", e)

# 3. Schema portfolio_targets_history
print("\n=== Schema portfolio_targets_history ===")
try:
    rows = cur.execute("PRAGMA table_info(portfolio_targets_history)").fetchall()
    for r in rows:
        print("  ", r["name"], r["type"])
except Exception as e:
    print("Erreur :", e)

# 4. Calcul : si previous target = X, smoothed = max(0, X - 2.0) ?
print("\n=== Calcul attendu si smoothing_max_delta_pct=2.0 ===")
# Recuperer le snapshot precedent : juste avant le dernier cycle
prev_targets = cur.execute(
    "SELECT ticker, target_weight_pct, snapshot_id, updated_at "
    "FROM portfolio_targets_history "
    "WHERE ticker IN ('AAPL','SOL','AMZN','BTC','ETH','GOOGL','LINK') "
    "ORDER BY id DESC LIMIT 50"
).fetchall()

# Pour chaque ticker, son avant-dernier (penultieme) snapshot
seen = {}
prev_by_ticker = {}
for r in prev_targets:
    tk = r["ticker"]
    seen[tk] = seen.get(tk, 0) + 1
    if seen[tk] == 2:  # avant-dernier
        prev_by_ticker[tk] = r

# Current targets
current = cur.execute(
    "SELECT ticker, target_weight_pct FROM portfolio_targets "
    "WHERE ticker IN ('AAPL','SOL','AMZN','BTC','ETH','GOOGL','LINK')"
).fetchall()
current_map = {r["ticker"]: r["target_weight_pct"] for r in current}

for tk in ["AAPL","SOL","AMZN","BTC","ETH","GOOGL","LINK"]:
    cur_v = current_map.get(tk, "?")
    prev_r = prev_by_ticker.get(tk)
    if prev_r:
        prev_v = prev_r["target_weight_pct"]
        expected_smoothed = max(0, prev_v - 2.0)
        match = "MATCH" if abs(cur_v - expected_smoothed) < 0.01 else "DIFF"
        print("  {} prev={:.3f} cur={:.3f} expected_if_smoothed=max(0,prev-2.0)={:.3f} {}".format(
            tk, prev_v, cur_v, expected_smoothed, match))
    else:
        print("  {} cur={} prev=? (pas assez d historique)".format(tk, cur_v))

con.close()
print("\n[DONE]")
