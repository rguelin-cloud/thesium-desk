# -*- coding: utf-8 -*-
"""
[DIAG_JWT_KEY_V1]
Identifie la cle localStorage utilisee pour stocker le token JWT
dans index.html. Cherche aussi sessionStorage et les fetch wrappers.
"""
import re
from pathlib import Path
from collections import Counter

HTML = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html")

def main():
    if not HTML.exists():
        print(f"[ERR] introuvable: {HTML}")
        return

    txt = HTML.read_text(encoding="utf-8-sig", errors="replace")
    print(f"[OK] lu {HTML} ({len(txt)} chars)")
    print()

    # 1) localStorage.setItem / getItem / removeItem
    print("=" * 70)
    print("1) APPELS localStorage")
    print("=" * 70)
    keys_set = Counter()
    keys_get = Counter()
    for m in re.finditer(r'localStorage\.setItem\(\s*[\'"]([^\'"]+)[\'"]', txt):
        keys_set[m.group(1)] += 1
    for m in re.finditer(r'localStorage\.getItem\(\s*[\'"]([^\'"]+)[\'"]', txt):
        keys_get[m.group(1)] += 1

    print(f"  setItem ({sum(keys_set.values())} occurrences):")
    for k, n in keys_set.most_common():
        print(f"    {n:3d}x  '{k}'")
    print(f"  getItem ({sum(keys_get.values())} occurrences):")
    for k, n in keys_get.most_common():
        print(f"    {n:3d}x  '{k}'")
    print()

    # 2) sessionStorage
    print("=" * 70)
    print("2) APPELS sessionStorage")
    print("=" * 70)
    sess_set = Counter()
    sess_get = Counter()
    for m in re.finditer(r'sessionStorage\.setItem\(\s*[\'"]([^\'"]+)[\'"]', txt):
        sess_set[m.group(1)] += 1
    for m in re.finditer(r'sessionStorage\.getItem\(\s*[\'"]([^\'"]+)[\'"]', txt):
        sess_get[m.group(1)] += 1
    print(f"  setItem: {dict(sess_set)}")
    print(f"  getItem: {dict(sess_get)}")
    print()

    # 3) Cherche les usages de "Bearer " pour voir comment le token est passe
    print("=" * 70)
    print("3) USAGES 'Bearer ' (auth header)")
    print("=" * 70)
    for i, m in enumerate(re.finditer(r'.{60}Bearer\s.{120}', txt)):
        snippet = m.group(0).replace('\n', ' ').replace('\r', ' ')
        print(f"  [{i+1}] ...{snippet}...")
        if i >= 15:
            print("  (truncated)")
            break
    print()

    # 4) Cherche fonction login pour voir ou le token est stocke apres /api/auth/login
    print("=" * 70)
    print("4) STOCKAGE APRES /api/auth/login")
    print("=" * 70)
    # bloc de 400 chars autour de /api/auth/login
    for m in re.finditer(r'/api/auth/login', txt):
        start = max(0, m.start() - 100)
        end = min(len(txt), m.end() + 600)
        block = txt[start:end]
        print("-" * 70)
        print(block)
    print()

    # 5) Cherche wrapper fetch (fonction apiCall, authFetch, etc.)
    print("=" * 70)
    print("5) WRAPPERS fetch candidats")
    print("=" * 70)
    candidates = [
        r'function\s+(\w*[Ff]etch\w*)\s*\(',
        r'function\s+(api\w*)\s*\(',
        r'const\s+(\w*[Ff]etch\w*)\s*=',
        r'const\s+(api\w*)\s*=',
        r'async\s+function\s+(\w+)\s*\([^)]*\)\s*{[^}]*Authorization',
    ]
    found = set()
    for pat in candidates:
        for m in re.finditer(pat, txt):
            found.add(m.group(1))
    print(f"  Candidats: {sorted(found)}")
    print()

    # 6) Suggestion
    print("=" * 70)
    print("6) SUGGESTION cle JWT")
    print("=" * 70)
    # la cle la plus probable = celle setItem apres /api/auth/login
    if keys_set:
        most = keys_set.most_common(1)[0][0]
        print(f"  Cle la plus utilisee en setItem: '{most}'")
    print("  -> Verifier visuellement le bloc 4 ci-dessus pour confirmer.")

if __name__ == "__main__":
    main()
