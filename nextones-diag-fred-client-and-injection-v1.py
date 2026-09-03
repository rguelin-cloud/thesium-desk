# -*- coding: utf-8 -*-
"""
Diag micro :
  1. Lire data_sentiment.py et extraire signature appel FRED (URL, params, format reponse)
  2. Lire execution_engine.py autour L2064 pour point d'injection precis
  3. Lister series FRED utilisees actuellement (pour confirmer la cle marche)
"""
import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

print("=" * 80)
print("1. data_sentiment.py : extraction signature FRED")
print("=" * 80)
fp = os.path.join(ROOT, "data_sentiment.py")
if os.path.exists(fp):
    with open(fp, "r", encoding="utf-8-sig", errors="ignore") as f:
        content = f.read()
    print(f"  Taille : {len(content)} chars, {len(content.splitlines())} lignes")
    # Trouver lignes contenant FRED, requests, fred, series
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        if re.search(r"FRED|fred|series_id|api\.stlouisfed", line, re.IGNORECASE):
            print(f"  L{i:5} | {line.rstrip()[:160]}")
else:
    print(f"  ABSENT : {fp}")

print()
print("=" * 80)
print("2. data_macro.py : meme chose (peut-etre client plus complet)")
print("=" * 80)
fp = os.path.join(ROOT, "data_macro.py")
if os.path.exists(fp):
    with open(fp, "r", encoding="utf-8-sig", errors="ignore") as f:
        content = f.read()
    print(f"  Taille : {len(content)} chars, {len(content.splitlines())} lignes")
    lines = content.splitlines()
    # Print toutes les fonctions def + signature
    print("\n  Fonctions def :")
    for i, line in enumerate(lines, 1):
        m = re.match(r"\s*def\s+(\w+)\s*\(", line)
        if m:
            print(f"    L{i:5} | def {m.group(1)}(...)")
    # Lignes FRED/series
    print("\n  Lignes FRED/series :")
    for i, line in enumerate(lines, 1):
        if re.search(r"FRED|fred|series_id|api\.stlouisfed|VIX|requests\.get", line):
            print(f"    L{i:5} | {line.rstrip()[:160]}")
else:
    print(f"  ABSENT : {fp}")

print()
print("=" * 80)
print("3. execution_engine.py : bloc autour de L2064 (point d'injection)")
print("=" * 80)
fp = os.path.join(ROOT, "execution_engine.py")
if os.path.exists(fp):
    with open(fp, "r", encoding="utf-8-sig", errors="ignore") as f:
        lines = f.read().splitlines()
    start = max(0, 2064 - 30)
    end = min(len(lines), 2064 + 30)
    print(f"  Affichage L{start+1} a L{end}")
    for i in range(start, end):
        marker = "  <-- ICI" if i == 2063 else ""
        print(f"  L{i+1:5} | {lines[i].rstrip()[:150]}{marker}")
else:
    print(f"  ABSENT : {fp}")

print()
print("=" * 80)
print("4. ENV : variable FRED_API_KEY dans systeme")
print("=" * 80)
key = os.environ.get("FRED_API_KEY", "")
if key:
    print(f"  FRED_API_KEY env : {key[:4]}******  (len={len(key)})")
else:
    print(f"  FRED_API_KEY env : ABSENT (sera lue depuis data_sentiment.py)")

print()
print("=" * 80)
print("5. EXTRAIRE LA CLE FRED depuis data_sentiment.py (pour usage)")
print("=" * 80)
fp = os.path.join(ROOT, "data_sentiment.py")
if os.path.exists(fp):
    with open(fp, "r", encoding="utf-8-sig", errors="ignore") as f:
        content = f.read()
    m = re.search(r"FRED_API_KEY\s*=\s*['\"]([A-Za-z0-9]+)['\"]", content)
    if m:
        k = m.group(1)
        print(f"  Cle trouvee : {k[:4]}******  (len={len(k)})")
    else:
        print(f"  Aucune cle hardcodee trouvee")

print()
print("=" * 80)
print("FIN DU DIAG")
print("=" * 80)
