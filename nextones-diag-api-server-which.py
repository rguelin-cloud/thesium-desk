# -*- coding: utf-8 -*-
"""
nextones-diag-api-server-which.py
Verifie le contenu de api_server_with_static.py et identifie si il monte api_server.
"""
import os

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

for fn in ["api_server_with_static.py", "api_server.py"]:
    p = os.path.join(ROOT, fn)
    if not os.path.exists(p):
        print(f"[NOT FOUND] {fn}")
        continue
    with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
        content = f.read()
    print(f"\n{'='*70}\n{fn}  ({len(content)} chars, {content.count(chr(10))+1} lignes)\n{'='*70}")
    
    if fn == "api_server_with_static.py":
        # Affiche tout (220 lignes)
        for i, line in enumerate(content.splitlines(), 1):
            print(f"  L{i:3d}: {line}")
    else:
        # Cherche imports + endpoint scan
        for i, line in enumerate(content.splitlines(), 1):
            if (line.strip().startswith("from ") or line.strip().startswith("import ") 
                or "/api/universe/scan" in line or "run_scan" in line):
                print(f"  L{i}: {line}")
            if i > 200 and "/api/universe/scan" not in line and "run_scan" not in line:
                continue
