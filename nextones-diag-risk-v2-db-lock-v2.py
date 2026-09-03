# -*- coding: utf-8 -*-
# nextones-diag-risk-v2-db-lock-v2.py
#
# Objectif : comprendre POURQUOI RISK V2 retombe en "database is locked"
#            alors qu'on a deja applique [DB_LOCK_FIX_V1] et fix-risk-v2-db-lock.
#
# On verifie :
#   1) Mode WAL actif + PRAGMA busy_timeout en cours dans la DB
#   2) Les opens sqlite3.connect dans risk_pretrade.py : timeout ? isolation_level ? PRAGMA ?
#   3) Combien d'occurrences de "database is locked" dans les ordres recents
#      et a quel(s) timestamp(s)
#   4) Y a-t-il une transaction longue qui detient le lock au moment des
#      cycles (ex: scheduler concurrent, reconciler, ingestion)
#   5) Structure du wrapper [RISK_V2_WIRED] dans execution_engine.py :
#      open() / try/except / commit/close /
#
# Lecture seule, ASCII pur.

import os
import re
import sys
import json
import sqlite3

WORKDIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(WORKDIR, "thesium.db")

FILES = {
    "risk_pretrade": "risk_pretrade.py",
    "execution_engine": "execution_engine.py",
    "scheduler": "scheduler.py",
    "broker_router": "broker_router.py",
    "broker_reconciler": "broker_reconciler.py",
}


def hr(t=""):
    print("")
    print("=" * 72)
    if t:
        print(t)
        print("-" * 72)


