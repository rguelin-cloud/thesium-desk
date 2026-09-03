"""
Diag : voir ETF_MAP dans data_crypto.py (crypto_ticker -> etf_ticker)
+ verifier si IBIT/ETHA/GSOL/GLNK ont ete tentes avant qu'on les blacklist.

Objectif : proposer une strategie
- soit tous les crypto ETFs passent en None (skip finviz)
- soit on garde uniquement les ETFs qui marchent (BITO fonctionnait avant ?)
"""
import os
import re

F = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_crypto.py"

with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
    src = fh.read()

# Trouve ETF_MAP
m = re.search(r"ETF_MAP\s*=\s*\{", src)
if not m:
    print("[NOT FOUND] ETF_MAP")
    for pat in ["etf_ticker", "etf_proxy", "crypto_etf", "IBIT", "ETHA"]:
        for mm in re.finditer(re.escape(pat), src):
            ln = src[:mm.start()].count("\n") + 1
            line_start = src.rfind("\n", 0, mm.start()) + 1
            line_end = src.find("\n", mm.end())
            print(f"  L{ln}: {src[line_start:line_end][:200]}")
        print()
else:
    start = m.start()
    ln_start = src[:start].count("\n") + 1
    # Trouve la fermeture }
    depth = 0
    end = start
    for i, ch in enumerate(src[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    print(f"[FOUND] ETF_MAP a L{ln_start}")
    print()
    print(src[start:end])

# Cherche aussi si un tel dict est defini plus haut dans le fichier
print()
print("[GLOBAL DICTS related au crypto]")
for m in re.finditer(r"^(\w+_MAP|\w+_ETF|\w+_ETFS)\s*=", src, re.MULTILINE):
    ln = src[:m.start()].count("\n") + 1
    line_end = src.find("\n", m.end())
    print(f"  L{ln}: {src[m.start():line_end][:200]}")

# Cherche les tickers pb dans le fichier
print()
print("[Where are IBIT / ETHA / GSOL / GLNK mentioned in data_crypto.py]")
for ticker in ["IBIT", "ETHA", "GSOL", "GLNK"]:
    hits = list(re.finditer(r'\b' + ticker + r'\b', src))
    print(f"  {ticker}: {len(hits)} occurrences")
    for mm in hits[:3]:
        ln = src[:mm.start()].count("\n") + 1
        line_start = src.rfind("\n", 0, mm.start()) + 1
        line_end = src.find("\n", mm.end())
        print(f"    L{ln}: {src[line_start:line_end][:180]}")

# Cherche aussi version installee de finvizfinance
print()
print("[finvizfinance version check]")
import subprocess
try:
    r = subprocess.run(
        ["py", "-3.13", "-m", "pip", "show", "finvizfinance"],
        capture_output=True, text=True, timeout=15
    )
    print(r.stdout[:600])
except Exception as e:
    print(f"  (pip check failed: {e})")
