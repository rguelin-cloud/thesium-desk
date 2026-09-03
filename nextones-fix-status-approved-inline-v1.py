# -*- coding: utf-8 -*-
# nextones-fix-status-approved-inline-v1.py
# Patch create_and_execute_order : status approved direct, pas via broker.execute_order
# - L1283 : "pending_validation" -> "approved" (statut INSERT)
# - Return final : "pending_validation" -> "approved"
# - Ajout log_event order_approved + commit
# Idempotent via marker.
import os, sys, shutil, time, ast, py_compile, re

PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"
MARKER = "# [FIX_STATUS_APPROVED_INLINE_V1]"

# Patch 1 : L1283 - changer "pending_validation" en "approved" dans INSERT
P1_OLD = '"pending_validation" if risk_result["approved"] else "rejected",'
P1_NEW = '"approved" if risk_result["approved"] else "rejected",  ' + MARKER

# Patch 2 : Return final L1483-1486 - changer "pending_validation" en "approved"
P2_OLD = '''    return {
        "success": True, "order_id": order_id,
        "status": "pending_validation", "risk_check": risk_result,
    }'''
P2_NEW = '''    # ''' + MARKER + '''
    try:
        log_event(conn, "order_approved", "order", order_id, {
            "instrument_id": instrument_id, "side": side, "quantity": approved_qty,
            "cycle_id": cycle_id,
        }, agent="ExecutionEngine")
    except Exception:
        pass
    try:
        conn.commit()
    except Exception:
        pass
    return {
        "success": True, "order_id": order_id,
        "status": "approved", "pending_approval": True, "risk_check": risk_result,
    }'''

def main():
    if not os.path.exists(PATH):
        print("FAIL: not found", PATH); sys.exit(1)

    with open(PATH, "rb") as f:
        text = f.read().decode("utf-8-sig")

    if MARKER in text:
        print("SKIP: marker present (idempotent)")
        return

    n1 = text.count(P1_OLD)
    n2 = text.count(P2_OLD)
    print("Patch 1 (INSERT status) occurrences:", n1)
    print("Patch 2 (return status)  occurrences:", n2)
    if n1 != 1:
        print("FAIL: Patch 1 attendu 1 occurrence, trouve", n1); sys.exit(1)
    if n2 != 1:
        print("FAIL: Patch 2 attendu 1 occurrence, trouve", n2); sys.exit(1)

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = PATH + ".bak." + ts
    shutil.copy2(PATH, bak)
    print("Backup:", bak)

    new_text = text.replace(P1_OLD, P1_NEW)
    new_text = new_text.replace(P2_OLD, P2_NEW)

    # Validate
    tmp = PATH + ".tmp." + ts
    with open(tmp, "wb") as f:
        f.write(new_text.encode("utf-8"))
    try:
        ast.parse(open(tmp, "rb").read().decode("utf-8"))
        print("ast.parse OK")
        py_compile.compile(tmp, doraise=True)
        print("py_compile OK")
    except Exception as e:
        print("FAIL validation:", e)
        os.remove(tmp); sys.exit(1)

    os.replace(tmp, PATH)
    print("WRITE OK")

    # Verif
    with open(PATH, "rb") as f:
        v = f.read().decode("utf-8-sig")
    print()
    print("Verif :")
    print("  P1_OLD restants  :", v.count(P1_OLD))
    print("  P2_OLD restants  :", v.count(P2_OLD))
    print("  Marker present   :", MARKER in v)
    print("  '\"approved\" if risk_result' :", v.count('"approved" if risk_result["approved"] else "rejected"'))
    print()
    print("OK fix applique")

if __name__ == "__main__":
    main()
