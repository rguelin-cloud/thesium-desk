# -*- coding: utf-8 -*-
# [NEXTONES-VALIDATE-BROKER-RECONCILER-V1]
#
# Validator full-stack Phase 3B etape 4
# Valide la chaine complete reconciler ActivTrades <-> Thesium :
#
#   [1] Pre-conditions : modules, DB, tables, schemas
#   [2] MetaAPI configure et atteignable (compte 1004815)
#   [3] Resolver heuristique : broker_universe peuple, BrokerMatch OK
#   [4] Reconciler dry-run no-broker (mode test sans MetaAPI)
#   [5] Reconciler live --source metaapi_live (saute si marche ferme)
#   [6] Idempotence : 2 runs -> 2 run_id distincts, log coherent
#   [7] Regression : --source shadow_only fonctionne
#
# Exit codes :
#   0 = tous tests pass
#   1 = un ou plusieurs FAIL
#   2 = pre-conditions KO (pas la peine de continuer)
#
# Usage :
#   py -3.13 nextones-validate-broker-reconciler.py             # complet
#   py -3.13 nextones-validate-broker-reconciler.py --skip-live # saute [5]

import argparse
import datetime as dt
import json
import os
import sqlite3
import subprocess
import sys

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(PROD, "thesium.db")
RECONCILER = os.path.join(PROD, "nextones-broker-reconciler.py")
RESOLVER = os.path.join(PROD, "nextones-broker-resolver.py")
PROVIDER = os.path.join(PROD, "metaapi_provider.py")
MARKET_CAL = os.path.join(PROD, "nextones-market-calendar.py")

sys.path.insert(0, PROD)

PASS = 0
FAIL = 0
FAILED_LABELS = []


# ===================================================================
# Helpers
# ===================================================================

def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


def check(label, cond, expected=None, got=None, fatal=False):
    global PASS, FAIL, FAILED_LABELS
    if cond:
        print(f"  [OK]   {label}")
        PASS += 1
        return True
    ex = f" expected={expected}" if expected is not None else ""
    gt = f" got={got}" if got is not None else ""
    print(f"  [FAIL] {label}{ex}{gt}")
    FAIL += 1
    FAILED_LABELS.append(label)
    if fatal:
        print("[FATAL] pre-condition KO, arret")
        summary()
        sys.exit(2)
    return False


def run_reconciler(args, timeout=120):
    """Lance le reconciler, retourne (rc, stdout, stderr)."""
    cmd = ["py", "-3.13", RECONCILER] + args
    print(f"  cmd : {' '.join(cmd)}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, cwd=PROD,
                           encoding="utf-8", errors="replace")
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"


def open_db():
    con = sqlite3.connect(DB, timeout=10.0)
    con.execute("PRAGMA busy_timeout=10000")
    con.row_factory = sqlite3.Row
    return con


def last_run_id(con):
    row = con.execute(
        "SELECT MAX(id) AS mid FROM broker_reconciliation_runs"
    ).fetchone()
    return row["mid"] if row and row["mid"] is not None else 0


def fetch_run(con, run_id):
    return con.execute(
        "SELECT * FROM broker_reconciliation_runs WHERE id=?",
        (run_id,),
    ).fetchone()


def count_log_for_run(con, run_id):
    return con.execute(
        "SELECT COUNT(*) AS n FROM broker_reconciliation_log WHERE run_id=?",
        (run_id,),
    ).fetchone()["n"]


def status_breakdown(con, run_id):
    rows = con.execute(
        "SELECT status, COUNT(*) AS n FROM broker_reconciliation_log "
        "WHERE run_id=? GROUP BY status",
        (run_id,),
    ).fetchall()
    return {r["status"]: r["n"] for r in rows}


# ===================================================================
# [1] Pre-conditions
# ===================================================================

