# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-METAAPI-HELPER-V1]
# Dump le corps complet de _metaapi() dans broker-shadow-executor
# + dump _entry_price() pour voir comment le prix MetaAPI est fetch.

import os
import re

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
SHADOW = os.path.join(PROD_DIR, "nextones-broker-shadow-executor.py")
SEED = os.path.join(PROD_DIR, "nextones-broker-seed-universe.py")


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


def dump_def(src, fn_name):
    """Trouve def fn_name(...) et dump jusqu'au prochain def au meme niveau."""
    m = re.search(
        r"^(?P<indent>[ \t]*)(?:async\s+)?def\s+" + re.escape(fn_name) + r"\s*\(",
        src, re.MULTILINE,
    )
    if not m:
        return None
    start = m.start()
    indent = m.group("indent")
    # Cherche le prochain def au meme niveau (ou EOF)
    rest = src[m.end():]
    pat_next = re.compile(
        r"^" + re.escape(indent) + r"(?:async\s+)?def\s+\w+\s*\(",
        re.MULTILINE,
    )
    nm = pat_next.search(rest)
    end = m.end() + nm.start() if nm else len(src)
    return src[start:end]


# ----------------------------- SHADOW EXECUTOR -----------------------------
banner("[1] Helpers MetaAPI dans broker-shadow-executor")
with open(SHADOW, "r", encoding="utf-8-sig") as f:
    src = f.read()

for fn in ["_metaapi", "_entry_price"]:
    body = dump_def(src, fn)
    print()
    print(f"  --- {fn}() ---")
    if body is None:
        print("    (introuvable)")
    else:
        for ln in body.split("\n"):
            print(f"    {ln[:200]}")


# ----------------------------- SEED UNIVERSE -----------------------------
banner("[2] enrich_specs() dans broker-seed-universe (peut-etre du fetch)")
with open(SEED, "r", encoding="utf-8-sig") as f:
    seed_src = f.read()

for fn in ["enrich_specs", "main"]:
    body = dump_def(seed_src, fn)
    print()
    print(f"  --- {fn}() ---")
    if body is None:
        print("    (introuvable)")
        continue
    # Tronque a 80 lignes max
    lines = body.split("\n")
    if len(lines) > 80:
        for ln in lines[:80]:
            print(f"    {ln[:180]}")
        print(f"    ... ({len(lines)-80} lignes restantes)")
    else:
        for ln in lines:
            print(f"    {ln[:180]}")


# ----------------------------- 3 -----------------------------
banner("[3] Recherche os.getenv / os.environ dans tous les .py NextOnes")
import re
pat = re.compile(r"os\.getenv\s*\(\s*['\"]([A-Z_]+)['\"]")
pat2 = re.compile(r"os\.environ\s*\[\s*['\"]([A-Z_]+)['\"]")
vars_seen = {}
for f in sorted(os.listdir(PROD_DIR)):
    if not f.startswith("nextones-") or not f.endswith(".py"):
        continue
    full = os.path.join(PROD_DIR, f)
    with open(full, "r", encoding="utf-8-sig", errors="ignore") as fp:
        s = fp.read()
    for m in pat.finditer(s):
        v = m.group(1)
        if "META" in v or "ACCOUNT" in v or "BROKER" in v or "TOKEN" in v or "API" in v:
            vars_seen.setdefault(v, []).append(f)
    for m in pat2.finditer(s):
        v = m.group(1)
        if "META" in v or "ACCOUNT" in v or "BROKER" in v or "TOKEN" in v or "API" in v:
            vars_seen.setdefault(v, []).append(f)

for v, files in sorted(vars_seen.items()):
    print(f"  {v} : utilise dans {len(files)} fichier(s)")
    for fl in set(files):
        print(f"    - {fl}")


# ----------------------------- 4 -----------------------------
banner("[4] Contenu .env actuel (cles seulement)")
env_p = os.path.join(PROD_DIR, ".env")
if os.path.exists(env_p):
    with open(env_p, "r", encoding="utf-8-sig", errors="ignore") as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            if "=" in ln:
                key = ln.split("=", 1)[0].strip()
                val = ln.split("=", 1)[1].strip()
                # Mask value
                shown = val[:6] + "..." + val[-4:] if len(val) > 12 else "***"
                print(f"  {key} = {shown}")
else:
    print("  (pas de .env)")

print()
print("[DONE]")
