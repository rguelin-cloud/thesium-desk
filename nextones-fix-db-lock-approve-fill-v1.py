# -*- coding: utf-8 -*-
# [FIX_DB_LOCK_APPROVE_FILL_V1]
# Objectif :
#   1) execution_engine.approve_and_fill_order : ajouter PRAGMA busy_timeout=30000
#      en TETE de fonction + BEGIN IMMEDIATE + retry sur "database is locked"
#   2) execution_engine.reject_pending_order : meme traitement (plus leger)
#   3) auth.authenticate_user : ajouter PRAGMA busy_timeout=30000 sur conn = get_db()
# Idempotent (skip si marker present). Backup .bak.<ts>. ASCII pur.
import io, os, re, sys, ast, py_compile, time

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TS = time.strftime("%Y%m%d-%H%M%S")
MARKER_EE = "# [FIX_DB_LOCK_APPROVE_FILL_V1]"
MARKER_AUTH = "# [FIX_DB_LOCK_AUTH_V1]"

def read_utf8(path):
    with io.open(path, "r", encoding="utf-8-sig") as f:
        return f.read()

def write_utf8(path, content):
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)

def assert_ascii(content, label):
    # On verifie seulement que le patch lui-meme est ASCII (pas le fichier hote).
    # Le fichier hote peut contenir des caracteres non-ASCII pre-existants.
    bad = [(i, ord(c)) for i, c in enumerate(content) if ord(c) > 127]
    print("  non-ASCII bytes in %s = %d (informational only)" % (label, len(bad)))

def assert_compiles(content, label):
    try:
        ast.parse(content)
        print("  ast.parse OK (%s)" % label)
    except SyntaxError as e:
        print("FAIL ast.parse %s: %s" % (label, e))
        sys.exit(1)

def backup(path):
    bk = path + ".bak." + TS
    with io.open(path, "rb") as f:
        data = f.read()
    with io.open(bk, "wb") as f:
        f.write(data)
    print("  backup -> " + os.path.basename(bk))

# =====================================================================
# 1) execution_engine.py
# =====================================================================
ee_path = os.path.join(ROOT, "execution_engine.py")
ee_src = read_utf8(ee_path)

if MARKER_EE in ee_src:
    print("[execution_engine.py] SKIP (marker deja present)")
