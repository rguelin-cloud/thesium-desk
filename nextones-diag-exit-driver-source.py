# -*- coding: utf-8 -*-
"""
Localise la f-string qui produit
'P&L X % ≤ seuil Y % → SELL 50 %'
dans execution_engine.py (et autres modules)
"""
import os, sys, io, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

candidates = [
    "execution_engine.py", "exit_agent.py", "exit_agent_v2.py",
    "agents.py", "agents_exit.py", "portfolio_construction_agent_jalon2.py",
]

# Patterns a chercher (variantes mojibake et clean)
needles = {
    "P&L": "tag P&L",
    "SELL 50": "fin SELL 50",
    "stop_loss": "STOP_LOSS",
    "STOP_LOSS": "STOP_LOSS",
    "seuil": "f-string seuil",
    "â‰¤": "mojibake ≤",
    "â†'": "mojibake →",
    "â†’": "mojibake → variante",
    "≤": "clean ≤",
    "→": "clean →",
    "<=": "ascii <=",
    "->": "ascii ->",
}

for fn in candidates:
    fp = os.path.join(BASE, fn)
    if not os.path.exists(fp):
        continue
    print(f"\n=== {fn} ===")
    # Lecture sans BOM avec preservation des octets
    with open(fp, "rb") as f:
        raw_bytes = f.read()
    try:
        src = raw_bytes.decode("utf-8-sig")
    except Exception as e:
        src = raw_bytes.decode("utf-8", errors="replace")
        print(f"  [WARN] decode utf-8-sig fail: {e}")

    lines = src.split("\n")
    # Cherche les lignes contenant 'P&L' ou 'driver' avec un % ou un f"
    for i, line in enumerate(lines, 1):
        if "driver" not in line.lower() and "P&L" not in line and "stop_loss" not in line.lower():
            continue
        # Heuristique : f-string ou .format ou concatenation
        if 'f"' in line or "f'" in line or '"P&L' in line or "'P&L" in line or ".format(" in line:
            print(f"  L{i}: {line.strip()[:180]}")

    # Recherche cible specifique : f"P&L
    for m in re.finditer(r'f["\'].{0,30}P&L.{0,200}["\']', src):
        line_num = src[:m.start()].count("\n") + 1
        # Extrait la ligne complete
        line = lines[line_num - 1]
        print(f"  >>> L{line_num} fstring P&L : {line.strip()[:200]}")

    # Search direct sur les patterns
    for pat, label in needles.items():
        cnt = src.count(pat)
        if cnt:
            for m in re.finditer(re.escape(pat), src):
                line_num = src[:m.start()].count("\n") + 1
                # Ignore les commentaires "* MAINTAIN" et docstrings au top
                if line_num < 50:
                    continue
                line = lines[line_num - 1]
                # Skip si la ligne est un commentaire seulement
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith("*") or stripped.startswith('"""'):
                    continue
                print(f"  L{line_num} [{label}] : {stripped[:180]}")
                break  # 1 echantillon par pattern par fichier

print("\n[DONE]")
