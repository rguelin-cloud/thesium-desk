# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-RISK-ENGINE-STRUCTURE-V1]
# Cartographie risk_engine.py / risk_pretrade.py pour identifier le point
# d'insertion exact du hook broker_mapping_ok.
#
# Reporte :
#   - fichiers candidats (risk_engine*.py, risk_pretrade*.py)
#   - fonctions top-level avec signature
#   - imports existants (pour eviter doublon)
#   - presence de marker NEXTONES-BROKER-CHECK-V1 (idempotence)
#   - 5 premieres lignes de chaque fonction "pretrade-like"
#
# Aucune modification. Read-only.

import os
import sys
import ast
import glob

ROOT = os.path.dirname(os.path.abspath(__file__))

CANDIDATES_GLOBS = [
    "risk_engine*.py",
    "risk_pretrade*.py",
    "risk*.py",
    os.path.join("agents", "risk*.py"),
    os.path.join("agents", "risk_engine*.py"),
]

PRETRADE_FUNC_NAMES = (
    "pretrade", "risk_pretrade", "check_pretrade",
    "validate_pretrade", "run_pretrade", "pretrade_check",
)

MARKER = "NEXTONES-BROKER-CHECK-V1"


def find_candidates():
    found = []
    for pat in CANDIDATES_GLOBS:
        for p in glob.glob(os.path.join(ROOT, pat)):
            if p.endswith(".bak") or ".bak." in p:
                continue
            if p not in found:
                found.append(p)
    return found


def analyze(path):
    with open(path, "rb") as f:
        raw = f.read()
    # decode utf-8-sig pour gerer BOM
    text = raw.decode("utf-8-sig", errors="replace")
    info = {
        "path": path,
        "size_bytes": len(raw),
        "lines": text.count("\n") + 1,
        "has_marker": MARKER in text,
        "imports": [],
        "functions": [],
        "pretrade_funcs": [],
    }
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        info["parse_error"] = str(e)
        return info

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            try:
                info["imports"].append(ast.unparse(node))
            except Exception:
                info["imports"].append(type(node).__name__)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            sig = node.name + "(" + ", ".join(args) + ")"
            info["functions"].append({
                "name": node.name,
                "lineno": node.lineno,
                "signature": sig,
            })
            lname = node.name.lower()
            if any(k in lname for k in PRETRADE_FUNC_NAMES):
                lines = text.splitlines()
                start = node.lineno - 1
                body_preview = "\n".join(lines[start:start + 8])
                info["pretrade_funcs"].append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "preview": body_preview,
                })
    return info


def main():
    cands = find_candidates()
    if not cands:
        print("[ERR] Aucun fichier risk_*.py trouve dans " + ROOT)
        print("      Listing repertoire (.py contenant 'risk'):")
        for f in sorted(os.listdir(ROOT)):
            if "risk" in f.lower() and f.endswith(".py"):
                print("        " + f)
        sys.exit(1)

    print("[INFO] " + str(len(cands)) + " fichier(s) candidat(s)")
    print()
    for path in cands:
        info = analyze(path)
        print("=" * 72)
        print("FICHIER : " + info["path"])
        print("  taille     : " + str(info["size_bytes"]) + " bytes / "
              + str(info["lines"]) + " lignes")
        print("  marker     : " + ("DEJA PATCHE" if info["has_marker"] else "ABSENT"))
        if "parse_error" in info:
            print("  PARSE ERROR: " + info["parse_error"])
            continue
        print("  imports (" + str(len(info["imports"])) + "):")
        for imp in info["imports"][:15]:
            print("    " + imp)
        if len(info["imports"]) > 15:
            print("    ... +" + str(len(info["imports"]) - 15) + " autres")
        print("  fonctions top-level (" + str(len(info["functions"])) + "):")
        for fn in info["functions"][:20]:
            print("    L" + str(fn["lineno"]) + "  " + fn["signature"])
        if len(info["functions"]) > 20:
            print("    ... +" + str(len(info["functions"]) - 20) + " autres")
        if info["pretrade_funcs"]:
            print("  CANDIDATES PRETRADE :")
            for fn in info["pretrade_funcs"]:
                print("    -> " + fn["name"] + "  (ligne " + str(fn["lineno"]) + ")")
                for ln in fn["preview"].splitlines():
                    print("       | " + ln)
        else:
            print("  CANDIDATES PRETRADE : aucune")
        print()


if __name__ == "__main__":
    main()
