# -*- coding: utf-8 -*-
# Diag complet du flow de create_and_execute_order pour comprendre
# pourquoi TXN reste en 'pending_validation' au lieu d'aller en 'approved'.
import os, sys

PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"

def main():
    if not os.path.exists(PATH):
        print("FAIL"); sys.exit(1)
    with open(PATH, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    n = len(lines)
    print("lines:", n)
    print()

    # 1) Trouver def create_and_execute_order
    print("=== def create_and_execute_order ===")
    start_def = None
    for i, ln in enumerate(lines):
        if "def create_and_execute_order" in ln:
            start_def = i
            print("L%d: %s" % (i+1, ln.strip()))
    print()

    # 2) Dump L1284 a L1400 pour voir flow apres INSERT
    print("=== L1284 a L1400 ===")
    for i in range(1283, min(1400, n)):
        print("%4d| %s" % (i+1, lines[i]))
    print()

    # 3) Recherche markers Option A
    print("=== Markers Option A ===")
    markers = [
        "[PATCH_EXECUTION_APPROVAL_WORKFLOW_V1]",
        "[FIX_DB_LOCK_APPROVE_FILL_V1]",
        "approve_and_fill_order",
        "'approved'",
        '"approved"',
        "status='filled'",
        'status="filled"',
    ]
    for m in markers:
        print()
        print("--- '%s' ---" % m)
        for i, ln in enumerate(lines):
            if m in ln:
                print("L%d: %s" % (i+1, ln.strip()[:140]))

    # 4) Toutes les occurrences UPDATE orders SET status
    print()
    print("=== UPDATE orders SET status ===")
    for i, ln in enumerate(lines):
        low = ln.replace(" ", "")
        if "UPDATEordersSETstatus" in low or "UPDATE orders SET status" in ln:
            print("L%d: %s" % (i+1, ln.strip()))

if __name__ == "__main__":
    main()
