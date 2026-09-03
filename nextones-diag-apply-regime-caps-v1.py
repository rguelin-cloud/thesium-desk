# -*- coding: utf-8 -*-
"""
Diag pour Phase 2-bis : trouver les points exacts d'application des caps
BUY/SELL dans apply_regime_to_proposals() afin d'y injecter le multiplier
marche (equity vs crypto).

On cherche :
  1. Le bloc de la fonction apply_regime_to_proposals (lignes start/end)
  2. Les constantes MAX_SELL_RATIO_BY_REGIME, MAX_OVERSHOOT_TARGET_MULT
  3. La logique BUY cap (overshoot vs target)
  4. La logique SELL cap (ratio de la position)
  5. Comment l'asset_class est determinable depuis une proposal (ticker -> instruments.asset_class)
"""
import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
EE = os.path.join(ROOT, "execution_engine.py")

with open(EE, "r", encoding="utf-8-sig") as f:
    content = f.read()
lines = content.splitlines()

print("=" * 80)
print("1. CONSTANTES DE CAPS (MAX_SELL_RATIO_BY_REGIME, MAX_OVERSHOOT_TARGET_MULT)")
print("=" * 80)
for i, line in enumerate(lines, 1):
    if any(k in line for k in ("MAX_SELL_RATIO_BY_REGIME", "MAX_OVERSHOOT_TARGET_MULT",
                                "AGENT_REGIME_WEIGHTS", "DEFAULT_AGENT_MULT")):
        print(f"  L{i:5} | {line.rstrip()[:160]}")

print()
print("=" * 80)
print("2. FONCTION apply_regime_to_proposals : bornes")
print("=" * 80)
start = None
end = None
for i, line in enumerate(lines):
    if re.match(r"\s*def\s+apply_regime_to_proposals\s*\(", line):
        start = i
        break
if start is not None:
    # Cherche la prochaine def au meme niveau d'indentation
    indent = len(lines[start]) - len(lines[start].lstrip())
    for j in range(start + 1, len(lines)):
        if re.match(r"^\s*def\s+\w+", lines[j]):
            j_indent = len(lines[j]) - len(lines[j].lstrip())
            if j_indent <= indent:
                end = j
                break
    if end is None:
        end = len(lines)
    print(f"  Fonction L{start+1} a L{end} ({end-start} lignes)")
    print()
    print(f"  Affichage L{start+1} a L{min(end, start+150)}")
    for i in range(start, min(end, start + 150)):
        marker = ""
        l = lines[i]
        if "MAX_SELL_RATIO" in l or "MAX_OVERSHOOT" in l:
            marker = "  <-- CAP"
        if "plafonn" in l.lower() or "cap_reason" in l:
            marker = "  <-- LOGIQUE CAP"
        if "asset_class" in l:
            marker = "  <-- ASSET_CLASS"
        print(f"  L{i+1:5} | {l.rstrip()[:160]}{marker}")
else:
    print("  Fonction non trouvee")

print()
print("=" * 80)
print("3. RECHERCHE asset_class dans le code")
print("=" * 80)
for i, line in enumerate(lines, 1):
    if "asset_class" in line:
        print(f"  L{i:5} | {line.rstrip()[:160]}")

print()
print("=" * 80)
print("4. RECHERCHE comment l'asset_class est lu depuis une proposal")
print("=" * 80)
# Le ticker est dans la proposal -> on peut joindre instruments
# Verifier si apply_regime_to_proposals fait deja ce join
for i, line in enumerate(lines, 1):
    if "instruments" in line.lower() and ("asset_class" in line or "ticker" in line):
        print(f"  L{i:5} | {line.rstrip()[:160]}")

print()
print("=" * 80)
print("FIN DU DIAG")
print("=" * 80)
