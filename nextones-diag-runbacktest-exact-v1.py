"""
Diag : dump exact des 60 lignes de runBacktest et 40 lignes de renderBacktestResults
pour identifier les patterns reels (vs ceux supposes par le patch v1).
ASCII pur.
"""
import io, os, re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
JS = os.path.join(ROOT, "app.js")

with io.open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()
lines = src.splitlines()

print("=" * 70)
print("DIAG runBacktest + renderBacktestResults EXACT")
print("=" * 70)

# 1) Trouver runBacktest
print("\n[1] runBacktest body (60 lignes)")
for i, ln in enumerate(lines, 1):
    if "function runBacktest" in ln or "runBacktest =" in ln or "runBacktest=" in ln:
        # afficher 60 lignes a partir de la
        end = min(i + 60, len(lines))
        for j in range(i - 1, end):
            print(f"  L{j+1:5d}: {lines[j].rstrip()[:180]}")
        break

# 2) Trouver apiFetch('/api/backtest'
print("\n[2] apiFetch('/api/backtest') et environs (30 lignes)")
for i, ln in enumerate(lines, 1):
    if "/api/backtest" in ln and ("apiFetch" in ln or "fetch(" in ln):
        start = max(0, i - 3)
        end = min(i + 20, len(lines))
        for j in range(start, end):
            print(f"  L{j+1:5d}: {lines[j].rstrip()[:180]}")
        break

# 3) renderBacktestResults
print("\n[3] renderBacktestResults debut (40 lignes)")
for i, ln in enumerate(lines, 1):
    if "function renderBacktestResults" in ln:
        end = min(i + 40, len(lines))
        for j in range(i - 1, end):
            print(f"  L{j+1:5d}: {lines[j].rstrip()[:180]}")
        break

# 4) Test des regex utilisees par le patch v1 (pour comprendre l'echec)
print("\n[4] Test des regex du patch UI v1 sur l'app.js actuel")
import re
p1 = re.search(r"apiFetch\(\s*['\"]/api/backtest['\"]", src)
print(f"  regex 'apiFetch\\(\\s*[\\'\\\"]/api/backtest[\\'\\\"]': {'TROUVE @' + str(p1.start()) if p1 else 'PAS TROUVE'}")
p2 = re.search(r"async\s+function\s+runBacktest\s*\(\s*\)\s*\{", src)
print(f"  regex 'async\\s+function\\s+runBacktest\\s*\\(\\s*\\)\\s*\\{{': {'TROUVE' if p2 else 'PAS TROUVE'}")
p3 = re.search(r"function\s+renderBacktestResults\s*\(", src)
print(f"  regex 'function\\s+renderBacktestResults\\s*\\(': {'TROUVE' if p3 else 'PAS TROUVE'}")

# 5) Comment runBacktest est declaree exactement ?
print("\n[5] Lignes contenant 'runBacktest' et signature exacte :")
for i, ln in enumerate(lines, 1):
    if "runBacktest" in ln:
        print(f"  L{i:5d}: {ln.rstrip()[:180]}")

print("\nDONE")
