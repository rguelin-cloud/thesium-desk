# -*- coding: utf-8 -*-
# nextones-diag-universe-equity-agent.py
# Diagnostic : que fait le scan equity ? D'ou prend-il ses candidats ?
# Affiche la liste hardcodee, et les 5 derniers candidats inseres.

import os
import sys
import re
import sqlite3

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"


def find_agent_files():
    """Cherche tous les fichiers .py de l'agent universe."""
    search = []
    for root, dirs, files in os.walk(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"):
        # Skip venv et caches
        if "venv" in root or "__pycache__" in root or ".git" in root:
            continue
        for f in files:
            if "universe" in f.lower() and f.endswith(".py"):
                search.append(os.path.join(root, f))
    return search


def show_top_of_file(path, max_lines=80):
    print(f"\n--- {path} (top {max_lines} lignes) ---")
    try:
        with open(path, encoding="utf-8-sig") as fh:
            for i, line in enumerate(fh, 1):
                if i > max_lines:
                    break
                print(f"  {i:3d} | {line.rstrip()}")
    except Exception as e:
        print(f"  KO lecture : {e}")


def find_ticker_lists(path):
    """Trouve les blocs ressemblant a une liste de tickers en majuscules."""
    print(f"\n--- Listes tickers detectees dans {os.path.basename(path)} ---")
    try:
        content = open(path, encoding="utf-8-sig").read()
    except Exception as e:
        print(f"  KO lecture : {e}")
        return

    # Pattern: ["XLK", "XLF", ...] ou ('XLK', 'XLF', ...) ou liste multi-ligne
    # On cherche des blocs avec au moins 3 tickers maj 2-5 chars
    pattern = re.compile(r"""
        [\[\(\{]                              # crochet/parenthese/accolade ouvrant
        \s*
        (?:["'][A-Z]{2,6}["']\s*,\s*){2,}     # au moins 3 tickers separes par virgules
        ["'][A-Z]{2,6}["']
        \s*[\]\)\}]                           # fermant
    """, re.VERBOSE | re.DOTALL)

    matches = pattern.findall(content)
    for i, m in enumerate(matches[:5], 1):
        # Resume + verifier presence REET
        flat = " ".join(m.split())
        has_reet = "REET" in m
        marker = " <-- contient REET" if has_reet else ""
        print(f"  match {i}{marker} :")
        print(f"    {flat[:200]}")

    # Recherche directe REET
    reet_lines = []
    for lineno, line in enumerate(content.split("\n"), 1):
        if "REET" in line:
            reet_lines.append((lineno, line.strip()))
    if reet_lines:
        print(f"  REET trouve a {len(reet_lines)} endroits :")
        for ln, l in reet_lines[:10]:
            print(f"    L{ln}: {l[:150]}")
    else:
        print("  REET ABSENT du fichier")


def show_last_scans():
    """Voir comment les derniers scans ont nomme leurs candidats."""
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    print("\n--- Derniers candidats inseres par scan (5 batchs) ---")
    cur.execute("""
        SELECT scan_batch, ticker, asset_class, status, score, proposed_at
        FROM universe_candidates
        WHERE scan_batch LIKE 'scan-%'
        ORDER BY proposed_at DESC
        LIMIT 30
    """)
    rows = cur.fetchall()
    current = None
    for r in rows:
        if r[0] != current:
            print(f"\n  [{r[0]}]")
            current = r[0]
        print(f"    {r[1]:8s} class={r[2]:8s} status={r[3]:10s} score={r[4]} ({r[5]})")
    conn.close()


def main():
    print("=" * 70)
    print("DIAGNOSTIC AGENT UNIVERSE EQUITY/ETF/CRYPTO")
    print("=" * 70)

    files = find_agent_files()
    print(f"\n{len(files)} fichier(s) universe detectes :")
    for f in files:
        try:
            size = os.path.getsize(f)
            print(f"  {os.path.basename(f):60s}  ({size} octets)")
        except Exception:
            print(f"  {f}")

    # Focus sur le plus pertinent
    target = None
    for f in files:
        if "universe-expansion-equity" in f or "universe_expansion_equity" in f:
            target = f
            break
    if not target and files:
        target = files[0]

    if target:
        print(f"\n>>> Focus sur : {target}")
        show_top_of_file(target, 60)
        find_ticker_lists(target)

    # Aussi scanner les autres fichiers pour REET
    print("\n--- Recherche REET dans TOUS les fichiers universe ---")
    for f in files:
        try:
            content = open(f, encoding="utf-8-sig").read()
            if "REET" in content:
                print(f"  PRESENT dans {os.path.basename(f)}")
        except Exception:
            pass

    show_last_scans()

    print("\n" + "=" * 70)
    print("FIN")
    print("=" * 70)


if __name__ == "__main__":
    main()
