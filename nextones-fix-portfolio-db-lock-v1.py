# -*- coding: utf-8 -*-
# [PORTFOLIO_DB_LOCK_FIX_V1]
# Patch api_server.py pour ajouter retry exponential sur portfolio.update()
# et garantir busy_timeout=5000 a la connexion.
#
# Cible : api_server.py L242-260 - bloc INSERT portfolio_history + UPDATE portfolio_state
# Strategie :
#   1. Remplacer le bloc "conn.execute(INSERT...); conn.execute(UPDATE...); conn.commit()"
#      par une fonction wrapper _portfolio_write_with_retry() qui tente 3 fois.
#   2. La fonction injecte PRAGMA busy_timeout=5000 sur la connexion avant chaque essai.
#   3. Apres 3 echecs, log explicite avec n_attempts.
#
# Validation : ast.parse + py_compile + backup.
# Idempotent : marker [PORTFOLIO_DB_LOCK_FIX_V1] verifie en debut.
import ast
import os
import py_compile
import re
import shutil
import sys
from datetime import datetime

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")
MARKER = "[PORTFOLIO_DB_LOCK_FIX_V1]"


HELPER_CODE = '''
# ---------------------------------------------------------------------- [PORTFOLIO_DB_LOCK_FIX_V1] BEGIN
def _portfolio_write_with_retry(conn, today_str, total_value, cash, total_pnl,
                                total_pnl_pct, daily_pnl, daily_pnl_pct,
                                max_attempts=3):
    """Wrapper avec retry exponential pour gerer les DB locks transitoires."""
    import time as _t
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            try:
                conn.execute("PRAGMA busy_timeout=5000")
            except Exception:
                pass
            conn.execute(
                """INSERT INTO portfolio_history (date, total_value, cash, total_pnl)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(date) DO UPDATE SET
                     total_value=excluded.total_value,
                     cash=excluded.cash,
                     total_pnl=excluded.total_pnl""",
                (today_str, round(total_value, 2), round(cash, 2), round(total_pnl, 2)),
            )
            conn.execute(
                """UPDATE portfolio_state
                   SET total_value=?, total_pnl=?, total_pnl_pct=?,
                       daily_pnl=?, daily_pnl_pct=?, updated_at=?
                   WHERE id=1""",
                (round(total_value, 2), round(total_pnl, 2), round(total_pnl_pct, 4),
                 round(daily_pnl, 2), round(daily_pnl_pct, 4),
                 datetime.now().isoformat()),
            )
            conn.commit()
            if attempt > 1:
                print("[portfolio] Write OK after %d attempt(s)" % attempt)
            return True
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if "locked" in msg or "busy" in msg:
                wait_ms = 100 * (3 ** (attempt - 1))
                print("[portfolio] DB locked (attempt %d/%d), wait %d ms" % (
                    attempt, max_attempts, wait_ms))
                _t.sleep(wait_ms / 1000.0)
                continue
            raise
    print("[portfolio] Update error after %d attempts: %s" % (max_attempts, last_err))
    return False
# ---------------------------------------------------------------------- [PORTFOLIO_DB_LOCK_FIX_V1] END
'''


def main():
    if not os.path.isfile(TARGET):
        print("[KO] cible introuvable : " + TARGET)
        sys.exit(1)

    with open(TARGET, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER in src:
        print("[SKIP] marker {} deja present - patch idempotent".format(MARKER))
        return

    # Backup
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = TARGET + ".bak." + ts
    shutil.copy2(TARGET, backup)
    print("[OK] backup -> " + backup)

    # Etape 1 : Inserer le helper juste avant le bloc portfolio update
    # On detecte par la signature du commentaire "Rate Limiter"
    anchor_rate = "# Rate Limiter"
    if anchor_rate not in src:
        print("[KO] anchor '{}' non trouve".format(anchor_rate))
        sys.exit(1)

    # Etape 2 : Remplacer le bloc des 2 conn.execute + conn.commit
    # On cherche le bloc exact contenant INSERT INTO portfolio_history
    pat_block = re.compile(
        r"(\n\s*conn\.execute\(\s*\n\s*\"\"\"INSERT INTO portfolio_history.*?"
        r"conn\.commit\(\)\s*\n\s*print\(f\"\[portfolio\] Updated:.*?\}\"\))",
        re.DOTALL,
    )
    m = pat_block.search(src)
    if not m:
        # Fallback : pattern plus large
        pat_block2 = re.compile(
            r"(conn\.execute\([^)]*\"\"\"INSERT INTO portfolio_history.*?"
            r"conn\.commit\(\))",
            re.DOTALL,
        )
        m = pat_block2.search(src)
        if not m:
            print("[KO] bloc INSERT/UPDATE/commit introuvable - inspecter manuellement")
            sys.exit(1)
        print("[INFO] match fallback pattern")
    else:
        print("[OK] bloc INSERT/UPDATE/commit/print trouve")

    old_block = m.group(0)
    print("[INFO] bloc remplace, taille = {} chars".format(len(old_block)))

    new_call = (
        "\n        # ------------------------------------------------------ {marker} CALL\n"
        "        ok = _portfolio_write_with_retry(\n"
        "            conn, today_str, total_value, cash, total_pnl,\n"
        "            total_pnl_pct, daily_pnl, daily_pnl_pct,\n"
        "            max_attempts=3,\n"
        "        )\n"
        "        if ok:\n"
        "            print(f\"[portfolio] Updated: total_value={{total_value:.2f}}, "
        "pnl={{total_pnl:.2f}}, daily_pnl={{daily_pnl:.2f}}\")\n"
        "        # ------------------------------------------------------ {marker} CALL END"
    ).format(marker=MARKER)
    # Avec f-string formatting on a double braces, donc on remplace apres
    new_call = new_call.replace("{{", "{").replace("}}", "}")

    src2 = src.replace(old_block, new_call)
    if src2 == src:
        print("[KO] remplacement n'a rien change")
        sys.exit(1)

    # Etape 3 : Inserer le helper avant "# Rate Limiter"
    src3 = src2.replace(
        anchor_rate,
        HELPER_CODE.rstrip() + "\n\n\n" + anchor_rate,
        1,
    )

    # Validation
    try:
        ast.parse(src3)
        print("[OK] ast.parse")
    except SyntaxError as e:
        print("[KO] ast.parse echoue : {}".format(e))
        # Dump pour debug
        with open(TARGET + ".broken", "w", encoding="utf-8") as f:
            f.write(src3)
        sys.exit(1)

    # Ecriture
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(src3)
    print("[OK] ecriture {} -> {} chars".format(TARGET, len(src3)))

    try:
        py_compile.compile(TARGET, doraise=True)
        print("[OK] py_compile")
    except py_compile.PyCompileError as e:
        print("[KO] py_compile echoue : {}".format(e))
        sys.exit(1)

    print()
    print("=" * 60)
    print("PATCH APPLIED - {}".format(MARKER))
    print("=" * 60)
    print("Redemarrer uvicorn pour activer.")


if __name__ == "__main__":
    main()
