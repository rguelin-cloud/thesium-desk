# -*- coding: utf-8 -*-
"""
Inspecte la signature exacte du handler GET /api/orders/pending dans api_server.py
pour construire un alias correct.
"""
import re
from pathlib import Path

P = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py")
src = P.read_text(encoding="utf-8-sig", errors="replace")
lines = src.splitlines()

# Cherche le decorateur @app.get("/api/orders/pending")
pat = re.compile(r'@app\.(get|post)\(\s*["\']/api/orders/pending["\']')
hits = []
for i, ln in enumerate(lines):
    if pat.search(ln):
        hits.append(i)

print(f"Decorators trouves: {len(hits)} sur lignes {[h+1 for h in hits]}")
for h in hits:
    print("\n--- bloc autour ligne", h + 1, "---")
    start = h
    end = min(h + 25, len(lines))
    for i in range(start, end):
        print(f"{i+1:5d}: {lines[i]}")

# Cherche aussi notre marker pour voir le code injecte
print("\n=== ZONE PATCH V1 ===")
for i, ln in enumerate(lines):
    if "[ORDERS_PENDING_ENDPOINT_V1]" in ln:
        for j in range(max(0, i - 2), min(len(lines), i + 30)):
            print(f"{j+1:5d}: {lines[j]}")
        break
