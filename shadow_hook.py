"""
shadow_hook.py - Phase 9.4 - Hook scheduler post-cycle pour Jalon 9 Shadow Overlap.

Appele en fin de execute_cycle() (api_server.py) :
  1. Lance shadow_engine sur le cycle qui vient de se terminer
  2. Si prev_cycle_id fourni : lance shadow_simulate_fills sur cycle precedent (J+1 dispo)
  3. Insere diff_log (n_orders, notional, tickers_only_X) par variant

Design :
  - SAFE-FAIL : toute exception est catch + loggee, ne casse JAMAIS execute_cycle
  - Idempotent : DELETE WHERE avant INSERT sur shadow_diff_log
  - Standalone : import minimal, pas de dependance sur api_server
"""
import sqlite3
import json
import subprocess
import sys
import os
import traceback
from datetime import datetime, timezone

# Path racine (suppose meme directory que les autres modules)
ROOT = os.path.dirname(os.path.abspath(__file__))

DB_DEFAULT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"


def _log(msg):
    """Print uniforme avec prefix marker."""
    print(f"[SHADOW_HOOK_V1] {msg}", flush=True)


def _run_subprocess(script_name, cycle_id, db_path):
    """Lance un sous-script Python avec --cycle-id. Capture stdout/stderr.

    Retourne (returncode, stdout, stderr).
    """
    script_path = os.path.join(ROOT, script_name)
    if not os.path.exists(script_path):
        return -1, "", f"script not found: {script_path}"

    cmd = [sys.executable, script_path, "--cycle-id", cycle_id, "--db", db_path]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -2, "", "TIMEOUT 180s"
    except Exception as e:
        return -3, "", f"subprocess exception: {e}"


def _find_prev_cycle_id(conn, current_cycle_id):
    """Trouve le cycle prod precedent (immediatement avant current_cycle_id).

    Source : convergence_snapshots.cycle_id DISTINCT, ordre desc.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT cycle_id FROM convergence_snapshots
        WHERE cycle_id < ?
        ORDER BY cycle_id DESC
        LIMIT 1
        """,
        (current_cycle_id,),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    return None


def _compute_and_insert_diff_log(conn, cycle_id):
    """Calcule + INSERT diff_log : 1 row par variant pour ce cycle.

    Pour chaque variant active :
      - n_orders_variant : COUNT(*) shadow_orders WHERE variant=X AND decision != filter
      - n_orders_prod    : COUNT(*) shadow_orders WHERE variant=prod AND decision != filter
      - n_blocked_by_convergence : COUNT(*) WHERE decision='exit'
      - notional_variant : SUM(notional) shadow_fills WHERE variant=X
      - notional_prod    : SUM(notional) shadow_fills WHERE variant=prod
      - tickers_only_variant_json : tickers presents dans variant mais pas prod (orders actifs)
      - tickers_only_prod_json    : tickers presents dans prod mais pas variant

    Idempotent : DELETE WHERE cycle_id=? AND variant_id=? avant INSERT.
    """
    cur = conn.cursor()

    # day_t depuis snapshot prod
    cur.execute(
        "SELECT day_t FROM shadow_cycle_snapshots WHERE cycle_id=? LIMIT 1",
        (cycle_id,),
    )
    row = cur.fetchone()
    if not row:
        _log(f"  diff_log SKIP : pas de snapshot pour cycle {cycle_id}")
        return 0
    day_t = row[0]

    # Variants actives (prod = variant_id 1)
    cur.execute(
        "SELECT variant_id, name FROM shadow_variants WHERE active=1 ORDER BY variant_id"
    )
    variants = cur.fetchall()
    if not variants:
        _log("  diff_log SKIP : aucune variant active")
        return 0

    # Prod stats (variant_id=1)
    PROD_VID = 1
    cur.execute(
        """
        SELECT ticker, decision FROM shadow_orders
        WHERE cycle_id=? AND variant_id=? AND decision != 'filter'
        """,
        (cycle_id, PROD_VID),
    )
    prod_orders = cur.fetchall()
    prod_tickers = set(r[0] for r in prod_orders)
    n_orders_prod = len(prod_orders)

    cur.execute(
        "SELECT COALESCE(SUM(notional),0) FROM shadow_fills WHERE cycle_id=? AND variant_id=?",
        (cycle_id, PROD_VID),
    )
    notional_prod = float(cur.fetchone()[0] or 0.0)

    inserted = 0
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    for variant_id, vname in variants:
        # Orders variant (non-filter)
        cur.execute(
            """
            SELECT ticker, decision FROM shadow_orders
            WHERE cycle_id=? AND variant_id=? AND decision != 'filter'
            """,
            (cycle_id, variant_id),
        )
        v_orders = cur.fetchall()
        v_tickers = set(r[0] for r in v_orders)
        n_orders_variant = len(v_orders)

        n_blocked = sum(1 for _, d in v_orders if d == "exit")

        cur.execute(
            "SELECT COALESCE(SUM(notional),0) FROM shadow_fills WHERE cycle_id=? AND variant_id=?",
            (cycle_id, variant_id),
        )
        notional_variant = float(cur.fetchone()[0] or 0.0)

        only_variant = sorted(v_tickers - prod_tickers)
        only_prod = sorted(prod_tickers - v_tickers)

        # Idempotence : delete existing row
        cur.execute(
            "DELETE FROM shadow_diff_log WHERE cycle_id=? AND variant_id=?",
            (cycle_id, variant_id),
        )

        cur.execute(
            """
            INSERT INTO shadow_diff_log (
                cycle_id, variant_id, day_t,
                n_orders_variant, n_orders_prod, n_blocked_by_convergence,
                notional_variant, notional_prod,
                pnl_variant_cycle, pnl_prod_cycle,
                tickers_only_variant_json, tickers_only_prod_json,
                notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
            """,
            (
                cycle_id,
                variant_id,
                day_t,
                n_orders_variant,
                n_orders_prod,
                n_blocked,
                notional_variant,
                notional_prod,
                json.dumps(only_variant),
                json.dumps(only_prod),
                f"variant={vname}",
                created_at,
            ),
        )
        inserted += 1
        _log(
            f"  diff_log [{vname:18s}] orders v/p={n_orders_variant}/{n_orders_prod} "
            f"notional v/p={notional_variant:,.0f}/{notional_prod:,.0f} "
            f"only_v={len(only_variant)} only_p={len(only_prod)}"
        )

    return inserted


