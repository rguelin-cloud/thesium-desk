# -*- coding: utf-8 -*-
# Diag L1260-1310 de execution_engine.py pour voir l'INSERT cassee
import os, sys

PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"

def main():
    if not os.path.exists(PATH):
        print("FAIL: not found", PATH)
        sys.exit(1)
    with open(PATH, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    n = len(lines)
    print("file lines:", n)
    print()
    # Print L1240-1310
    start = 1240
    end = min(1320, n)
    print("=== L%d-L%d ===" % (start, end))
    for i in range(start, end):
        print("%4d| %s" % (i + 1, lines[i]))
    print()
    # Search for INSERT INTO orders to see all candidates
    print("=== Occurrences 'INSERT INTO orders' ===")
    for i, ln in enumerate(lines):
        if "INSERT INTO orders" in ln:
            print("L%d: %s" % (i + 1, ln.strip()))
    print()
    # Search for json.dumps(risk
    print("=== Occurrences 'json.dumps(risk' ===")
    for i, ln in enumerate(lines):
        if "json.dumps(risk" in ln:
            print("L%d: %s" % (i + 1, ln.strip()))

if __name__ == "__main__":
    main()
