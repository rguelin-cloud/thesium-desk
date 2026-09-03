# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-METAAPI-PATTERN-V1]
# Extrait le pattern MetaAPI utilise dans broker-seed-universe et
# broker-shadow-executor pour reprendre exactement le meme dans le reconciler.

import os
import re
import sys

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGETS = [
    "nextones-broker-seed-universe.py",
    "nextones-broker-shadow-executor.py",
]


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


for fn in TARGETS:
    p = os.path.join(PROD_DIR, fn)
    if not os.path.exists(p):
        print(f"[SKIP] {fn} introuvable")
        continue

    banner(f"FILE : {fn}")
    with open(p, "r", encoding="utf-8-sig") as f:
        src = f.read()

    print(f"  taille : {len(src):,} chars / {src.count(chr(10))+1} lignes")

    # Imports (top 30 imports)
    print("\n  --- IMPORTS ---")
    for ln in src.split("\n")[:60]:
        if ln.startswith("import ") or ln.startswith("from "):
            print(f"    {ln}")

    # Fonctions
    defs = re.findall(r"^(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)", src, re.MULTILINE)
    print(f"\n  --- DEFS ({len(defs)}) ---")
    for name, args in defs[:30]:
        args_short = re.sub(r"\s+", " ", args)[:100]
        print(f"    {name}({args_short})")

    # Cherche les blocs autour de TOKEN / ACCOUNT_ID / connect
    print("\n  --- BLOCS METAAPI (extraits) ---")
    patterns = [
        r"METAAPI_TOKEN.*?=.*",
        r"ACCOUNT_ID.*?=.*",
        r"os\.environ\[['\"][A-Z_]*META[A-Z_]*['\"]\]",
        r"os\.getenv\(['\"][A-Z_]*META[A-Z_]*['\"]\)",
        r"os\.getenv\(['\"][A-Z_]*ACCOUNT[A-Z_]*['\"]\)",
        r"MetaApi\([^)]*\)",
        r"await\s+api\.\w+",
        r"\.metatrader_account_api\.",
        r"\.get_account\(",
        r"\.terminal_state\.",
        r"\.connect\(",
        r"positions",
    ]
    seen = set()
    for pat in patterns:
        for m in re.finditer(pat, src):
            line_no = src[:m.start()].count("\n") + 1
            line = src.split("\n")[line_no - 1].rstrip()
            key = (line_no, line)
            if key in seen:
                continue
            seen.add(key)
            print(f"    L{line_no:4} | {line[:110]}")

    # Si le mot 'positions' apparait : montre le bloc complet (function)
    if "positions" in src.lower():
        # Cherche les defs qui contiennent 'position' dans leur corps
        # On va dumper toutes les definitions qui mentionnent positions
        print("\n  --- DEFS QUI MENTIONNENT 'positions' (corps) ---")
        # Split par def
        parts = re.split(r"\n(?=def |async def )", src)
        for part in parts:
            if "position" in part.lower() and ("await" in part or "metaapi" in part.lower()
                                               or "MetaApi" in part):
                first_line = part.split("\n")[0]
                print(f"\n    >>> {first_line[:120]}")
                # Premiere 30 lignes
                for ln in part.split("\n")[:35]:
                    print(f"        {ln[:120]}")

print()
print("[DONE]")
