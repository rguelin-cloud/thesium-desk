# -*- coding: utf-8 -*-
# nextones-fix-memo-verdict-reason-v3.py  (rev3)
#
# Strategie rev3 :
#   - On ne match PLUS sur le marker V1 (ambigu : present 2x dont 1 commentaire
#     d'en-tete du helper).
#   - On match directement sur la signature UNIQUE du bloc bugue :
#       "_details_for_humanize = o.get(...)" ... jusqu'a "verdict = ..."
#   - Le marker V1 ligne juste au-dessus est preserve tel quel (on ne le touche pas).
#
# Pre-requis : le fichier doit etre RESTAURE depuis un backup propre avant exec
#              (le rev2 a casse le fichier en l'amputant du helper).
#
# Verifie aussi :
#   - Que le helper _humanize_block_reason est present (sinon abandon)
#   - Que la fonction _build_risk_v2_section est presente (sinon abandon)

import os
import re
import ast
import sys
import time
import shutil
import py_compile
import tempfile

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\memo_generator.py"

MARKER_V1 = "[MEMO_VERDICT_REASON_FIX_V1]"
MARKER_V2 = "[MEMO_VERDICT_REASON_FIX_V2]"


def read_file(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_file_atomic(path, content):
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".memo_v3_", suffix=".tmp", dir=d)
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        py_compile.compile(tmp, doraise=True)
        shutil.move(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def main():
    if not os.path.exists(TARGET):
        print("ERREUR : fichier introuvable : " + TARGET)
        sys.exit(2)

    src = read_file(TARGET)
    print("Taille fichier : " + str(len(src)) + " bytes")

    # --- Verifications d'integrite (le fichier doit etre sain) ---
    if "def _humanize_block_reason" not in src:
        print("ERREUR : helper _humanize_block_reason absent.")
        print("        Le fichier est probablement casse par le rev2.")
        print("        RESTAURER depuis le backup le plus recent :")
        print("        Get-ChildItem .\\memo_generator.py.bak.* | Sort-Object LastWriteTime -Descending | Select-Object -First 1")
        sys.exit(3)

    if "def _build_risk_v2_section" not in src:
        print("ERREUR : _build_risk_v2_section absent. Fichier corrompu.")
        sys.exit(4)

    if MARKER_V2 in src:
        print("OK : " + MARKER_V2 + " deja present -> aucun changement (idempotent)")
        sys.exit(0)

    if MARKER_V1 not in src:
        print("ERREUR : " + MARKER_V1 + " absent. Patch v1 requis avant v3.")
        sys.exit(5)

    # --- Recherche du bloc bugue par signature UNIQUE ---
    # Le bloc bugue commence par :
    #   _details_for_humanize = o.get("details_json") if isinstance(o, dict) else None
    # et se termine par :
    #   verdict = "PASS" if passed else ("BLOCK - " + _short_r)
    #
    # On capture aussi l'indentation de la 1ere ligne pour la reutiliser.

    pattern = re.compile(
        r"([ \t]+)_details_for_humanize\s*=\s*o\.get\([^\n]+\n"   # ligne 1 + indent
        r"(?:[ \t]*[^\n]*\n)*?"                                    # corps lazy
        r"[ \t]*verdict\s*=\s*\"PASS\"[^\n]+\n",                   # ligne verdict =
        re.MULTILINE,
    )

    m = pattern.search(src)
    if not m:
        print("ERREUR : bloc bugue introuvable.")
        print("        Signature attendue : _details_for_humanize = o.get(...) ... verdict = \"PASS\" ...")
        # Diag : montrer les lignes contenant _details_for_humanize
        for i, ln in enumerate(src.splitlines(), 1):
            if "_details_for_humanize" in ln:
                print("  L" + str(i) + " : " + ln)
        sys.exit(6)

    indent = m.group(1)
    old_block = m.group(0)
    print("Bloc bugue trouve, indent=" + repr(indent) + " (" + str(len(indent)) + " chars), taille=" + str(len(old_block)) + " chars")
    print("--- ANCIEN BLOC ---")
    for ln in old_block.splitlines():
        print("  " + ln)
    print("--- FIN ---")

    # Verifier que l'indent est bien 8 espaces (corps boucle for o in orders)
    if indent != "        ":
        print("ATTENTION : indent inhabituelle (" + repr(indent) + "), attendu 8 espaces.")
        # On ne bloque pas, on garde l'indent capturee

    # --- Nouveau bloc V2 ---
    # On remplace SEULEMENT le contenu bugue (pas le commentaire marker V1 au-dessus).
    new_block = (
        indent + "# [MEMO_VERDICT_REASON_FIX_V2] motif lisible depuis risk_v2.details_json\n"
        + indent + "_details_for_humanize = v2.get(\"details_json\") if isinstance(v2, dict) else None\n"
        + indent + "_short_r, _long_r = _humanize_block_reason(blocked, _details_for_humanize)\n"
        + indent + "verdict = \"PASS\" if passed else (\"BLOCK - \" + _short_r)\n"
    )

    print("--- NOUVEAU BLOC ---")
    for ln in new_block.splitlines():
        print("  " + ln)
    print("--- FIN ---")

    new_src = src[:m.start()] + new_block + src[m.end():]

    if MARKER_V2 not in new_src:
        print("ERREUR : marker V2 absent apres substitution.")
        sys.exit(7)

    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print("ERREUR AST : " + str(e))
        new_lines = new_src.splitlines()
        approx_line = src[:m.start()].count("\n") + 1
        print("Zone modifiee autour ligne " + str(approx_line) + ":")
        a = max(0, approx_line - 4)
        b = min(len(new_lines), approx_line + 10)
        for i in range(a, b):
            print("  " + str(i + 1).rjust(4) + " | " + new_lines[i])
        sys.exit(8)

    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = TARGET + ".bak." + ts
    shutil.copy2(TARGET, bak)
    print("Backup : " + bak)

    write_file_atomic(TARGET, new_src)
    print("OK : " + TARGET + " patche -> " + MARKER_V2)
    print("Taille apres : " + str(len(new_src)) + " bytes")
    print("")
    print("PROCHAINES ETAPES :")
    print("  1) Restart API :")
    print("     Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }")
    print("     py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print("  2) Rouvrir le memo IC -> verdict attendu :")
    print("     BLOCK - Non tradable (regle A)")


if __name__ == "__main__":
    main()
