# -*- coding: utf-8 -*-
# Dump fin de create_and_execute_order (L1400 jusqu'au prochain def)
import os, sys
PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"
def main():
    with open(PATH, "rb") as f:
        text = f.read().decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    # Cherche prochain "def " ou "class " apres L1148
    end = None
    for i in range(1149, len(lines)):
        ln = lines[i]
        if ln.startswith("def ") or ln.startswith("class "):
            end = i
            break
    print("create_and_execute_order def L1148 -> next def/class at L%s" % ((end+1) if end else "EOF"))
    print()
    # Dump L1400 a end (ou +200)
    last = end if end else min(1700, len(lines))
    print("=== L1400 a L%d ===" % last)
    for i in range(1399, last):
        print("%4d| %s" % (i+1, lines[i]))
    print()
    # Recherche broker.execute_order ou .execute_order(
    print("=== broker.execute_order / execute_order( ===")
    for i, ln in enumerate(lines):
        if "broker.execute_order" in ln or ("execute_order(" in ln and "def " not in ln):
            print("L%d: %s" % (i+1, ln.strip()[:160]))
if __name__ == "__main__":
    main()
