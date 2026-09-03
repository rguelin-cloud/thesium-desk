# -*- coding: utf-8 -*-
# Diag : pourquoi VIX = None dans le wrapper replay 8B.1
# Inspecte market_regime_v1.py : comment _fetch_vix_from_fred est appelee
# et comment le resultat est injecte dans le dict regime retourne.

import os
import re

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(PROD_DIR, "market_regime_v1.py")

if not os.path.exists(TARGET):
    print(f"NOT FOUND: {TARGET}")
    raise SystemExit(1)

with open(TARGET, "r", encoding="utf-8-sig") as f:
    src = f.read()

print("=" * 70)
print(f"TARGET : {TARGET}  ({len(src)} chars, {src.count(chr(10))} lignes)")
print("=" * 70)

# 1. Signature de _fetch_vix_from_fred
print("\n[1] Signatures contenant 'vix' (case-insensitive):")
for m in re.finditer(r"^def\s+([A-Za-z_0-9]*[vV][iI][xX][A-Za-z_0-9]*)\s*\(([^)]*)\):", src, re.MULTILINE):
    print(f"  def {m.group(1)}({m.group(2)})")

# 2. Tous les call-sites de _fetch_vix_from_fred
print("\n[2] Call-sites de _fetch_vix_from_fred:")
for m in re.finditer(r"_fetch_vix_from_fred\s*\(([^)]*)\)", src):
    line_start = src.rfind("\n", 0, m.start()) + 1
    line_end = src.find("\n", m.end())
    line_no = src[:m.start()].count("\n") + 1
    print(f"  L{line_no}: {src[line_start:line_end].strip()}")

# 3. Toutes les occurrences "vix" (mot)
print("\n[3] Lignes contenant 'vix' (premieres 40):")
count = 0
for i, line in enumerate(src.split("\n"), start=1):
    if re.search(r"\bvix\b", line, re.IGNORECASE):
        print(f"  L{i}: {line.rstrip()}")
        count += 1
        if count >= 40:
            print("  ... (truncated)")
            break

# 4. Detect_market_regime : signature + return
print("\n[4] Fonction detect_market_regime:")
m = re.search(r"^def\s+detect_market_regime\s*\(([^)]*)\):", src, re.MULTILINE)
if m:
    line_no = src[:m.start()].count("\n") + 1
    print(f"  L{line_no}: def detect_market_regime({m.group(1)})")
    # Cherche le 'return' suivant
    body_start = m.end()
    # Cherche fin de fonction (heuristique : prochain def au meme niveau)
    next_def = re.search(r"^def\s+", src[body_start + 1:], re.MULTILINE)
    body_end = body_start + 1 + (next_def.start() if next_def else len(src))
    body = src[body_start:body_end]
    print(f"  body length: {len(body)} chars")
    # Trouve tous les 'return'
    for rm in re.finditer(r"^\s*return\s+(.+)$", body, re.MULTILINE):
        rel_line = body[:rm.start()].count("\n")
        abs_line = line_no + rel_line
        print(f"  return L{abs_line}: {rm.group(0).strip()[:120]}")

# 5. Cherche definitions de 'vix_value' (la cle du dict retourne)
print("\n[5] Affectations 'vix_value' :")
for m in re.finditer(r"['\"]vix_value['\"]\s*:\s*([^,\n}]+)", src):
    line_no = src[:m.start()].count("\n") + 1
    print(f"  L{line_no}: vix_value = {m.group(1).strip()[:100]}")

# 6. Affectations a une variable contenant 'vix'
print("\n[6] Affectations a une variable 'vix*' :")
for m in re.finditer(r"^\s*(vix[A-Za-z_0-9]*)\s*=\s*(.+)$", src, re.MULTILINE):
    line_no = src[:m.start()].count("\n") + 1
    print(f"  L{line_no}: {m.group(1)} = {m.group(2).strip()[:100]}")
