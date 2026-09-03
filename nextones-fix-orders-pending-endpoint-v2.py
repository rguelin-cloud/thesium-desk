# -*- coding: utf-8 -*-
"""
nextones-fix-orders-pending-endpoint-v2.py

Corrige le bug V1 : le wrapper *args/**kwargs etait interprete par FastAPI comme
des query params (-> 422 Field required).

Strategie V2:
  - Retire le bloc V1 (wrapper).
  - Ajoute un SECOND decorateur @app.get("/api/orders/pending-validation")
    juste AU-DESSUS du decorateur existant de list_pending_orders.
  - FastAPI cree alors 2 routes pointant sur la MEME fonction, avec la meme
    signature -> Depends(require_manager) fonctionne, pas de wrapper.

Marker V2 idempotent: [ORDERS_PENDING_ENDPOINT_V2]
Si V1 est present, il est retire. Si V2 est deja present, no-op.

Backup: api_server.py.bak.YYYYMMDDTHHMMSS
"""

import re
import sys
import shutil
import datetime
from pathlib import Path

API_SERVER = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py")
MARKER_V1_BEGIN = "[ORDERS_PENDING_ENDPOINT_V1] BEGIN"
MARKER_V1_END = "[ORDERS_PENDING_ENDPOINT_V1] END"
MARKER_V2 = "[ORDERS_PENDING_ENDPOINT_V2]"

NEW_DECORATOR_LINE = (
    '@app.get("/api/orders/pending-validation")  ' + MARKER_V2 + "\n"
)


def main():
    if not API_SERVER.exists():
        print(f"FAIL: {API_SERVER} introuvable")
        return 1

    src = API_SERVER.read_text(encoding="utf-8-sig", errors="replace")
    original = src

    # 1. Backup
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = API_SERVER.with_suffix(API_SERVER.suffix + f".bak.{ts}")
    shutil.copy2(API_SERVER, backup)
    print(f"[backup] {backup.name}")

    # 2. Si V2 deja en place -> rien a faire
    if MARKER_V2 in src:
        print("[skip] marker V2 deja present, aucune modification")
        return 0

    # 3. Retirer le bloc V1 s'il existe (entre les deux markers, lignes inclues)
    if MARKER_V1_BEGIN in src and MARKER_V1_END in src:
        pat_v1 = re.compile(
            r"\n?#\s*-+\s*\[ORDERS_PENDING_ENDPOINT_V1\]\s*BEGIN.*?"
            r"\[ORDERS_PENDING_ENDPOINT_V1\]\s*END[^\n]*\n",
            re.DOTALL,
        )
        new_src, n = pat_v1.subn("\n", src)
        if n == 0:
            print("[warn] markers V1 trouves mais regex n'a pas matche le bloc")
        else:
            print(f"[v1-remove] {n} bloc(s) V1 supprime(s)")
            src = new_src

    # 4. Trouver le decorateur existant @app.get("/api/orders/pending") et inserer
    #    la nouvelle ligne juste au-dessus.
    dec_pat = re.compile(
        r'(^[ \t]*@app\.get\(\s*["\']/api/orders/pending["\']\s*\)\s*\n)',
        re.MULTILINE,
    )
    m = dec_pat.search(src)
    if not m:
        print("FAIL: decorateur @app.get('/api/orders/pending') introuvable")
        return 1

    insert_pos = m.start()
    src = src[:insert_pos] + NEW_DECORATOR_LINE + src[insert_pos:]
    print(f"[insert] decorateur V2 ajoute avant le decorateur original")

    # 5. Validation syntaxe avant ecriture
    import ast
    try:
        ast.parse(src)
    except SyntaxError as e:
        print(f"FAIL: ast.parse erreur ligne {e.lineno}: {e.msg}")
        # Restaurer le backup
        shutil.copy2(backup, API_SERVER)
        print(f"[rollback] backup restaure")
        return 1

    if src == original:
        print("[noop] aucun changement applique")
        return 0

    # 6. Ecriture utf-8 sans BOM
    API_SERVER.write_text(src, encoding="utf-8", newline="\n")
    print(f"[write] {API_SERVER.name} sauvegarde ({len(src)} chars)")

    # 7. Verification post-ecriture
    re_read = API_SERVER.read_text(encoding="utf-8-sig", errors="replace")
    if MARKER_V2 not in re_read:
        print("FAIL: marker V2 absent apres ecriture")
        return 1
    if MARKER_V1_BEGIN in re_read:
        print("WARN: marker V1 BEGIN encore present apres nettoyage")
    print("[verify] marker V2 confirme dans le fichier")
    print("OK - relancer uvicorn maintenant")
    return 0


if __name__ == "__main__":
    sys.exit(main())
