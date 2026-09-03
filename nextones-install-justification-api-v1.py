"""
Patch 4/6 - API endpoints justification
========================================

Modifie api_server_with_static.py :

A) Enrichit /api/orders/pending_approval (endpoint existant L397+)
   -> ajoute o.justification et has_memo au SELECT + dict retour

B) Ajoute nouveau POST /api/orders/{order_id}/memo
   -> genere memo IA via pplx_client.pplx_query() a la demande
   -> cache : si justification_memo deja rempli, renvoie l'existant
   -> stocke dans orders.justification_memo + justification_generated_at

Idempotent via marker [JUSTIFICATION_API_V1]
Backup auto api_server_with_static.py.bak.<TS>
Validation compile() avant ecriture.
"""
import os
import re
import shutil
import sys
import time

F = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server_with_static.py"
MARK = "# [JUSTIFICATION_API_V1]"
TS = time.strftime("%Y%m%d_%H%M%S")


# ---------- Ancien body de /api/orders/pending_approval (exact) ----------
OLD_BODY = '''@app.get("/api/orders/pending_approval")
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
            WHERE o.status IN ('approved', 'pending_validation')  -- [FIX_OPTION_2_UNIFIED_QUEUE_V1]
            ORDER BY o.created_at DESC
            LIMIT 50
        """).fetchall()
        out = [dict(r) for r in rows]
        conn.close()
        return {"count": len(out), "orders": out}
    except Exception as e:
        raise _HTTPException_pavl(status_code=500, detail=str(e))'''


NEW_BODY = '''@app.get("/api/orders/pending_approval")
def _api_orders_pending_approval_v1():
    """Liste des ordres en attente d'execution humaine (status='approved')."""
    # [JUSTIFICATION_API_V1] enrichit avec justification + has_memo
    import sqlite3 as _sql
    try:
        _db = globals().get("DB_PATH") or globals().get("DB") or r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\thesium.db"
        conn = _sql.connect(_db, timeout=15)
        conn.execute("PRAGMA busy_timeout=15000")
        conn.row_factory = _sql.Row
        rows = conn.execute("""
            SELECT o.id, o.side, o.quantity, o.status, o.cycle_id,
                   o.created_at, o.thesis_id, o.order_type, o.limit_price,
                   o.justification,
                   CASE WHEN o.justification_memo IS NOT NULL AND length(o.justification_memo) > 0
                        THEN 1 ELSE 0 END AS has_memo,
                   i.ticker, i.name,
                   (SELECT close FROM prices WHERE instrument_id = o.instrument_id
                    ORDER BY date DESC LIMIT 1) AS last_price
            FROM orders o
            JOIN instruments i ON i.id = o.instrument_id
            WHERE o.status IN ('approved', 'pending_validation')  -- [FIX_OPTION_2_UNIFIED_QUEUE_V1]
            ORDER BY o.created_at DESC
            LIMIT 50
        """).fetchall()
        out = [dict(r) for r in rows]
        conn.close()
        return {"count": len(out), "orders": out}
    except Exception as e:
        raise _HTTPException_pavl(status_code=500, detail=str(e))


# [JUSTIFICATION_API_V1] Nouveau endpoint POST /api/orders/{order_id}/memo
@app.post("/api/orders/{order_id}/memo")
def _api_order_memo_v1(order_id: int):
    """
    Genere (ou retourne cache) le memo IA pour un ordre.
    Cache : si orders.justification_memo deja rempli, renvoie l'existant.
    Sinon : appelle pplx_client.pplx_query(sonar) et stocke.
    """
    import sqlite3 as _sql
    import datetime as _dt
    try:
        _db = globals().get("DB_PATH") or globals().get("DB") or r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\thesium.db"
        conn = _sql.connect(_db, timeout=15)
        conn.execute("PRAGMA busy_timeout=15000")
        conn.row_factory = _sql.Row
        row = conn.execute("""
            SELECT o.id, o.side, o.quantity, o.cycle_id, o.status,
                   o.justification, o.justification_memo, o.justification_generated_at,
                   i.ticker, i.name
              FROM orders o
              JOIN instruments i ON i.id = o.instrument_id
             WHERE o.id = ?
        """, (order_id,)).fetchone()

        if not row:
            conn.close()
            raise _HTTPException_pavl(status_code=404, detail="order not found")

        # Cache hit
        if row["justification_memo"]:
            data = {
                "order_id": order_id,
                "ticker": row["ticker"],
                "side": row["side"],
                "quantity": row["quantity"],
                "justification": row["justification"],
                "memo": row["justification_memo"],
                "generated_at": row["justification_generated_at"],
                "cached": True,
            }
            conn.close()
            return data

        # Cache miss : genere via pplx_client
        justification = row["justification"] or ""
        if not justification:
            conn.close()
            return {
                "order_id": order_id,
                "memo": None,
                "error": "no_justification_available",
                "hint": "cet ordre n'a pas de justification structuree (anterieur au Patch 3 Jalon 10)",
            }

        try:
            import pplx_client
        except Exception as e:
            conn.close()
            raise _HTTPException_pavl(
                status_code=500,
                detail="pplx_client import failed: " + str(e),
            )

        prompt = (
            "Tu es un analyste quantitatif. Ecris un memo court (200 mots max) "
            "en francais qui explique aux investisseurs pourquoi cet ordre a "
            "ete pris et si l'amplitude est justifiee. Structure : verdict "
            "(1 phrase), justification (2-3 phrases sur convergence/regime/delta), "
            "risque principal (1 phrase). Sois factuel, pas de langue de bois.\\n\\n"
            + "Ordre : " + str(row["side"]).upper() + " " + str(row["quantity"])
            + " " + str(row["ticker"]) + " (cycle " + str(row["cycle_id"]) + ")\\n"
            + "Justification structuree : " + justification
        )

        schema = {
            "type": "object",
            "properties": {
                "verdict": {"type": "string"},
                "justification": {"type": "string"},
                "risque": {"type": "string"},
            },
            "required": ["verdict", "justification", "risque"],
        }

        try:
            result = pplx_client.pplx_query(
                agent="order_memo",
                prompt=prompt,
                schema=schema,
                ttl=3600,
                timeout=45,
            )
        except Exception as e:
            conn.close()
            raise _HTTPException_pavl(
                status_code=502,
                detail="pplx_query failed: " + str(e),
            )

        if not result or not isinstance(result, dict) or "data" not in result:
            conn.close()
            raise _HTTPException_pavl(
                status_code=502,
                detail="pplx_query returned empty result",
            )

        data = result["data"] or {}
        # Compose le memo lisible
        memo_text = (
            "VERDICT : " + str(data.get("verdict", "n/a")).strip() + "\\n\\n"
            + "JUSTIFICATION\\n" + str(data.get("justification", "n/a")).strip() + "\\n\\n"
            + "RISQUE\\n" + str(data.get("risque", "n/a")).strip()
        )

        now_iso = _dt.datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "UPDATE orders SET justification_memo = ?, justification_generated_at = ? WHERE id = ?",
            (memo_text, now_iso, order_id),
        )
        conn.commit()
        conn.close()

        return {
            "order_id": order_id,
            "ticker": row["ticker"],
            "side": row["side"],
            "quantity": row["quantity"],
            "justification": justification,
            "memo": memo_text,
            "generated_at": now_iso,
            "cached": False,
            "citations": result.get("citations", []),
            "model": result.get("model"),
        }

    except _HTTPException_pavl:
        raise
    except Exception as e:
        raise _HTTPException_pavl(status_code=500, detail=str(e))'''


