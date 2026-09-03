"""
[ROW_FACTORY_CONSTRUCTION_V1]

Fix : conn.row_factory = sqlite3.Row dans api_server_with_static.py handler
      run_construction est mal place (dans except, apres 'pass;') donc
      jamais execute en cas normal -> jalon2 recoit tuples -> row["n"] crash.

Cible : api_server_with_static.py
Avant :
    except Exception:
        pass; conn.row_factory = sqlite3.Row

Apres :
    except Exception:
        pass
    conn.row_factory = sqlite3.Row  # [ROW_FACTORY_CONSTRUCTION_V1]

Idempotent : detecte la presence du marker et skip si deja patche.
ASCII pur. AST valide. Backup .bak.<ts>.
"""
import os
import re
import sys
import ast
import time
import shutil
import py_compile

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET   = os.path.join(PROD_DIR, "api_server_with_static.py")
MARKER   = "[ROW_FACTORY_CONSTRUCTION_V1]"


def main():
    if not os.path.isfile(TARGET):
        print("[ERR] target not found : " + TARGET)
        sys.exit(2)

    with open(TARGET, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER in src:
        print("[SKIP] marker already present : " + MARKER)
        return

    # Pattern exact (avec 'pass; conn.row_factory')
    pattern = re.compile(
        r"(\n    except Exception:\n)"
        r"(        pass; conn\.row_factory = sqlite3\.Row\n)"
    )

    m = pattern.search(src)
    if not m:
        # Fallback : chercher 'pass; conn.row_factory'
        if "pass; conn.row_factory = sqlite3.Row" not in src:
            print("[ERR] pattern not found, manual inspection needed.")
            print("[ERR] cherche : 'pass; conn.row_factory = sqlite3.Row'")
            sys.exit(3)
        replacement_src = src.replace(
            "        pass; conn.row_factory = sqlite3.Row\n",
            "        pass\n"
            "    conn.row_factory = sqlite3.Row  # " + MARKER + "\n",
            1,
        )
    else:
        replacement = (
            m.group(1)
            + "        pass\n"
            + "    conn.row_factory = sqlite3.Row  # " + MARKER + "\n"
        )
        replacement_src = src[:m.start()] + replacement + src[m.end():]

    # Validation AST
    try:
        ast.parse(replacement_src)
    except SyntaxError as e:
        print("[ERR] AST parse failed : " + str(e))
        sys.exit(4)

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = TARGET + ".bak." + ts
    shutil.copy2(TARGET, bak)
    print("[BACKUP] " + bak)

    # Ecriture utf-8 sans BOM
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(replacement_src)

    # py_compile
    try:
        py_compile.compile(TARGET, doraise=True)
    except py_compile.PyCompileError as e:
        print("[ERR] py_compile failed : " + str(e))
        print("[ROLLBACK] restoring backup")
        shutil.copy2(bak, TARGET)
        sys.exit(5)

    # Verifier le resultat
    with open(TARGET, "r", encoding="utf-8-sig") as f:
        verify = f.read()
    if MARKER not in verify:
        print("[ERR] marker not found after write")
        sys.exit(6)
    if "pass; conn.row_factory" in verify:
        print("[ERR] old pattern still present after write")
        sys.exit(7)

    print("[OK] patch applied : " + MARKER)
    print("[NEXT] restart API :")
    print("       Get-NetTCPConnection -LocalPort 8000 | "
          "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }")
    print("       py -3.13 -m uvicorn api_server_with_static:app "
          "--host 0.0.0.0 --port 8000")


if __name__ == "__main__":
    main()
