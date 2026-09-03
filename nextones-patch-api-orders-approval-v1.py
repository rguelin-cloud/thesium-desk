# -*- coding: utf-8 -*-
# [PATCH_API_ORDERS_APPROVAL_V1]
# Ajoute 3 endpoints dans api_server_with_static.py :
#   POST /api/orders/{id}/execute    -> approve_and_fill_order
#   POST /api/orders/{id}/reject     -> reject_pending_order
#   GET  /api/orders/pending_approval -> liste des orders status='approved'
# Idempotent (marker en commentaire). ASCII pur, Windows-safe.

import io
import os
import re
import sys
import ast
import py_compile
import time
import shutil

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
# On vise le fichier api_server_with_static (server reel) sinon api_server
CAND = ["api_server_with_static.py", "api_server.py"]
TARGET = None
for c in CAND:
    p = os.path.join(ROOT, c)
    if os.path.exists(p):
        TARGET = p
        break

MARKER = "[PATCH_API_ORDERS_APPROVAL_V1]"


def read_text(path):
    with io.open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def write_text(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    if TARGET is None:
        print("MISSING: ni api_server_with_static.py ni api_server.py trouve dans", ROOT)
        sys.exit(2)
    print("[TARGET]", TARGET)

    src = read_text(TARGET)
    if MARKER in src:
        print("[SKIP] marker already present")
        return

    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = TARGET + ".bak." + ts
    shutil.copy2(TARGET, bak)
    print("[BACKUP]", bak)

    # Detection FastAPI vs Flask
    is_fastapi = "FastAPI" in src or "@app.post" in src or "from fastapi" in src
    is_flask = "Flask(" in src or "@app.route" in src

    # On suppose FastAPI (api_server_with_static + uvicorn)
    block_fastapi = '''

# [PATCH_API_ORDERS_APPROVAL_V1] Orders approval endpoints
from fastapi import HTTPException as _HTTPException_pavl
from pydantic import BaseModel as _BaseModel_pavl

class _OrderRejectBody_pavl(_BaseModel_pavl):
    reason: str = "user_rejected"


@app.get("/api/orders/pending_approval")
def _api_orders_pending_approval_v1():
    """Liste des ordres en attente d'execution humaine (status='approved')."""
    import sqlite3 as _sql
    try:
        _db = globals().get("DB_PATH") or globals().get("DB") or r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\thesium.db"
        conn = _sql.connect(_db, timeout=15)
        conn.execute("PRAGMA busy_timeout=15000")
        conn.row_factory = _sql.Row
        rows = conn.execute("""
            SELECT o.id, o.side, o.quantity, o.status, o.cycle_id,
                   o.created_at, o.thesis_id, o.order_type, o.limit_price,
                   i.ticker, i.name,
                   (SELECT close FROM prices WHERE instrument_id = o.instrument_id
                    ORDER BY date DESC LIMIT 1) AS last_price
            FROM orders o
            JOIN instruments i ON i.id = o.instrument_id
            WHERE o.status = 'approved'
            ORDER BY o.created_at DESC
            LIMIT 50
        """).fetchall()
        out = [dict(r) for r in rows]
        conn.close()
        return {"count": len(out), "orders": out}
    except Exception as e:
        raise _HTTPException_pavl(status_code=500, detail=str(e))


@app.post("/api/orders/{order_id}/execute")
def _api_order_execute_v1(order_id: int):
    """Execute un ordre approuve (humain) -> fill + position + cash."""
    import sqlite3 as _sql
    try:
        from execution_engine import approve_and_fill_order
    except Exception as e:
        raise _HTTPException_pavl(status_code=500,
                                  detail="import approve_and_fill_order: " + str(e))
    try:
        _db = globals().get("DB_PATH") or globals().get("DB") or r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\thesium.db"
        conn = _sql.connect(_db, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        result = approve_and_fill_order(conn, order_id, validated_by="ui_user")
        conn.close()
        if not result.get("success"):
            raise _HTTPException_pavl(status_code=400, detail=result)
        return result
    except _HTTPException_pavl:
        raise
    except Exception as e:
        raise _HTTPException_pavl(status_code=500, detail=str(e))


@app.post("/api/orders/{order_id}/reject")
def _api_order_reject_v1(order_id: int, body: _OrderRejectBody_pavl):
    """Reject un ordre approuve (humain)."""
    import sqlite3 as _sql
    try:
        from execution_engine import reject_pending_order
    except Exception as e:
        raise _HTTPException_pavl(status_code=500,
                                  detail="import reject_pending_order: " + str(e))
    try:
        _db = globals().get("DB_PATH") or globals().get("DB") or r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\thesium.db"
        conn = _sql.connect(_db, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        result = reject_pending_order(conn, order_id, reason=body.reason, validated_by="ui_user")
        conn.close()
        if not result.get("success"):
            raise _HTTPException_pavl(status_code=400, detail=result)
        return result
    except _HTTPException_pavl:
        raise
    except Exception as e:
        raise _HTTPException_pavl(status_code=500, detail=str(e))
# [/PATCH_API_ORDERS_APPROVAL_V1]
'''

    block_flask = '''

# [PATCH_API_ORDERS_APPROVAL_V1] Orders approval endpoints (Flask)
@app.route("/api/orders/pending_approval", methods=["GET"])
def _api_orders_pending_approval_v1():
    import sqlite3 as _sql
    from flask import jsonify
    _db = globals().get("DB_PATH") or globals().get("DB") or r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\thesium.db"
    conn = _sql.connect(_db, timeout=15)
    conn.execute("PRAGMA busy_timeout=15000")
    conn.row_factory = _sql.Row
    rows = conn.execute("""
        SELECT o.id, o.side, o.quantity, o.status, o.cycle_id,
               o.created_at, o.thesis_id, o.order_type, o.limit_price,
               i.ticker, i.name,
               (SELECT close FROM prices WHERE instrument_id = o.instrument_id
                ORDER BY date DESC LIMIT 1) AS last_price
        FROM orders o
        JOIN instruments i ON i.id = o.instrument_id
        WHERE o.status = 'approved'
        ORDER BY o.created_at DESC
        LIMIT 50
    """).fetchall()
    out = [dict(r) for r in rows]
    conn.close()
    return jsonify({"count": len(out), "orders": out})


@app.route("/api/orders/<int:order_id>/execute", methods=["POST"])
def _api_order_execute_v1(order_id):
    from flask import jsonify
    from execution_engine import approve_and_fill_order
    import sqlite3 as _sql
    _db = globals().get("DB_PATH") or globals().get("DB") or r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\thesium.db"
    conn = _sql.connect(_db, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    result = approve_and_fill_order(conn, order_id, validated_by="ui_user")
    conn.close()
    return jsonify(result), (200 if result.get("success") else 400)


@app.route("/api/orders/<int:order_id>/reject", methods=["POST"])
def _api_order_reject_v1(order_id):
    from flask import jsonify, request
    from execution_engine import reject_pending_order
    import sqlite3 as _sql
    reason = (request.json or {}).get("reason", "user_rejected") if request.is_json else "user_rejected"
    _db = globals().get("DB_PATH") or globals().get("DB") or r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\thesium.db"
    conn = _sql.connect(_db, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    result = reject_pending_order(conn, order_id, reason=reason, validated_by="ui_user")
    conn.close()
    return jsonify(result), (200 if result.get("success") else 400)
# [/PATCH_API_ORDERS_APPROVAL_V1]
'''

    if is_fastapi:
        print("[INFO] FastAPI detected")
        block = block_fastapi
    elif is_flask:
        print("[INFO] Flask detected")
        block = block_flask
    else:
        print("[WARN] Framework non detecte, defaut FastAPI")
        block = block_fastapi

    # Append a la fin du fichier
    src = src.rstrip() + "\n" + block + "\n"

    # Validation
    try:
        ast.parse(src)
    except SyntaxError as e:
        print("[FAIL] AST parse :", e)
        sys.exit(3)
    print("[OK] AST parse")

    write_text(TARGET, src)
    py_compile.compile(TARGET, doraise=True)
    print("[OK] py_compile final")
    print("[DONE]", MARKER, "on", TARGET)


if __name__ == "__main__":
    main()