else:
    print("[execution_engine.py] patch...")
    backup(ee_path)

    # --- Patch approve_and_fill_order ---
    # On wrappe le corps existant en :
    # def approve_and_fill_order(conn, order_id, validated_by="ui_user"):
    #     # [FIX_DB_LOCK_APPROVE_FILL_V1]
    #     import time as _afo_time
    #     for _afo_attempt in range(1, 6):
    #         try:
    #             try: conn.execute("PRAGMA busy_timeout=30000")
    #             except Exception: pass
    #             return _approve_and_fill_order_inner(conn, order_id, validated_by)
    #         except Exception as _afo_e:
    #             _afo_msg = str(_afo_e).lower()
    #             if "locked" in _afo_msg or "busy" in _afo_msg:
    #                 _afo_wait = 0.2 * (2 ** (_afo_attempt - 1))
    #                 try: conn.rollback()
    #                 except Exception: pass
    #                 _afo_time.sleep(_afo_wait)
    #                 continue
    #             try: conn.rollback()
    #             except Exception: pass
    #             raise
    #     raise RuntimeError("approve_and_fill_order: db locked after 5 retries")
    #
    # def _approve_and_fill_order_inner(conn, order_id, validated_by="ui_user"):
    #     <corps original>

    # Reperer la signature de approve_and_fill_order
    sig_re = re.compile(
        r'^def\s+approve_and_fill_order\s*\(conn,\s*order_id,\s*validated_by\s*=\s*"ui_user"\)\s*:\s*$',
        re.MULTILINE,
    )
    m = sig_re.search(ee_src)
    if not m:
        print("FAIL: signature approve_and_fill_order introuvable")
        sys.exit(1)

    # Renommer la fonction originale en _approve_and_fill_order_inner
    # puis inserer un wrapper avant
    old_line = m.group(0)
    new_line = 'def _approve_and_fill_order_inner(conn, order_id, validated_by="ui_user"):'
    ee_src2 = ee_src.replace(old_line, new_line, 1)

    wrapper = (
        '\n'
        'def approve_and_fill_order(conn, order_id, validated_by="ui_user"):\n'
        '    ' + MARKER_EE + '\n'
        '    """Wrapper retry/busy_timeout autour de _approve_and_fill_order_inner."""\n'
        '    import time as _afo_time\n'
        '    _afo_last = None\n'
        '    for _afo_attempt in range(1, 6):\n'
        '        try:\n'
        '            try:\n'
        '                conn.execute("PRAGMA busy_timeout=30000")\n'
        '            except Exception:\n'
        '                pass\n'
        '            return _approve_and_fill_order_inner(conn, order_id, validated_by)\n'
        '        except Exception as _afo_e:\n'
        '            _afo_last = _afo_e\n'
        '            _afo_msg = str(_afo_e).lower()\n'
        '            if "locked" in _afo_msg or "busy" in _afo_msg:\n'
        '                _afo_wait = 0.2 * (2 ** (_afo_attempt - 1))\n'
        '                try:\n'
        '                    conn.rollback()\n'
        '                except Exception:\n'
        '                    pass\n'
        '                print("[approve_and_fill_order] DB locked attempt %d/5 wait %.2fs" % (_afo_attempt, _afo_wait))\n'
        '                _afo_time.sleep(_afo_wait)\n'
        '                continue\n'
        '            try:\n'
        '                conn.rollback()\n'
        '            except Exception:\n'
        '                pass\n'
        '            raise\n'
        '    raise RuntimeError("approve_and_fill_order: db locked after 5 retries: " + str(_afo_last))\n'
        '\n'
    )

    # Inserer le wrapper juste avant la nouvelle signature renommee
    idx = ee_src2.find(new_line)
    ee_src2 = ee_src2[:idx] + wrapper + ee_src2[idx:]

    # --- Patch reject_pending_order (plus simple : juste busy_timeout en tete) ---
    rej_re = re.compile(
        r'(def\s+reject_pending_order\s*\([^)]*\)\s*:\s*\n\s*"""[^"]*"""\s*\n)',
        re.MULTILINE,
    )
    mrej = rej_re.search(ee_src2)
    if mrej:
        insert_after = mrej.end()
        rej_inject = (
            '    ' + MARKER_EE + '\n'
            '    try:\n'
            '        conn.execute("PRAGMA busy_timeout=30000")\n'
            '    except Exception:\n'
            '        pass\n'
        )
        ee_src2 = ee_src2[:insert_after] + rej_inject + ee_src2[insert_after:]
        print("  reject_pending_order : busy_timeout injecte")
    else:
        print("  WARN: reject_pending_order docstring pattern non matche (skip)")

    # Verifier que le wrapper qu'on injecte est ASCII pur
    bad_w = [(i, ord(c)) for i, c in enumerate(wrapper) if ord(c) > 127]
    if bad_w:
        print("FAIL: wrapper non-ASCII -> %r" % bad_w[:5])
        sys.exit(1)
    print("  wrapper ASCII pur OK (%d chars)" % len(wrapper))
    assert_ascii(ee_src2, "execution_engine.py")
    assert_compiles(ee_src2, "execution_engine.py")
    write_utf8(ee_path, ee_src2)
    # py_compile final
    py_compile.compile(ee_path, doraise=True)
    print("  py_compile OK")
    print("[execution_engine.py] OK")

# =====================================================================
# 2) auth.py
# =====================================================================
auth_path = os.path.join(ROOT, "auth.py")
auth_src = read_utf8(auth_path)

if MARKER_AUTH in auth_src:
    print("[auth.py] SKIP (marker deja present)")
else:
    print("[auth.py] patch...")
    backup(auth_path)

    # Cibler authenticate_user : injecter PRAGMA busy_timeout apres "conn = get_db()"
    # Pattern :  conn = get_db()
    #            try:
    # -> injecter apres la ligne try:
    pattern = re.compile(
        r'(def\s+authenticate_user\s*\([^)]*\)[^\n]*\n[^\n]*"""[^"]*"""\s*\n\s*conn\s*=\s*get_db\(\)\s*\n\s*try:\s*\n)',
        re.MULTILINE,
    )
    m = pattern.search(auth_src)
    if not m:
        print("FAIL: pattern authenticate_user non trouve")
        sys.exit(1)
    inject = (
        '        ' + MARKER_AUTH + '\n'
        '        try:\n'
        '            conn.execute("PRAGMA busy_timeout=30000")\n'
        '        except Exception:\n'
        '            pass\n'
    )
    auth_src2 = auth_src[:m.end()] + inject + auth_src[m.end():]

    # Verifier que l'injection est ASCII pure
    bad_i = [(i, ord(c)) for i, c in enumerate(inject) if ord(c) > 127]
    if bad_i:
        print("FAIL: inject non-ASCII -> %r" % bad_i[:5])
        sys.exit(1)
    print("  inject ASCII pur OK (%d chars)" % len(inject))
    assert_ascii(auth_src2, "auth.py")
    assert_compiles(auth_src2, "auth.py")
    write_utf8(auth_path, auth_src2)
    py_compile.compile(auth_path, doraise=True)
    print("  py_compile OK")
    print("[auth.py] OK")

print("\n[DONE] FIX_DB_LOCK_APPROVE_FILL_V1 deploye")
print("  -> restart API : kill port 8000 puis uvicorn api_server_with_static:app")
print("  -> retester clic Execute sur order #343")
