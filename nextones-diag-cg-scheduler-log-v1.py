"""
Diag : trouver la ligne buggy '[scheduler] CG crypto refresh error: {e}'
qui log '{e}' litteral au lieu d'interpoler la vraie exception.
"""
import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# Fichiers candidats
candidates = [
    "api_server_with_static.py",
    "scheduler.py",
    "crypto_scheduler.py",
    "data_ingestion.py",
    "data_crypto.py",
]

# Cherche aussi dans tout .py a la racine
for fn in os.listdir(ROOT):
    if fn.endswith(".py") and fn not in candidates:
        candidates.append(fn)

needle = "CG crypto refresh error"

print(f"[SEARCH] {needle!r} dans {len(candidates)} fichiers .py")
print()

hits = []
for fn in candidates:
    fp = os.path.join(ROOT, fn)
    if not os.path.exists(fp):
        continue
    try:
        with open(fp, "r", encoding="utf-8-sig", errors="replace") as fh:
            src = fh.read()
    except Exception as e:
        print(f"[SKIP] {fn}: {e}")
        continue

    for m in re.finditer(re.escape(needle), src):
        ln = src[:m.start()].count("\n") + 1
        line_start = src.rfind("\n", 0, m.start()) + 1
        line_end = src.find("\n", m.end())
        snippet = src[line_start:line_end]
        hits.append((fn, ln, snippet))

if not hits:
    print("[NOT FOUND] recherche variantes...")
    for variant in ["CG crypto refresh", "CoinGecko refresh", "cg_crypto_refresh", "cg_refresh"]:
        print(f"\n  [VARIANT] {variant!r} :")
        for fn in candidates:
            fp = os.path.join(ROOT, fn)
            if not os.path.exists(fp):
                continue
            with open(fp, "r", encoding="utf-8-sig", errors="replace") as fh:
                src = fh.read()
            for m in re.finditer(re.escape(variant), src):
                ln = src[:m.start()].count("\n") + 1
                line_start = src.rfind("\n", 0, m.start()) + 1
                line_end = src.find("\n", m.end())
                print(f"    {fn}:L{ln}: {src[line_start:line_end][:200]}")
else:
    print(f"[FOUND] {len(hits)} occurrence(s) :")
    for fn, ln, snippet in hits:
        print(f"\n  {fn}:L{ln}")
        print(f"  {snippet!r}")
        # dump 5 lignes autour
        fp = os.path.join(ROOT, fn)
        with open(fp, "r", encoding="utf-8-sig", errors="replace") as fh:
            all_lines = fh.read().splitlines()
        print(f"  [CONTEXT L{ln-5} a L{ln+5}]")
        for k in range(max(0, ln - 6), min(len(all_lines), ln + 5)):
            marker = " >>> " if k == ln - 1 else "     "
            print(f"    L{k+1:5d}{marker}{all_lines[k][:200]}")