def main():
    if not os.path.exists(F):
        print("[ERR] file not found:", F)
        return 2

    with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
        src = fh.read()

    if MARK in src:
        print("[SKIP] API patch already applied (marker present)")
        return 0

    # Verifie que l'ancien body est present integralement
    if OLD_BODY not in src:
        print("[ERR] OLD_BODY not found verbatim in file")
        # dump 2 premieres lignes pour debug
        print("[HINT] premieres lignes du bloc attendu :")
        for i, ln in enumerate(OLD_BODY.splitlines()[:5]):
            print(f"  OLD[{i}]: {ln!r}")
        # cherche dans src
        for i, ln in enumerate(src.splitlines(), 1):
            if "def _api_orders_pending_approval_v1" in ln:
                print(f"[HINT] endpoint trouve L{i}, mais body diff\u00e8re du modele attendu")
                # dump 5 lignes autour
                lines_src = src.splitlines()
                for k in range(max(0, i - 2), min(len(lines_src), i + 25)):
                    print(f"  L{k+1}: {lines_src[k][:180]}")
                break
        return 3

    print("[OK] OLD_BODY found verbatim")

    new_src = src.replace(OLD_BODY, NEW_BODY, 1)

    if new_src == src:
        print("[ERR] no change produced")
        return 4

    # Validation syntaxique
    try:
        compile(new_src, F, "exec")
        print("[OK] compile() passes on patched source")
    except SyntaxError as e:
        print(f"[ERR] SyntaxError post-patch: {e}")
        return 5

    # Backup + write
    bak = F + ".bak." + TS
    shutil.copy2(F, bak)
    print("[BAK]", bak)

    with open(F, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_src)
    print("[OK] written:", F)

    # Sanity check
    with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
        check = fh.read()
    n_marker = check.count(MARK)
    print(f"[CHECK] marker occurrences: {n_marker} (expected 3 = 1 header + 2 in body)")

    if "/api/orders/{order_id}/memo" not in check:
        print("[ERR] new endpoint route missing in written file")
        return 6

    print()
    print("[NEXT] Restart uvicorn pour charger le nouveau endpoint")
    print("[NEXT] Puis Patch 5a : UI card Pending Approvals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
