"""
[DIAG_AGENTS_OUTPUT_V1]
Diag de la structure de sortie des agents pour preparer le mapping L1-L5
du Convergence Engine.

Perimetre :
  - Table `theses` : agents Macro / Factor / Microstructure / Crypto /
    AltData / Exit / PortfolioConstruction
  - Tables auxiliaires : `factor_quality`, `pplx_geo`, `crypto_context`
    (sorties pplx hors `theses`)

Output : ASCII pur, sections lisibles, sample tronque a 200 chars.
"""

import os
import re
import json
import sqlite3
from collections import OrderedDict

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

SEP = "=" * 78
SUB = "-" * 78


def safe_json_keys(value):
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s or s[0] not in "{[":
        return None
    try:
        obj = json.loads(s)
    except Exception:
        return None
    if isinstance(obj, dict):
        return sorted(list(obj.keys()))
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return sorted(list(obj[0].keys()))
    return None


def truncate(value, limit=200):
    if value is None:
        return "<None>"
    s = str(value)
    s = s.replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s)
    if len(s) > limit:
        return s[:limit] + " ..."
    return s


def get_columns(conn, table):
    cur = conn.execute("PRAGMA table_info(%s)" % table)
    return [r[1] for r in cur.fetchall()]


def latest_cycle_id(conn):
    cur = conn.execute(
        "SELECT cycle_id FROM regime_log ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
    return row[0] if row else None


def section(title):
    print("")
    print(SEP)
    print(title)
    print(SEP)


def subsection(title):
    print("")
    print(SUB)
    print(title)
    print(SUB)


def diag_theses(conn, cycle_id):
    section("THESES TABLE")

    cols = get_columns(conn, "theses")
    print("Columns (%d) : %s" % (len(cols), ", ".join(cols)))

    cur = conn.execute("SELECT COUNT(*) FROM theses")
    print("Total rows : %d" % cur.fetchone()[0])

    # Distinct agents (toutes periodes)
    cur = conn.execute(
        "SELECT agent_name, COUNT(*) FROM theses "
        "GROUP BY agent_name ORDER BY 2 DESC"
    )
    rows = cur.fetchall()
    subsection("Agents (all-time)")
    for r in rows:
        print("  %-30s %6d" % (r[0], r[1]))

    # Identifier la colonne cycle (cycle_id ? cycle ?)
    cycle_col = None
    for cand in ("cycle_id", "cycle"):
        if cand in cols:
            cycle_col = cand
            break
    print("")
    print("Cycle column detected : %s" % cycle_col)

    if not cycle_col or not cycle_id:
        print("Cannot filter by cycle - aborting per-agent dump")
        return

    # Pour chaque agent : count + range conviction + sample
    cur = conn.execute(
        "SELECT DISTINCT agent_name FROM theses WHERE %s = ? "
        "ORDER BY agent_name" % cycle_col,
        (cycle_id,),
    )
    agents = [r[0] for r in cur.fetchall()]

    subsection("Per-agent dump for cycle_id = %s" % cycle_id)
    print("Agents on this cycle : %d" % len(agents))

    json_like_cols = [
        c for c in cols
        if c.endswith("_json") or c in ("meta", "payload", "context", "drivers")
    ]
    text_cols = [
        c for c in cols
        if c in ("thesis", "rationale", "notes", "summary", "narrative")
    ]
    signal_cols = [
        c for c in cols
        if c in ("bias", "direction", "action", "signal", "stance", "side")
    ]
    conviction_col = None
    for cand in ("conviction_score", "conviction", "score"):
        if cand in cols:
            conviction_col = cand
            break
    ticker_col = None
    for cand in ("ticker", "symbol", "universe", "scope"):
        if cand in cols:
            ticker_col = cand
            break

    print("")
    print("Detected signal cols     : %s" % signal_cols)
    print("Detected conviction col  : %s" % conviction_col)
    print("Detected ticker col      : %s" % ticker_col)
    print("Detected text cols       : %s" % text_cols)
    print("Detected JSON-like cols  : %s" % json_like_cols)

    for agent in agents:
        subsection("Agent : %s" % agent)

        cur = conn.execute(
            "SELECT COUNT(*) FROM theses WHERE %s = ? AND agent_name = ?"
            % cycle_col,
            (cycle_id, agent),
        )
        n = cur.fetchone()[0]
        print("  rows on cycle : %d" % n)

        if conviction_col:
            cur = conn.execute(
                "SELECT MIN(%s), MAX(%s), AVG(%s) FROM theses "
                "WHERE %s = ? AND agent_name = ?"
                % (conviction_col, conviction_col, conviction_col, cycle_col),
                (cycle_id, agent),
            )
            mn, mx, av = cur.fetchone()
            print(
                "  %s : min=%s max=%s avg=%s"
                % (conviction_col, mn, mx, av)
            )

        if signal_cols:
            for sc in signal_cols:
                cur = conn.execute(
                    "SELECT %s, COUNT(*) FROM theses "
                    "WHERE %s = ? AND agent_name = ? "
                    "GROUP BY %s ORDER BY 2 DESC"
                    % (sc, cycle_col, sc),
                    (cycle_id, agent),
                )
                vals = cur.fetchall()
                if vals:
                    print("  %s distribution :" % sc)
                    for v in vals:
                        print("    %-20s %4d" % (truncate(v[0], 40), v[1]))

        if ticker_col:
            cur = conn.execute(
                "SELECT DISTINCT %s FROM theses "
                "WHERE %s = ? AND agent_name = ? LIMIT 20"
                % (ticker_col, cycle_col),
                (cycle_id, agent),
            )
            tickers = [r[0] for r in cur.fetchall()]
            print("  %s sample : %s" % (ticker_col, tickers))

        # Sample 1 row complete
        cur = conn.execute(
            "SELECT * FROM theses WHERE %s = ? AND agent_name = ? LIMIT 1"
            % cycle_col,
            (cycle_id, agent),
        )
        row = cur.fetchone()
        if row:
            print("")
            print("  Sample row :")
            for i, c in enumerate(cols):
                val = row[i]
                keys = safe_json_keys(val) if c in json_like_cols else None
                if keys:
                    print("    %-25s [JSON keys] %s" % (c, keys))
                else:
                    print("    %-25s : %s" % (c, truncate(val, 180)))


def diag_aux_table(conn, table, cycle_id):
    section("AUX TABLE : %s" % table)

    try:
        cols = get_columns(conn, table)
    except sqlite3.OperationalError as e:
        print("  Table missing : %s" % e)
        return

    print("Columns (%d) : %s" % (len(cols), ", ".join(cols)))

    cur = conn.execute("SELECT COUNT(*) FROM %s" % table)
    print("Total rows : %d" % cur.fetchone()[0])

    # Date / cycle column ?
    cycle_col = None
    for cand in ("cycle_id", "cycle", "snapshot_date", "ts", "created_at"):
        if cand in cols:
            cycle_col = cand
            break
    print("Time/cycle column detected : %s" % cycle_col)

    # Derniere ligne (peu importe le cycle)
    if cycle_col:
        cur = conn.execute(
            "SELECT * FROM %s ORDER BY %s DESC LIMIT 1" % (table, cycle_col)
        )
    else:
        cur = conn.execute("SELECT * FROM %s LIMIT 1" % table)
    row = cur.fetchone()

    json_like_cols = [
        c for c in cols
        if c.endswith("_json") or c in (
            "payload", "context", "data", "summary", "details"
        )
    ]

    if row:
        subsection("Latest row")
        for i, c in enumerate(cols):
            val = row[i]
            keys = safe_json_keys(val) if c in json_like_cols else None
            if keys:
                print("  %-25s [JSON keys] %s" % (c, keys))
                # Si payload_json : tenter de dumper sample keys d'un niveau plus bas
                if c.endswith("_json") and isinstance(val, str):
                    try:
                        obj = json.loads(val)
                        if isinstance(obj, dict):
                            for k, v in list(obj.items())[:5]:
                                if isinstance(v, dict):
                                    inner = sorted(list(v.keys()))[:10]
                                    print(
                                        "      sub[%s] keys : %s" % (k, inner)
                                    )
                                elif isinstance(v, list):
                                    if v and isinstance(v[0], dict):
                                        inner = sorted(list(v[0].keys()))[:10]
                                        print(
                                            "      sub[%s][0] keys : %s"
                                            % (k, inner)
                                        )
                                    else:
                                        print(
                                            "      sub[%s] : list[%d] %s"
                                            % (k, len(v), truncate(v, 80))
                                        )
                                else:
                                    print(
                                        "      sub[%s] : %s"
                                        % (k, truncate(v, 80))
                                    )
                    except Exception:
                        pass
            else:
                print("  %-25s : %s" % (c, truncate(val, 180)))


def main():
    if not os.path.exists(DB_PATH):
        print("ERROR: DB not found at %s" % DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cycle_id = latest_cycle_id(conn)
        print("Latest cycle_id : %s" % cycle_id)

        diag_theses(conn, cycle_id)
        diag_aux_table(conn, "factor_quality", cycle_id)
        diag_aux_table(conn, "pplx_geo", cycle_id)
        diag_aux_table(conn, "crypto_context", cycle_id)

        section("DONE")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
