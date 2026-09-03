# -*- coding: utf-8 -*-
"""
[DIAG_APP_JS_AUTH_V1]
Lit app.js et extrait :
1) Definition de getToken()
2) Cle localStorage / sessionStorage utilisee pour le token
3) Code du login (apres /api/auth/login)
"""
import re
from pathlib import Path
from collections import Counter

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
APPJS = ROOT / "app.js"

def section(t):
    print()
    print("=" * 72)
    print(t)
    print("=" * 72)

def main():
    if not APPJS.exists():
        # cherche dans static/, public/, assets/
        for sub in ["static", "public", "assets", "js"]:
            p = ROOT / sub / "app.js"
            if p.exists():
                print(f"[OK] trouve a la place : {p}")
                appjs = p
                break
        else:
            # glob recursif
            for cand in ROOT.rglob("app.js"):
                print(f"[OK] trouve : {cand}")
                appjs = cand
                break
            else:
                print(f"[ERR] app.js introuvable sous {ROOT}")
                return
    else:
        appjs = APPJS

    txt = appjs.read_text(encoding="utf-8-sig", errors="replace")
    print(f"[OK] lu {appjs} ({len(txt)} chars, {txt.count(chr(10))+1} lignes)")

    section("1) Definition getToken / setToken")
    for pat_name, pat in [
        ("function getToken", r'function\s+getToken\s*\([^)]*\)\s*\{[^}]{0,500}\}'),
        ("const getToken",    r'const\s+getToken\s*=\s*[^;]{0,500};'),
        ("function setToken", r'function\s+setToken\s*\([^)]*\)\s*\{[^}]{0,500}\}'),
        ("const setToken",    r'const\s+setToken\s*=\s*[^;]{0,500};'),
    ]:
        for m in re.finditer(pat, txt):
            print(f"--- {pat_name} ---")
            print(m.group(0))
            print()

    section("2) Tous appels localStorage")
    keys_set = Counter()
    keys_get = Counter()
    for m in re.finditer(r'localStorage\.setItem\(\s*[\'"]([^\'"]+)[\'"]', txt):
        keys_set[m.group(1)] += 1
    for m in re.finditer(r'localStorage\.getItem\(\s*[\'"]([^\'"]+)[\'"]', txt):
        keys_get[m.group(1)] += 1
    print(f"  setItem: {dict(keys_set)}")
    print(f"  getItem: {dict(keys_get)}")

    section("3) Tous appels sessionStorage")
    ss_set = Counter()
    ss_get = Counter()
    for m in re.finditer(r'sessionStorage\.setItem\(\s*[\'"]([^\'"]+)[\'"]', txt):
        ss_set[m.group(1)] += 1
    for m in re.finditer(r'sessionStorage\.getItem\(\s*[\'"]([^\'"]+)[\'"]', txt):
        ss_get[m.group(1)] += 1
    print(f"  setItem: {dict(ss_set)}")
    print(f"  getItem: {dict(ss_get)}")

    section("4) Contexte autour de /api/auth/login (500 chars apres)")
    for m in re.finditer(r'/api/auth/login', txt):
        start = max(0, m.start() - 100)
        end = min(len(txt), m.end() + 600)
        print("-" * 70)
        print(txt[start:end])
        print()

    section("5) Usages Bearer dans app.js")
    for i, m in enumerate(re.finditer(r'.{40}Bearer\s.{120}', txt)):
        print(f"  [{i+1}] {m.group(0).replace(chr(10),' ')[:200]}")
        if i >= 10:
            break

    section("6) Reponse — cle JWT a utiliser dans la carte Univers")
    # Heuristique : la cle la plus utilisee en getItem dans app.js (hors token vide)
    keys_all = (keys_get + keys_set + ss_get + ss_set)
    if keys_all:
        top = keys_all.most_common(5)
        print("  Top cles storage detectees :")
        for k, n in top:
            print(f"    {n:3d}x  '{k}'")
        print()
        print(f"  >>> Utiliser la plus probable dans le patch UI <<<")

if __name__ == "__main__":
    main()