def read(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except FileNotFoundError:
        return None


def grep_lines(src, pattern, label, max_lines=40, context=1):
    """Affiche les lignes matchant `pattern` (regex) avec contexte."""
    if src is None:
        print("  [" + label + "] fichier absent")
        return
    lines = src.splitlines()
    rx = re.compile(pattern)
    hits = []
    for i, ln in enumerate(lines):
        if rx.search(ln):
            hits.append(i)
    print("  [" + label + "] " + str(len(hits)) + " match(s) pour /" + pattern + "/")
    shown = 0
    for i in hits:
        if shown >= max_lines:
            print("  ... (truncated)")
            break
        a = max(0, i - context)
        b = min(len(lines), i + context + 1)
        for j in range(a, b):
            marker = ">>" if j == i else "  "
            print("    " + marker + " L" + str(j + 1).rjust(4) + " | " + lines[j][:200])
        print("    ---")
        shown += 1


def main():
    if not os.path.exists(WORKDIR):
        print("ERREUR : workdir introuvable " + WORKDIR)
        sys.exit(2)

    # --- 1) WAL + busy_timeout sur la DB ---
    hr("[1] PRAGMA de la DB")
    conn = sqlite3.connect(DB, timeout=2.0)
    try:
        for p in ("journal_mode", "busy_timeout", "synchronous",
                  "wal_autocheckpoint", "locking_mode"):
            try:
                v = conn.execute("PRAGMA " + p).fetchone()
                print("  PRAGMA " + p + " = " + str(v[0] if v else "?"))
            except Exception as e:
                print("  PRAGMA " + p + " : ERREUR " + str(e))
        # Fichiers WAL/SHM presents ?
        for ext in ("-wal", "-shm"):
            f = DB + ext
            if os.path.exists(f):
                sz = os.path.getsize(f)
                print("  " + os.path.basename(f) + " : " + str(sz) + " bytes")
            else:
                print("  " + os.path.basename(f) + " : absent")
    finally:
        conn.close()

    # --- 2) Connect patterns dans risk_pretrade.py ---
    hr("[2] sqlite3.connect / open patterns dans risk_pretrade.py")
    src_risk = read(os.path.join(WORKDIR, FILES["risk_pretrade"]))
    if src_risk is None:
        print("  ABSENT : risk_pretrade.py")
    else:
        print("  Taille : " + str(len(src_risk)) + " bytes, " + str(src_risk.count(chr(10))) + " lignes")
        # Markers connus
        for m in ("[RISK_V2]", "[DB_LOCK_FIX_V1]", "RISK_V2_FALLBACK"):
            c = src_risk.count(m)
            print("  marker " + m + " : " + str(c) + " occurrence(s)")
        print("")
        grep_lines(src_risk, r"sqlite3\.connect", "sqlite3.connect", max_lines=10, context=2)
        grep_lines(src_risk, r"busy_timeout", "busy_timeout", max_lines=10, context=1)
        grep_lines(src_risk, r"PRAGMA", "PRAGMA", max_lines=10, context=1)
        grep_lines(src_risk, r"isolation_level", "isolation_level", max_lines=10, context=1)
        grep_lines(src_risk, r"timeout\s*=", "timeout=...", max_lines=10, context=1)
        grep_lines(src_risk, r"\.commit\(\)|\.rollback\(\)|\.close\(\)", "commit/rollback/close", max_lines=15, context=0)
        grep_lines(src_risk, r"database is locked|OperationalError", "lock handling", max_lines=10, context=2)

    # --- 3) Wrapper dans execution_engine.py ---
    hr("[3] Wrapper [RISK_V2_WIRED] dans execution_engine.py")
    src_exe = read(os.path.join(WORKDIR, FILES["execution_engine"]))
    if src_exe is None:
        print("  ABSENT : execution_engine.py")
    else:
        print("  Taille : " + str(len(src_exe)) + " bytes")
        for m in ("[RISK_V2_WIRED]", "[RISK_V2]", "risk_v2_error", "database is locked"):
            print("  marker " + m + " : " + str(src_exe.count(m)) + " occurrence(s)")
        print("")
        grep_lines(src_exe, r"\[RISK_V2_WIRED\]", "[RISK_V2_WIRED]", max_lines=5, context=4)
        grep_lines(src_exe, r"risk_v2_error", "risk_v2_error", max_lines=5, context=3)
        grep_lines(src_exe, r"def\s+run_risk_v2|risk_pretrade", "appel risk_v2", max_lines=10, context=2)

    # --- 4) Erreurs risk_v2 sur les ordres recents ---
    hr("[4] Occurrences 'database is locked' dans orders.risk_check_result (recent)")
    conn = sqlite3.connect(DB, timeout=2.0)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, created_at, status, instrument_id, side, quantity, "
            "       substr(risk_check_result, 1, 500) AS rc_head "
            "FROM orders "
            "WHERE created_at >= date('now','-2 day') "
            "ORDER BY id DESC LIMIT 50"
        ).fetchall()
        locked_orders = []
        risk_v2_present = 0
        risk_v2_passed = 0
        risk_v2_blocked = 0
        for r in rows:
            rc = r["rc_head"] or ""
            if "database is locked" in rc:
                locked_orders.append(r["id"])
            if "risk_v2" in rc.lower():
                risk_v2_present += 1
            if "\"passed\": 1" in rc or "\"passed\":1" in rc:
                risk_v2_passed += 1
            if "\"passed\": 0" in rc or "\"passed\":0" in rc:
                risk_v2_blocked += 1
        print("  orders scannes : " + str(len(rows)))
        print("  with 'database is locked' : " + str(len(locked_orders))
              + " -> " + str(locked_orders))
        print("  with risk_v2 anywhere     : " + str(risk_v2_present))
        print("  with risk_v2 passed=1     : " + str(risk_v2_passed))
        print("  with risk_v2 passed=0     : " + str(risk_v2_blocked))

        # Detail des 5 derniers ordres locked
        if locked_orders:
            print("")
            print("  Detail des 5 derniers ordres en lock :")
            for oid in locked_orders[:5]:
                full = conn.execute(
                    "SELECT id, created_at, instrument_id, side, quantity, risk_check_result "
                    "FROM orders WHERE id=?", (oid,)
                ).fetchone()
                print("    --- order #" + str(full["id"]) + " ("
                      + str(full["created_at"]) + ") ---")
                rc_str = full["risk_check_result"] or ""
                try:
                    rc = json.loads(rc_str)
                    print("    approved=" + str(rc.get("approved"))
                          + "  action=" + str(rc.get("action")))
                    warns = rc.get("warnings") or []
                    for w in warns:
                        if isinstance(w, dict) and w.get("source") == "[RISK_V2]":
                            print("    RISK_V2: " + json.dumps(w, ensure_ascii=False))
                except Exception as e:
                    print("    parse err: " + str(e))

        # --- 5) Process(es) tenant la DB au moment des cycles ---
        # On regarde les timestamps des cycles d'aujourd'hui pour voir
        # s'ils correspondent a une activite scheduler.
        print("")
        print("  Cycles d'aujourd'hui (orders.created_at) :")
        days = conn.execute(
            "SELECT date(created_at) AS d, count(*) AS n "
            "FROM orders WHERE created_at >= date('now','-2 day') "
            "GROUP BY date(created_at) ORDER BY d DESC"
        ).fetchall()
        for d in days:
            print("    " + str(d["d"]) + " : " + str(d["n"]) + " ordres")
    finally:
        conn.close()

    # --- 6) Scheduler : qui ecrit en concurrent ---
    hr("[6] Tasks scheduler suceptibles de tenir un lock long")
    src_sch = read(os.path.join(WORKDIR, FILES["scheduler"]))
    if src_sch is None:
        print("  ABSENT : scheduler.py")
    else:
        print("  Taille : " + str(len(src_sch)) + " bytes")
        grep_lines(src_sch, r"add_job|cron|interval", "jobs schedules", max_lines=30, context=0)
        grep_lines(src_sch, r"reconcil|ingestion|hype|pplx", "potential writers", max_lines=15, context=0)

    # --- 7) broker_reconciler : transactions ---
    hr("[7] broker_reconciler.py - transactions")
    src_rec = read(os.path.join(WORKDIR, FILES["broker_reconciler"]))
    if src_rec is None:
        print("  ABSENT : broker_reconciler.py")
    else:
        grep_lines(src_rec, r"sqlite3\.connect|BEGIN|commit", "txn patterns", max_lines=15, context=1)
        grep_lines(src_rec, r"busy_timeout|PRAGMA", "PRAGMA", max_lines=5, context=1)

    hr("FIN DIAG RISK V2 LOCK")


if __name__ == "__main__":
    main()
