# -*- coding: utf-8 -*-
# Diag du bloc render pending-validation-panel L2620-2720 pour comprendre
# comment le masquer proprement.
import os
PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
def main():
    with open(PATH, "rb") as f:
        text = f.read().decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    # Dump L2615-2720
    print("=== L2615-L2720 (ancienne UI pending-validation) ===")
    for i in range(2614, min(2720, len(lines))):
        print("%4d| %s" % (i+1, lines[i]))
    print()
    # Cherche le nom de la fonction qui contient ce bloc
    print("=== Recherche function/render englobant L2701 ===")
    for i in range(2700, max(0, 2700-200), -1):
        ln = lines[i]
        if "function " in ln or "= async function" in ln or "= function" in ln or "const " in ln and "=>" in ln:
            print("L%d: %s" % (i+1, ln.strip()[:160]))
            break
if __name__ == "__main__":
    main()
