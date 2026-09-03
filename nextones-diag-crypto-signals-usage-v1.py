"""
Diag : voir qui appelle fetch_crypto_signals() et comment les signals sont utilises.
Si personne ne les consomme reellement -> option A propre (vider ETF_MAP).
Si crypto_agent en depend -> il faut une alternative avant de vider.
"""
import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

needle = "fetch_crypto_signals"

print(f"[SEARCH] {needle!r} dans tous les .py racine")
print()

hits = []
for fn in os.listdir(ROOT):
    if not fn.endswith(".py"):
        continue
    fp = os.path.join(ROOT, fn)
    try:
        with open(fp, "r", encoding="utf-8-sig", errors="replace") as fh:
            src = fh.read()
    except Exception:
        continue

    for m in re.finditer(re.escape(needle), src):
        ln = src[:m.start()].count("\n") + 1
        line_start = src.rfind("\n", 0, m.start()) + 1
        line_end = src.find("\n", m.end())
        hits.append((fn, ln, src[line_start:line_end].strip()))

if not hits:
    print("[ORPHAN] fetch_crypto_signals appele nulle part ?!")
    print()
else:
    print(f"[FOUND] {len(hits)} references :")
    for fn, ln, snippet in hits:
        tag = "[DEF]" if snippet.startswith("def ") else "[CALL]"
        print(f"  {tag} {fn}:L{ln}: {snippet[:180]}")

# Cherche aussi les usages du dict retourne (rsi, sma20, etc.)
print()
print("[STAGE 2] Est-ce que crypto_signals ou etf_proxy sont lus dans autres modules ?")
for search_term in ["crypto_signals", "etf_proxy", "'rsi'", '"rsi"']:
    print(f"\n  [{search_term!r}]")
    n_hits = 0
    for fn in os.listdir(ROOT):
        if not fn.endswith(".py"):
            continue
        if fn == "data_crypto.py":
            continue  # on skip la def elle-meme
        fp = os.path.join(ROOT, fn)
        try:
            with open(fp, "r", encoding="utf-8-sig", errors="replace") as fh:
                src = fh.read()
        except Exception:
            continue

        for m in re.finditer(re.escape(search_term), src):
            ln = src[:m.start()].count("\n") + 1
            line_start = src.rfind("\n", 0, m.start()) + 1
            line_end = src.find("\n", m.end())
            print(f"    {fn}:L{ln}: {src[line_start:line_end].strip()[:180]}")
            n_hits += 1
            if n_hits >= 5:
                break
        if n_hits >= 5:
            break

# Look at pplx_crypto_agent - le principal consommateur potentiel
print()
print("[STAGE 3] pplx_crypto_agent.py structure")
fp = os.path.join(ROOT, "pplx_crypto_agent.py")
if os.path.exists(fp):
    with open(fp, "r", encoding="utf-8-sig", errors="replace") as fh:
        src = fh.read()
    # cherche imports
    for m in re.finditer(r"^(from|import)\s+.*data_crypto.*", src, re.MULTILINE):
        ln = src[:m.start()].count("\n") + 1
        print(f"  L{ln}: {m.group(0)[:180]}")
    # cherche appels a data_crypto.*
    for m in re.finditer(r"data_crypto\.\w+", src):
        ln = src[:m.start()].count("\n") + 1
        print(f"  L{ln}: {m.group(0)}")
else:
    print("  (fichier n'existe pas)")

# Idem crypto_agent.py
print()
print("[STAGE 4] crypto_agent.py structure")
fp = os.path.join(ROOT, "crypto_agent.py")
if os.path.exists(fp):
    with open(fp, "r", encoding="utf-8-sig", errors="replace") as fh:
        src = fh.read()
    for m in re.finditer(r"^(from|import)\s+.*data_crypto.*", src, re.MULTILINE):
        ln = src[:m.start()].count("\n") + 1
        print(f"  L{ln}: {m.group(0)[:180]}")
    for m in re.finditer(r"data_crypto\.\w+", src):
        ln = src[:m.start()].count("\n") + 1
        print(f"  L{ln}: {m.group(0)}")
else:
    print("  (fichier n'existe pas)")
