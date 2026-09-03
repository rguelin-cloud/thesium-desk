# -*- coding: utf-8 -*-
# nextones-fix-risk-v2-dblock-v2.py
#
# Patch [RISK_V2_DBLOCK_FIX_V2] - elimine le "database is locked" sur RISK V2.
#
# Strategie :
#   FICHIER 1 : risk_pretrade.py
#     - Ajoute param optionnel `conn=None` a run_pretrade_checks
#     - Si conn fourni : reutilise la conn existante (PAS de 2e connect)
#                       et NE close PAS a la fin
#     - Sinon : fallback _conn(db_path) comme avant
#     - Ajoute retry x3 backoff 100/300/900ms dans _conn() sur OperationalError
#
#   FICHIER 2 : execution_engine.py (wrapper [RISK_V2_WIRED])
#     - Passe conn=conn au _rv2_run() pour reutiliser la conn ouverte
#
# Garanties :
#   - Idempotent (skip si marker V2 deja present)
#   - Backup .py.bak.<timestamp> pour chaque fichier
#   - Validation ast.parse + py_compile avant ecriture finale
#   - Ecriture utf-8 sans BOM, atomique
#   - Rollback en chaine : si fichier 2 echoue, restaure fichier 1

import os
import re
import ast
import sys
import time
import shutil
import py_compile
import tempfile

WORKDIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
F_RISK = os.path.join(WORKDIR, "risk_pretrade.py")
F_EXEC = os.path.join(WORKDIR, "execution_engine.py")

MARKER_V2 = "[RISK_V2_DBLOCK_FIX_V2]"


