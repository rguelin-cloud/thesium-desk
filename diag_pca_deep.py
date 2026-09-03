# =====================================================================
# diag_pca_deep.py
# Inspection ciblee de :
#   - compute_realized_score (composante R)
#   - run_construction_agent (la grosse routine, L754-979)
#   - generation des orders BUY/SELL
# =====================================================================
import re
from pathlib import Path

pca_path = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py")
src = pca_path.read_text(encoding="utf-8", errors="ignore")
lines = src.splitlines()

print("=" * 80)
print("  DIAG PCA DEEP")
print("=" * 80)

# ---------------------------------------------------------------------
# 1. compute_realized_score (L272) - voir son corps + appels
# ---------------------------------------------------------------------
print()
print("[1] compute_realized_score - corps de la fonction")
print("-" * 80)
start = 272
end = start + 1
brace = 0
# Compte les lignes jusqu'au prochain "def " ou EOF
for i in range(start, min(start + 30, len(lines))):
    line = lines[i-1]
    if i > start and re.match(r"^\s*def\s+\w+", line):
        end = i - 1
        break
    end = i
for i in range(start, end + 1):
    print(f"  L{i:>4}  {lines[i-1]}")

# ---------------------------------------------------------------------
# 2. Appels a compute_realized_score
# ---------------------------------------------------------------------
print()
print("[2] Ou compute_realized_score est-il appele ?")
print("-" * 80)
calls = list(re.finditer(r"compute_realized_score\s*\(", src))
if not calls:
    print("  AUCUN APPEL trouve - la fonction est definie mais jamais utilisee.")
else:
    for m in calls:
        ln = src[:m.start()].count("\n") + 1
        line = lines[ln-1].strip()[:100]
        print(f"  L{ln:>4}  {line}")

# ---------------------------------------------------------------------
# 3. run_construction_agent (L754) - debut + lignes cles
# ---------------------------------------------------------------------
print()
print("[3] run_construction_agent - debut + signatures internes")
print("-" * 80)
start = 754
end = 979
print(f"  Fonction L{start} -> L{end} ({end-start+1} lignes)")
print()
print("  Premieres lignes :")
for i in range(start, min(start + 15, end+1)):
    print(f"  L{i:>4}  {lines[i-1]}")

# ---------------------------------------------------------------------
# 4. Cherche dans run_construction_agent : mentions positions, BTC, qty=0
# ---------------------------------------------------------------------
print()
print("[4] Recherche cles dans run_construction_agent")
print("-" * 80)
body = "\n".join(lines[start-1:end])
patterns = [
    (r"orders?\.append",          "ajout d'ordre"),
    (r"INSERT INTO orders",       "insert SQL orders"),
    (r"current_qty|cur_qty",      "quantite courante"),
    (r"qty\s*=\s*0",              "qty = 0"),
    (r"if\s+.*target",            "if sur target"),
    (r"crypto|BTC",               "mention crypto/BTC"),
    (r"compute_realized_score",   "appel realized_score"),
    (r"compute_macro_affinity",   "appel macro_affinity"),
    (r"compute_vol_penalty",      "appel vol_penalty"),
    (r"compute_diversification",  "appel diversification"),
    (r"compute_avg_conviction",   "appel avg_conviction"),
    (r"normalize_components",     "appel normalize_components"),
    (r"softmax_allocate",         "appel softmax_allocate"),
]
for p, label in patterns:
    for m in re.finditer(p, body, re.IGNORECASE):
        rel = body[:m.start()].count("\n")
        ln = start + rel
        line = lines[ln-1].strip()[:90]
        print(f"  L{ln:>4}  [{label:<25}] {line}")

# ---------------------------------------------------------------------
# 5. normalize_components (L542) - voir si R est pondere
# ---------------------------------------------------------------------
print()
print("[5] normalize_components - voir la formule de combinaison")
print("-" * 80)
start_nc = 542
for i in range(start_nc, min(start_nc + 28, len(lines))):
    line = lines[i-1]
    if i > start_nc and re.match(r"^\s*def\s+\w+", line):
        break
    print(f"  L{i:>4}  {line}")

# ---------------------------------------------------------------------
# 6. Bug BTC : voir la requete L807 sur portfolio_positions
# ---------------------------------------------------------------------
print()
print("[6] Requete L807 (portfolio_positions) - contexte +/- 12 lignes")
print("-" * 80)
for i in range(max(1, 807-3), min(len(lines), 807+15)):
    marker = " >>" if i == 807 else "   "
    print(f"  L{i:>4}{marker}  {lines[i-1]}")

print()
print("=" * 80)
print("  FIN DIAG PCA")
print("=" * 80)
