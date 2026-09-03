# -*- coding: utf-8 -*-
# Diag jalon 8B.2 : inspecter convergence_engine + portfolio_construction_agent
# Buts :
#   1. Lister toutes les tables lues (SELECT FROM xxx) par conn
#   2. Lister toutes les tables ecrites (INSERT/UPDATE/DELETE)
#   3. Reperer les appels datetime.now/utcnow/today (a monkey-patcher si replay)
#   4. Reperer les imports de modules externes (PPLX agents, FRED, etc.)
#   5. Signatures publiques (functions exposees)

import os
import re
import sys

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

TARGETS = [
    "convergence_engine.py",
    "portfolio_construction_agent.py",
]


def analyze(path):
    print("=" * 78)
    print(f"FILE : {path}")
    print("=" * 78)
    if not os.path.exists(path):
        print("  NOT FOUND")
        return
    with open(path, "r", encoding="utf-8-sig") as f:
        src = f.read()
    lines = src.split("\n")
    print(f"  {len(src)} chars, {len(lines)} lignes\n")

    # 1. Tables lues (FROM xxx, JOIN xxx)
    print("  [1] Tables lues (FROM/JOIN) :")
    tables_read = set()
    for m in re.finditer(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z_0-9]*)", src, re.IGNORECASE):
        tables_read.add(m.group(1).lower())
    for t in sorted(tables_read):
        print(f"    - {t}")

    # 2. Tables ecrites (INSERT INTO xxx, UPDATE xxx, DELETE FROM xxx)
    print("\n  [2] Tables ecrites (INSERT/UPDATE/DELETE) :")
    tables_write = set()
    for m in re.finditer(r"\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+([a-zA-Z_][a-zA-Z_0-9]*)", src, re.IGNORECASE):
        tables_write.add(("INSERT", m.group(1).lower()))
    for m in re.finditer(r"\bUPDATE\s+([a-zA-Z_][a-zA-Z_0-9]*)", src, re.IGNORECASE):
        tables_write.add(("UPDATE", m.group(1).lower()))
    for m in re.finditer(r"\bDELETE\s+FROM\s+([a-zA-Z_][a-zA-Z_0-9]*)", src, re.IGNORECASE):
        tables_write.add(("DELETE", m.group(1).lower()))
    for op, t in sorted(tables_write):
        print(f"    - {op:6s} {t}")

    # 3. CREATE TABLE statements (schemas inline)
    print("\n  [3] CREATE TABLE statements :")
    for m in re.finditer(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][a-zA-Z_0-9]*)", src, re.IGNORECASE):
        line_no = src[:m.start()].count("\n") + 1
        print(f"    L{line_no:4d}: CREATE TABLE {m.group(1)}")

    # 4. datetime.now / utcnow / today / time.time()
    print("\n  [4] Appels temporels (now/utcnow/today/time()) :")
    for m in re.finditer(r"\b(datetime\.(?:datetime\.)?(?:now|utcnow|today)\s*\(|date\.today\s*\(|time\.time\s*\()", src):
        line_no = src[:m.start()].count("\n") + 1
        line_start = src.rfind("\n", 0, m.start()) + 1
        line_end = src.find("\n", m.end())
        snippet = src[line_start:line_end].strip()[:120]
        print(f"    L{line_no:4d}: {snippet}")

    # 5. Imports
    print("\n  [5] Imports :")
    for m in re.finditer(r"^(?:from\s+([\w.]+)\s+)?import\s+(.+)$", src, re.MULTILINE):
        line_no = src[:m.start()].count("\n") + 1
        mod = m.group(1) or ""
        imp = m.group(2).strip()
        # Filtre stdlib courant
        if mod.startswith(("os", "sys", "json", "datetime", "typing", "sqlite3", "math",
                            "logging", "re", "collections", "dataclasses", "enum", "time")):
            continue
        print(f"    L{line_no:4d}: from {mod} import {imp}" if mod else f"    L{line_no:4d}: import {imp}")

    # 6. Signatures publiques (def sans _)
    print("\n  [6] Fonctions publiques (def sans _) :")
    pub = []
    for m in re.finditer(r"^def\s+([a-zA-Z][a-zA-Z_0-9]*)\s*\(([^)]*)\):", src, re.MULTILINE):
        line_no = src[:m.start()].count("\n") + 1
        pub.append((line_no, m.group(1), m.group(2)))
    for ln, name, args in pub:
        print(f"    L{ln:4d}: def {name}({args[:80]})")

    # 7. sqlite3.connect (combien d'opens directs)
    print("\n  [7] sqlite3.connect calls (open directs) :")
    cnt = 0
    for m in re.finditer(r"sqlite3\.connect\s*\(", src):
        line_no = src[:m.start()].count("\n") + 1
        line_start = src.rfind("\n", 0, m.start()) + 1
        line_end = src.find("\n", m.end() + 80)
        snippet = src[line_start:line_end].strip()[:140]
        print(f"    L{line_no:4d}: {snippet}")
        cnt += 1
    if cnt == 0:
        print("    (aucun - conn passee en argument, parfait pour replay)")

    print()


for fname in TARGETS:
    analyze(os.path.join(PROD_DIR, fname))

# Aussi : risk_pretrade.py (utilise pour 8B.3 mais bon a connaitre)
print("\n" + "=" * 78)
print("BONUS : risk_pretrade.py (pour 8B.3)")
print("=" * 78)
analyze(os.path.join(PROD_DIR, "risk_pretrade.py"))
