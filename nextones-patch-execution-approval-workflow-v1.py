# -*- coding: utf-8 -*-
# [PATCH_EXECUTION_APPROVAL_WORKFLOW_V1]
# Option A : workflow d'approval humain reel.
# - execute_order: ne fait PLUS le fill direct. Marque status='approved' et stop.
# - create_and_execute_order: accepte cycle_id, le passe au INSERT INTO orders.
# - run_decision_cycle: passe cycle_id a chaque create_and_execute_order.
# - Nouvelle fonction approve_and_fill_order(conn, order_id, validated_by):
#     reprend la logique de fill (fills + position + cash + refresh + log).
# Idempotent (marker en commentaire). ASCII pur, Windows-safe.
# Read utf-8-sig / write utf-8 sans BOM. Backup .bak.<ts>.

import io
import os
import re
import sys
import ast
import py_compile
import time
import shutil

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "execution_engine.py")
MARKER = "[PATCH_EXECUTION_APPROVAL_WORKFLOW_V1]"


def read_text(path):
    with io.open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def write_text(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def backup(path):
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = path + ".bak." + ts
    shutil.copy2(path, bak)
    return bak


def validate(src, label):
    try:
        ast.parse(src)
    except SyntaxError as e:
        print("[FAIL] AST parse ({0}): {1}".format(label, e))
        sys.exit(3)
    print("[OK] AST parse {0}".format(label))


def main():
    if not os.path.exists(TARGET):
        print("MISSING:", TARGET); sys.exit(2)

    src = read_text(TARGET)
    if MARKER in src:
        print("[SKIP] marker already present, no-op")
        return

    bak = backup(TARGET)
    print("[BACKUP]", bak)

    # ----- MODIF 1 : execute_order -- stopper avant fill -----
    # Cible le bloc actuel L1057-1103 (calcul fill_price + INSERT fills + UPDATE filled + positions + cash + refresh + log_event)
    # On le remplace par : marquage 'approved' + retour {pending_approval: True}
    pat1_old = (
        "    def execute_order(self, conn, order_id, instrument_id, side, quantity,\n"
        "                      order_type, limit_price, current_price) -> dict:\n"
        "        fill_price = self._calculate_fill_price(current_price, side)\n"
        "        slippage   = abs(fill_price - current_price) * quantity\n"
        "        fees       = round(quantity * self.fee_per_share, 4)\n"
        "        filled_at  = datetime.utcnow().isoformat()\n"
        "\n"
        "        if order_type == \"limit\" and limit_price is not None:\n"
        "            if side == \"buy\" and current_price > limit_price:\n"
        "                return {\"success\": False, \"reason\": \"Limit price not reached (buy above limit)\"}\n"
        "            if side == \"sell\" and current_price < limit_price:\n"
        "                return {\"success\": False, \"reason\": \"Limit price not reached (sell below limit)\"}\n"
        "\n"
        "        cur = conn.execute(\n"
        "            \"\"\"INSERT INTO fills (order_id, fill_price, fill_quantity, slippage, fees, filled_at)\n"
        "               VALUES (?, ?, ?, ?, ?, ?)\"\"\",\n"
        "            (order_id, fill_price, quantity, round(slippage, 4), fees, filled_at)\n"
        "        )\n"
        "        fill_id = cur.lastrowid\n"
        "\n"
        "        conn.execute(\"UPDATE orders SET status = 'filled' WHERE id = ?\", (order_id,))\n"
        "\n"
        "        self._update_position(conn, instrument_id, side, quantity, fill_price)\n"
        "\n"
        "        trade_value = quantity * fill_price\n"
        "        if side == \"buy\":\n"
        "            conn.execute(\n"
        "                \"UPDATE portfolio_state SET cash = cash - ? - ? WHERE id = 1\",\n"
        "                (trade_value, fees)\n"
        "            )\n"
        "        else:\n"
        "            conn.execute(\n"
        "                \"UPDATE portfolio_state SET cash = cash + ? - ? WHERE id = 1\",\n"
        "                (trade_value, fees)\n"
        "            )\n"
        "\n"
        "        refresh_portfolio_state(conn)\n"
        "\n"
        "        log_event(conn, \"order_filled\", \"fill\", fill_id, {\n"
        "            \"order_id\": order_id, \"instrument_id\": instrument_id, \"side\": side,\n"
        "            \"quantity\": quantity, \"fill_price\": fill_price,\n"
        "            \"slippage\": round(slippage, 4), \"fees\": fees,\n"
        "        }, agent=\"PaperBroker\")\n"
        "\n"
        "        return {\n"
        "            \"success\": True, \"fill_id\": fill_id, \"fill_price\": fill_price,\n"
        "            \"fill_quantity\": quantity, \"slippage\": round(slippage, 4),\n"
        "            \"fees\": fees, "
        "\"filled_at\": filled_at,\n"
        "        }\n"
    )

    pat1_new = (
        "    def execute_order(self, conn, order_id, instrument_id, side, quantity,\n"
        "                      order_type, limit_price, current_price) -> dict:\n"
        "        # [PATCH_EXECUTION_APPROVAL_WORKFLOW_V1] Option A : stop avant fill, queue humaine\n"
        "        if order_type == \"limit\" and limit_price is not None:\n"
        "            if side == \"buy\" and current_price > limit_price:\n"
        "                return {\"success\": False, \"reason\": \"Limit price not reached (buy above limit)\"}\n"
        "            if side == \"sell\" and current_price < limit_price:\n"
        "                return {\"success\": False, \"reason\": \"Limit price not reached (sell below limit)\"}\n"
        "\n"
        "        # Marquage 'approved' : l'ordre est valide par le risk engine mais en attente d'execution humaine.\n"
        "        # Le fill effectif est differe a approve_and_fill_order() declenche par l'UI.\n"
        "        conn.execute(\"UPDATE orders SET status = 'approved' WHERE id = ?\", (order_id,))\n"
        "\n"
        "        log_event(conn, \"order_approved\", \"order\", order_id, {\n"
        "            \"order_id\": order_id, \"instrument_id\": instrument_id, \"side\": side,\n"
        "            \"quantity\": quantity, \"current_price\": current_price,\n"
        "        }, agent=\"RiskEngine\")\n"
        "\n"
        "        return {\n"
        "            \"success\": True, \"status\": \"approved\", \"pending_approval\": True,\n"
        "            \"order_id\": order_id, \"current_price\": current_price,\n"
        "        }\n"
    )

    if pat1_old not in src:
        print("[FAIL] pattern 1 (execute_order body) introuvable. Aborting.")
        # Dump du bloc actuel pour debug
        idx = src.find("def execute_order(self, conn, order_id")
        if idx >= 0:
            print("---- dump 3500 chars around execute_order ----")
            print(src[idx:idx + 3500])
        sys.exit(4)
    src = src.replace(pat1_old, pat1_new, 1)
    print("[OK] MODIF 1 applied : execute_order -> approved")

    # ----- MODIF 2 : create_and_execute_order signature + INSERT cycle_id -----
    # On capture la signature actuelle pour ajouter cycle_id=None.
    m2_sig = re.search(
        r"def\s+create_and_execute_order\s*\(\s*conn\s*,\s*instrument_id\s*,\s*thesis_id\s*,\s*side\s*,\s*quantity\s*,",
        src
    )
    if not m2_sig:
        print("[FAIL] signature create_and_execute_order introuvable")
        sys.exit(5)

    # Cherche le def complet et ajoute cycle_id=None a la fin du parametre list
    # Pattern : def create_and_execute_order(conn, ..., order_type="market", limit_price=None, ...):
    def_pat = re.compile(
        r"(def\s+create_and_execute_order\s*\([^)]*?)(\)\s*(?:->\s*[^:]+)?\s*:)",
        re.DOTALL
    )
    m_def = def_pat.search(src)
    if not m_def:
        print("[FAIL] def create_and_execute_order full signature introuvable")
        sys.exit(5)

    sig_inside = m_def.group(1)
    sig_close = m_def.group(2)

    if "cycle_id" in sig_inside:
        print("[SKIP] cycle_id deja present dans signature create_and_execute_order")
    else:
        # Ajout ", cycle_id=None" avant la fermeture
        # On ajoute proprement avec une virgule prefixe
        new_sig = sig_inside.rstrip().rstrip(",") + ", cycle_id=None"
        src = src.replace(m_def.group(0), new_sig + sig_close, 1)
        print("[OK] MODIF 2a applied : signature create_and_execute_order +cycle_id")

    # ----- MODIF 3 : INSERT INTO orders -> ajouter cycle_id -----
    # Cible L1305 : INSERT INTO orders ... (instrument_id, thesis_id, side, quantity, order_type, limit_price, status, risk_check_result)
    # On localise le bloc INSERT puis on ajoute cycle_id.
    m3 = re.search(
        r"(conn\.execute\(\s*\n?\s*[\"']{3}INSERT\s+INTO\s+orders\s*\n?)"
        r"(\s*\([^)]*?\)\s*\n?\s*VALUES\s*\([^)]*?\))"
        r"([\"']{3}\s*,\s*\n?\s*\([^)]*?\)\s*\))",
        src,
        re.IGNORECASE | re.DOTALL
    )
    if not m3:
        # Fallback : pattern simple ligne par ligne
        print("[INFO] pattern complexe INSERT non trouve, tentative pattern simple")
        # Localiser le INSERT
        idx_ins = src.find("INSERT INTO orders")
        if idx_ins < 0:
            print("[FAIL] INSERT INTO orders introuvable")
            sys.exit(6)
        # Dump pour debug
        print("---- dump 2000 chars autour INSERT orders ----")
        print(src[max(0, idx_ins - 200):idx_ins + 1800])
        sys.exit(6)

    insert_full = m3.group(0)
    if "cycle_id" in insert_full:
        print("[SKIP] cycle_id deja present dans INSERT orders")
    else:
        # On ajoute cycle_id a la liste des colonnes et un ? dans VALUES,
        # ET cycle_id a la fin du tuple de valeurs.
        col_block = m3.group(2)  # "(col1, col2, ...) VALUES (?, ?, ...)"
        # Split col_block en cols et vals
        m_cb = re.match(r"\s*\((.*?)\)\s*VALUES\s*\((.*?)\)", col_block, re.DOTALL)
        if not m_cb:
            print("[FAIL] decoupage col/vals INSERT impossible")
            sys.exit(6)
        cols = m_cb.group(1).strip()
        vals = m_cb.group(2).strip()
        new_cols = cols + ", cycle_id"
        new_vals = vals + ", ?"
        new_col_block = "({0})\n           VALUES ({1})".format(new_cols, new_vals)

        # Pour le tuple Python des valeurs, on ajoute cycle_id a la fin
        # Le m3.group(3) contient: """ , (val1, val2, ...))
        tuple_block = m3.group(3)
        m_tup = re.search(r"\(\s*([^)]*?)\s*\)\s*\)\s*$", tuple_block, re.DOTALL)
        if not m_tup:
            print("[FAIL] decoupage tuple values INSERT impossible")
            print("tuple_block:", tuple_block)
            sys.exit(6)
        tup_inner = m_tup.group(1).rstrip().rstrip(",")
        new_tup_inner = tup_inner + ", cycle_id"
        new_tuple_block = tuple_block.replace(m_tup.group(0), "({0}))".format(new_tup_inner))
        # On reconstruit le INSERT complet
        new_insert = m3.group(1) + new_col_block + new_tuple_block
        # Nettoyage : ferme proprement la triple-quote
        # m3.group(3) commence par """  donc on doit garder cette fermeture avant les valeurs
        # On refait plus proprement :
        # Reconstruction structuree :
        old_pat = m3.group(0)
        # Reconstruire :
        # conn.execute(
        #     """INSERT INTO orders
        #        (cols..., cycle_id)
        #        VALUES (?, ?, ..., ?)""",
        #     (val1, ..., cycle_id)
        # )
        # Plus simple : remplacer cols -> cols+cycle_id, vals -> vals+?, tuple -> tuple+cycle_id
        new_block = old_pat
        new_block = new_block.replace("(" + cols + ")", "(" + new_cols + ")", 1)
        new_block = new_block.replace("VALUES (" + vals + ")", "VALUES (" + new_vals + ")", 1)
        new_block = new_block.replace("(" + tup_inner + ")", "(" + new_tup_inner + ")", 1)
        src = src.replace(old_pat, new_block, 1)
        print("[OK] MODIF 3 applied : INSERT INTO orders +cycle_id")

    # ----- MODIF 4 : appel L2285 create_and_execute_order -> passer cycle_id -----
    # On cherche tous les appels et on ajoute cycle_id=cycle_id si absent
    # dans run_decision_cycle (zone L2050-2350 environ).
    # Pattern : result = create_and_execute_order(
    call_pat = re.compile(
        r"(create_and_execute_order\s*\(\s*conn[^)]*?)(\))",
        re.DOTALL
    )
    n_calls = 0
    n_patched = 0
    def _repl(m):
        nonlocal n_calls, n_patched
        n_calls += 1
        inner = m.group(1)
        if "cycle_id" in inner:
            return m.group(0)
        n_patched += 1
        return inner.rstrip().rstrip(",") + ", cycle_id=cycle_id" + m.group(2)

    src = call_pat.sub(_repl, src)
    print("[OK] MODIF 4 : create_and_execute_order calls scanned={0} patched={1}".format(n_calls, n_patched))

    # ----- MODIF 5 : Ajouter la fonction approve_and_fill_order -----
    if "def approve_and_fill_order(" in src:
        print("[SKIP] approve_and_fill_order deja present")
    else:
        # On insere la fonction juste avant le `if __name__` ou en fin de fichier
        approve_fn = '''

# [PATCH_EXECUTION_APPROVAL_WORKFLOW_V1] approve_and_fill_order
def approve_and_fill_order(conn, order_id, validated_by="ui_user"):
    """
    Declenche par l'UI quand l'humain clique Execute sur un ordre 'approved'.
    Reprend la logique de fill (fills + position + cash + refresh + log).
    Retour: dict avec success / fill_id / fill_price / fees / slippage.
    """
    from datetime import datetime as _dt

    row = conn.execute(
        "SELECT id, instrument_id, thesis_id, side, quantity, order_type, "
        "limit_price, status, cycle_id "
        "FROM orders WHERE id = ?",
        (order_id,)
    ).fetchone()
    if not row:
        return {"success": False, "reason": "order_not_found", "order_id": order_id}

    keys = ["id", "instrument_id", "thesis_id", "side", "quantity",
            "order_type", "limit_price", "status", "cycle_id"]
    r = dict(zip(keys, row))

    if r["status"] != "approved":
        return {"success": False, "reason": "status_not_approved",
                "order_id": order_id, "current_status": r["status"]}

    # Recuperer le current_price
    price_row = conn.execute(
        "SELECT close FROM prices WHERE instrument_id = ? "
        "ORDER BY date DESC LIMIT 1",
        (r["instrument_id"],)
    ).fetchone()
    if not price_row or price_row[0] is None:
        return {"success": False, "reason": "no_price", "order_id": order_id}
    current_price = float(price_row[0])

    side = r["side"]
    quantity = float(r["quantity"])

    # Reutiliser PaperBroker pour calcul fill_price/slippage/fees
    broker = PaperBroker()
    fill_price = broker._calculate_fill_price(current_price, side)
    slippage = abs(fill_price - current_price) * quantity
    fees = round(quantity * broker.fee_per_share, 4)
    filled_at = _dt.utcnow().isoformat()

    cur = conn.execute(
        """INSERT INTO fills (order_id, fill_price, fill_quantity, slippage, fees, filled_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (order_id, fill_price, quantity, round(slippage, 4), fees, filled_at)
    )
    fill_id = cur.lastrowid

    conn.execute(
        "UPDATE orders SET status = 'filled', validated_by = ?, validated_at = ? "
        "WHERE id = ?",
        (validated_by, filled_at, order_id)
    )

    broker._update_position(conn, r["instrument_id"], side, quantity, fill_price)

    trade_value = quantity * fill_price
    if side == "buy":
        conn.execute(
            "UPDATE portfolio_state SET cash = cash - ? - ? WHERE id = 1",
            (trade_value, fees)
        )
    else:
        conn.execute(
            "UPDATE portfolio_state SET cash = cash + ? - ? WHERE id = 1",
            (trade_value, fees)
        )

    refresh_portfolio_state(conn)

    log_event(conn, "order_filled_human", "fill", fill_id, {
        "order_id": order_id, "instrument_id": r["instrument_id"], "side": side,
        "quantity": quantity, "fill_price": fill_price,
        "slippage": round(slippage, 4), "fees": fees,
        "validated_by": validated_by,
    }, agent="HumanApproval")

    conn.commit()

    return {
        "success": True, "fill_id": fill_id, "fill_price": fill_price,
        "fill_quantity": quantity, "slippage": round(slippage, 4),
        "fees": fees, "filled_at": filled_at, "order_id": order_id,
    }


def reject_pending_order(conn, order_id, reason="user_rejected", validated_by="ui_user"):
    """Reject un ordre 'approved' via l'UI."""
    from datetime import datetime as _dt
    row = conn.execute(
        "SELECT status FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    if not row:
        return {"success": False, "reason": "order_not_found"}
    if row[0] not in ("approved", "pending_validation", "pending"):
        return {"success": False, "reason": "status_not_rejectable",
                "current_status": row[0]}

    conn.execute(
        "UPDATE orders SET status = 'rejected', rejection_reason = ?, "
        "validated_by = ?, validated_at = ? WHERE id = ?",
        (reason, validated_by, _dt.utcnow().isoformat(), order_id)
    )

    log_event(conn, "order_rejected_human", "order", order_id, {
        "order_id": order_id, "reason": reason, "validated_by": validated_by,
    }, agent="HumanApproval")

    conn.commit()
    return {"success": True, "order_id": order_id, "status": "rejected"}
'''

        # Insertion : on cherche le `if __name__ == "__main__":` final, sinon EOF
        m_main = re.search(r"\n\s*if\s+__name__\s*==\s*[\"']__main__[\"']\s*:\s*\n", src)
        if m_main:
            src = src[:m_main.start()] + approve_fn + "\n" + src[m_main.start():]
        else:
            src = src.rstrip() + "\n" + approve_fn + "\n"
        print("[OK] MODIF 5 applied : approve_and_fill_order + reject_pending_order ajoutees")

    # Validation finale
    validate(src, TARGET)

    # Ecriture
    write_text(TARGET, src)
    py_compile.compile(TARGET, doraise=True)
    print("[OK] py_compile final OK")
    print("[DONE]", MARKER)


if __name__ == "__main__":
    main()
