# -*- coding: utf-8 -*-
# Diag : run_construction_agent appelle-t-il apply_convergence_sizing en interne ?
# Et : quels print() font, comment derive-t-on 'regime' (BUILD/MAINTAIN/REBALANCE) du
# market_info renvoye par market_regime_v1 (qui retourne CALM/NORMAL/STRESS) ?
import os, re

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# A. portfolio_construction_agent.py : qui appelle apply_convergence_sizing ?
path = os.path.join(PROD_DIR, "portfolio_construction_agent.py")
with open(path, "r", encoding="utf-8-sig") as f:
    src = f.read()
lines = src.split("\n")

print("=" * 78)
print("[A] Call sites apply_convergence_sizing dans portfolio_construction_agent.py")
print("=" * 78)
for m in re.finditer(r"apply_convergence_sizing\s*\(", src):
    line_no = src[:m.start()].count("\n") + 1
    line_start = src.rfind("\n", 0, m.start()) + 1
    line_end = src.find("\n", m.end() + 100)
    snippet = src[line_start:line_end].strip()[:160]
    print(f"  L{line_no:4d}: {snippet}")

print("\n" + "=" * 78)
print("[B] Fin de run_construction_agent (L1080-1106) : return + dernieres etapes")
print("=" * 78)
for i in range(1075, min(1110, len(lines))):
    print(f"  L{i+1:4d}: {lines[i]}")

# C. Comment derive-t-on 'regime' BUILD/MAINTAIN/REBALANCE depuis market_info ?
# Probablement via une autre logique. Cherche les usages de regime_info dans le code
# (pas juste regime.get) et la signification des 3 modes.
print("\n" + "=" * 78)
print("[C] Recherche logique BUILD/MAINTAIN/REBALANCE (regime decision)")
print("=" * 78)
# Cherche 'BUILD' / 'MAINTAIN' / 'REBALANCE' dans le module + scheduler
for pat in ("BUILD", "MAINTAIN", "REBALANCE"):
    print(f"\n  Pattern {pat!r} dans portfolio_construction_agent.py :")
    cnt = 0
    for m in re.finditer(rf"\b{pat}\b", src):
        line_no = src[:m.start()].count("\n") + 1
        line_start = src.rfind("\n", 0, m.start()) + 1
        line_end = src.find("\n", m.end())
        snippet = src[line_start:line_end].strip()[:130]
        print(f"    L{line_no:4d}: {snippet}")
        cnt += 1
        if cnt >= 6:
            print(f"    ... ({cnt}+ matches)")
            break

# D. Cherche dans execution_engine.py ou scheduler.py la derivation regime
print("\n" + "=" * 78)
print("[D] Recherche 'def _decide_regime' ou 'def regime_decision' ou similar dans tout PROD")
print("=" * 78)
for fname in os.listdir(PROD_DIR):
    if not fname.endswith(".py"):
        continue
    fpath = os.path.join(PROD_DIR, fname)
    try:
        with open(fpath, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except Exception:
        continue
    for m in re.finditer(r"^def\s+(_?(?:decide_regime|regime_decision|determine_regime|build_regime|run_decision|portfolio_regime)\w*)\s*\(", text, re.MULTILINE):
        line_no = text[:m.start()].count("\n") + 1
        print(f"  {fname}:L{line_no}  def {m.group(1)}()")

# E. Recherche le call site qui passe regime_info a run_construction_agent dans la prod
print("\n" + "=" * 78)
print("[E] Call sites run_construction_agent (pour voir comment regime_info est forme)")
print("=" * 78)
for fname in os.listdir(PROD_DIR):
    if not fname.endswith(".py"):
        continue
    fpath = os.path.join(PROD_DIR, fname)
    try:
        with open(fpath, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except Exception:
        continue
    for m in re.finditer(r"run_construction_agent\s*\(", text):
        line_no = text[:m.start()].count("\n") + 1
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.end() + 400)
        snippet = text[line_start:line_end][:400]
        print(f"  {fname}:L{line_no}")
        for sl in snippet.split("\n")[:8]:
            print(f"      {sl}")
