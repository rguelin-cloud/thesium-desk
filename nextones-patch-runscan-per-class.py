# -*- coding: utf-8 -*-
"""
nextones-patch-runscan-per-class.py
Patche universe_expansion_agent.py pour ranker run_scan() PAR CLASSE
(crypto / etf / equity) au lieu d'un top global.

AVANT (L770-772) :
    _normalize_features(kept)
    kept.sort(key=lambda f: -f.score)
    top = kept[:top_n]

APRES :
    _normalize_features(kept)
    # [TOP_N_PER_CLASS_V1] Ranker par classe pour preserver diversification
    by_class: dict[str, list] = {}
    for f in kept:
        by_class.setdefault(f.asset_class, []).append(f)
    top = []
    for cls, items in by_class.items():
        items.sort(key=lambda f: -f.score)
        top.extend(items[:top_n])
    top.sort(key=lambda f: -f.score)

Idempotent via marker [TOP_N_PER_CLASS_V1].
Backup automatique.
"""

import os, re, shutil, sys, ast, py_compile
from datetime import datetime

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
AGENT = os.path.join(ROOT, "universe_expansion_agent.py")
MARKER = "[TOP_N_PER_CLASS_V1]"

def section(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)

def main():
    if not os.path.exists(AGENT):
        print(f"[ERREUR] {AGENT} introuvable")
        sys.exit(1)

    section("1) Lecture fichier")
    with open(AGENT, "r", encoding="utf-8-sig") as f:
        src = f.read()
    print(f"  Taille : {len(src)} chars, {src.count(chr(10))+1} lignes")

    if MARKER in src:
        print(f"  [SKIP] Marker {MARKER} deja present, patch deja applique.")
        return

    section("2) Backup")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = AGENT + f".bak.topnperclass.{ts}"
    shutil.copy2(AGENT, backup)
    print(f"  Backup : {backup}")

    section("3) Recherche du bloc a remplacer")
    # On cible le bloc exact :
    #     kept.sort(key=lambda f: -f.score)
    #     top = kept[:top_n]
    old = (
        "        _normalize_features(kept)\n"
        "        kept.sort(key=lambda f: -f.score)\n"
        "        top = kept[:top_n]\n"
    )
    if old not in src:
        # Tente avec variation espaces
        pat = re.compile(
            r"(\s*)_normalize_features\(kept\)\s*\n"
            r"(\s*)kept\.sort\(key=lambda f: -f\.score\)\s*\n"
            r"(\s*)top\s*=\s*kept\[:top_n\]\s*\n"
        )
        m = pat.search(src)
        if not m:
            print("  [ERREUR] Bloc a patcher introuvable. Abort.")
            print("  Recherche pattern fuzzy :")
            for i, line in enumerate(src.splitlines(), 1):
                if "kept[:top_n]" in line or "kept.sort" in line:
                    print(f"    L{i}: {line!r}")
            sys.exit(2)
        old = m.group(0)
        indent = m.group(1).replace("\n", "") or "        "
        print(f"  Pattern trouve via regex, indent='{indent}'")
    else:
        indent = "        "
        print(f"  Pattern trouve exact match, indent='{indent}'")

    new = (
        f"{indent}_normalize_features(kept)\n"
        f"{indent}# {MARKER} Ranker par classe (crypto/etf/equity) pour preserver diversification\n"
        f"{indent}by_class: dict[str, list] = {{}}\n"
        f"{indent}for f in kept:\n"
        f"{indent}    by_class.setdefault(f.asset_class, []).append(f)\n"
        f"{indent}top = []\n"
        f"{indent}for _cls, _items in by_class.items():\n"
        f"{indent}    _items.sort(key=lambda f: -f.score)\n"
        f"{indent}    top.extend(_items[:top_n])\n"
        f"{indent}top.sort(key=lambda f: -f.score)\n"
        f"{indent}log.info('%s top_n_per_class : %s', MARKER, "
        f"{{c: len([f for f in top if f.asset_class==c]) for c in by_class}})\n"
    )

    section("4) Application du patch")
    new_src = src.replace(old, new, 1)
    if new_src == src:
        print("  [ERREUR] Replace n'a rien change. Abort.")
        sys.exit(3)
    print(f"  Delta : +{len(new_src)-len(src)} chars")

    section("5) Validation syntaxe avant ecriture")
    try:
        ast.parse(new_src)
        print("  [OK] ast.parse")
    except SyntaxError as e:
        print(f"  [ERREUR] SyntaxError : {e}")
        sys.exit(4)

    # Ecriture
    with open(AGENT, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_src)
    print(f"  Ecrit : {AGENT}")

    # py_compile
    try:
        py_compile.compile(AGENT, doraise=True)
        print("  [OK] py_compile")
    except py_compile.PyCompileError as e:
        print(f"  [ERREUR] py_compile : {e}")
        print(f"  Restauration backup : {backup}")
        shutil.copy2(backup, AGENT)
        sys.exit(5)

    section("6) Verification marker")
    with open(AGENT, "r", encoding="utf-8") as f:
        verif = f.read()
    if MARKER in verif:
        print(f"  [OK] Marker {MARKER} present")
        for i, line in enumerate(verif.splitlines(), 1):
            if MARKER in line:
                print(f"    L{i}: {line.strip()[:120]}")
    else:
        print(f"  [WARN] Marker absent apres ecriture, etrange")

    section("PROCHAINES ETAPES")
    print("""
  1) REDEMARRER uvicorn (IMPERATIF, cache module) :
     Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {Stop-Process -Id $_.OwningProcess -Force}
     Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue   # doit etre vide
     Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk; py -3.13 -m uvicorn api_server:app --host 0.0.0.0 --port 8000"

  ATTENTION : api_server.py (PAS api_server_with_static.py qui ne contient pas les endpoints universe)

  2) Login + scan :
     Start-Sleep -Seconds 5
     $tok = (Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/auth/login" -Body '{"username":"rguelin","password":"Thesium2026!"}' -ContentType "application/json").access_token
     $res = Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/universe/scan" -Headers @{Authorization="Bearer $tok"}
     $res | ConvertTo-Json -Depth 5

  3) Verifier REET present :
     py -3.13 .\\nextones-check-reet-status.py

  ATTENDU :
   - Le scan retourne environ 5+5+5 = 15 candidats (5 par classe)
   - REET present avec score / mom / sharpe calcules
""")

if __name__ == "__main__":
    main()
