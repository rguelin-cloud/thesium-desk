# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-MODULES-WHERE-V1]
# Localise les modules Phase 1/2 dans l'arborescence et explique
# pourquoi risk_pretrade.py les importe avec succes alors que diag-imports
# ne les trouve pas.
#
# Hypotheses testees :
#   A. Modules dans un sous-dossier (ex: bridge/, broker/, modules/)
#   B. Modules avec prefix nextones- (scripts livres mais pas renommes)
#   C. risk_pretrade utilise un import dynamique avec sys.path manipule
#
# Usage : py -3.13 nextones-diag-modules-where.py

import os
import re
import sys

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# Modules a localiser
TARGETS = [
    "broker_shadow_executor",
    "risk_broker_check",
    "broker_resolver",
    "order_translator",
    "broker_mapping_schema",
    "broker_seed_universe",
    "broker_shadow_schema",
]


def banner(t):
    print()
    print("=" * 72)
    print(t)
    print("=" * 72)


def section_walk_filesystem():
    banner("[1] WALK arborescence : recherche des fichiers (variantes nom)")
    # On cherche : module.py, module-*.py, nextones-module*.py, *module*.py
    patterns_per_target = {}
    for t in TARGETS:
        norm = t.replace("_", "[_-]")
        patterns_per_target[t] = re.compile(rf"^(nextones-)?{norm}(-.+)?\.py$", re.IGNORECASE)

    found = {t: [] for t in TARGETS}
    for root, dirs, files in os.walk(PROD_DIR):
        # Ignorer venv et caches
        skip = [d for d in dirs if d in ("__pycache__", ".venv", "venv", "node_modules", ".git")]
        for d in skip:
            dirs.remove(d)
        for f in files:
            if not f.endswith(".py"):
                continue
            for t, pat in patterns_per_target.items():
                if pat.match(f):
                    found[t].append(os.path.join(root, f))

    for t in TARGETS:
        print(f"\n  {t} :")
        if not found[t]:
            print("    (aucun fichier trouve)")
        else:
            for p in found[t]:
                size = os.path.getsize(p)
                rel = os.path.relpath(p, PROD_DIR)
                print(f"    - {rel}  ({size} bytes)")


def section_risk_pretrade_imports():
    banner("[2] Comment risk_pretrade.py importe-t-il les modules broker ?")
    rp = os.path.join(PROD_DIR, "risk_pretrade.py")
    if not os.path.exists(rp):
        print("  [ERR] risk_pretrade.py introuvable")
        return
    with open(rp, "r", encoding="utf-8-sig") as f:
        src = f.read()
    # Cherche tous les import/from referencant nos targets ou contenant 'broker'
    print(f"  Taille fichier : {len(src)} bytes")
    import_lines = []
    for i, line in enumerate(src.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            if any(t in line for t in TARGETS) or "broker" in line.lower() or "shadow" in line.lower():
                import_lines.append((i, line.rstrip()))
    if not import_lines:
        print("  Aucun import broker/shadow detecte dans risk_pretrade.py")
    else:
        print("  Imports broker/shadow detectes :")
        for i, ln in import_lines:
            print(f"    L{i:4d} : {ln}")
    # Cherche aussi les marker
    print("\n  Marker [NEXTONES-BROKER-CHECK-V1] dans risk_pretrade.py :")
    if "[NEXTONES-BROKER-CHECK-V1]" in src or "NEXTONES-BROKER-CHECK-V1" in src:
        # Affiche 30 lignes autour
        for i, line in enumerate(src.splitlines(), 1):
            if "NEXTONES-BROKER-CHECK-V1" in line:
                print(f"    L{i:4d} : {line.rstrip()}")
    else:
        print("    ABSENT")


def section_sys_path():
    banner("[3] sys.path utilise par risk_pretrade en runtime")
    # On charge risk_pretrade dans un sous-process et on dump le sys.path + le module risk_broker_check
    import subprocess
    code = "\n".join([
        "import sys",
        f"sys.path.insert(0, r'{PROD_DIR}')",
        "import risk_pretrade",
        "print('--- sys.path ---')",
        "for p in sys.path:",
        "    print('  ' + repr(p))",
        "print('--- modules charges contenant broker/shadow ---')",
        "for n, m in list(sys.modules.items()):",
        "    if n and (('broker' in n.lower()) or ('shadow' in n.lower())):",
        "        print('  ' + n + '  -> ' + str(getattr(m, '__file__', '?')))",
    ])
    res = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=30,
    )
    print(res.stdout.rstrip())
    if res.stderr.strip():
        print("--- STDERR ---")
        print(res.stderr.rstrip())


def section_audit_table():
    banner("[4] Trace de Phase 1/2 dans broker_mapping_audit (preuve d'execution)")
    import sqlite3
    db = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
    if not os.path.exists(db):
        print(f"  [ERR] {db} introuvable")
        return
    con = sqlite3.connect(db)
    cur = con.execute(
        "SELECT id, ts, action, broker_symbol, notes "
        "FROM broker_mapping_audit ORDER BY id DESC LIMIT 20"
    )
    for r in cur.fetchall():
        print(f"  {r}")
    con.close()


def main():
    print(f"PROD_DIR : {PROD_DIR}")
    section_walk_filesystem()
    section_risk_pretrade_imports()
    section_sys_path()
    section_audit_table()
    print()
    print("=" * 72)
    print("FIN diag")
    print("=" * 72)


if __name__ == "__main__":
    main()
