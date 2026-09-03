# -*- coding: utf-8 -*-
"""
[DIAG_AUTH_FLOW_V1]
L'app n'a aucun login JS dans index.html. Cherche :
1) Fichiers JS externes (script src=)
2) Comment auth_required est appliquee cote serveur (api_server.py)
3) Si /api/universe/* exigent vraiment auth ou non
4) Comment les autres cartes (orders, theses) appellent l'API sans token
5) Tests directs sans token sur quelques endpoints
"""
import re
import sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
HTML = ROOT / "index.html"
API  = ROOT / "api_server.py"

def section(t):
    print()
    print("=" * 72)
    print(t)
    print("=" * 72)

def main():
    html = HTML.read_text(encoding="utf-8-sig", errors="replace")
    api  = API.read_text(encoding="utf-8-sig", errors="replace") if API.exists() else ""

    # 1) Scripts externes referenced par index.html
    section("1) <script src=...> externes dans index.html")
    srcs = re.findall(r'<script[^>]*\bsrc=[\'"]([^\'"]+)[\'"]', html)
    if srcs:
        for s in srcs:
            print(f"  - {s}")
    else:
        print("  (aucun script externe — tout est inline)")

    # 2) Tous les fetch() dans index.html avec contexte
    section("2) Premiers 30 fetch() dans index.html (chemin + headers)")
    for i, m in enumerate(re.finditer(r'fetch\s*\(\s*[`\'"]([^`\'"]+)[`\'"]', html)):
        if i >= 30:
            print("  (truncated...)")
            break
        url = m.group(1)
        # 200 chars apres pour voir headers
        start = m.start()
        end = min(len(html), m.end() + 250)
        after = html[m.end():end].replace('\n', ' ').replace('\r', ' ')[:200]
        has_auth = 'Authorization' in after or 'Bearer' in after
        flag = "[AUTH]" if has_auth else "      "
        print(f"  {flag} {url}")

    # 3) Fonction api() identifiee comme wrapper — montre son code
    section("3) Code de la fonction 'api' (wrapper)")
    # Cherche `function api(` ou `const api =` ou `api:` ou `var api`
    patterns = [
        r'function\s+api\s*\([^)]*\)\s*{',
        r'const\s+api\s*=\s*async?\s*\([^)]*\)\s*=>\s*{',
        r'const\s+api\s*=\s*function\s*\([^)]*\)\s*{',
        r'async\s+function\s+api\s*\([^)]*\)\s*{',
    ]
    found = False
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            found = True
            # extract jusqu'a fermeture { } equilibree (approx 1500 chars)
            start = m.start()
            end = min(len(html), start + 1500)
            block = html[start:end]
            print(f"--- match @ {start} ---")
            print(block[:1500])
            print("--- end ---")
            break
    if not found:
        print("  Pas de wrapper 'api(...)' clair trouve.")

    # 4) Cote serveur : qui protege quoi (Depends / auth_required) ?
    section("4) Endpoints API_UNIVERSE_V2 — auth-protected ?")
    m = re.search(r'\[API_UNIVERSE_V2_BEGIN\].*?\[API_UNIVERSE_V2_END\]', api, re.DOTALL)
    if m:
        block = m.group(0)
        print(f"Bloc trouve ({len(block)} chars). Lignes definition route :")
        for line in block.splitlines():
            ls = line.strip()
            if ls.startswith('@app.') or 'Depends' in ls or 'def ' in ls and '/api/universe' in block[:block.find(ls)+200]:
                print(f"  {ls[:140]}")
        # extraction lignes route + signatures
        for r in re.finditer(r'@app\.(get|post|put|delete)\([\'"]([^\'"]+)[\'"](.*?)\)\s*\n(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)', block, re.DOTALL):
            method, path, deco_rest, fn, params = r.groups()
            print(f"  {method.upper():6} {path}  ->  {fn}({params.strip()[:200]})")
    else:
        print("  [API_UNIVERSE_V2_*] introuvable dans api_server.py")

    # 5) Pour comparaison : signature d'un endpoint qui MARCHE sans token
    section("5) Comparaison — endpoints /api/orders/pending et /api/theses (signatures)")
    for target in ['/api/orders/pending', '/api/theses', '/api/portfolio/targets', '/api/auth/login']:
        for r in re.finditer(r'@app\.(get|post|put|delete)\([\'"]' + re.escape(target) + r'[\'"](.*?)\)\s*\n(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)', api, re.DOTALL):
            method, deco_rest, fn, params = r.groups()
            print(f"  {method.upper():6} {target}")
            print(f"         def {fn}({params.strip()[:200]})")
            break

    # 6) Cherche Depends usages pour comprendre comment l'auth est appliquee
    section("6) Tous Depends(get_current_user / auth_required / ...) dans api_server.py")
    deps = re.findall(r'Depends\s*\(\s*(\w+)\s*\)', api)
    from collections import Counter
    print("  ", Counter(deps).most_common())

    # 7) Test direct : appel curl-style depuis ce script aux endpoints universe
    section("7) Test HTTP direct (sans token) — verifier 401 reel")
    import urllib.request, urllib.error, json
    base = "http://127.0.0.1:8000"
    for url in [
        "/api/universe/candidates",
        "/api/orders/pending",
        "/api/theses",
        "/api/portfolio/targets",
    ]:
        try:
            req = urllib.request.Request(base + url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = resp.read(200).decode('utf-8', errors='replace')
                print(f"  {resp.status:3d}  {url}  -> {body[:120]}...")
        except urllib.error.HTTPError as e:
            body = e.read(200).decode('utf-8', errors='replace')
            print(f"  {e.code:3d}  {url}  -> {body[:120]}")
        except Exception as e:
            print(f"  ERR  {url}  -> {e}")

if __name__ == "__main__":
    main()
