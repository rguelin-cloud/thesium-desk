# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-SHADOW-INSERTION-POINT-V1]
# Diag complementaire : prepare le wiring Phase 3A.
#
# Sortie attendue :
#   1. Imports en tete de execution_engine.py (pour savoir ou ajouter
#      `from broker_shadow_executor import execute_shadow`)
#   2. Le bloc COMPLET de create_and_execute_order (L1172 a fin de fonction)
#      avec numeros de ligne -> point d'insertion exact entre pretrade V2
#      accept et INSERT orders
#   3. Recherche PineConnector / MT5Bridge / send_setup / webhook sur TOUS
#      les .py du dossier prod -> identifier ou l'envoi broker se fait
#   4. Verification que broker_shadow_executor.py et risk_pretrade.py sont
#      importables, et que execute_shadow + check_broker_mapping existent
#
# Usage : py -3.13 nextones-diag-shadow-insertion-point.py

import os
import re
import subprocess
import sys

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(PROD_DIR, "execution_engine.py")


def banner(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def section_imports():
    banner("[1] IMPORTS en tete de execution_engine.py (60 premieres lignes)")
    with open(TARGET, "r", encoding="utf-8-sig") as f:
        for i, line in enumerate(f, 1):
            if i > 60:
                break
            if line.strip().startswith(("import ", "from ")) or i <= 30:
                print(f"  L{i:4d} : {line.rstrip()}")


def find_function_block(src_lines, start_line):
    """
    A partir de la ligne start_line (1-based, def ...), retourne (start, end)
    en se basant sur la premiere ligne ayant l'indent <= def_indent qui suit
    une ligne non vide a l'interieur de la fonction.
    """
    idx = start_line - 1
    def_line = src_lines[idx]
    def_indent = len(def_line) - len(def_line.lstrip())
    end = len(src_lines)
    for j in range(idx + 1, len(src_lines)):
        line = src_lines[j]
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= def_indent and not stripped.startswith("#"):
            end = j
            break
    return idx + 1, end


def section_function_block():
    banner("[2] FONCTION create_and_execute_order (L1172 -> fin)")
    with open(TARGET, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    # Trouver def create_and_execute_order
    target_re = re.compile(r"^def\s+create_and_execute_order\s*\(")
    start = None
    for i, line in enumerate(lines, 1):
        if target_re.match(line):
            start = i
            break
    if start is None:
        print("  [ERR] def create_and_execute_order introuvable")
        return
    s, e = find_function_block(lines, start)
    print(f"  Bornes : L{s} -> L{e} ({e - s + 1} lignes)")
    print("-" * 72)
    for i in range(s, e + 1):
        if i - 1 >= len(lines):
            break
        marker = ""
        ln = lines[i - 1].rstrip("\n")
        if "run_pretrade_checks" in ln or "_rv2_run" in ln:
            marker = "  <-- PRETRADE V2"
        if "INSERT INTO orders" in ln:
            marker = "  <-- INSERT orders"
        if "risk_result" in ln and "blocked" in ln:
            marker = "  <-- RISK GATE"
        print(f"  L{i:4d} : {ln}{marker}")


def section_broker_send_search():
    banner("[3] Recherche envoi broker (PineConnector/MT5/webhook/send_setup)")
    patterns = [
        r"PineConnector",
        r"MT5Bridge",
        r"send_setup",
        r"pineconnector",
        r"webhook\.pineconnector",
        r"to_mt5_commands",
        r"send_raw",
        r"metaapi",
        r"MetaApi",
    ]
    py_files = []
    for name in os.listdir(PROD_DIR):
        if name.endswith(".py") and not name.endswith(".pyc"):
            py_files.append(os.path.join(PROD_DIR, name))
    print(f"  Fichiers scannes : {len(py_files)}")
    hits_by_file = {}
    for path in py_files:
        try:
            with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    for pat in patterns:
                        if re.search(pat, line):
                            hits_by_file.setdefault(path, []).append(
                                (i, pat, line.rstrip())
                            )
                            break
        except Exception as e:
            print(f"  [WARN] lecture {path} : {e}")
    if not hits_by_file:
        print("  (aucun match dans le dossier prod)")
        return
    for path, hits in sorted(hits_by_file.items()):
        rel = os.path.basename(path)
        print(f"\n  -- {rel} ({len(hits)} match)")
        # max 10 lignes par fichier pour eviter le bruit
        for i, (ln, pat, content) in enumerate(hits[:10]):
            print(f"     L{ln:4d} [{pat}] : {content[:140]}")
        if len(hits) > 10:
            print(f"     ... +{len(hits) - 10} autres")


def section_modules_check():
    banner("[4] Verifie que broker_shadow_executor.execute_shadow est dispo")
    code = (
        "import sys, importlib;"
        f"sys.path.insert(0, r'{PROD_DIR}');"
        "ok=True;"
        "try:\n"
        "    m1 = importlib.import_module('broker_shadow_executor');\n"
        "    print('broker_shadow_executor: OK, attrs=', "
        "[a for a in ['execute_shadow','snapshot_pnl'] if hasattr(m1,a)])\n"
        "except Exception as e:\n"
        "    ok=False; print('broker_shadow_executor: ERR', e)\n"
        "try:\n"
        "    m2 = importlib.import_module('risk_broker_check');\n"
        "    print('risk_broker_check: OK, attrs=', "
        "[a for a in ['check_broker_mapping','make_risk_decorator'] if hasattr(m2,a)])\n"
        "except Exception as e:\n"
        "    print('risk_broker_check: ERR', e)\n"
        "try:\n"
        "    m3 = importlib.import_module('bridge_config');\n"
        "    print('bridge_config: OK',"
        "{k: getattr(m3,k,'<MISSING>') for k in "
        "['BROKER_SHADOW_ENABLED','BROKER_LIVE_ENABLED','MAX_LIVE_NAV','BROKER_LIVE_ACCOUNT']})\n"
        "except Exception as e:\n"
        "    print('bridge_config: ERR', e)\n"
    )
    res = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=20,
    )
    print(res.stdout.rstrip())
    if res.stderr:
        print("--- STDERR ---")
        print(res.stderr.rstrip())


def main():
    if not os.path.exists(TARGET):
        print(f"[ERR] {TARGET} introuvable")
        sys.exit(2)
    section_imports()
    section_function_block()
    section_broker_send_search()
    section_modules_check()
    print()
    print("=" * 72)
    print("FIN diag insertion-point")
    print("=" * 72)


if __name__ == "__main__":
    main()
