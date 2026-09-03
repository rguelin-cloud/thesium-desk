# -*- coding: utf-8 -*-
# [ORDERS_PENDING_ENDPOINT_V1]
# Ajoute l'endpoint GET /api/orders/pending-validation dans api_server.py
# (alias de /api/orders/pending - le UI appelle pending-validation, l'endpoint
# existant s'appelle pending).
#
# Strategie : copier la signature de /api/orders/pending et creer un alias.
# Validation : ast.parse + py_compile + backup.
# Idempotent : marker [ORDERS_PENDING_ENDPOINT_V1] verifie.
import ast
import os
import py_compile
import re
import shutil
import sys
from datetime import datetime

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")
MARKER = "[ORDERS_PENDING_ENDPOINT_V1]"


def main():
    if not os.path.isfile(TARGET):
        print("[KO] cible introuvable : " + TARGET)
        sys.exit(1)

    with open(TARGET, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER in src:
        print("[SKIP] marker {} deja present".format(MARKER))
        return

    # Backup
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = TARGET + ".bak." + ts
    shutil.copy2(TARGET, backup)
    print("[OK] backup -> " + backup)

    # Trouver l'endpoint /api/orders/pending pour copier sa logique
    # Pattern : @app.get("/api/orders/pending") ... def NAME(...): ... return ...
    pat = re.compile(
        r"(@app\.get\([\"']/api/orders/pending[\"']\).*?\n"
        r"(?:async\s+)?def\s+(\w+)\s*\([^)]*\)[^:]*:.*?)"
        r"(?=\n@app\.|\nasync def |\ndef |\Z)",
        re.DOTALL,
    )
    m = pat.search(src)
    if not m:
        print("[KO] endpoint /api/orders/pending introuvable - aucun modele")
        sys.exit(1)
    existing_block = m.group(1)
    existing_fn_name = m.group(2)
    print("[OK] endpoint modele trouve : def {} ({} lignes)".format(
        existing_fn_name, existing_block.count("\n") + 1))

    # Generer un alias : meme corps, decorateur different + nom de fonction different
    # Strategie simple : decorateur supplementaire avant le @app.get existant
    # FastAPI permet d'empiler plusieurs decorateurs sur la meme fonction
    # MAIS plus propre : creer une seconde fonction qui appelle la premiere
    alias_block = (
        "\n\n# ---------------------------------------------------------------- "
        + MARKER + " BEGIN\n"
        + "@app.get(\"/api/orders/pending-validation\")\n"
        + "async def {}_alias_pending_validation(*args, **kwargs):\n".format(existing_fn_name)
        + "    \"\"\"Alias de /api/orders/pending pour compatibilite UI.\"\"\"\n"
        + "    return await {}(*args, **kwargs)\n".format(existing_fn_name)
        + "# ---------------------------------------------------------------- "
        + MARKER + " END\n"
    )

    # Verifier que la fonction modele est async
    if "async def " + existing_fn_name not in src:
        # Si non async, generer sans await
        alias_block = (
            "\n\n# ---------------------------------------------------------------- "
            + MARKER + " BEGIN\n"
            + "@app.get(\"/api/orders/pending-validation\")\n"
            + "def {}_alias_pending_validation(*args, **kwargs):\n".format(existing_fn_name)
            + "    \"\"\"Alias de /api/orders/pending pour compatibilite UI.\"\"\"\n"
            + "    return {}(*args, **kwargs)\n".format(existing_fn_name)
            + "# ---------------------------------------------------------------- "
            + MARKER + " END\n"
        )
        print("[INFO] fonction modele non-async, generation alias sync")
    else:
        print("[INFO] fonction modele async, generation alias async")

    # Inserer juste apres le bloc existant
    insertion_point = m.end()
    src2 = src[:insertion_point] + alias_block + src[insertion_point:]

    # Validation
    try:
        ast.parse(src2)
        print("[OK] ast.parse")
    except SyntaxError as e:
        print("[KO] ast.parse echoue : {}".format(e))
        with open(TARGET + ".broken", "w", encoding="utf-8") as f:
            f.write(src2)
        sys.exit(1)

    # Ecriture
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(src2)
    print("[OK] ecriture - taille = {} chars".format(len(src2)))

    try:
        py_compile.compile(TARGET, doraise=True)
        print("[OK] py_compile")
    except py_compile.PyCompileError as e:
        print("[KO] py_compile echoue : {}".format(e))
        sys.exit(1)

    print()
    print("=" * 60)
    print("PATCH APPLIED - {}".format(MARKER))
    print("=" * 60)
    print("Redemarrer uvicorn pour activer.")
    print()
    print("Test apres restart :")
    print("  $tok = (Invoke-RestMethod -Method POST -Uri \\")
    print("    \"http://localhost:8000/api/auth/login\" -ContentType \\")
    print("    \"application/json\" -Body '{{\"username\":\"rguelin\",\\")
    print("    \"password\":\"Thesium2026!\"}}').access_token")
    print("  Invoke-RestMethod -Method GET -Uri \\")
    print("    \"http://localhost:8000/api/orders/pending-validation\" \\")
    print("    -Headers @{{Authorization=\"Bearer $tok\"}}")


if __name__ == "__main__":
    main()
