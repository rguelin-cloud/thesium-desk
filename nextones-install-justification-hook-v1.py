"""
Patch 3/6 - Hook justification dans execution_engine.py
========================================================

Insere 2 blocs :

1) En tete de fichier (apres les imports existants) :
     import justification_builder
   -> import fail-safe (try/except) : si le module manque, on continue

2) Apres L1373 (UPDATE orders SET quantity = ? WHERE id = ?) :
     try:
         _j = justification_builder.build_justification(conn, order_id)
         if _j:
             conn.execute(
                 "UPDATE orders SET justification = ? WHERE id = ?",
                 (_j, order_id),
             )
     except Exception:
         pass

Marker : # [JUSTIFICATION_HOOK_V1]
Idempotent : skip si marker present.
Backup : execution_engine.py.bak.<TS>
"""
import os
import re
import shutil
import sys
import time

F = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"
MARK = "# [JUSTIFICATION_HOOK_V1]"
TS = time.strftime("%Y%m%d_%H%M%S")

IMPORT_BLOCK = (
    "\n"
    + MARK + " import block\n"
    + "try:\n"
    + "    import justification_builder as _jb_v1\n"
    + "except Exception:\n"
    + "    _jb_v1 = None\n"
)

HOOK_BLOCK = (
    "\n"
    + "    " + MARK + " ecrit orders.justification apres approved_qty\n"
    + "    try:\n"
    + "        if _jb_v1 is not None:\n"
    + "            _j_v1 = _jb_v1.build_justification(conn, order_id)\n"
    + "            if _j_v1:\n"
    + "                conn.execute(\n"
    + "                    \"UPDATE orders SET justification = ? WHERE id = ?\",\n"
    + "                    (_j_v1, order_id),\n"
    + "                )\n"
    + "    except Exception:\n"
    + "        pass\n"
)


def main():
    if not os.path.exists(F):
        print("[ERR] file not found:", F)
        return 2

    with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
        src = fh.read()

    if MARK in src:
        print("[SKIP] hook already installed (marker present)")
        return 0

    lines = src.splitlines(keepends=True)

    # ---------- 1) Localise le dernier import en tete de fichier ----------
    # On cherche la derniere ligne matchant "^import " ou "^from " AVANT
    # la premiere ligne de logique (def, class, if, try...)
    last_import_idx = None
    for i, ln in enumerate(lines):
        stripped = ln.lstrip()
        # stop des qu'on quitte le bloc de tete
        if stripped.startswith(("def ", "class ", "if __name__")):
            break
        if re.match(r"^(import|from)\s+", stripped):
            last_import_idx = i

    if last_import_idx is None:
        print("[ERR] cannot find import block")
        return 3

    print(f"[INFO] last import at line {last_import_idx + 1}: {lines[last_import_idx].rstrip()[:120]}")

    # ---------- 2) Localise l'ancre : UPDATE orders SET quantity ----------
    anchor_line_idx = None
    for i, ln in enumerate(lines):
        if "UPDATE orders SET quantity = ?" in ln and "approved_qty" in "".join(lines[i:i+3]):
            # verifie que la ligne suivante contient bien (approved_qty, order_id)
            # ou proche
            anchor_line_idx = i
            break

    if anchor_line_idx is None:
        # fallback : cherche juste "UPDATE orders SET quantity"
        for i, ln in enumerate(lines):
            if "UPDATE orders SET quantity" in ln:
                anchor_line_idx = i
                break

    if anchor_line_idx is None:
        print("[ERR] anchor 'UPDATE orders SET quantity' not found")
        return 4

    # L'ancre est la ligne conn.execute("UPDATE ..."), qui s'etend sur 2 lignes
    # (voir L1372-L1373). On veut inserer APRES la fin de cette instruction.
    # Le pattern : conn.execute(...\n    (approved_qty, order_id))
    # -> on cherche la ligne suivante qui contient "order_id)"
    insert_after_idx = anchor_line_idx
    for j in range(anchor_line_idx, min(anchor_line_idx + 5, len(lines))):
        if ")" in lines[j] and "approved_qty" in "".join(lines[anchor_line_idx:j+1]):
            insert_after_idx = j
            break

    print(f"[INFO] anchor line: L{anchor_line_idx + 1}: {lines[anchor_line_idx].rstrip()[:120]}")
    print(f"[INFO] insert after: L{insert_after_idx + 1}: {lines[insert_after_idx].rstrip()[:120]}")

    # ---------- 3) Injecte les 2 blocs ----------
    # ORDRE CRITIQUE : d'abord le hook (indice plus grand), puis l'import
    # (sinon les indices sont decales)
    new_lines = list(lines)

    # Injection hook : apres insert_after_idx
    new_lines.insert(insert_after_idx + 1, HOOK_BLOCK)

    # Injection import : apres last_import_idx
    # (les indices ne bougent pas car on a insere APRES insert_after_idx qui est > last_import_idx)
    new_lines.insert(last_import_idx + 1, IMPORT_BLOCK)

    new_src = "".join(new_lines)

    # ---------- 4) Validation syntaxique ----------
    try:
        compile(new_src, F, "exec")
        print("[OK] compile() passes on patched source")
    except SyntaxError as e:
        print(f"[ERR] SyntaxError post-patch: {e}")
        # dump 5 lignes autour pour debug
        el = e.lineno or 0
        for k in range(max(0, el - 3), min(len(new_lines), el + 3)):
            print(f"  L{k+1}: {new_lines[k].rstrip()[:180]}")
        return 5

    # ---------- 5) Backup + write ----------
    bak = F + ".bak." + TS
    shutil.copy2(F, bak)
    print("[BAK]", bak)

    with open(F, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_src)
    print("[OK] written:", F)

    # ---------- 6) Sanity check post-write ----------
    with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
        check = fh.read()
    n_marker = check.count(MARK)
    print(f"[CHECK] marker occurrences: {n_marker} (expected 2)")
    if n_marker < 2:
        print("[ERR] marker missing in written file")
        return 6

    print()
    print("[NEXT] Kill uvicorn puis restart pour prendre en compte l'import")
    print("[NEXT] Puis Patch 4 : API endpoints")
    return 0


if __name__ == "__main__":
    sys.exit(main())
