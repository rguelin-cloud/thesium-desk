# -*- coding: utf-8 -*-
# [DIAG_TOTAL_PNL_WRITERS_DEEP]
# Trouve TOUS les sites qui ecrivent portfolio_state.total_pnl
# (UPDATE OR INSERT), avec contexte +/- 8 lignes pour voir la formule.

from pathlib import Path
import re

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

EXCLUDES = ("\\venv\\", "\\.venv\\", "\\__pycache__\\", ".bak.", "_backups", "\\backup")

def read_text(p):
    try:
        with open(p, "rb") as f:
            data = f.read()
    except Exception:
        return None
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return None

def section(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)

# ---- 1. Tous les fichiers .py qui contiennent UPDATE portfolio_state ----
section("1. Sites UPDATE portfolio_state ... total_pnl")
all_hits = []
for py in ROOT.rglob("*.py"):
    sp = str(py).lower()
    if any(x in sp for x in EXCLUDES):
        continue
    if "nextones-diag" in py.name or "nextones-fix" in py.name:
        # Skip nos propres scripts utilitaires
        continue
    t = read_text(py)
    if not t or "portfolio_state" not in t:
        continue
    # Cherche les UPDATE portfolio_state contenant total_pnl
    for m in re.finditer(r"UPDATE\s+portfolio_state[^;]{0,500}", t, re.IGNORECASE | re.DOTALL):
        block = m.group(0)
        if "total_pnl" not in block.lower():
            continue
        ln = t[:m.start()].count("\n") + 1
        all_hits.append((py.relative_to(ROOT), ln, block[:300]))

print("Total UPDATE sites : " + str(len(all_hits)))
for rel, ln, snip in all_hits:
    print()
    print("--- " + str(rel) + "  L" + str(ln) + " ---")
    print(snip[:280].replace("\n", " | "))

# ---- 2. Toutes les assignations "total_pnl = ..." dans .py ----
section("2. Assignations total_pnl = ... (formule)")
assigns = []
for py in ROOT.rglob("*.py"):
    sp = str(py).lower()
    if any(x in sp for x in EXCLUDES):
        continue
    if "nextones-diag" in py.name or "nextones-fix" in py.name:
        continue
    t = read_text(py)
    if not t:
        continue
    for m in re.finditer(r"^\s*total_pnl\s*=\s*[^\n]+", t, re.MULTILINE):
        ln = t[:m.start()].count("\n") + 1
        line = m.group(0).strip()
        assigns.append((py.relative_to(ROOT), ln, line))

print("Total assignations total_pnl = : " + str(len(assigns)))
for rel, ln, line in assigns:
    print("  " + str(rel) + "  L" + str(ln) + " : " + line[:120])

# ---- 3. Contexte autour de l'UPDATE dans api_server.py (L295-310 region) ----
section("3. api_server.py : contexte autour du UPDATE portfolio_state")
api = read_text(ROOT / "api_server.py")
if api:
    lines = api.splitlines()
    for i, l in enumerate(lines, 1):
        if "UPDATE portfolio_state" in l:
            start = max(1, i - 18)
            end = min(len(lines), i + 8)
            print()
            print("--- api_server.py L" + str(start) + "-" + str(end) + " ---")
            for j in range(start, end + 1):
                marker = " >>" if j == i else "   "
                print(marker + " L" + str(j) + ": " + lines[j-1][:140])

# ---- 4. Verifier presence du calcul unrealized_pnl autour du UPDATE ----
section("4. api_server.py : marker FIX_API_CAPITAL_FLOWS_V1 present ?")
if api:
    print("  Marker FIX_API_CAPITAL_FLOWS_V1 : " + ("OUI" if "FIX_API_CAPITAL_FLOWS_V1" in api else "NON"))
    # Compte d'occurrences
    print("  Occurrences du marker : " + str(api.count("FIX_API_CAPITAL_FLOWS_V1")))
    # Verifie que le calcul unrealized + total_return est present
    print("  'unrealized_pnl = _sum_mv - _sum_cost' present : " + ("OUI" if "_sum_mv - _sum_cost" in api else "NON"))
    print("  'compute_total_return' present : " + ("OUI" if "compute_total_return" in api else "NON"))
    print("  'get_net_capital_flows' present : " + ("OUI" if "get_net_capital_flows" in api else "NON"))

# ---- 5. Lecture actuelle DB portfolio_state ----
section("5. Etat actuel DB portfolio_state")
import sqlite3
db = ROOT / "thesium.db"
try:
    conn = sqlite3.connect(str(db), timeout=5)
    cur = conn.execute("SELECT * FROM portfolio_state WHERE id=1")
    row = cur.fetchone()
    cols = [c[1] for c in conn.execute("PRAGMA table_info(portfolio_state)").fetchall()]
    if row:
        for c, v in zip(cols, row):
            print("  " + c + " = " + str(v))
    # capital_flows
    cur = conn.execute("SELECT COUNT(*), COALESCE(SUM(CASE WHEN side='deposit' THEN amount ELSE -amount END), 0) FROM capital_flows")
    cnt, net = cur.fetchone()
    print()
    print("  capital_flows : " + str(cnt) + " rows, net = " + str(net))
    # portfolio_history dernier
    cur = conn.execute("SELECT date, total_value, total_pnl, cash FROM portfolio_history ORDER BY date DESC LIMIT 3")
    print()
    print("  portfolio_history (3 derniers) :")
    for r in cur.fetchall():
        print("    " + str(r))
    conn.close()
except Exception as e:
    print("  [!] DB error : " + str(e))

# ---- 6. Scan fonctions appelees pendant Run Decision Cycle ----
section("6. Fonctions susceptibles d'etre appelees par Run Decision Cycle")
if api:
    for kw in ["execute_cycle", "run_decision_cycle", "update_portfolio_state", "recalc_portfolio"]:
        n = api.count(kw)
        if n > 0:
            print("  '" + kw + "' : " + str(n) + " occurrences")

print()
print("DONE [DIAG_TOTAL_PNL_WRITERS_DEEP]")
