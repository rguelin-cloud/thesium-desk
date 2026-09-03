#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# [ANTI_DUPLICATE_ORDER_V1]
# Patch execution_engine.py create_and_execute_order :
# avant l INSERT INTO orders (L1263), si l ordre va etre approuve
# (risk_result["approved"]==True), annule les pending_validation
# existants sur le meme (instrument_id, side) en status='cancelled'
# avec rejection_reason='superseded_by_new_order_anti_dup_v1'.
#
# Insertion chirurgicale : on cherche la ligne exacte
#   "    order_id = conn.execute("
# (4 espaces indent + texte stable) et on insere le bloc juste avant.
# Idempotent (skip si marker present).

import os
import sys
import ast
import time
import shutil
import py_compile

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "execution_engine.py")
MARKER = "[ANTI_DUPLICATE_ORDER_V1]"

ANCHOR = "    order_id = conn.execute("

PATCH_BLOCK = """    # [ANTI_DUPLICATE_ORDER_V1]
    # Annule les pending_validation anterieurs sur (instrument_id, side)
    # pour eviter les doublons en cas de cycles successifs.
    # Skip si l'ordre va etre rejete (on garde la base inchangee).
    try:
        if isinstance(risk_result, dict) and risk_result.get("approved"):
            _adu_cur = conn.execute(
                "SELECT id FROM orders "
                "WHERE instrument_id = ? AND side = ? "
                "AND status = 'pending_validation'",
                (instrument_id, side),
            ).fetchall()
            _adu_ids = [r[0] for r in _adu_cur]
            if _adu_ids:
                _adu_placeholders = ",".join("?" for _ in _adu_ids)
                conn.execute(
                    f"UPDATE orders SET status='cancelled', "
                    f"rejection_reason='superseded_by_new_order_anti_dup_v1', "
                    f"validated_at=?, validated_by='anti_duplicate_order_v1' "
                    f"WHERE id IN ({_adu_placeholders})",
                    [time.strftime("%Y-%m-%d %H:%M:%S")] + _adu_ids,
                )
                try:
                    log_event(conn, "order_superseded", "order", _adu_ids[0], {
                        "superseded_count": len(_adu_ids),
                        "ids": _adu_ids,
                        "instrument_id": instrument_id,
                        "side": side,
                    }, agent="AntiDupOrderV1")
                except Exception:
                    pass
    except Exception as _adu_err:
        # Fail-open : pas bloquant
        if isinstance(risk_result, dict):
            risk_result.setdefault("warnings", []).append({
                "source": "[ANTI_DUPLICATE_ORDER_V1]",
                "code": "anti_dup_error",
                "message": str(_adu_err)[:160],
            })

"""


def main():
    if not os.path.isfile(TARGET):
        print("ERR : fichier introuvable :", TARGET)
        sys.exit(1)

    with open(TARGET, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER in src:
        print("SKIP : marker", MARKER, "deja present (idempotent)")
        sys.exit(0)

    # Pre-checks
    n_anchor = src.count(ANCHOR)
    print("Pre-check : anchor count =", n_anchor)
    if n_anchor != 1:
        print("ERR : anchor non unique, abort")
        sys.exit(2)

    # Verifie qu il y a bien un import time (pour time.strftime)
    has_import_time = "import time" in src
    print("Pre-check : import time present =", has_import_time)

    new_src = src.replace(ANCHOR, PATCH_BLOCK + ANCHOR, 1)

    # Si pas d import time, ajoute en haut apres premier import
    if not has_import_time:
        # Ajoute apres premiere ligne import
        lines = new_src.splitlines(keepends=True)
        for i, ln in enumerate(lines):
            if ln.startswith("import ") or ln.startswith("from "):
                lines.insert(i, "import time  # [ANTI_DUPLICATE_ORDER_V1]\n")
                break
        new_src = "".join(lines)
        print("Note : import time ajoute en tete")

    # Verifications
    if MARKER not in new_src:
        print("ERR : marker absent apres patch, abort")
        sys.exit(3)

    # AST
    try:
        ast.parse(new_src)
        print("AST OK")
    except SyntaxError as e:
        print("ERR AST :", e)
        sys.exit(4)

    # Verifie qu il y a toujours exactement 1 INSERT INTO orders
    if src.count("INSERT INTO orders") != new_src.count("INSERT INTO orders"):
        print("ERR : nombre d INSERT INTO orders modifie, abort")
        sys.exit(5)

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = TARGET + ".bak." + ts
    shutil.copy2(TARGET, bak)
    print("Backup :", bak)

    # Write utf-8 sans BOM
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(new_src)
    print("Ecrit :", TARGET)

    # py_compile
    try:
        py_compile.compile(TARGET, doraise=True)
        print("py_compile OK")
    except py_compile.PyCompileError as e:
        print("ERR py_compile :", e)
        sys.exit(6)

    print()
    print("=== DONE [ANTI_DUPLICATE_ORDER_V1] ===")
    print("Patch insere juste avant l INSERT INTO orders (L1263).")
    print("Restart API + cycle pour valider.")


if __name__ == "__main__":
    main()
