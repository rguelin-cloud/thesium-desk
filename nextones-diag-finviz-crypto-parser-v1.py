"""
Diag 1 : Trouver le code qui produit les erreurs
  [data_crypto] Finviz error for IBIT: 'NoneType' object has no attribute 'find_all'

Cherche dans data_crypto.py (et autres .py racine) la fonction qui :
- fait un requests.get sur finviz
- parse avec BeautifulSoup
- appelle .find_all() sur un resultat de .find()

Dump le code + les headers/URL utilises.
"""
import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# Chercher dans les fichiers pertinents
candidates = []
for fn in os.listdir(ROOT):
    if fn.endswith(".py") and ("crypto" in fn.lower() or "finviz" in fn.lower() or "data" in fn.lower()):
        candidates.append(fn)

# Ajouter les usual suspects
for fn in ["data_crypto.py", "data_ingestion.py", "finviz_client.py"]:
    if fn not in candidates and os.path.exists(os.path.join(ROOT, fn)):
        candidates.append(fn)

print(f"[SEARCH] {len(candidates)} fichiers candidats")
print()

# Cherche "Finviz error for"
needle = "Finviz error for"
print(f"[STAGE 1] Recherche log source: {needle!r}")
print()

hits = []
for fn in candidates:
    fp = os.path.join(ROOT, fn)
    try:
        with open(fp, "r", encoding="utf-8-sig", errors="replace") as fh:
            src = fh.read()
    except Exception as e:
        continue

    for m in re.finditer(re.escape(needle), src):
        ln = src[:m.start()].count("\n") + 1
        hits.append((fn, ln, src))

if not hits:
    print("[NOT FOUND] - cherche 'finviz.com' dans tous les .py :")
    for fn in os.listdir(ROOT):
        if not fn.endswith(".py"):
            continue
        fp = os.path.join(ROOT, fn)
        try:
            with open(fp, "r", encoding="utf-8-sig", errors="replace") as fh:
                s = fh.read()
        except Exception:
            continue
        if "finviz" in s.lower():
            n = s.lower().count("finviz")
            print(f"  {fn}: {n} occurrences de 'finviz'")
    raise SystemExit(1)

# Dump la fonction contenant le log
for fn, ln, src in hits[:3]:  # premiers 3 hits
    print(f"[HIT] {fn}:L{ln}")

    lines = src.splitlines()

    # remonte pour trouver le def enclosant
    def_line = None
    for i in range(ln - 1, -1, -1):
        m = re.match(r"^(def|async def)\s+(\w+)", lines[i])
        if m:
            def_line = i
            func_name = m.group(2)
            break

    if def_line is None:
        print("  (pas de fonction enclosante trouvee)")
        continue

    # trouve fin de la fonction (prochain def au meme niveau)
    end_line = len(lines)
    for i in range(def_line + 1, len(lines)):
        if re.match(r"^(def|async def|class)\s+", lines[i]):
            end_line = i
            break

    print(f"  fonction: {func_name} (L{def_line + 1} - L{end_line})")
    print()
    print(f"  [DUMP L{def_line + 1} a L{min(end_line, def_line + 60)}]")
    print("  " + "-" * 76)
    for i in range(def_line, min(end_line, def_line + 60)):
        marker = " >>> " if i == ln - 1 else "     "
        print(f"  L{i+1:5d}{marker}{lines[i][:200]}")
    print()

# Cherche URL et headers Finviz utilises
print()
print("[STAGE 2] URLs Finviz")
for fn in candidates:
    fp = os.path.join(ROOT, fn)
    try:
        with open(fp, "r", encoding="utf-8-sig", errors="replace") as fh:
            src = fh.read()
    except Exception:
        continue

    for m in re.finditer(r"(https?://[^\s'\"]*finviz\.com[^\s'\"]*)", src):
        ln = src[:m.start()].count("\n") + 1
        print(f"  {fn}:L{ln}: {m.group(1)}")

print()
print("[STAGE 3] User-Agent et headers")
for fn in candidates:
    fp = os.path.join(ROOT, fn)
    try:
        with open(fp, "r", encoding="utf-8-sig", errors="replace") as fh:
            src = fh.read()
    except Exception:
        continue

    for m in re.finditer(r"['\"]User-Agent['\"]", src):
        ln = src[:m.start()].count("\n") + 1
        line_start = src.rfind("\n", 0, m.start()) + 1
        line_end = src.find("\n", m.end())
        print(f"  {fn}:L{ln}: {src[line_start:line_end].strip()[:180]}")