def run_shadow_cycle(db_path, cycle_id, prev_cycle_id=None):
    """Entree principale du hook.

    Args :
      db_path : chemin DB sqlite
      cycle_id : cycle prod qui vient de se terminer
      prev_cycle_id : si fourni, simule fills sur ce cycle (J+1 = today). Si None, auto-detect.

    Retourne dict : {ok, engine_rc, fills_rc, diff_rows, prev_cycle_id, errors}
    """
    out = {
        "ok": False,
        "engine_rc": None,
        "fills_rc": None,
        "diff_rows": 0,
        "prev_cycle_id": None,
        "errors": [],
    }

    try:
        _log(f"=== START cycle={cycle_id} ===")

        # 1. Shadow engine sur cycle courant
        rc, sout, serr = _run_subprocess("shadow_engine.py", cycle_id, db_path)
        out["engine_rc"] = rc
        if rc != 0:
            out["errors"].append(f"shadow_engine rc={rc} stderr={serr[:200]}")
            _log(f"  shadow_engine FAIL rc={rc}")
        else:
            _log(f"  shadow_engine OK")

        # 2. Detection auto prev_cycle_id si non fourni
        conn = sqlite3.connect(db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            if prev_cycle_id is None:
                prev_cycle_id = _find_prev_cycle_id(conn, cycle_id)
            out["prev_cycle_id"] = prev_cycle_id
        finally:
            conn.close()

        # 3. Shadow simulate fills sur prev_cycle_id
        if prev_cycle_id:
            rc, sout, serr = _run_subprocess(
                "shadow_simulate_fills.py", prev_cycle_id, db_path
            )
            out["fills_rc"] = rc
            if rc != 0:
                out["errors"].append(f"shadow_fills rc={rc} stderr={serr[:200]}")
                _log(f"  shadow_fills [{prev_cycle_id}] FAIL rc={rc}")
            else:
                _log(f"  shadow_fills [{prev_cycle_id}] OK")
        else:
            _log("  shadow_fills SKIP : pas de prev_cycle_id")

        # 4. Diff log sur cycle courant
        conn = sqlite3.connect(db_path, timeout=30)
        try:
            inserted = _compute_and_insert_diff_log(conn, cycle_id)
            conn.commit()
            out["diff_rows"] = inserted
        except Exception as e:
            conn.rollback()
            out["errors"].append(f"diff_log exception: {e}")
            _log(f"  diff_log EXC: {e}")
        finally:
            conn.close()

        out["ok"] = len(out["errors"]) == 0
        _log(f"=== DONE ok={out['ok']} diff_rows={out['diff_rows']} ===")

    except Exception as e:
        out["errors"].append(f"top-level exception: {e}")
        out["errors"].append(traceback.format_exc()[:500])
        _log(f"=== TOP-LEVEL EXC: {e} ===")

    return out


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--db", default=DB_DEFAULT)
    p.add_argument("--cycle-id", required=True)
    p.add_argument("--prev-cycle-id", default=None)
    args = p.parse_args()

    result = run_shadow_cycle(args.db, args.cycle_id, args.prev_cycle_id)
    print()
    print("RESULT:", json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)
