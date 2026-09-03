"""
[DIAG_AGENTS_OUTPUT_V2]
Diag de la structure de sortie des agents - corrige apres retour v1 :
  - theses utilise `agent_type` (pas agent_name)
  - theses n'a PAS de cycle_id -> filtrer par created_at sur dernier cycle
  - `instrument_id` (FK) au lieu de ticker -> JOIN instruments si possible
  - `key_drivers` + `thesis_text` + `proposed_action` colonnes reelles

Perimetre : theses + factor_quality + pplx_geo + crypto_context
Output : ASCII pur.
"""

import os
import re
import json
import sqlite3

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

SEP = "=" * 78
SUB = "-" * 78


def safe_json_keys(value):
    if value is None or not isinstance(value, str):
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
    s = str(value).replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s)
    if len(s) > limit:
        return s[:limit] + " ..."
    return s


def get_columns(conn, table):
    cur = conn.execute("PRAGMA table_info(%s)" % table)
    return [r[1] for r in cur.fetchall()]


def table_exists(conn, table):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cur.fetchone() is not None


def section(t):
    print("")
    print(SEP)
    print(t)
    print(SEP)


def subsection(t):
    print("")
    print(SUB)
    print(t)
    print(SUB)


def latest_cycle_info(conn):
    """Retourne (cycle_id, created_at) du dernier cycle dans regime_log."""
    cur = conn.execute(
        "SELECT cycle_id, created_at FROM regime_log ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
    return row if row else (None, None)


def previous_cycle_created_at(conn):
    """Created_at du cycle precedent - sert de borne inf pour filtrer theses."""
    cur = conn.execute(
        "SELECT created_at FROM regime_log ORDER BY id DESC LIMIT 1 OFFSET 1"
    )
    row = cur.fetchone()
    return row[0] if row else None


def diag_theses(conn, cycle_id, lo_ts, hi_ts):
    section("THESES TABLE")

    cols = get_columns(conn, "theses")
    print("Columns (%d) : %s" % (len(cols), ", ".join(cols)))

    cur = conn.execute("SELECT COUNT(*) FROM theses")
    print("Total rows : %d" % cur.fetchone()[0])

    # Distinct agents (all-time) sur agent_type
    cur = conn.execute(
        "SELECT agent_type, COUNT(*) FROM theses "
        "GROUP BY agent_type ORDER BY 2 DESC"
    )
    print("")
    subsection("Agents all-time (agent_type)")
    for r in cur.fetchall():
        print("  %-30s %6d" % (r[0], r[1]))

    print("")
    print("Filter window for 'this cycle' : created_at > %s AND <= %s"
          % (lo_ts, hi_ts))
    if not hi_ts:
        print("No cycle timestamp - aborting per-agent dump")
        return

    where_parts = ["created_at <= ?"]
    params = [hi_ts]
    if lo_ts:
        where_parts.append("created_at > ?")
        params.append(lo_ts)
    where = " AND ".join(where_parts)

    cur = conn.execute(
        "SELECT DISTINCT agent_type FROM theses WHERE %s ORDER BY agent_type"
        % where,
        params,
    )
    agents = [r[0] for r in cur.fetchall()]

    subsection("Per-agent dump (cycle %s)" % cycle_id)
    print("Agents on this cycle : %d" % len(agents))

    has_instruments = table_exists(conn, "instruments")

    for agent in agents:
        subsection("Agent : %s" % agent)

        p = params + [agent]
        cur = conn.execute(
            "SELECT COUNT(*) FROM theses WHERE %s AND agent_type = ?" % where,
            p,
        )
        n = cur.fetchone()[0]
        print("  rows on cycle : %d" % n)

        # Conviction range
        cur = conn.execute(
            "SELECT MIN(conviction_score), MAX(conviction_score), "
            "AVG(conviction_score) FROM theses "
            "WHERE %s AND agent_type = ?" % where,
            p,
        )
        mn, mx, av = cur.fetchone()
        print("  conviction_score : min=%s max=%s avg=%s" % (mn, mx, av))

        # Proposed action distribution
        cur = conn.execute(
            "SELECT proposed_action, COUNT(*) FROM theses "
            "WHERE %s AND agent_type = ? "
            "GROUP BY proposed_action ORDER BY 2 DESC" % where,
            p,
        )
        vals = cur.fetchall()
        if vals:
            print("  proposed_action distribution :")
            for v in vals:
                print("    %-20s %4d" % (truncate(v[0], 40), v[1]))

        # Status / horizon
        for fld in ("status", "horizon"):
            cur = conn.execute(
                "SELECT %s, COUNT(*) FROM theses "
                "WHERE %s AND agent_type = ? "
                "GROUP BY %s ORDER BY 2 DESC LIMIT 10"
                % (fld, where, fld),
                p,
            )
            v2 = cur.fetchall()
            if v2:
                print("  %s :" % fld)
                for v in v2:
                    print("    %-20s %4d" % (truncate(v[0], 40), v[1]))

        # Sample tickers (via JOIN instruments si dispo)
        if has_instruments:
            cur = conn.execute(
                "SELECT DISTINCT i.ticker FROM theses t "
                "LEFT JOIN instruments i ON i.id = t.instrument_id "
                "WHERE %s AND t.agent_type = ? LIMIT 20" % where,
                p,
            )
            tks = [r[0] for r in cur.fetchall()]
            print("  tickers sample (via instruments) : %s" % tks)
        else:
            cur = conn.execute(
                "SELECT DISTINCT instrument_id FROM theses "
                "WHERE %s AND agent_type = ? LIMIT 20" % where,
                p,
            )
            print("  instrument_id sample : %s"
                  % [r[0] for r in cur.fetchall()])

        # Sample 1 row complete
        cur = conn.execute(
            "SELECT * FROM theses WHERE %s AND agent_type = ? LIMIT 1" % where,
            p,
        )
        row = cur.fetchone()
        if row:
            print("")
            print("  Sample row :")
            for i, c in enumerate(cols):
                val = row[i]
                # key_drivers est JSON la plupart du temps
                keys = None
                if c in ("key_drivers",) or c.endswith("_json"):
                    keys = safe_json_keys(val)
                if keys:
                    print("    %-22s [JSON keys] %s" % (c, keys))
                    # Si dict -> dump quelques valeurs
                    try:
                        obj = json.loads(val)
                        if isinstance(obj, dict):
                            for k in list(obj.keys())[:6]:
                                sub = obj[k]
                                if isinstance(sub, (dict, list)):
                                    print("        [%s] = %s"
                                          % (k, truncate(json.dumps(sub), 120)))
                                else:
                                    print("        [%s] = %s"
                                          % (k, truncate(sub, 120)))
                    except Exception:
                        pass
                else:
                    print("    %-22s : %s" % (c, truncate(val, 180)))


def diag_aux(conn, table):
    section("AUX TABLE : %s" % table)

    if not table_exists(conn, table):
        print("  Table missing")
        return

    cols = get_columns(conn, table)
    print("Columns (%d) : %s" % (len(cols), ", ".join(cols)))

    cur = conn.execute("SELECT COUNT(*) FROM %s" % table)
    print("Total rows : %d" % cur.fetchone()[0])

    # Time col
    time_col = None
    for cand in ("snapshot_date", "created_at", "ts", "cycle_id"):
        if cand in cols:
            time_col = cand
            break
    print("Time/cycle column : %s" % time_col)

    if time_col:
        cur = conn.execute(
            "SELECT * FROM %s ORDER BY %s DESC LIMIT 1" % (table, time_col)
        )
    else:
        cur = conn.execute("SELECT * FROM %s LIMIT 1" % table)
    row = cur.fetchone()
    if not row:
        print("  No rows")
        return

    subsection("Latest row")
    for i, c in enumerate(cols):
        val = row[i]
        keys = None
        if c.endswith("_json") or c in ("payload", "context", "data"):
            keys = safe_json_keys(val)
        if keys:
            print("  %-22s [JSON keys] %s" % (c, keys))
            try:
                obj = json.loads(val)
                if isinstance(obj, dict):
                    for k in list(obj.keys())[:8]:
                        sub = obj[k]
                        if isinstance(sub, dict):
                            inner = sorted(list(sub.keys()))[:10]
                            print("      sub[%s] keys : %s" % (k, inner))
                        elif isinstance(sub, list):
                            if sub and isinstance(sub[0], dict):
                                inner = sorted(list(sub[0].keys()))[:10]
                                print("      sub[%s][0] keys : %s"
                                      % (k, inner))
                            else:
                                print("      sub[%s] : list[%d] %s"
                                      % (k, len(sub), truncate(sub, 80)))
                        else:
                            print("      sub[%s] = %s"
                                  % (k, truncate(sub, 80)))
            except Exception:
                pass
        else:
            print("  %-22s : %s" % (c, truncate(val, 180)))


def main():
    if not os.path.exists(DB_PATH):
        print("ERROR: DB not found")
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        cycle_id, hi_ts = latest_cycle_info(conn)
        lo_ts = previous_cycle_created_at(conn)
        print("Latest cycle  : %s @ %s" % (cycle_id, hi_ts))
        print("Previous cycle ends @ : %s" % lo_ts)

        diag_theses(conn, cycle_id, lo_ts, hi_ts)
        diag_aux(conn, "factor_quality")
        diag_aux(conn, "pplx_geo")
        diag_aux(conn, "crypto_context")

        section("DONE")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
