"""
Diag : confirmer le bug {{...}} dans result = ... de refresh_crypto_prices_to_db()
Dump aussi les autres {{...}} dans data_crypto.py pour voir si d'autres sont buggees.
"""
import os
import re

F = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_crypto.py"

with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
    src = fh.read()

lines = src.splitlines()

# Cherche toutes les occurrences de {{ (double accolade)
print("[SEARCH] '{{' dans data_crypto.py")
print()

for i, line in enumerate(lines):
    if "{{" in line:
        # Determine si c'est dans un docstring (heuristique : ligne dans un """...""" bloc)
        # Simple version: on affiche et on juge
        print(f"L{i+1:5d}  {line[:200]}")

# Idem '}}'
print()
print("[SEARCH] '}}' dans data_crypto.py (pour verif appariement)")
for i, line in enumerate(lines):
    if "}}" in line:
        print(f"L{i+1:5d}  {line[:200]}")

# Test runtime : essayer d'importer + appeler la fonction pour reproduire l'erreur
print()
print("[STAGE 2] Runtime import test")
import sys
sys.path.insert(0, r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
try:
    import data_crypto
    print("  [OK] import data_crypto")

    # essaie juste la ligne buggy en isolation
    try:
        test = {{"updated": [], "skipped": [], "errors": []}}
        print(f"  {{... test type: {type(test).__name__}")
    except Exception as e:
        print(f"  [CONFIRMED BUG] {type(e).__name__}: {e}")

    # essaie l'appel reel (attention : peut faire un fetch reel)
    print()
    print("  [RUNTIME] tentative appel refresh_crypto_prices_to_db() ...")
    try:
        res = data_crypto.refresh_crypto_prices_to_db()
        print(f"  [OK] result type: {type(res).__name__} = {res}")
    except Exception as e:
        print(f"  [CONFIRMED CRASH] {type(e).__name__}: {e}")
except Exception as e:
    print(f"  [ERR IMPORT] {type(e).__name__}: {e}")
