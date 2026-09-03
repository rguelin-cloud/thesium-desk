# -*- coding: utf-8 -*-
# [DIAG_2_RENDERKPIS_AND_RISK_ENGINE]
# 1. Localise les 2 occurrences de kpiGrid.innerHTML dans app.js
# 2. Dumpe le contexte de risk_engine.py L355-380 (formule total_pnl)
# 3. Verifie si risk_engine.py ecrit dans portfolio_state

from pathlib import Path
import re

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")

# ---- 1. Les 2 renderKPIs / kpiGrid.innerHTML ----
js = read_text(BASE / "app.js")
print("=" * 70)
print("1. Les 2 occurrences kpiGrid.innerHTML dans app.js")
print("=" * 70)
positions = []
start = 0
while True:
    idx = js.find("kpiGrid.innerHTML = `", start)
    if idx == -1:
        break
    ln = js[:idx].count("\n") + 1
    positions.append((idx, ln))
    start = idx + 1
print("Total occurrences : " + str(len(positions)))
for i, (idx, ln) in enumerate(positions, 1):
    # Lit le bloc
    scan = idx + len("kpiGrid.innerHTML = `")
    j = scan
    end = -1
    while j < len(js):
        if js[j] == "`":
            k = j + 1
            while k < len(js) and js[k] in (" ", "\t"):
                k += 1
            if k < len(js) and js[k] == ";":
                end = j
                break
        j += 1
    if end > 0:
        block = js[scan:end]
        labels = re.findall(r'<div class="kpi-label">([^<]+)</div>', block)
        # Cherche la fonction englobante
        # Remonte de 200 chars pour trouver function name
        before = js[max(0, idx - 500):idx]
        func_match = re.findall(r"(?:function\s+(\w+)|(\w+)\s*[:=]\s*(?:async\s+)?function|(\w+)\s*=\s*(?:async\s+)?\(.*?\)\s*=>)", before)
        func_names = [n for tup in func_match for n in tup if n]
        likely_func = func_names[-1] if func_names else "?"
        print()
        print("--- Occurrence #" + str(i) + " a L" + str(ln) + " ---")
        print("  Fonction probable : " + likely_func)
        print("  Cards (" + str(len(labels)) + ") : " + str(labels))
        print("  Taille bloc : " + str(end - scan) + " chars")

# Maintenant : qui appelle renderKPIs ou genere kpiGrid.innerHTML ?
print()
print("--- Callers renderKPIs / kpiGrid ---")
for pat in ["renderKPIs", "renderKpis", "renderKPI"]:
    for m in re.finditer(r"\b" + pat + r"\s*\(", js):
        ln = js[:m.start()].count("\n") + 1
        # Ligne complete
        line_start = js.rfind("\n", 0, m.start()) + 1
        line_end = js.find("\n", m.end())
        print("  L" + str(ln) + ": " + js[line_start:line_end].strip()[:140])

# ---- 2. risk_engine.py L355-380 ----
print()
print("=" * 70)
print("2. risk_engine.py : contexte L355-380 (total_pnl)")
print("=" * 70)
re_path = BASE / "risk_engine.py"
if re_path.exists():
    re_lines = read_text(re_path).splitlines()
    for i in range(354, min(385, len(re_lines))):
        print("  L" + str(i+1) + ": " + re_lines[i][:140])
else:
    print("  [!] risk_engine.py introuvable")

# ---- 3. Tous les UPDATE portfolio_state ... dans risk_engine.py ----
print()
print("=" * 70)
print("3. UPDATE portfolio_state dans risk_engine.py + execution_engine.py")
print("=" * 70)
for fname in ["risk_engine.py", "execution_engine.py", "memo_generator.py", "portfolio_construction_agent.py", "broker_reconciler.py", "diff_engine.py", "convergence_engine.py"]:
    p = BASE / fname
    if not p.exists():
        continue
    t = read_text(p)
    if "portfolio_state" not in t:
        continue
    # Cherche UPDATE ou INSERT portfolio_state
    n_update = 0
    for m in re.finditer(r"(UPDATE|INSERT\s+INTO)\s+portfolio_state[^;]{0,300}", t, re.IGNORECASE | re.DOTALL):
        ln = t[:m.start()].count("\n") + 1
        n_update += 1
        snippet = m.group(0)[:200].replace("\n", " | ")
        print()
        print("  " + fname + "  L" + str(ln))
        print("    " + snippet)
    if n_update == 0:
        # Pas de UPDATE mais peut-etre une assignation total_pnl + commit
        for m in re.finditer(r"^\s*total_pnl\s*=\s*[^\n]+", t, re.MULTILINE):
            ln = t[:m.start()].count("\n") + 1
            print("  " + fname + "  L" + str(ln) + " (assign) : " + m.group(0).strip()[:120])

# ---- 4. Verifier execute_cycle / run_decision_cycle dans api_server.py ----
print()
print("=" * 70)
print("4. api_server.py : execute_cycle / run_decision_cycle context")
print("=" * 70)
api = read_text(BASE / "api_server.py")
for kw in ["def execute_cycle", "def run_decision_cycle"]:
    idx = api.find(kw)
    if idx != -1:
        ln = api[:idx].count("\n") + 1
        # Dump 30 lignes apres
        lines = api.splitlines()
        print()
        print("--- " + kw + " a L" + str(ln) + " ---")
        for j in range(ln-1, min(ln+25, len(lines))):
            print("  L" + str(j+1) + ": " + lines[j][:140])

print()
print("DONE [DIAG_2_RENDERKPIS_AND_RISK_ENGINE]")
