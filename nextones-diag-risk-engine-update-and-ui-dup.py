# -*- coding: utf-8 -*-
# [DIAG_RISK_ENGINE_UPDATE_AND_UI_DUP]
# 1. risk_engine.py : dump L355-450 pour trouver le UPDATE portfolio_state complet
# 2. app.js L1080-1180 : dump pour voir la 2e renderKPIs (4 cards) et son contexte
# 3. Verifie quelle fonction app.js encadre chaque renderKPIs

from pathlib import Path
import re

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")

print("=" * 70)
print("1. risk_engine.py L355-470")
print("=" * 70)
re_lines = read_text(BASE / "risk_engine.py").splitlines()
for i in range(354, min(470, len(re_lines))):
    print("  L" + str(i+1) + ": " + re_lines[i][:140])

print()
print("=" * 70)
print("2. app.js L1080-1200 (zone 2e renderKPIs)")
print("=" * 70)
js_lines = read_text(BASE / "app.js").splitlines()
for i in range(1079, min(1200, len(js_lines))):
    print("  L" + str(i+1) + ": " + js_lines[i][:160])

print()
print("=" * 70)
print("3. Fonctions englobantes des 2 renderKPIs")
print("=" * 70)
js = read_text(BASE / "app.js")
# Trouve les 2 idx
positions = []
start = 0
while True:
    idx = js.find("kpiGrid.innerHTML = `", start)
    if idx == -1:
        break
    positions.append(idx)
    start = idx + 1

for k, idx in enumerate(positions, 1):
    ln = js[:idx].count("\n") + 1
    # Remonte pour trouver "function XXX(" ou "async function XXX("
    pre = js[:idx]
    # Cherche derniere occurrence de "function " dans le pre
    matches = list(re.finditer(r"(?:async\s+)?function\s+(\w+)\s*\(", pre))
    func_name = matches[-1].group(1) if matches else "?"
    func_line = pre[:matches[-1].start()].count("\n") + 1 if matches else 0
    print()
    print("  Occurrence #" + str(k) + " a L" + str(ln))
    print("    Fonction englobante : " + func_name + " (declaree L" + str(func_line) + ")")
    # Dump 8 lignes avant
    print("    Contexte (8 lignes avant) :")
    start_l = max(0, ln - 9)
    for j in range(start_l, ln - 1):
        print("      L" + str(j+1) + ": " + js_lines[j][:140])

print()
print("DONE [DIAG_RISK_ENGINE_UPDATE_AND_UI_DUP]")
