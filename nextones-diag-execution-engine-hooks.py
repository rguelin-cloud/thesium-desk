# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-EXECUTION-ENGINE-HOOKS-V1]
# Cartographie execution_engine.py pour identifier le point d'injection
# du shadow executor (Phase 3A).
#
# Recherche:
#   - fonctions top-level + signature
#   - lignes appelant pretrade / run_pretrade_checks / risk_v2
#   - lignes appelant PineConnector / webhook / send_setup / MT5
#   - lignes INSERT INTO orders / fills
#   - presence marker existant NEXTONES-SHADOW-EXEC-V1
#   - signature des proposals passes a pretrade (ticker, qty, price, side)
#
# Read-only.

import os
import re
import ast
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(ROOT, "execution_engine.py")
MARKER = "NEXTONES-SHADOW-EXEC-V1"

PATTERNS = {
    "pretrade_calls": [
        r"run_pretrade_checks\s*\(",
        r"_rv2_run\s*\(",
        r"_risk_v2_run\s*\(",
        r"check_pretrade\s*\(",
    ],
    "pineconnector_calls": [
        r"PineConnector",
        r"send_setup\s*\(",
        r"send_raw\s*\(",
        r"webhook",
        r"to_mt5_commands",
    ],
    "order_inserts": [
        r"INSERT\s+INTO\s+orders",
        r"INSERT\s+INTO\s+fills",
        r"INSERT\s+INTO\s+executions",
        r"cur\.execute\(.+orders",
    ],
    "broker_check_hook": [
        r"NEXTONES-BROKER-CHECK-V1",
    ],
}


def main():
    if not os.path.exists(TARGET):
        print("[ERR] " + TARGET + " introuvable")
        sys.exit(1)

    with open(TARGET, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()

    print("[INFO] fichier : " + TARGET)
    print("[INFO] taille  : " + str(len(raw)) + " bytes / "
          + str(len(lines)) + " lignes")
    print("[INFO] marker " + MARKER + " : "
          + ("DEJA PRESENT" if MARKER in text else "ABSENT"))
    print()

    # AST: fonctions top-level
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        print("[ERR] parse: " + str(e))
        sys.exit(2)

    funcs = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            funcs.append((node.lineno, node.name, args))

    print("=" * 72)
    print("FONCTIONS TOP-LEVEL (" + str(len(funcs)) + ")")
    print("=" * 72)
    for ln, name, args in funcs:
        print("  L" + str(ln) + "  " + name + "(" + ", ".join(args) + ")")
    print()

    # Recherche patterns
    for cat, patterns in PATTERNS.items():
        print("=" * 72)
        print(cat.upper())
        print("=" * 72)
        hits = []
        for i, ln in enumerate(lines):
            for pat in patterns:
                if re.search(pat, ln):
                    hits.append((i + 1, ln.strip()))
                    break
        if not hits:
            print("  (aucun match)")
        else:
            for ln_no, content in hits[:30]:
                if len(content) > 130:
                    content = content[:127] + "..."
                print("  L" + str(ln_no) + " : " + content)
            if len(hits) > 30:
                print("  ... +" + str(len(hits) - 30) + " autres")
        print()

    # Cherche le bloc autour des appels pretrade pour comprendre le flow
    print("=" * 72)
    print("CONTEXTE PRETRADE (15 lignes autour de chaque appel)")
    print("=" * 72)
    for i, ln in enumerate(lines):
        if re.search(r"(run_pretrade_checks|_rv2_run|_risk_v2_run)\s*\(", ln):
            print()
            print("--- Bloc autour L" + str(i + 1) + " ---")
            start = max(0, i - 7)
            end = min(len(lines), i + 8)
            for j in range(start, end):
                marker = ">>>" if j == i else "   "
                print("  " + marker + " L" + str(j + 1) + " : " + lines[j])


if __name__ == "__main__":
    main()
