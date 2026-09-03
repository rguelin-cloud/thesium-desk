# -*- coding: utf-8 -*-
# nextones-diag-sol-buy-vs-convergence.py
#
# Objectif : comprendre pourquoi l'ordre #266 BUY SOL 51 a ete genere alors que
# le verdict Convergence pour SOL est "forced_exit (sizing x0.0)".
#
# Plan :
#   1) Resoudre instrument_id de SOL (attendu : 18)
#   2) Position actuelle SOL dans portfolio_positions
#   3) Order #266 : tout le risk_check_result, cycle_id, agent source
#   4) Cycle de creation de l'ordre (#266) : run_cycles + thesis source
#   5) Toutes les theses du cycle pour SOL (qui a propose BUY 51 ?)
#   6) Convergence snapshot le plus recent : verdict SOL
#   7) Construction snapshot du cycle qui a cree #266 : targets, weights, conv
#   8) Croisement : la cible SOL a-t-elle ete calculee avec ou sans
#      le forced_exit de la convergence ?
#
# Affiche tout brut, en ASCII pur.

import os
import sys
import json
import sqlite3

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def hr(title=""):
    print("")
    print("=" * 72)
    if title:
        print(title)
        print("-" * 72)

def safe_json(s):
    if s is None:
        return None
    if not isinstance(s, str):
        return s
    try:
        return json.loads(s)
    except Exception:
        return {"_raw": s[:500]}

def print_row(r):
    if r is None:
        print("  <None>")
        return
    if isinstance(r, sqlite3.Row):
        for k in r.keys():
            v = r[k]
            if isinstance(v, str) and len(v) > 400:
                print("  " + str(k) + " = " + v[:400] + " ...[truncated]")
            else:
                print("  " + str(k) + " = " + str(v))
    else:
        print("  " + str(r))

def list_tables(conn):
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]

def has_table(conn, name):
    return name in list_tables(conn)

def cols(conn, table):
    try:
        return [r[1] for r in conn.execute("PRAGMA table_info(" + table + ")").fetchall()]
    except Exception:
        return []

