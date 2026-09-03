# -*- coding: utf-8 -*-
# [DIAG_BUGS_V1]
# Diag des 2 bugs identifies :
#   1. "[portfolio] Update error: database is locked"
#   2. GET /api/orders/pending-validation -> 404 Not Found
#
# Inspecte :
#   - api_server_with_static.py : endpoints orders + fonction portfolio update
#   - mode journal SQLite (rollback vs WAL)
#   - emplacement du portfolio.update() (a wrapper avec retry)
import os
import re
import sqlite3

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(ROOT, "thesium.db")
API = os.path.join(ROOT, "api_server_with_static.py")


def header(t):
    print()
    print("=" * 72)
    print("  " + t)
    print("=" * 72)


def step1_journal_mode():
    header("1. Mode journal SQLite")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    mode = cur.execute("PRAGMA journal_mode").fetchone()[0]
    print("  journal_mode = {}".format(mode))
    if mode.lower() != "wal":
        print("  [!!] Mode actuel = {} (rollback)".format(mode))
        print("       Recommande : WAL pour reduire les locks lecture/ecriture")
    else:
        print("  [OK] WAL actif")
    # busy_timeout
    bt = cur.execute("PRAGMA busy_timeout").fetchone()[0]
    print("  busy_timeout = {} ms".format(bt))
    con.close()


def step2_endpoints_orders():
    header("2. Endpoints /api/orders/* existants")
    with open(API, "r", encoding="utf-8-sig") as f:
        src = f.read()
    pat = re.compile(
        r"@app\.(get|post|put|delete)\([\"'](/api/orders[^\"']*)[\"']",
    )
    found = []
    for m in pat.finditer(src):
        verb = m.group(1).upper()
        path = m.group(2)
        found.append((verb, path))
        print("  {:6s} {}".format(verb, path))
    if not found:
        print("  AUCUN endpoint /api/orders/*")
    print()
    # Verifier specifiquement pending-validation
    if any("pending-validation" in p for v, p in found):
        print("  [OK] /api/orders/pending-validation existe")
    else:
        print("  [KO] /api/orders/pending-validation MANQUANT")
    return found


def step3_orders_table_schema():
    header("3. Schema table orders")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cols = cur.execute("PRAGMA table_info(orders)").fetchall()
    if not cols:
        # Peut etre une autre table
        tables = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND (name LIKE '%order%' OR name LIKE '%fill%') "
            "ORDER BY name"
        ).fetchall()
        print("  Tables candidates :")
        for t in tables:
            print("    " + t[0])
            for c in cur.execute(
                "PRAGMA table_info({})".format(t[0])
            ).fetchall():
                print("      cid={} name={} type={} notnull={}".format(
                    c[0], c[1], c[2], c[3]
                ))
        con.close()
        return
    print("  Colonnes orders :")
    for c in cols:
        print("    cid={} name={} type={} notnull={} dflt={}".format(
            c[0], c[1], c[2], c[3], c[4]
        ))
    # Compter par statut
    print()
    print("  Repartition par statut :")
    rows = cur.execute(
        "SELECT status, COUNT(*) FROM orders GROUP BY status ORDER BY 2 DESC"
    ).fetchall()
    for s, n in rows:
        print("    {:25s} : {}".format(s or "(null)", n))
    con.close()


def step4_portfolio_update_callsite():
    header("4. Localisation de portfolio.update() dans le code")
    # Cherche tous les .py qui font "Update error" ou "[portfolio]"
    found_files = []
    for f in os.listdir(ROOT):
        if not f.endswith(".py"):
            continue
        full = os.path.join(ROOT, f)
        try:
            with open(full, "r", encoding="utf-8-sig", errors="ignore") as fh:
                content = fh.read()
        except Exception:
            continue
        if "[portfolio]" in content or "portfolio.update" in content:
            found_files.append(f)

    print("  Fichiers contenant [portfolio] ou portfolio.update :")
    for f in found_files:
        print("    " + f)

    # Pour chaque fichier, montrer les lignes avec "Update error" ou "is locked"
    print()
    for f in found_files:
        full = os.path.join(ROOT, f)
        with open(full, "r", encoding="utf-8-sig", errors="ignore") as fh:
            lines = fh.readlines()
        hits = []
        for i, ln in enumerate(lines, 1):
            if "Update error" in ln or "[portfolio]" in ln or "database is locked" in ln.lower():
                hits.append((i, ln.rstrip()))
        if hits:
            print("  {} :".format(f))
            for i, ln in hits[:15]:
                print("    L{:5d}: {}".format(i, ln[:130]))


def step5_uvicorn_workers_lock():
    header("5. Inspection api_server_with_static.py - connexion DB et workers")
    with open(API, "r", encoding="utf-8-sig") as f:
        src = f.read()
    # Pattern : sqlite3.connect / get_db / DB_PATH / WAL / journal_mode
    patterns = [
        ("sqlite3.connect", r"sqlite3\.connect\([^)]+\)"),
        ("check_same_thread", r"check_same_thread\s*=\s*\w+"),
        ("isolation_level", r"isolation_level\s*=\s*\w+"),
        ("PRAGMA journal_mode", r"PRAGMA\s+journal_mode"),
        ("PRAGMA busy_timeout", r"PRAGMA\s+busy_timeout"),
        ("WAL keyword", r"\bWAL\b"),
    ]
    for label, pat in patterns:
        matches = re.findall(pat, src, re.IGNORECASE)
        print("  {:25s} : {} occurrence(s)".format(label, len(matches)))
        for m in matches[:3]:
            print("      -> {}".format(m[:80]))


def step6_recommendations():
    header("6. Recommandations a appliquer")
    print("  A. Activer WAL une fois pour toutes en DB :")
    print("     sqlite3 thesium.db \"PRAGMA journal_mode=WAL;\"")
    print("     (persistant sur le fichier .db, survie au restart)")
    print()
    print("  B. Ajouter au moment de chaque connexion :")
    print("     con.execute('PRAGMA journal_mode=WAL')")
    print("     con.execute('PRAGMA busy_timeout=5000')  # 5 sec")
    print()
    print("  C. Wrapper portfolio.update() avec retry exponential (max 3)")
    print()
    print("  D. Ajouter endpoint GET /api/orders/pending-validation")
    print("     -> SELECT * FROM orders WHERE status IN ('pending_validation',")
    print("        'EN ATTENTE', 'awaiting_validation') ORDER BY created_at DESC")


def main():
    print("NEXTONES diag bugs - DB lock + endpoint pending-validation")
    step1_journal_mode()
    step2_endpoints_orders()
    step3_orders_table_schema()
    step4_portfolio_update_callsite()
    step5_uvicorn_workers_lock()
    step6_recommendations()


if __name__ == "__main__":
    main()
