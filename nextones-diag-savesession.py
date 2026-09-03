# -*- coding: utf-8 -*-
"""
[DIAG_SAVESESSION_V1]
Extrait :
1) saveSession() definition
2) refreshAll() / hideLogin() pour comprendre le flow
3) Toute variable globale SESSION / TOKEN / state
4) Intercepteur fetch (window.fetch wrap, ou variable globale token)
5) API_BASE
6) Tout usage de 'access_token' / 'token' dans app.js
"""
import re
from pathlib import Path

APPJS = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js")

def section(t):
    print()
    print("=" * 72)
    print(t)
    print("=" * 72)

def find_block(txt, start_idx, max_len=1500):
    """Renvoie le bloc de fonction (depuis idx jusqu'a } equilibre)."""
    # cherche premier {
    depth = 0
    i = start_idx
    started = False
    while i < len(txt) and i - start_idx < max_len * 3:
        c = txt[i]
        if c == '{':
            depth += 1
            started = True
        elif c == '}':
            depth -= 1
            if started and depth == 0:
                return txt[start_idx:i+1]
        i += 1
    return txt[start_idx:start_idx+max_len]

def main():
    txt = APPJS.read_text(encoding="utf-8-sig", errors="replace")
    print(f"[OK] {len(txt)} chars")

    section("1) saveSession definition")
    for pat in [
        r'function\s+saveSession\s*\(',
        r'const\s+saveSession\s*=',
        r'saveSession\s*=\s*function',
        r'saveSession\s*=\s*\(',
    ]:
        for m in re.finditer(pat, txt):
            blk = find_block(txt, m.start(), 800)
            print(f"--- @ {m.start()} ---")
            print(blk[:1200])
            print()

    section("2) refreshAll / hideLogin / handleLogout")
    for fn in ['refreshAll', 'hideLogin', 'handleLogout', 'loadSession', 'getSession', 'currentToken', 'getCurrentToken']:
        for pat in [rf'function\s+{fn}\s*\(', rf'const\s+{fn}\s*=', rf'{fn}\s*=\s*function']:
            for m in re.finditer(pat, txt):
                blk = find_block(txt, m.start(), 600)
                print(f"--- {fn} @ {m.start()} ---")
                print(blk[:900])
                print()

    section("3) Variables globales token / session / state (top-level let/const/var)")
    # cherche let/const/var TOKEN ou SESSION ou state au debut des lignes
    for m in re.finditer(r'^(let|const|var)\s+(\w*(?:[Tt]oken|[Ss]ession|STATE|state)\w*)\s*=', txt, re.MULTILINE):
        line_start = m.start()
        line_end = txt.find('\n', line_start)
        print(f"  L{txt[:line_start].count(chr(10))+1}: {txt[line_start:line_end][:180]}")

    section("4) Wrapper fetch global / intercepteur")
    # cherche window.fetch = ou const _fetch = ou function apiFetch
    for pat in [
        r'window\.fetch\s*=',
        r'const\s+(\w*[Ff]etch\w*)\s*=',
        r'function\s+(\w*[Ff]etch\w*)\s*\(',
        r'const\s+_fetch\s*=',
    ]:
        for m in re.finditer(pat, txt):
            line_start = max(0, m.start() - 30)
            blk = find_block(txt, m.start(), 1200)
            print(f"--- @ {m.start()} ({pat}) ---")
            print(blk[:1200])
            print()

    section("5) API_BASE")
    for m in re.finditer(r'(const|let|var)\s+API_BASE\s*=\s*([^;\n]+)', txt):
        print(f"  {m.group(0)[:200]}")
    # API_BASE usages (premiers 5)
    print("  Usages :")
    for i, m in enumerate(re.finditer(r'API_BASE', txt)):
        if i >= 8: break
        line_start = txt.rfind('\n', 0, m.start()) + 1
        line_end = txt.find('\n', m.start())
        print(f"    L{txt[:m.start()].count(chr(10))+1}: {txt[line_start:line_end].strip()[:160]}")

    section("6) Toutes occurrences de 'access_token' et '\"token\"' dans app.js")
    for kw in ['access_token', '"token"', "'token'"]:
        print(f"--- {kw} ---")
        for m in re.finditer(re.escape(kw), txt):
            line_start = txt.rfind('\n', 0, m.start()) + 1
            line_end = txt.find('\n', m.start())
            print(f"  L{txt[:m.start()].count(chr(10))+1}: {txt[line_start:line_end].strip()[:180]}")

    section("7) Premieres lignes du fichier (200 lignes initiales = setup global)")
    lines = txt.splitlines()
    for i, ln in enumerate(lines[:80], 1):
        print(f"  L{i:3d}: {ln[:160]}")

if __name__ == "__main__":
    main()
