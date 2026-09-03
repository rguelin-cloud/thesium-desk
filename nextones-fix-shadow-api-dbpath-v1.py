# -*- coding: utf-8 -*-
"""
FIX [SHADOW_API_V1_FIX_DBPATH] :
DB_PATH n'existe pas en module-level. On reproduit le pattern local
deja utilise a L3439-3440 :

    import sqlite3, os as _os
    DB = _os.environ.get("THESIUM_DB", r"C:\\...\\thesium.db")
    conn = sqlite3.connect(DB, timeout=10.0)

Strategie :
  1. Remplacer ligne 'conn = sqlite3.connect(DB_PATH, ...)' par
     'DB = ...\\n    conn = sqlite3.connect(DB, ...)'
  2. Idempotent : skip si '[SHADOW_API_V1_FIX_DBPATH]' present

Backup + ast + py_compile + marker check.
"""
import os
import sys
import time
import ast
import py_compile
import shutil

API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
MARKER = "[SHADOW_API_V1_FIX_DBPATH]"

OLD_LINE = 'conn = sqlite3.connect(DB_PATH, timeout=10.0)'
NEW_BLOCK = '''import os as _os_shadow  # {marker}
    DB = _os_shadow.environ.get("THESIUM_DB", r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\thesium.db")
    conn = sqlite3.connect(DB, timeout=10.0)'''.format(marker=MARKER)


def log(m):
    print(m, flush=True)


def main():
    if not os.path.exists(API):
        log("[ERR] api_server.py introuvable")
        sys.exit(1)

    with open(API, "rb") as f:
        raw = f.read()
    src = raw.decode("utf-8-sig")

    if MARKER in src:
        log("[SKIP] marker " + MARKER + " deja present.")
        sys.exit(0)

    # Verifier presence cible
    count_old = src.count(OLD_LINE)
    log("[INFO] occurrences de 'sqlite3.connect(DB_PATH, ...)': " + str(count_old))
    if count_old == 0:
        log("[ERR] cible introuvable. Patch deja applique ou code modifie.")
        sys.exit(2)
    if count_old != 2:
        log("[WARN] attendu 2 occurrences, trouve " + str(count_old))

    # Replace all
    new_src = src.replace(OLD_LINE, NEW_BLOCK)

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = API + ".bak." + ts
    shutil.copy2(API, bak)
    log("[OK] backup : " + bak)

    # Write tmp + validate
    tmp = API + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_src)

    try:
        with open(tmp, "rb") as f:
            d = f.read()
        non_ascii = sum(1 for b in d if b > 127)
        log("[CHECK] non-ASCII bytes : " + str(non_ascii))
        ast.parse(d.decode("utf-8"))
        log("[CHECK] ast.parse OK")
        py_compile.compile(tmp, doraise=True)
        log("[CHECK] py_compile OK")
    except Exception as e:
        log("[ERR] validation echouee : " + repr(e))
        os.remove(tmp)
        sys.exit(3)

    os.replace(tmp, API)
    log("[OK] api_server.py patche.")

    # Verifier marker present
    with open(API, "rb") as f:
        d2 = f.read()
    if MARKER.encode() in d2:
        n = d2.count(MARKER.encode())
        log("[OK] marker " + MARKER + " present " + str(n) + " fois.")
    else:
        log("[WARN] marker non trouve apres swap.")

    log("")
    log("FIX [SHADOW_API_V1_FIX_DBPATH] DONE")
    log("Backup     : " + bak)
    log("Action     : uvicorn auto-reload doit recharger automatiquement.")
    log("Si pas auto-reload, redemarrer uvicorn manuellement.")


if __name__ == "__main__":
    main()
