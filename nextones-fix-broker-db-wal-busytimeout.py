# -*- coding: utf-8 -*-
# [NEXTONES-FIX-BROKER-DB-WAL-BUSYTIMEOUT-V1]
# Corrige le probleme 'database is locked' qui bloque execute_shadow et risk_v2 :
#  1) active PRAGMA journal_mode=WAL une fois pour toutes sur thesium.db
#     (compatible avec l'API en marche, persistant a travers les restarts)
#  2) patche les 4 modules broker (resolver, order-translator, risk-broker-check,
#     shadow-executor) pour ajouter PRAGMA busy_timeout=10000 + timeout sqlite3.connect
#  3) rollback : --rollback (restaure les .bak)
#
# Idempotent : detecte si deja patche via marker.

import argparse
import ast
import os
import py_compile
import re
import shutil
import sqlite3
import sys
import time

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(PROD_DIR, "thesium.db")
MARKER = "# [NEXTONES-BROKER-DB-HARDENED-V1]"

MODULES = [
    "nextones-broker-resolver.py",
    "nextones-order-translator.py",
    "nextones-risk-broker-check.py",
    "nextones-broker-shadow-executor.py",
]


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


# ----------------------------- WAL -----------------------------
def enable_wal():
    banner("[1] Active WAL sur thesium.db")
    c = sqlite3.connect(DB, timeout=10.0)
    try:
        before = c.execute("PRAGMA journal_mode").fetchone()[0]
        print(f"  mode actuel : {before}")
        if before.upper() == "WAL":
            print("  [OK] deja en WAL")
            return True
        # Bascule
        after = c.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        print(f"  nouveau mode : {after}")
        if after.upper() != "WAL":
            print(f"  [FAIL] basculement refuse (mode reste {after}) "
                  f"-> sans doute des connexions actives sur DELETE journal")
            print("  Conseil : arreter brievement l'API puis relancer ce script")
            return False
        print("  [OK] WAL active")
        return True
    finally:
        c.close()


# ----------------------------- patch module -----------------------------
def patch_module(path):
    if not os.path.exists(path):
        print(f"  [SKIP] {os.path.basename(path)} (introuvable)")
        return False
    with open(path, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER in src:
        print(f"  [SKIP] {os.path.basename(path)} (deja patche)")
        return False

    # Strategie : on intercale, juste apres chaque sqlite3.connect(...),
    # un appel a un helper qui set busy_timeout=10000.
    # Implementation simple : on remplace les "sqlite3.connect(<args>)" qui n'ont
    # pas deja un argument 'timeout=' par "sqlite3.connect(<args>, timeout=10.0)".
    # Puis on insere juste apres l'instruction d'assignation un setter PRAGMA.
    #
    # Pour rester robuste, on injecte plutot un helper en debut de module +
    # on remplace les appels via regex simple.

    helper = (
        "\n" + MARKER + "\n"
        "import sqlite3 as _sq_nx_h\n"
        "def _nx_open_db(_p, **_kw):\n"
        "    _kw.setdefault('timeout', 10.0)\n"
        "    _c = _sq_nx_h.connect(_p, **_kw)\n"
        "    try:\n"
        "        _c.execute('PRAGMA busy_timeout=10000')\n"
        "    except Exception:\n"
        "        pass\n"
        "    return _c\n"
    )

    # Trouve la fin de la zone d'imports
    lines = src.split("\n")
    insert_at = 0
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("import ") or s.startswith("from "):
            insert_at = i + 1
        elif s.startswith("#") or s == "":
            continue
        else:
            break
    # Insere le helper juste apres les imports
    lines.insert(insert_at, helper)
    new_src = "\n".join(lines)

    # Remplace les sqlite3.connect(...) qui n'ont pas deja timeout=
    # Pattern : sqlite3.connect(  <args sans 'timeout=' inside>  )
    # Simple : si la ligne contient "timeout=" on ne touche pas.
    def fixup(m):
        full = m.group(0)
        if "timeout=" in full:
            return full
        # Remplace par _nx_open_db(...)
        # Conserve les arguments tels quels
        return full.replace("sqlite3.connect(", "_nx_open_db(")

    # Pattern simple sur chaque ligne (evite multiline)
    fixed_lines = []
    for ln in new_src.split("\n"):
        if "sqlite3.connect(" in ln and "timeout=" not in ln:
            ln = ln.replace("sqlite3.connect(", "_nx_open_db(")
        fixed_lines.append(ln)
    new_src = "\n".join(fixed_lines)

    # Validation ast.parse + py_compile sur un tmp
    tmp = path + ".tmp.fix"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_src)
    try:
        ast.parse(new_src)
        py_compile.compile(tmp, doraise=True)
    except Exception as e:
        os.remove(tmp)
        print(f"  [FAIL] {os.path.basename(path)} : validation ast/py_compile -> {e}")
        return False

    # Backup
    bak = f"{path}.bak.{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copyfile(path, bak)
    # Apply
    shutil.move(tmp, path)
    print(f"  [OK] {os.path.basename(path)} patche (backup : {os.path.basename(bak)})")
    return True


def patch_all():
    banner("[2] Patch des 4 modules broker")
    any_ok = False
    for m in MODULES:
        p = os.path.join(PROD_DIR, m)
        print(f"\n  -- {m}")
        if patch_module(p):
            any_ok = True
    return any_ok


# ----------------------------- rollback -----------------------------
def rollback():
    banner("[ROLLBACK] Restaure les .bak les plus recents")
    for m in MODULES:
        p = os.path.join(PROD_DIR, m)
        if not os.path.exists(p):
            continue
        baks = sorted(
            [f for f in os.listdir(PROD_DIR)
             if f.startswith(m + ".bak.")],
            reverse=True,
        )
        if not baks:
            print(f"  [SKIP] {m} : aucun .bak")
            continue
        latest = os.path.join(PROD_DIR, baks[0])
        shutil.copyfile(latest, p)
        print(f"  [OK] {m} restaure depuis {baks[0]}")


# ----------------------------- main -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--skip-wal", action="store_true",
                    help="ne pas (re)activer WAL (utile si echec a l'etape 1)")
    args = ap.parse_args()

    if args.rollback:
        rollback()
        return

    if not args.skip_wal:
        if not enable_wal():
            print("\n[ABORT] WAL non actif, le patch des modules seul ne suffira pas")
            print("Re-essayer apres avoir arrete l'API, ou passer --skip-wal")
            sys.exit(1)

    patched = patch_all()

    banner("[VERDICT]")
    if patched:
        print("  [OK] patch applique. Re-lancer :")
        print("    py -3.13 nextones-validate-shadow-wired.py")
    else:
        print("  [INFO] aucun module n'a ete modifie (deja patches ?)")


if __name__ == "__main__":
    main()
