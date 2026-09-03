# -*- coding: utf-8 -*-
# [NEXTONES-FIX-RECONCILER-PRINT-ORDER]
# Fix L462 : le print(len(mapping_by_broker)) referencait la variable
# avant son affectation. On retire le print orphelin, on l'ajoute juste
# apres fetch_mappings().
#
# Validation : ast.parse + py_compile + smoke --help + backup.

import argparse
import ast
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(PROD, "nextones-broker-reconciler.py")

ORPHAN = '    # Charge mappings (toujours)\n    print(f"  {len(mapping_by_broker)} mappings instrument_broker_mapping")\n\n'

INJECT_AFTER = '    mapping_by_broker, mapping_by_thesium = fetch_mappings(con, thesium_tickers=list(thesium_positions.keys()))\n'

INJECT_LINE = '    print(f"  {len(mapping_by_broker)} mappings instrument_broker_mapping")\n'


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    banner("[1] Lecture target")
    with open(TARGET, "r", encoding="utf-8-sig") as fh:
        src = fh.read()
    print(f"  taille : {len(src)} octets")

    # idempotence : si le print suit deja fetch_mappings, on skip
    expected_pair = INJECT_AFTER + INJECT_LINE
    if expected_pair in src and ORPHAN not in src:
        print("  [SKIP] deja patche")
        return

    n_orphan = src.count(ORPHAN)
    n_inject_after = src.count(INJECT_AFTER)
    print(f"  occurrences ORPHAN bloc      : {n_orphan}")
    print(f"  occurrences INJECT_AFTER     : {n_inject_after}")

    if n_orphan != 1 or n_inject_after != 1:
        print("[FAIL] structure inattendue")
        # Diag
        for i, ln in enumerate(src.splitlines(), 1):
            if "mapping_by_broker" in ln or "mappings instrument_broker_mapping" in ln:
                print(f"  L{i}: {ln}")
        sys.exit(1)

    banner("[2] Retire le print orphelin + injecte apres fetch_mappings")
    src2 = src.replace(ORPHAN, "", 1)
    src2 = src2.replace(INJECT_AFTER, INJECT_AFTER + INJECT_LINE, 1)
    print(f"  nouvelle taille : {len(src2)} octets")

    banner("[3] ast.parse + py_compile")
    ast.parse(src2)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(src2)
        tmpname = tf.name
    try:
        py_compile.compile(tmpname, doraise=True)
        print("  [OK]")
    finally:
        try:
            os.unlink(tmpname)
        except Exception:
            pass

    banner("[4] Smoke --help")
    tmp_target = TARGET + ".tmpprint"
    with open(tmp_target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src2)
    try:
        r = subprocess.run(
            ["py", "-3.13", tmp_target, "--help"],
            capture_output=True, text=True, timeout=30, cwd=PROD,
        )
        if r.returncode != 0:
            print(f"[FAIL] smoke rc={r.returncode}")
            print(r.stderr[-500:])
            sys.exit(1)
        print("  [OK]")
    finally:
        try:
            os.unlink(tmp_target)
        except Exception:
            pass

    if args.dry_run:
        banner("[5] DRY-RUN")
    else:
        banner("[5] Backup + ecriture")
        bak = TARGET + ".bak." + datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(TARGET, bak)
        print(f"  backup : {bak}")
        with open(TARGET, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(src2)
        print(f"  ecrit  : {TARGET}")

    banner("[6] DONE")
    print("  py -3.13 nextones-broker-reconciler.py --no-broker --verbose")


if __name__ == "__main__":
    main()
