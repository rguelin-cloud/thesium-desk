# -*- coding: utf-8 -*-
"""Diag : extrait la signature exacte de pplx_query et montre un exemple d'usage."""
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parent

import pplx_client
print("=== Module pplx_client ===")
print(f"  Fichier : {pplx_client.__file__}")
print()

# Liste des fonctions publiques
for name in dir(pplx_client):
    if name.startswith("_"):
        continue
    obj = getattr(pplx_client, name)
    if callable(obj):
        try:
            sig = inspect.signature(obj)
            print(f"  {name}{sig}")
        except (ValueError, TypeError):
            print(f"  {name} (signature inconnue)")

print()
print("=== Source de pplx_query ===")
try:
    src = inspect.getsource(pplx_client.pplx_query)
    print(src)
except Exception as e:
    print(f"  ERREUR: {e}")

# Cherche un exemple d'usage dans les autres agents
print("\n=== Exemples d'usage dans les autres agents ===")
for f in ROOT.glob("pplx_*_agent.py"):
    if f.name == "pplx_memo_agent.py":
        continue
    try:
        text = f.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    # Cherche les appels a pplx_query
    import re
    matches = list(re.finditer(r"pplx_query\s*\([^)]*\)", text, re.DOTALL))
    if matches:
        print(f"\n--- {f.name} ---")
        for m in matches[:2]:
            snippet = m.group(0)
            print(f"  {snippet[:400]}")