def main():
    if not os.path.exists(DB):
        print("ERREUR : DB introuvable " + DB)
        sys.exit(2)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    tables = list_tables(conn)
    print("Tables disponibles : " + str(len(tables)))

    # 1) instrument SOL
    hr("[1] Instrument SOL")
    sol = conn.execute(
        "SELECT * FROM instruments WHERE upper(ticker)='SOL' OR ticker LIKE 'SOL%' LIMIT 5"
    ).fetchall()
    for r in sol:
        print_row(r)
        print("  ---")
    sol_id = sol[0]["id"] if sol else None
    print("instrument_id SOL = " + str(sol_id))

    # 2) Position SOL
    hr("[2] Position SOL dans portfolio_positions")
    if has_table(conn, "portfolio_positions") and sol_id:
        pos = conn.execute(
            "SELECT * FROM portfolio_positions WHERE instrument_id=?",
            (sol_id,)
        ).fetchall()
        if not pos:
            print("  Aucune ligne portfolio_positions pour SOL (quantite=0)")
        for r in pos:
            print_row(r)
            print("  ---")
    else:
        print("  Pas de table portfolio_positions ou sol_id manquant")

    # 3) Order #266
    hr("[3] Order #266 (SOL BUY 51)")
    o = conn.execute("SELECT * FROM orders WHERE id=266").fetchone()
    if not o:
        # fallback : dernier BUY SOL
        o = conn.execute(
            "SELECT * FROM orders WHERE instrument_id=? AND lower(side)='buy' ORDER BY id DESC LIMIT 1",
            (sol_id,)
        ).fetchone()
    if o is None:
        print("  Order #266 introuvable.")
    else:
        print_row(o)
        rc = safe_json(o["risk_check_result"]) if "risk_check_result" in o.keys() else None
        print("")
        print("  risk_check_result (parsed) :")
        print("    " + json.dumps(rc, indent=2, ensure_ascii=False)[:2000])

    order_cycle_id = None
    order_thesis_id = None
    if o is not None:
        # cycle_id eventuel
        for cand in ("cycle_id", "run_cycle_id", "cycle"):
            if cand in o.keys():
                order_cycle_id = o[cand]
                break
        for cand in ("thesis_id", "source_thesis_id", "src_thesis"):
            if cand in o.keys():
                order_thesis_id = o[cand]
                break
    print("")
    print("  order_cycle_id = " + str(order_cycle_id))
    print("  order_thesis_id = " + str(order_thesis_id))

    # 4) Cycle de l'ordre - trouver le run_cycles entry
    hr("[4] Run cycle associe a l'ordre #266")
    run_cycles_tbl = None
    for cand in ("run_cycles", "decision_cycles", "cycles"):
        if cand in tables:
            run_cycles_tbl = cand
            break
    print("  table candidate : " + str(run_cycles_tbl))
    if run_cycles_tbl:
        rc_cols = cols(conn, run_cycles_tbl)
        print("  cols : " + ", ".join(rc_cols))
        # On veut le cycle le plus recent (ce matin)
        order_by = "id DESC"
        for cand in ("created_at", "started_at", "ts"):
            if cand in rc_cols:
                order_by = cand + " DESC"
                break
        cyc = conn.execute(
            "SELECT * FROM " + run_cycles_tbl + " ORDER BY " + order_by + " LIMIT 5"
        ).fetchall()
        for r in cyc:
            print_row(r)
            print("  ---")

    # 5) Theses SOL dans la fenetre recente
    hr("[5] Theses SOL recentes (ts >= aujourd'hui)")
    if has_table(conn, "theses"):
        th_cols = cols(conn, "theses")
        ts_col = None
        for cand in ("created_at", "ts", "generated_at"):
            if cand in th_cols:
                ts_col = cand
                break
        agent_col = "agent" if "agent" in th_cols else (
            "agent_name" if "agent_name" in th_cols else None
        )
        sig_col = "signal" if "signal" in th_cols else None
        ticker_col = None
        for cand in ("ticker", "symbol"):
            if cand in th_cols:
                ticker_col = cand
                break
        instr_col = "instrument_id" if "instrument_id" in th_cols else None

        where = "WHERE 1=1"
        params = []
        if ticker_col:
            where += " AND upper(" + ticker_col + ")='SOL'"
        elif instr_col and sol_id:
            where += " AND " + instr_col + "=?"
            params.append(sol_id)
        if ts_col:
            where += " AND date(" + ts_col + ") >= date('now','-1 day')"
        q = "SELECT * FROM theses " + where + " ORDER BY " + (ts_col if ts_col else "id") + " DESC LIMIT 20"
        try:
            ths = conn.execute(q, params).fetchall()
            print("  query : " + q)
            print("  found : " + str(len(ths)))
            for r in ths:
                # On affiche les champs clefs
                d = dict(r)
                keep = {}
                for k in ("id", ts_col, agent_col, ticker_col, sig_col,
                          "side", "qty", "quantity", "conviction", "horizon",
                          "rationale", "summary", "details"):
                    if k and k in d:
                        v = d[k]
                        if isinstance(v, str) and len(v) > 200:
                            v = v[:200] + "..."
                        keep[k] = v
                print("  " + json.dumps(keep, ensure_ascii=False, default=str))
        except Exception as e:
            print("  ERREUR query theses : " + str(e))
    else:
        print("  Pas de table theses")

    # 6) Convergence snapshot recent
    hr("[6] Convergence snapshot le plus recent + verdict SOL")
    conv_tbls = [t for t in tables if "convergence" in t.lower()]
    print("  tables convergence trouvees : " + ", ".join(conv_tbls))
    for tname in conv_tbls:
        print("")
        print("  >>> " + tname + " (" + ", ".join(cols(conn, tname)) + ")")
        c = cols(conn, tname)
        order_by = "id DESC" if "id" in c else "rowid DESC"
        for cand in ("created_at", "ts", "snapshot_ts"):
            if cand in c:
                order_by = cand + " DESC"
                break
        try:
            rows = conn.execute(
                "SELECT * FROM " + tname + " ORDER BY " + order_by + " LIMIT 5"
            ).fetchall()
            for r in rows:
                d = dict(r)
                # Compact : montrer id/ts/cycle + verdict SOL si present
                small = {k: d.get(k) for k in d.keys() if k in (
                    "id", "ts", "created_at", "snapshot_ts", "cycle_id",
                    "ticker", "consensus", "n_aligned", "sizing", "bucket",
                    "verdict", "details_json", "payload"
                )}
                # Si payload/details_json est JSON, tenter extraire SOL
                for k in ("details_json", "payload"):
                    if k in small and isinstance(small[k], str):
                        parsed = safe_json(small[k])
                        if isinstance(parsed, (dict, list)):
                            # Chercher SOL dedans
                            found_sol = None
                            if isinstance(parsed, dict):
                                # cas dict ticker->verdict
                                for kk, vv in parsed.items():
                                    if "SOL" in str(kk).upper():
                                        found_sol = vv
                                # cas forced_exit list
                                for category in ("forced_exit", "drift", "strong", "neutres", "neutral"):
                                    if category in parsed:
                                        lst = parsed[category]
                                        if isinstance(lst, list):
                                            for it in lst:
                                                if isinstance(it, dict):
                                                    t = it.get("ticker") or it.get("symbol")
                                                    if t and "SOL" in str(t).upper():
                                                        found_sol = {"category": category, "data": it}
                            elif isinstance(parsed, list):
                                for it in parsed:
                                    if isinstance(it, dict):
                                        t = it.get("ticker") or it.get("symbol")
                                        if t and "SOL" in str(t).upper():
                                            found_sol = it
                            small[k + "_SOL"] = found_sol
                            small[k] = "<len=" + str(len(small[k])) + ">"
                print("    " + json.dumps(small, ensure_ascii=False, default=str)[:1500])
        except Exception as e:
            print("    ERREUR : " + str(e))

    # 7) Construction snapshot recent
    hr("[7] Construction snapshot le plus recent + ligne SOL")
    constr_tbls = [t for t in tables if "construction" in t.lower() or "target" in t.lower()]
    print("  tables construction/targets : " + ", ".join(constr_tbls))
    for tname in constr_tbls[:5]:
        print("")
        print("  >>> " + tname + " (" + ", ".join(cols(conn, tname)) + ")")
        c = cols(conn, tname)
        order_by = "id DESC" if "id" in c else "rowid DESC"
        for cand in ("created_at", "ts", "snapshot_ts"):
            if cand in c:
                order_by = cand + " DESC"
                break
        # Limiter aux 30 derniers + filtre SOL si colonne ticker
        try:
            if "ticker" in c:
                rows = conn.execute(
                    "SELECT * FROM " + tname + " WHERE upper(ticker)='SOL' ORDER BY " + order_by + " LIMIT 5"
                ).fetchall()
            elif "instrument_id" in c and sol_id:
                rows = conn.execute(
                    "SELECT * FROM " + tname + " WHERE instrument_id=? ORDER BY " + order_by + " LIMIT 5",
                    (sol_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM " + tname + " ORDER BY " + order_by + " LIMIT 3"
                ).fetchall()
            print("  found : " + str(len(rows)))
            for r in rows:
                print_row(r)
                print("    ---")
        except Exception as e:
            print("    ERREUR : " + str(e))

    # 8) Audit trail SOL aujourd'hui
    hr("[8] Audit trail SOL aujourd'hui (events lies a #266 ou ticker SOL)")
    audit_tbls = [t for t in tables if "audit" in t.lower() or "event" in t.lower()]
    print("  tables audit : " + ", ".join(audit_tbls))
    for tname in audit_tbls:
        c = cols(conn, tname)
        if not c:
            continue
        ts_col = None
        for cand in ("ts", "created_at", "timestamp"):
            if cand in c:
                ts_col = cand
                break
        if not ts_col:
            continue
        # Heuristique: details contient SOL ou entity_id = 266 ou ticker=SOL
        cond = []
        params = []
        if "entity" in c:
            cond.append("entity LIKE '%266%' OR entity LIKE '%SOL%'")
        if "details" in c:
            cond.append("details LIKE '%SOL%'")
        if "ticker" in c:
            cond.append("ticker='SOL'")
        where = " OR ".join(cond) if cond else "1=1"
        q = ("SELECT * FROM " + tname + " WHERE date(" + ts_col + ") >= date('now','-1 day') AND ("
             + where + ") ORDER BY " + ts_col + " DESC LIMIT 30")
        try:
            rows = conn.execute(q, params).fetchall()
            print("")
            print("  >>> " + tname + " : " + str(len(rows)) + " events")
            for r in rows:
                d = {k: r[k] for k in r.keys()}
                # compact
                if "details" in d and isinstance(d["details"], str) and len(d["details"]) > 200:
                    d["details"] = d["details"][:200] + "..."
                print("    " + json.dumps(d, ensure_ascii=False, default=str)[:600])
        except Exception as e:
            print("    ERREUR : " + str(e))

    hr("FIN DIAG")
    conn.close()


if __name__ == "__main__":
    main()