def test_preconditions():
    banner("[1] Pre-conditions : fichiers + tables")

    check(f"reconciler present : {RECONCILER}",
          os.path.exists(RECONCILER), fatal=True)
    check(f"resolver present  : {RESOLVER}",
          os.path.exists(RESOLVER), fatal=True)
    check(f"provider present  : {PROVIDER}",
          os.path.exists(PROVIDER), fatal=True)
    check(f"market cal present: {MARKET_CAL}",
          os.path.exists(MARKET_CAL), fatal=True)
    check(f"DB present        : {DB}",
          os.path.exists(DB), fatal=True)

    con = open_db()
    try:
        tables = {r["name"] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        required = {
            "broker_reconciliation_runs",
            "broker_reconciliation_log",
            "broker_universe_activtrades",
            "instrument_broker_mapping",
            "portfolio_positions",
        }
        missing = required - tables
        check(f"tables requises presentes ({len(required)})",
              not missing, expected="all", got=f"missing={missing}",
              fatal=True)

        # Verifie schema broker_reconciliation_runs
        cols_runs = {r[1] for r in con.execute(
            "PRAGMA table_info(broker_reconciliation_runs)"
        ).fetchall()}
        required_cols_runs = {
            "id", "ts", "source", "status", "n_thesium", "n_broker",
            "n_matched", "n_drifts_qty", "n_thesium_only", "n_broker_only",
        }
        check("schema broker_reconciliation_runs",
              required_cols_runs <= cols_runs,
              expected=str(required_cols_runs),
              got=str(cols_runs))

        # Verifie schema log
        cols_log = {r[1] for r in con.execute(
            "PRAGMA table_info(broker_reconciliation_log)"
        ).fetchall()}
        required_cols_log = {
            "id", "run_id", "ts", "thesium_ticker", "broker_symbol",
            "qty_thesium", "qty_broker", "qty_drift", "status",
        }
        check("schema broker_reconciliation_log",
              required_cols_log <= cols_log,
              expected=str(required_cols_log),
              got=str(cols_log))

        # Verifie broker_universe non vide
        n_universe = con.execute(
            "SELECT COUNT(*) AS n FROM broker_universe_activtrades"
        ).fetchone()["n"]
        check(f"broker_universe_activtrades peuple ({n_universe} lignes)",
              n_universe >= 100, expected=">=100", got=n_universe)

        # Verifie portfolio_positions
        n_pos = con.execute(
            "SELECT COUNT(*) AS n FROM portfolio_positions "
            "WHERE quantity IS NOT NULL AND quantity != 0"
        ).fetchone()["n"]
        check(f"portfolio_positions non vide ({n_pos} positions actives)",
              n_pos >= 1, expected=">=1", got=n_pos)
    finally:
        con.close()


# ===================================================================
# [2] MetaAPI configure
# ===================================================================

def test_metaapi_configured():
    banner("[2] MetaAPI configure (test import + is_configured)")
    try:
        import metaapi_provider as mp
        check("import metaapi_provider", True)
    except Exception as e:
        check(f"import metaapi_provider : {e}", False, fatal=True)
        return

    # is_configured() doit exister et retourner bool
    is_cfg = getattr(mp, "is_configured", None)
    if not check("metaapi_provider.is_configured() existe",
                 callable(is_cfg)):
        return
    try:
        cfg = mp.is_configured()
        check(f"is_configured() retourne bool (got {cfg})",
              isinstance(cfg, bool))
        check("is_configured() = True (token + account configures)",
              cfg is True, expected=True, got=cfg)
    except Exception as e:
        check(f"is_configured() leve : {e}", False)


# ===================================================================
# [3] Resolver
# ===================================================================

def test_resolver():
    banner("[3] Resolver heuristique")
    try:
        import importlib.util as ilu
        spec = ilu.spec_from_file_location("_nx_resolver", RESOLVER)
        mod = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        check("import resolver par chemin", True)
    except Exception as e:
        check(f"import resolver : {e}", False)
        return

    resolve = getattr(mod, "resolve", None)
    if not check("resolver.resolve() existe", callable(resolve)):
        return

    # Cas attendus connus
    cases = [
        ("LINK", "crypto", "LINKUSD"),
        ("BTC", "crypto", "BTCUSD"),
        ("ETH", "crypto", "ETHUSD"),
        ("SOL", "crypto", "SOLUSD"),
        ("AAPL", "equity", "AAPL.US"),
        ("NVDA", "equity", "NVDA.US"),
        ("TSLA", "equity", "TSLA.US"),
        ("XLE", "equity", "XLE.US"),
    ]
    for thesium, asset, expected_broker in cases:
        try:
            res = resolve(thesium, asset_class=asset, db_path=DB)
            got = getattr(res, "broker_symbol", None)
            check(f"resolve({thesium},{asset}) -> {expected_broker}",
                  got == expected_broker,
                  expected=expected_broker, got=got)
        except Exception as e:
            check(f"resolve({thesium}) leve : {e}", False)


# ===================================================================
# [4] Reconciler dry-run no-broker
# ===================================================================

def test_reconciler_no_broker():
    banner("[4] Reconciler --no-broker (test no-network)")
    con = open_db()
    rid_before = last_run_id(con)
    con.close()
    print(f"  run_id avant : {rid_before}")

    rc, out, err = run_reconciler(["--no-broker", "--verbose"], timeout=60)
    print(f"  rc = {rc}")
    if rc != 0:
        print("  STDOUT (last 800c):", (out or "")[-800:])
        print("  STDERR (last 400c):", (err or "")[-400:])
    check("reconciler --no-broker rc=0", rc == 0,
          expected=0, got=rc)

    con = open_db()
    try:
        rid_after = last_run_id(con)
        check(f"run_id incremente ({rid_before} -> {rid_after})",
              rid_after > rid_before,
              expected=f">{rid_before}", got=rid_after)

        row = fetch_run(con, rid_after)
        if row is not None:
            check(f"run.source = 'shadow_only' (got {row['source']})",
                  row["source"] == "shadow_only",
                  expected="shadow_only", got=row["source"])
            check(f"run.status in (ok,partial) got {row['status']}",
                  row["status"] in ("ok", "partial"),
                  expected="ok|partial", got=row["status"])
            n_log = count_log_for_run(con, rid_after)
            print(f"  log lignes : {n_log}")
            print(f"  breakdown  : {status_breakdown(con, rid_after)}")
    finally:
        con.close()


# ===================================================================
# [5] Reconciler live metaapi
# ===================================================================

def test_reconciler_live(skip_live=False):
    banner("[5] Reconciler --source metaapi_live (LIVE)")
    if skip_live:
        print("  [SKIP] --skip-live actif, on saute le test live")
        return

    # Verifie si marche US ouvert via market-calendar
    market_open = None
    try:
        import importlib.util as ilu
        spec = ilu.spec_from_file_location("_nx_mc", MARKET_CAL)
        mc = ilu.module_from_spec(spec)
        spec.loader.exec_module(mc)
        market_open = mc.is_us_market_open()
        print(f"  marche US ouvert : {market_open}")
    except Exception as e:
        print(f"  [WARN] market-calendar import KO : {e}")

    con = open_db()
    rid_before = last_run_id(con)
    con.close()
    print(f"  run_id avant : {rid_before}")

    rc, out, err = run_reconciler(
        ["--source", "metaapi_live", "--verbose"],
        timeout=180,
    )
    print(f"  rc = {rc}")
    if rc != 0 or "[ERR" in (out + err):
        print("  STDOUT (last 1200c):", (out or "")[-1200:])
        print("  STDERR (last 600c):", (err or "")[-600:])

    if market_open is False:
        # Tolerant : marche ferme = positions vides chez ActivTrades
        # On accepte rc=0 OU rc!=0 avec mention 'market closed'
        if rc == 0:
            check("reconciler metaapi_live rc=0 (marche ferme tolerant)",
                  True)
        else:
            ml = (out + err).lower()
            check(
                "marche ferme : reconciler explicite l'erreur",
                "closed" in ml or "timeout" in ml or "no positions" in ml,
                expected="message coherent", got=f"rc={rc}",
            )
    else:
        check("reconciler metaapi_live rc=0", rc == 0,
              expected=0, got=rc)

    con = open_db()
    try:
        rid_after = last_run_id(con)
        if rid_after > rid_before:
            check(f"run_id incremente ({rid_before} -> {rid_after})",
                  True)
            row = fetch_run(con, rid_after)
            if row is not None:
                check(f"run.source = 'metaapi_live' (got {row['source']})",
                      row["source"] == "metaapi_live",
                      expected="metaapi_live", got=row["source"])
                # account_id renseigne ?
                if row["account_id"]:
                    check(f"run.account_id = '1004815'",
                          str(row["account_id"]) == "1004815",
                          expected="1004815", got=row["account_id"])
                if row["balance"] is not None:
                    check(f"run.balance > 0 (got {row['balance']})",
                          row["balance"] > 0,
                          expected=">0", got=row["balance"])

                n_log = count_log_for_run(con, rid_after)
                bd = status_breakdown(con, rid_after)
                print(f"  log lignes : {n_log}")
                print(f"  breakdown  : {bd}")
                # Si marche ouvert et compte a au moins 1 position broker,
                # on s'attend a au moins 1 ligne 'broker_only' ou 'match'.
                if market_open and row["n_broker"] > 0:
                    check("au moins une ligne avec qty_broker non nulle",
                          (bd.get("match", 0) + bd.get("drift_qty", 0)
                           + bd.get("broker_only", 0)) >= 1)
        else:
            check(f"run_id incremente ({rid_before} -> {rid_after})",
                  False, expected=f">{rid_before}", got=rid_after)
    finally:
        con.close()


# ===================================================================
# [6] Idempotence : 2 runs successifs no-broker
# ===================================================================

def test_idempotence():
    banner("[6] Idempotence : 2 runs --no-broker successifs")
    con = open_db()
    rid_0 = last_run_id(con)
    con.close()

    rc1, _, _ = run_reconciler(["--no-broker"], timeout=60)
    check("run1 --no-broker rc=0", rc1 == 0, expected=0, got=rc1)

    rc2, _, _ = run_reconciler(["--no-broker"], timeout=60)
    check("run2 --no-broker rc=0", rc2 == 0, expected=0, got=rc2)

    con = open_db()
    try:
        rid_2 = last_run_id(con)
        diff = rid_2 - rid_0
        check(f"2 runs -> run_id +2 (got +{diff})",
              diff >= 2, expected=">=2", got=diff)

        # Les 2 derniers runs doivent etre coherents (meme source)
        if diff >= 2:
            rows = con.execute(
                "SELECT id, source, status FROM broker_reconciliation_runs "
                "ORDER BY id DESC LIMIT 2"
            ).fetchall()
            sources = {r["source"] for r in rows}
            check(f"2 derniers runs source=shadow_only (got {sources})",
                  sources == {"shadow_only"},
                  expected="{'shadow_only'}", got=str(sources))
    finally:
        con.close()


# ===================================================================
# [7] Regression --source shadow_only
# ===================================================================

def test_shadow_only():
    banner("[7] Regression --source shadow_only")
    con = open_db()
    rid_before = last_run_id(con)
    con.close()

    rc, out, err = run_reconciler(
        ["--source", "shadow_only", "--verbose"], timeout=60,
    )
    print(f"  rc = {rc}")
    if rc != 0:
        print("  STDOUT (last 800c):", (out or "")[-800:])
        print("  STDERR (last 400c):", (err or "")[-400:])
    check("reconciler --source shadow_only rc=0", rc == 0,
          expected=0, got=rc)

    con = open_db()
    try:
        rid_after = last_run_id(con)
        check(f"run_id incremente ({rid_before} -> {rid_after})",
              rid_after > rid_before, expected=f">{rid_before}",
              got=rid_after)
        row = fetch_run(con, rid_after)
        if row is not None:
            check(f"run.source = 'shadow_only' (got {row['source']})",
                  row["source"] == "shadow_only",
                  expected="shadow_only", got=row["source"])
    finally:
        con.close()


# ===================================================================
# Resume
# ===================================================================

def summary():
    banner("RESUME")
    total = PASS + FAIL
    print(f"  PASS : {PASS} / {total}")
    print(f"  FAIL : {FAIL} / {total}")
    if FAIL == 0:
        print("  [OK] tous les tests passent")
    else:
        print(f"  [KO] {FAIL} test(s) en echec :")
        for lbl in FAILED_LABELS:
            print(f"    - {lbl}")


# ===================================================================
# Main
# ===================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-live", action="store_true",
                    help="saute le test live metaapi (utile WE/feries)")
    ap.add_argument("--skip-idempotence", action="store_true",
                    help="saute le test idempotence (gain temps)")
    args = ap.parse_args()

    print()
    print("=" * 60)
    print("VALIDATOR FULL-STACK BROKER RECONCILER")
    print(f"  date  : {dt.datetime.now().isoformat(timespec='seconds')}")
    print(f"  PROD  : {PROD}")
    print(f"  DB    : {DB}")
    print(f"  skip-live        : {args.skip_live}")
    print(f"  skip-idempotence : {args.skip_idempotence}")
    print("=" * 60)

    test_preconditions()
    test_metaapi_configured()
    test_resolver()
    test_reconciler_no_broker()
    test_reconciler_live(skip_live=args.skip_live)
    if not args.skip_idempotence:
        test_idempotence()
    test_shadow_only()

    summary()
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
