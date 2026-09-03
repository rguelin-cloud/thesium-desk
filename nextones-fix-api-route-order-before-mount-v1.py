# -*- coding: utf-8 -*-
# [FIX_API_ROUTE_ORDER_BEFORE_MOUNT_V1]
# Probleme : le bloc PATCH_API_ORDERS_APPROVAL_V1 (L391-L473) a ete appende en
# fin de fichier mais se trouve APRES app.mount("/", StaticFiles, html=True) (L388),
# ce qui fait que FastAPI/Starlette repond 404 sur GET /api/orders/pending_approval
# parce que le mount catch-all intercepte tous les GET avant les routes suivantes.
#
# Solution : extraire le bloc complet PATCH_API_ORDERS_APPROVAL_V1 + son corps et
# le reinjecter JUSTE AVANT la ligne app.mount("/", ...).
# Idempotent (marker FIX_API_ROUTE_ORDER_BEFORE_MOUNT_V1).
# ASCII pur, Windows-safe. Backup .bak.<ts>.

import io
import os
import re
import sys
import ast
import py_compile
import time
import shutil

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server_with_static.py")
MARKER = "[FIX_API_ROUTE_ORDER_BEFORE_MOUNT_V1]"
BLOCK_START = "# [PATCH_API_ORDERS_APPROVAL_V1]"
BLOCK_END = "# [/PATCH_API_ORDERS_APPROVAL_V1]"


def read_text(path):
    with io.open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def write_text(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    if not os.path.exists(TARGET):
        print("MISSING:", TARGET); sys.exit(2)

    src = read_text(TARGET)
    if MARKER in src:
        print("[SKIP] FIX marker already present, no-op")
        return

    # 1) Localiser le bloc patch
    idx_start = src.find(BLOCK_START)
    idx_end = src.find(BLOCK_END)
    if idx_start < 0 or idx_end < 0:
        print("[FAIL] bloc PATCH_API_ORDERS_APPROVAL_V1 introuvable")
        print("  start:", idx_start, " end:", idx_end)
        sys.exit(3)
    # Inclure la ligne END complete + EOL
    idx_end_full = src.find("\n", idx_end)
    if idx_end_full < 0:
        idx_end_full = len(src)
    else:
        idx_end_full += 1  # include the \n

    block_text = src[idx_start:idx_end_full]
    print("[INFO] bloc patch extrait : {0} chars (L{1}-L{2})".format(
        len(block_text),
        src[:idx_start].count("\n") + 1,
        src[:idx_end_full].count("\n") + 1
    ))

    # 2) Retirer le bloc de sa position actuelle
    src_no_block = src[:idx_start] + src[idx_end_full:]

    # 3) Localiser app.mount("/", ...
    # On veut INSERER avant la ligne contenant `app.mount("/"` (premiere occurrence du root mount)
    mount_pat = re.compile(r"^\s*app\.mount\s*\(\s*[\"']/[\"']", re.MULTILINE)
    m_mount = mount_pat.search(src_no_block)
    if not m_mount:
        print("[FAIL] app.mount('/', ...) introuvable apres retrait")
        sys.exit(4)
    # On insere au debut de la ligne (pas au milieu)
    mount_line_start = src_no_block.rfind("\n", 0, m_mount.start())
    if mount_line_start < 0:
        mount_line_start = 0
    else:
        mount_line_start += 1
    print("[INFO] app.mount detecte L{0}".format(
        src_no_block[:mount_line_start].count("\n") + 1
    ))

    # 4) Reinjection : on ajoute une ligne marker FIX en haut, puis le bloc, puis un saut de ligne
    insert = (
        "\n# " + MARKER + " - block moved before app.mount('/') to avoid catch-all shadowing\n"
        + block_text
        + "\n"
    )
    new_src = src_no_block[:mount_line_start] + insert + src_no_block[mount_line_start:]

    # 5) Backup + validation AST
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = TARGET + ".bak." + ts
    shutil.copy2(TARGET, bak)
    print("[BACKUP]", bak)

    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print("[FAIL] AST parse :", e)
        sys.exit(5)
    print("[OK] AST parse")

    # 6) Ecriture + py_compile
    write_text(TARGET, new_src)
    py_compile.compile(TARGET, doraise=True)
    print("[OK] py_compile final")

    # 7) Re-localisation de controle
    src2 = read_text(TARGET)
    lines = src2.splitlines()
    fix_l = None
    patch_l = None
    mount_l = None
    for i, ln in enumerate(lines, 1):
        if MARKER in ln and fix_l is None:
            fix_l = i
        if BLOCK_START in ln and patch_l is None:
            patch_l = i
        if "app.mount(" in ln and '"/"' in ln and mount_l is None:
            mount_l = i
    print("[POST-CHECK] FIX marker L={0}, PATCH block L={1}, mount L={2}".format(
        fix_l, patch_l, mount_l
    ))
    if patch_l and mount_l and patch_l < mount_l:
        print("[VERDICT] OK : routes avant mount")
    else:
        print("[VERDICT] FAIL : routes encore apres mount")
        sys.exit(6)

    print("[DONE]", MARKER)


if __name__ == "__main__":
    main()
