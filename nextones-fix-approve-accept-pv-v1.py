# -*- coding: utf-8 -*-
# Fix : _approve_and_fill_order_inner accepte 'approved' ET 'pending_validation'
# avant le fill. Sinon Execute echoue avec status_not_approved sur ordres pv.
import os, sys, shutil, time, ast, py_compile

PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"
MARKER = "# [FIX_APPROVE_ACCEPT_PV_V1]"

OLD = '''    if r["status"] != "approved":'''
NEW = '''    if r["status"] not in ("approved", "pending_validation"):  ''' + MARKER

def main():
    if not os.path.exists(PATH):
        print("FAIL: not found"); sys.exit(1)
    with open(PATH, "rb") as f:
        text = f.read().decode("utf-8-sig")

    if MARKER in text:
        print("SKIP: marker present"); return

    n = text.count(OLD)
    print("OLD occurrences:", n)
    if n != 1:
        print("FAIL: expected 1"); sys.exit(1)

    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = PATH + ".bak." + ts
    shutil.copy2(PATH, bak)
    print("Backup:", bak)

    new_text = text.replace(OLD, NEW)
    tmp = PATH + ".tmp." + ts
    with open(tmp, "wb") as f:
        f.write(new_text.encode("utf-8"))

    try:
        ast.parse(open(tmp, "rb").read().decode("utf-8"))
        py_compile.compile(tmp, doraise=True)
        print("ast + compile OK")
    except Exception as e:
        print("FAIL:", e); os.remove(tmp); sys.exit(1)

    os.replace(tmp, PATH)
    print("WRITE OK")

    with open(PATH, "rb") as f:
        v = f.read().decode("utf-8-sig")
    print("Marker present:", MARKER in v)
    print("NEW guard present:", '("approved", "pending_validation")' in v)

if __name__ == "__main__":
    main()
