# -*- coding: utf-8 -*-
"""
nextones-diag-scan-routes.py
Trouve quel endpoint declenche quel type de scan (crypto / ETF / equity).
Cherche dans api_server_with_static.py et scheduler_*.py les routes /api/universe/*
et les fonctions appelees.
"""

import os, re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def section(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)

def search_in_file(path, patterns, label):
    if not os.path.exists(path):
        print(f"  [SKIP] {path} introuvable")
        return
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.read().splitlines()
    print(f"\n  Fichier : {os.path.basename(path)} ({len(lines)} lignes)")
    for pat in patterns:
        hits = []
        for i, line in enumerate(lines, 1):
            if re.search(pat, line, re.IGNORECASE):
                hits.append((i, line.strip()))
        if hits:
            print(f"\n    Pattern : {pat}")
            for i, l in hits[:25]:
                print(f"      L{i}: {l[:140]}")

def main():
    section("1) Endpoints /api/universe/* dans api_server_with_static.py")
    api = os.path.join(ROOT, "api_server_with_static.py")
    search_in_file(api, [
        r"@app\.(post|get|put|delete).*universe",
        r"/api/universe",
        r"def\s+\w*scan\w*",
        r"def\s+\w*universe\w*",
    ], "api_server")

    section("2) Fonctions de scan dans universe_expansion_agent.py")
    agent = os.path.join(ROOT, "universe_expansion_agent.py")
    search_in_file(agent, [
        r"def\s+scan_\w+",
        r"def\s+run_\w+",
        r"def\s+expand_\w+",
        r"def\s+\w*equity\w*",
        r"def\s+\w*etf\w*",
        r"def\s+\w*crypto\w*",
        r"ETF_SPDR_SECTORIELS",
        r"EQUITY_WATCHLIST|EQUITY_UNIVERSE",
        r"CRYPTO_WATCHLIST|CRYPTO_UNIVERSE",
    ], "agent")

    section("3) Cherche fichiers scheduler / equity-v1")
    files_to_check = []
    for root, dirs, files in os.walk(ROOT):
        # Skip caches et venv
        if any(x in root for x in ["__pycache__", ".venv", "venv", "node_modules", ".git"]):
            continue
        for f in files:
            low = f.lower()
            if (low.startswith("scheduler") or low.startswith("universe_") or 
                "equity" in low or "etf_scan" in low) and low.endswith(".py"):
                files_to_check.append(os.path.join(root, f))
    print(f"  Fichiers candidats : {len(files_to_check)}")
    for f in files_to_check[:30]:
        print(f"    {os.path.relpath(f, ROOT)}")

    section("4) Pour chacun : routes + fonctions main + ETF_SPDR")
    for f in files_to_check[:15]:
        search_in_file(f, [
            r"@app\.(post|get|put|delete)",
            r"ETF_SPDR_SECTORIELS",
            r"def\s+(scan|run|expand|main)",
            r"asset_class\s*=\s*['\"]etf['\"]",
            r"asset_class\s*=\s*['\"]equity['\"]",
        ], os.path.basename(f))

    section("5) Universe equity v1 (du dernier patch session)")
    eq = os.path.join(ROOT, "universe_expansion_equity_v1.py")
    if os.path.exists(eq):
        with open(eq, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read()
        print(f"  Taille : {len(content)} chars")
        # Voir s'il importe / definit ETF
        for kw in ["ETF_SPDR", "ETF_WATCHLIST", "REET", "etf", "asset_class"]:
            cnt = content.lower().count(kw.lower())
            print(f"    {kw:20s} : {cnt} occurrences")

    section("6) Liste fonctions def dans universe_expansion_agent.py")
    if os.path.exists(agent):
        with open(agent, "r", encoding="utf-8-sig", errors="replace") as f:
            lines = f.read().splitlines()
        for i, line in enumerate(lines, 1):
            m = re.match(r"^\s*def\s+(\w+)", line)
            if m:
                print(f"    L{i}: def {m.group(1)}(...)")
        for i, line in enumerate(lines, 1):
            m = re.match(r"^\s*class\s+(\w+)", line)
            if m:
                print(f"    L{i}: class {m.group(1)}")

if __name__ == "__main__":
    main()