def read_file(p):
    with open(p, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_atomic(p, content):
    d = os.path.dirname(p)
    fd, tmp = tempfile.mkstemp(prefix=".rv2dlf2_", suffix=".tmp", dir=d)
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        py_compile.compile(tmp, doraise=True)
        shutil.move(tmp, p)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def backup(p, ts):
    bak = p + ".bak." + ts
    shutil.copy2(p, bak)
    return bak


# -----------------------------------------------------------------
# PATCH FICHIER 1 : risk_pretrade.py
# -----------------------------------------------------------------
def patch_risk_pretrade(src):
    """Retourne (new_src, info_dict) ou leve une Exception."""

    # --- Patch _conn : ajouter retry sur OperationalError ---
    old_conn = (
        "def _conn(db_path: str) -> sqlite3.Connection:  # [RISK_V2_DBLOCK_FIX_V1]\n"
        "    c = sqlite3.connect(db_path, timeout=30.0)\n"
        "    c.row_factory = sqlite3.Row\n"
        "    try:\n"
        "        c.execute(\"PRAGMA busy_timeout=30000\")\n"
        "    except Exception:\n"
        "        pass\n"
        "    return c\n"
    )
    new_conn = (
        "def _conn(db_path: str) -> sqlite3.Connection:  # " + MARKER_V2 + "\n"
        "    import time as _t\n"
        "    _last = None\n"
        "    for _attempt in range(3):\n"
        "        try:\n"
        "            c = sqlite3.connect(db_path, timeout=30.0)\n"
        "            c.row_factory = sqlite3.Row\n"
        "            try:\n"
        "                c.execute(\"PRAGMA busy_timeout=30000\")\n"
        "            except Exception:\n"
        "                pass\n"
        "            return c\n"
        "        except sqlite3.OperationalError as _e:\n"
        "            _last = _e\n"
        "            if \"locked\" not in str(_e).lower():\n"
        "                raise\n"
        "            _t.sleep([0.1, 0.3, 0.9][_attempt])\n"
        "    raise _last if _last is not None else sqlite3.OperationalError(\"unknown lock\")\n"
    )
    if old_conn not in src:
        raise RuntimeError("ANCIEN _conn introuvable - le fichier a deja ete modifie ?")
    src2 = src.replace(old_conn, new_conn, 1)

    # --- Patch signature run_pretrade_checks : ajouter conn=None ---
    # On cherche la ligne "side: str," dans la signature et on insere
    # "    conn: Optional[sqlite3.Connection] = None," apres "side: str,"
    # MAIS uniquement dans la signature de run_pretrade_checks.
    sig_old = (
        "def run_pretrade_checks(\n"
        "    ticker: str,\n"
        "    qty: float,\n"
        "    price: float,\n"
        "    side: str,\n"
        "    db_path: Optional[str] = None,\n"
        "    params: Optional[Dict[str, Any]] = None,\n"
        ") -> Dict[str, Any]:\n"
    )
    sig_new = (
        "def run_pretrade_checks(\n"
        "    ticker: str,\n"
        "    qty: float,\n"
        "    price: float,\n"
        "    side: str,\n"
        "    db_path: Optional[str] = None,\n"
        "    params: Optional[Dict[str, Any]] = None,\n"
        "    conn: Optional[sqlite3.Connection] = None,  # " + MARKER_V2 + " accepte conn existante\n"
        ") -> Dict[str, Any]:\n"
    )
    if sig_old not in src2:
        raise RuntimeError("ANCIENNE signature run_pretrade_checks introuvable")
    src2 = src2.replace(sig_old, sig_new, 1)

    # --- Patch corps : utiliser conn fourni si disponible ---
    # On cible la ligne "c = _conn(db_path)" qui est unique dans le fichier.
    body_old = "    c = _conn(db_path)\n    try:\n"
    body_new = (
        "    # " + MARKER_V2 + " reutilise la conn existante pour eviter le 2e writer lock\n"
        "    _own_conn = conn is None\n"
        "    c = conn if conn is not None else _conn(db_path)\n"
        "    try:\n"
    )
    if body_old not in src2:
        raise RuntimeError("ANCIEN 'c = _conn(db_path)' introuvable")
    src2 = src2.replace(body_old, body_new, 1)

    # --- Patch finally close : ne fermer que si on a ouvert la conn ---
    close_old = "    finally:\n        c.close()\n"
    close_new = (
        "    finally:\n"
        "        if _own_conn:  # " + MARKER_V2 + " ne ferme pas la conn empruntee\n"
        "            c.close()\n"
    )
    if close_old not in src2:
        raise RuntimeError("ANCIEN 'finally: c.close()' introuvable")
    src2 = src2.replace(close_old, close_new, 1)

    return src2


# -----------------------------------------------------------------
# PATCH FICHIER 2 : execution_engine.py
# -----------------------------------------------------------------
def patch_execution_engine(src):
    """Retourne new_src ou leve."""
    # Cible la ligne unique :
    #     _rv2 = _rv2_run(_rv2_ticker, quantity, effective_price, side)
    # On ajoute conn=conn en kwarg.
    old = "            _rv2 = _rv2_run(_rv2_ticker, quantity, effective_price, side)\n"
    new = (
        "            # " + MARKER_V2 + " passe la conn ouverte pour eviter db lock\n"
        "            _rv2 = _rv2_run(_rv2_ticker, quantity, effective_price, side, conn=conn)\n"
    )
    if old not in src:
        # Tolerant : variations d'indentation
        # On cherche par regex
        rx = re.compile(
            r"([ \t]+)_rv2\s*=\s*_rv2_run\(\s*_rv2_ticker\s*,\s*quantity\s*,\s*effective_price\s*,\s*side\s*\)\s*\n"
        )
        m = rx.search(src)
        if not m:
            raise RuntimeError("Appel _rv2_run(...) introuvable dans execution_engine.py")
        indent = m.group(1)
        new_dyn = (
            indent + "# " + MARKER_V2 + " passe la conn ouverte pour eviter db lock\n"
            + indent + "_rv2 = _rv2_run(_rv2_ticker, quantity, effective_price, side, conn=conn)\n"
        )
        return src[:m.start()] + new_dyn + src[m.end():]
    return src.replace(old, new, 1)


# -----------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------
def main():
    for p in (F_RISK, F_EXEC):
        if not os.path.exists(p):
            print("ERREUR : " + p + " absent")
            sys.exit(2)

    src_risk = read_file(F_RISK)
    src_exec = read_file(F_EXEC)

    # Idempotence
    if MARKER_V2 in src_risk and MARKER_V2 in src_exec:
        print("OK : " + MARKER_V2 + " deja present dans les 2 fichiers -> skip")
        sys.exit(0)
    if MARKER_V2 in src_risk and MARKER_V2 not in src_exec:
        print("ATTENTION : V2 present dans risk_pretrade mais PAS dans execution_engine.")
        print("           On va patcher uniquement execution_engine.")
    if MARKER_V2 not in src_risk and MARKER_V2 in src_exec:
        print("ATTENTION : V2 present dans execution_engine mais PAS dans risk_pretrade.")
        print("           On va patcher uniquement risk_pretrade.")

    ts = time.strftime("%Y%m%d_%H%M%S")

    # Patch risk_pretrade
    bak_risk = None
    if MARKER_V2 not in src_risk:
        print("")
        print("=== PATCH risk_pretrade.py ===")
        try:
            new_risk = patch_risk_pretrade(src_risk)
        except Exception as e:
            print("ERREUR patch risk_pretrade : " + str(e))
            sys.exit(3)
        try:
            ast.parse(new_risk)
        except SyntaxError as e:
            print("ERREUR AST risk_pretrade : " + str(e))
            sys.exit(4)
        bak_risk = backup(F_RISK, ts)
        print("Backup risk_pretrade : " + bak_risk)
        write_atomic(F_RISK, new_risk)
        print("OK : risk_pretrade.py patche (" + str(len(src_risk)) + " -> " + str(len(new_risk)) + " bytes)")

    # Patch execution_engine
    if MARKER_V2 not in src_exec:
        print("")
        print("=== PATCH execution_engine.py ===")
        try:
            new_exec = patch_execution_engine(src_exec)
        except Exception as e:
            print("ERREUR patch execution_engine : " + str(e))
            if bak_risk:
                print("ROLLBACK risk_pretrade depuis " + bak_risk)
                shutil.copy2(bak_risk, F_RISK)
            sys.exit(5)
        try:
            ast.parse(new_exec)
        except SyntaxError as e:
            print("ERREUR AST execution_engine : " + str(e))
            if bak_risk:
                print("ROLLBACK risk_pretrade depuis " + bak_risk)
                shutil.copy2(bak_risk, F_RISK)
            sys.exit(6)
        bak_exec = backup(F_EXEC, ts)
        print("Backup execution_engine : " + bak_exec)
        try:
            write_atomic(F_EXEC, new_exec)
            print("OK : execution_engine.py patche (" + str(len(src_exec)) + " -> " + str(len(new_exec)) + " bytes)")
        except Exception as e:
            print("ERREUR ecriture execution_engine : " + str(e))
            if bak_risk:
                print("ROLLBACK risk_pretrade depuis " + bak_risk)
                shutil.copy2(bak_risk, F_RISK)
            sys.exit(7)

    print("")
    print("=" * 60)
    print("PATCH " + MARKER_V2 + " applique avec succes.")
    print("")
    print("VALIDATION :")
    print("  1) Restart API :")
    print("     Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }")
    print("     py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print("  2) Trigger un cycle (POST /api/cycle/execute avec JWT)")
    print("  3) Verifier sur le prochain ordre que risk_check_result ne contient")
    print("     PLUS 'database is locked' et que risk_v2.passed est defini.")


if __name__ == "__main__":
    main()
