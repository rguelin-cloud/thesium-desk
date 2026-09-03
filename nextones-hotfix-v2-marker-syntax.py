# -*- coding: utf-8 -*-
"""
HOTFIX: V2 a injecte une ligne avec le marker en clair (sans #) ->
NameError au runtime.

  Mauvais: @app.get("/api/orders/pending-validation")  [ORDERS_PENDING_ENDPOINT_V2]
  Correct: @app.get("/api/orders/pending-validation")  # [ORDERS_PENDING_ENDPOINT_V2]

Idempotent: si la ligne est deja commentee, no-op.
Backup avant ecriture.
"""

import sys
import shutil
import datetime
import ast
from pathlib import Path

P = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py")

BAD = '@app.get("/api/orders/pending-validation")  [ORDERS_PENDING_ENDPOINT_V2]'
GOOD = '@app.get("/api/orders/pending-validation")  # [ORDERS_PENDING_ENDPOINT_V2]'


def main():
    if not P.exists():
        print(f"FAIL: {P} introuvable")
        return 1

    src = P.read_text(encoding="utf-8-sig", errors="replace")

    if BAD not in src:
        if GOOD in src:
            print("[skip] deja corrige (commentaire present)")
            return 0
        print("FAIL: ni la ligne buguee ni la ligne corrigee trouvees")
        print("      Inspecter manuellement la ligne ~715 d'api_server.py")
        return 1

    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = P.with_suffix(P.suffix + f".bak.{ts}")
    shutil.copy2(P, backup)
    print(f"[backup] {backup.name}")

    new_src = src.replace(BAD, GOOD)
    if new_src.count(GOOD) == 0:
        print("FAIL: remplacement n'a rien produit")
        return 1

    # Validation ast
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print(f"FAIL ast.parse ligne {e.lineno}: {e.msg}")
        shutil.copy2(backup, P)
        print("[rollback] backup restaure")
        return 1

    P.write_text(new_src, encoding="utf-8", newline="\n")
    print(f"[write] ligne corrigee, marker en commentaire")

    # Sanity: import simule via compile
    import py_compile
    try:
        py_compile.compile(str(P), doraise=True)
        print("[verify] py_compile OK")
    except Exception as e:
        print(f"FAIL py_compile: {e}")
        return 1

    print("OK - relancer uvicorn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
