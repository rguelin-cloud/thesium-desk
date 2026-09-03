# -*- coding: utf-8 -*-
# Liste TOUTES les def (publiques + privees) de convergence_engine + portfolio_construction_agent
# + signatures exactes + premieres lignes du corps
import os
import re

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

for fname in ("convergence_engine.py", "portfolio_construction_agent.py"):
    path = os.path.join(PROD_DIR, fname)
    print("=" * 78)
    print(f"FILE : {fname}")
    print("=" * 78)
    with open(path, "r", encoding="utf-8-sig") as f:
        src = f.read()
    # Toutes les def (multi-ligne supportee via DOTALL)
    for m in re.finditer(r"^(def\s+[\w_]+\s*\([^)]*\)(?:\s*->\s*[^:]+)?\s*:)", src, re.MULTILINE):
        line_no = src[:m.start()].count("\n") + 1
        sig = m.group(1).replace("\n", " ").strip()
        print(f"  L{line_no:4d}: {sig[:140]}")
