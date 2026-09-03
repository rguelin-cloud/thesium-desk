# -*- coding: utf-8 -*-
# [DIAG_BUGS_V2]
# Inspecte api_server.py (le vrai fichier qui contient les routes + portfolio update)
# pour preparer 2 patchs cibles.
import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API = os.path.join(ROOT, "api_server.py")
STATIC = os.path.join(ROOT, "api_server_with_static.py")


def header(t):
    print()
    print("=" * 72)
    print("  " + t)
    print("=" * 72)


def step1_orders_endpoints():
    header("1. Endpoints /api/orders/* dans api_server.py")
    with open(API, "r", encoding="utf-8-sig") as f:
        src = f.read()
    pat = re.compile(
        r"@app\.(get|post|put|delete)\([\"'](/api/orders[^\"']*)[\"']",
    )
    found = []
    for m in pat.finditer(src):
        verb = m.group(1).upper()
        path = m.group(2)
        found.append((verb, path))
        print("  {:6s} {}".format(verb, path))
    if not found:
        print("  AUCUN endpoint /api/orders/* dans api_server.py non plus")
    return found


def step2_portfolio_update_block():
    header("2. Bloc portfolio.update() dans api_server.py (lignes 240-280)")
    with open(API, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    # Print lignes 240-280
    start = 235
    end = min(len(lines), 285)
    for i in range(start, end):
        print("  L{:4d}: {}".format(i + 1, lines[i].rstrip()[:130]))


def step3_db_connect_sites():
    header("3. Tous les sqlite3.connect dans api_server.py")
    with open(API, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    for i, ln in enumerate(lines, 1):
        if "sqlite3.connect" in ln:
            # Print 2 lignes apres pour voir s'il y a un PRAGMA
            ctx = "  L{:4d}: {}".format(i, ln.rstrip()[:130])
            print(ctx)
            for j in range(i, min(i + 4, len(lines))):
                if "PRAGMA" in lines[j] or "execute" in lines[j]:
                    print("    +{:4d}: {}".format(j + 1, lines[j].rstrip()[:130]))


def step4_existing_pending_endpoints():
    header("4. Endpoints similaires existants (modele pour copier la signature)")
    with open(API, "r", encoding="utf-8-sig") as f:
        src = f.read()
    # Cherche un endpoint GET avec une signature simple
    pat = re.compile(
        r"(@app\.get\([\"']/api/orders[\"'].*?)(?=@app\.|^def |^async def |\Z)",
        re.DOTALL | re.MULTILINE,
    )
    m = pat.search(src)
    if m:
        print("  Endpoint /api/orders trouve :")
        for ln in m.group(1).split("\n")[:25]:
            print("    " + ln[:130])
    else:
        # Cherche n'importe quel endpoint GET pour avoir le pattern d'auth
        pat2 = re.compile(
            r"(@app\.get\([\"']/api/[^\"']+[\"'].*?\nasync def [^(]+\([^)]*\)[^:]*:)",
            re.DOTALL,
        )
        m2 = pat2.search(src)
        if m2:
            print("  Premier endpoint GET trouve (modele) :")
            for ln in m2.group(1).split("\n")[:5]:
                print("    " + ln[:130])


def step5_static_imports():
    header("5. Imports de api_server.py dans api_server_with_static.py")
    with open(STATIC, "r", encoding="utf-8-sig") as f:
        src = f.read()
    for ln in src.split("\n")[:40]:
        if "import" in ln or "from" in ln:
            print("  " + ln[:130])


def main():
    print("NEXTONES diag bugs v2 - api_server.py inspection")
    step1_orders_endpoints()
    step2_portfolio_update_block()
    step3_db_connect_sites()
    step4_existing_pending_endpoints()
    step5_static_imports()


if __name__ == "__main__":
    main()
