# -*- coding: utf-8 -*-
# Dump L1050-1090 + L2280-2320 pour voir le patch Option A et approve_and_fill_order
import os, sys
PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"
def main():
    with open(PATH, "rb") as f:
        text = f.read().decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    print("=== L1050-L1100 (bloc patch workflow approval) ===")
    for i in range(1049, min(1100, len(lines))):
        print("%4d| %s" % (i+1, lines[i]))
    print()
    print("=== L2280-L2330 (approve_and_fill_order wrapper) ===")
    for i in range(2279, min(2330, len(lines))):
        print("%4d| %s" % (i+1, lines[i]))
    print()
    # Verif s'il y a un return prematur dans le bloc patch
    print("=== L1140-1170 (def line + suite) ===")
    for i in range(1139, min(1170, len(lines))):
        print("%4d| %s" % (i+1, lines[i]))
    # UI/API : query pending_approval
    print()
    print("=== UI : recherche endpoint pending_approval ===")
    api_path = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server_with_static.py"
    if os.path.exists(api_path):
        with open(api_path, "rb") as f:
            atext = f.read().decode("utf-8-sig", errors="replace")
        alines = atext.splitlines()
        for i, ln in enumerate(alines):
            if "pending_approval" in ln or "pending_validation" in ln:
                print("L%d: %s" % (i+1, ln.strip()[:140]))
if __name__ == "__main__":
    main()
