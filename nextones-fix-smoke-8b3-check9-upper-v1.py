# -*- coding: utf-8 -*-
# nextones-fix-smoke-8b3-check9-upper-v1.py
# Fix check 9 du smoke-test 8B.3 : utilise UPPER(side) pour etre robuste
# au stockage lowercase ('buy'/'sell') de replay_fills.side (heritage
# fill_simulator.py) tout en restant compatible avec replay_orders.side
# stocke en uppercase.
#
# Marker : # [SMOKE_8B3_CHECK9_UPPER_V1]
# Idempotent. Backup .py.bak.<timestamp>.
# 100% ASCII. ast.parse + py_compile.

import ast
import os
import py_compile
import shutil
import sys
import tempfile
from datetime import datetime

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\nextones-run-replay-8b3-v2.py"
MARKER = "[SMOKE_8B3_CHECK9_UPPER_V1]"


def _read_utf8_sig(path):
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")


def _write_utf8_nobom(path, content):
    with open(path, "wb") as f:
        f.write(content.encode("utf-8"))


def _validate_ascii(content, label):
    bad = [(i, ord(c)) for i, c in enumerate(content) if ord(c) > 127]
    if bad[:5]:
        print(f"FAIL {label} : non-ASCII : {bad[:5]}")
        sys.exit(1)


def _validate_python(content, label):
    try:
        ast.parse(content)
    except SyntaxError as e:
        print(f"FAIL {label} ast.parse : {e}")
        sys.exit(1)
    tmp = tempfile.NamedTemporaryFile("wb", delete=False, suffix=".py")
    tmp.write(content.encode("utf-8"))
    tmp.close()
    try:
        py_compile.compile(tmp.name, doraise=True)
    except py_compile.PyCompileError as e:
        print(f"FAIL {label} py_compile : {e}")
        sys.exit(1)
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def main():
    if not os.path.exists(TARGET):
        print(f"FAIL : target not found : {TARGET}")
        sys.exit(1)

    src = _read_utf8_sig(TARGET)

    if MARKER in src:
        print(f"SKIP : marker {MARKER} already present")
        _validate_python(src, "current")
        print("OK   : file is valid Python.")
        return

    # Remplacement cible : toutes occurrences de "side='BUY'" et "side='SELL'"
    # (avec apostrophes simples ou doubles) dans la query du check 9.
    # On localise le bloc check 9 par son label "9. Integrity" pour eviter
    # de toucher des references ailleurs.

    # Strategie sure : remplacer 4 patterns explicites (single + double quotes)
    replacements = [
        ("side='BUY'",  "UPPER(side)='BUY'"),
        ('side="BUY"',  'UPPER(side)="BUY"'),
        ("side='SELL'", "UPPER(side)='SELL'"),
        ('side="SELL"', 'UPPER(side)="SELL"'),
    ]

    patched = src
    n_repl = 0
    for old, new in replacements:
        # On evite les doubles patches : ne remplace que si l'occurrence
        # n'est pas deja precedee de "UPPER(".
        idx = 0
        while True:
            pos = patched.find(old, idx)
            if pos == -1:
                break
            # check qu'on n'est pas deja sur "UPPER(side..."
            preceding = patched[max(0, pos - 7):pos]
            if preceding.endswith("UPPER("):
                idx = pos + len(old)
                continue
            patched = patched[:pos] + new + patched[pos + len(old):]
            n_repl += 1
            idx = pos + len(new)

    if n_repl == 0:
        print("WARN : no 'side=BUY/SELL' patterns found. Check naming.")
        # On force quand meme l'ajout du marker pour idempotence si futur run.
        # Mais ici on prefere stopper pour eviter de marquer un fichier non modifie.
        print("FAIL : aborting (nothing to patch)")
        sys.exit(2)

    # Inject marker comme commentaire en tete (apres shebang/encoding)
    marker_line = f"# {MARKER} - check 9 utilise UPPER(side)\n"
    # Insertion juste apres la ligne d'encoding ou en tete sinon
    lines = patched.splitlines(keepends=True)
    insert_at = 0
    for i, ln in enumerate(lines[:5]):
        if "coding" in ln or ln.startswith("#!"):
            insert_at = i + 1
    lines.insert(insert_at, marker_line)
    patched = "".join(lines)

    _validate_ascii(patched, "patched")
    _validate_python(patched, "patched")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = TARGET + ".bak." + ts
    shutil.copy2(TARGET, bak)
    print(f"BACKUP : {bak}")

    _write_utf8_nobom(TARGET, patched)
    print(f"WRITE  : {TARGET} ({len(patched)} chars, {n_repl} substitutions)")

    final = _read_utf8_sig(TARGET)
    if MARKER not in final:
        print("FAIL : marker missing after write")
        sys.exit(1)
    _validate_python(final, "post-write")
    print(f"OK     : marker present, {n_repl} side=... -> UPPER(side)=...")
    print("DONE   : relance py -3.13 .\\nextones-run-replay-8b3-v2.py")


if __name__ == "__main__":
    main()
