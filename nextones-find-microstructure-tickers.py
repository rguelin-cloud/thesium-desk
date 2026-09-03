# nextones-find-microstructure-tickers.py
# Localise la liste hardcodee des tickers couverts par MicrostructureAgent
# dans agents.py (et toutes les listes de tickers similaires)
# ASCII pur.

import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
AGENTS_FILE = os.path.join(ROOT, "agents.py")

if not os.path.exists(AGENTS_FILE):
    print(f"introuvable: {AGENTS_FILE}")
    raise SystemExit(1)

with open(AGENTS_FILE, "r", encoding="utf-8-sig") as f:
    content = f.read()
lines = content.splitlines()

print(f"agents.py : {len(lines)} lignes")
print()

# 1) Recherche des listes de tickers
print("=" * 70)
print("LISTES DE TICKERS hardcodees")
print("=" * 70)
patterns = [
    r"\[['\"]AAPL['\"]",
    r"\[['\"]SPY['\"]",
    r"\[['\"]QQQ['\"]",
    r"\[['\"]BTC['\"]",
    r"['\"]QQQ['\"]\s*,\s*['\"]SPY['\"]",
    r"['\"]SPY['\"]\s*,\s*['\"]QQQ['\"]",
    r"ETF_TICKERS",
    r"EQUITY_TICKERS",
    r"CRYPTO_TICKERS",
    r"TICKERS\s*=",
]
hits = []
for i, l in enumerate(lines, 1):
    for pat in patterns:
        if re.search(pat, l):
            hits.append((i, l.strip()))
            break

for ln, txt in hits[:30]:
    print(f"L{ln:>5}: {txt[:140]}")
print()

# 2) Recherche autour de "MicrostructureAgent"
print("=" * 70)
print("CONTEXTE 'MicrostructureAgent'")
print("=" * 70)
for i, l in enumerate(lines, 1):
    if "MicrostructureAgent" in l or "microstructure" in l.lower():
        # Imprime 5 lignes autour
        start = max(0, i - 3)
        end = min(len(lines), i + 5)
        print(f"--- autour L{i} ---")
        for j in range(start, end):
            print(f"L{j+1:>5}: {lines[j]}")
        print()

# 3) Recherche def ou class MicrostructureAgent
print("=" * 70)
print("Definition class/def MicrostructureAgent")
print("=" * 70)
for i, l in enumerate(lines, 1):
    if re.search(r"(class|def)\s+\w*[Mm]icro", l):
        print(f"L{i:>5}: {l}")
        # Imprime les 30 lignes suivantes pour voir la liste de tickers utilisee
        for j in range(i, min(i + 80, len(lines))):
            ll = lines[j]
            if "TICKERS" in ll or "tickers" in ll or "['" in ll or "[\"" in ll:
                print(f"L{j+1:>5}: {ll}")
        print()

# 4) Cherche les WHERE asset_class et les LISTE SELECT instruments
print("=" * 70)
print("Requetes SELECT instruments avec filtre")
print("=" * 70)
for i, l in enumerate(lines, 1):
    if "FROM instruments" in l or "from instruments" in l:
        start = max(0, i - 4)
        end = min(len(lines), i + 4)
        print(f"--- autour L{i} ---")
        for j in range(start, end):
            print(f"L{j+1:>5}: {lines[j]}")
        print()

print("Done.")
