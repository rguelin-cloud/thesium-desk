# -*- coding: utf-8 -*-
# Cherche les endpoints qui declenchent run_construction_agent

import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

KEYWORDS = [
    "run_construction_agent",
    "construction",
    "portfolio_targets",
]


def scan_file(path):
    results = []
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            for i, ln in enumerate(f, 1):
                for kw in KEYWORDS:
                    if kw in ln:
                        results.append((i, kw, ln.rstrip()[:150]))
    except Exception as e:
        return [(0, "ERR", str(e))]
    return results


def main():
    # Cherche dans api_server*.py et scheduler.py
    targets = []
    for f in os.listdir(ROOT):
        if (f.startswith("api_server") or f == "scheduler.py" or f == "execution_engine.py") and f.endswith(".py"):
            targets.append(os.path.join(ROOT, f))

    for path in targets:
        print("=" * 70)
        print(path)
        print("=" * 70)
        results = scan_file(path)
        for i, kw, ln in results:
            print("  L" + str(i) + " [" + kw + "] " + ln)

    # Routes FastAPI specifiquement
    print("\n" + "=" * 70)
    print("Routes FastAPI (POST/GET liees construction/targets)")
    print("=" * 70)
    for path in targets:
        if "api_server" not in os.path.basename(path):
            continue
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read()
        # Cherche les decorateurs @app.post @app.get
        for m in re.finditer(r'@app\.(post|get|put|delete)\("([^"]+)"', content):
            method, route = m.group(1), m.group(2)
            if "construct" in route.lower() or "target" in route.lower() or "cycle" in route.lower():
                pos = m.start()
                # Cherche le def juste apres
                def_match = re.search(r"def\s+(\w+)\s*\(", content[pos:pos + 500])
                fname = def_match.group(1) if def_match else "?"
                # Trouver numero de ligne
                line_no = content[:pos].count("\n") + 1
                print("  " + method.upper() + " " + route + " -> " + fname + " (L" + str(line_no) + ")")


if __name__ == "__main__":
    main()
