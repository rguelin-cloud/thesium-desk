# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-RISK-PRETRADE-BROKER-LOGIC-V1]
# Lit risk_pretrade.py et extrait :
#   - le bloc complet [NEXTONES-BROKER-CHECK-V1] (L 360 a L 500)
#   - le nom EXACT du module que l'import lazy tente d'importer
#   - le flux de decision en cas de module absent vs present
#
# Usage : py -3.13 nextones-diag-risk-pretrade-broker-logic.py

import os
import re
import sys

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\risk_pretrade.py"


def banner(t):
    print()
    print("=" * 72)
    print(t)
    print("=" * 72)


def main():
    if not os.path.exists(TARGET):
        print(f"[ERR] {TARGET} introuvable")
        sys.exit(2)
    with open(TARGET, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    total = len(lines)
    banner(f"[INFO] {TARGET} - {total} lignes")

    # Extraire tout entre L 360 et L 500 (zone broker-check)
    banner("[1] BLOC complet L 360 -> L 500")
    start = 359
    end = min(500, total)
    for i in range(start, end):
        ln = lines[i].rstrip("\n")
        marker = ""
        # Marqueurs d'analyse
        if "import" in ln and ("broker" in ln.lower() or "check" in ln.lower()):
            marker = "  <-- IMPORT"
        if "module absent" in ln.lower() or "bypass" in ln.lower():
            marker = "  <-- BRANCHE BYPASS"
        if "blocked_by" in ln and ("=" in ln or ":" in ln) and "broker_mapping" in ln:
            marker = "  <-- BLOCKED_BY broker_mapping"
        if "passed" in ln and "0" in ln and "broker" in ln.lower():
            marker = "  <-- RETURN passed=0"
        if "return" in ln and ("passed" in ln or "blocked_by" in ln):
            marker = marker or "  <-- RETURN"
        print(f"  L{i + 1:4d} : {ln}{marker}")

    # Cherche tous les import lazy quel que soit l'endroit
    banner("[2] TOUS les import lazy dans risk_pretrade.py")
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if not s:
            continue
        # imports a l'interieur de fonctions / try
        if re.match(r"^\s+(from|import)\s", line):
            print(f"  L{i:4d} : {line.rstrip()}")

    # Cherche tous les occurrences de "broker_mapping_ok" et noms voisins
    banner("[3] OCCURRENCES 'broker_mapping_ok' / 'not_tradable' / 'tradable'")
    for i, line in enumerate(lines, 1):
        if any(kw in line for kw in [
            "broker_mapping_ok",
            "not_tradable",
            "strict_refusal",
            "tradable",
            "check_broker_mapping",
            "broker_check",
            "risk_broker_check",
        ]):
            print(f"  L{i:4d} : {line.rstrip()}")

    # Cherche la fonction run_pretrade_checks et sa signature
    banner("[4] Signature run_pretrade_checks")
    for i, line in enumerate(lines, 1):
        if "def run_pretrade_checks" in line:
            print(f"  L{i:4d} : {line.rstrip()}")
            # Affiche 10 lignes apres pour voir le debut de la fonction
            for j in range(i, min(i + 25, total)):
                print(f"  L{j + 1:4d} : {lines[j].rstrip()}")
            break

    # Liste les .py importables au niveau prod_dir
    banner("[5] Modules .py importables dans le dossier prod (filtrage broker/check)")
    d = os.path.dirname(TARGET)
    candidates = sorted(
        f for f in os.listdir(d)
        if f.endswith(".py") and ("broker" in f.lower() or "check" in f.lower() or "risk" in f.lower())
    )
    for f in candidates:
        size = os.path.getsize(os.path.join(d, f))
        print(f"  {f}  ({size} bytes)")


if __name__ == "__main__":
    main()
