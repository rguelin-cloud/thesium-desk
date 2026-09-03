# -*- coding: utf-8 -*-
# Localise tous les "row[\"...\"]" dans portfolio_construction_agent_jalon2.py
# qui pourraient planter si la conn n'a pas row_factory = sqlite3.Row

import os

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
PATH = os.path.join(ROOT, "portfolio_construction_agent_jalon2.py")


def main():
    with open(PATH, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    # Cherche tous les acces row["xxx"] ou similaires
    print("=== Acces par nom de colonne (row['n'], etc.) ===")
    for i, ln in enumerate(lines, 1):
        # Pattern row["something"] ou row[\u0022...\u0022]
        if 'row["' in ln or "row['" in ln:
            print("  L" + str(i) + ": " + ln.rstrip()[:160])

    # Cherche les SELECT
    print("\n=== SELECT (toutes les requetes) ===")
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if s.startswith('"SELECT') or s.startswith("'SELECT") or s.startswith("SELECT "):
            print("  L" + str(i) + ": " + ln.rstrip()[:160])

    # Cherche les .fetchone() et .fetchall()
    print("\n=== fetchone / fetchall ===")
    for i, ln in enumerate(lines, 1):
        if ".fetchone()" in ln or ".fetchall()" in ln:
            print("  L" + str(i) + ": " + ln.rstrip()[:160])

    # Verifier si conn.row_factory est setup quelque part
    print("\n=== row_factory ===")
    for i, ln in enumerate(lines, 1):
        if "row_factory" in ln:
            print("  L" + str(i) + ": " + ln.rstrip()[:160])

    # Idem dans api_server_with_static.py
    print("\n=== api_server_with_static.py : run_construction handler ===")
    api_path = os.path.join(ROOT, "api_server_with_static.py")
    with open(api_path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    # Trouver le handler run_construction
    idx = content.find("async def run_construction(")
    if idx >= 0:
        end = content.find("\n@app.", idx + 50)
        snippet = content[idx:end if end > 0 else idx + 1500]
        # Afficher avec numeros de ligne
        start_line = content[:idx].count("\n") + 1
        for off, ln in enumerate(snippet.split("\n")):
            print("  L" + str(start_line + off) + ": " + ln.rstrip()[:170])


if __name__ == "__main__":
    main()
