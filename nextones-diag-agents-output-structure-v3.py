"""
[DIAG_AGENTS_OUTPUT_V3]
Corrections v3 :
  - JOIN instruments : prefixer t.created_at (ambiguite)
  - ExitAgent tourne sur cycle court -> ne pas filtrer par fenetre de 2 cycles
    Strategie : pour chaque agent_type distinct, recuperer son DERNIER lot
    (max(created_at) -> tolerance 5 min en arriere pour grouper la rafale)
  - Garde diag des aux tables identique
"""

import os
import re
import json
import sqlite3
from datetime import datetime, timedelta

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

SEP = "=" * 78
SUB = "-" * 78
BURST_TOLERANCE_MIN = 5  # minutes pour grouper une rafale d'inserts d'un agent


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


def diag_theses(conn):
    section("THESES TABLE")
    cols = get_columns(conn, "theses")
    print("Columns (%d) : %s" % (len(cols), ", ".join(cols)))
    cur = conn.execute("SELECT COUNT(*) FROM theses")
    print("Total rows : %d" % cur.fetchone()[0])

    cur = conn.execute(
        "SELECT agent_type, COUNT(*), MAX(created_at) FROM theses "
        "GROUP BY agent_type ORDER BY 2 DESC"
    )
    rows = cur.fetchall()
    subsection("Agents all-time (count + last_run)")
    for r in rows:
        print("  %-30s %6d   last=%s" % (r[0], r[1], r[2]))

    has_instruments = table_exists(conn, "instruments")
    print("")
    print("instruments table present : %s" % has_instruments)

    # Pour chaque agent : derniere rafale = [max-5min, max]
    agents = [r[0] for r in rows]

    for agent in agents:
        subsection("Agent : %s" % agent)

        cur = conn.execute(
            "SELECT MAX(created_at) FROM theses WHERE agent_type = ?",
            (agent,),
        )
        last_ts = cur.fetchone()[0]
        if not last_ts:
            print("  no rows")
            continue

        # Borne basse = last_ts - tolerance
        try:
            dt = datetime.fromisoformat(last_ts)
            lo_ts = (dt - timedelta(minutes=BURST_TOLERANCE_MIN)).isoformat(" ")
        except Exception:
            lo_ts = last_ts  # fallback strict

        print("  last burst window : [%s, %s]" % (lo_ts, last_ts))

        cur = conn.execute(
            "SELECT COUNT(*) FROM theses "
            "WHERE agent_type = ? AND created_at BETWEEN ? AND ?",
            (agent, lo_ts, last_ts),
        )
        n = cur.fetchone()[0]
        print("  rows in burst : %d" % n)

        cur = conn.execute(
            "SELECT MIN(conviction_score), MAX(conviction_score), "
            "AVG(conviction_score) FROM theses "
            "WHERE agent_type = ? AND created_at BETWEEN ? AND ?",
            (agent, lo_ts, last_ts),
        )
        mn, mx, av = cur.fetchone()
        print("  conviction_score : min=%s max=%s avg=%s" % (mn, mx, av))

        # Distributions
        for fld in ("proposed_action", "status", "horizon"):
            cur = conn.execute(
                "SELECT %s, COUNT(*) FROM theses "
                "WHERE agent_type = ? AND created_at BETWEEN ? AND ? "
                "GROUP BY %s ORDER BY 2 DESC LIMIT 15"
                % (fld, fld),
                (agent, lo_ts, last_ts),
            )
            vals = cur.fetchall()
            if vals:
                print("  %s :" % fld)
                for v in vals:
                    print("    %-25s %4d" % (truncate(v[0], 50), v[1]))

        # Tickers
        if has_instruments:
            cur = conn.execute(
                "SELECT DISTINCT i.ticker FROM theses t "
                "LEFT JOIN instruments i ON i.id = t.instrument_id "
                "WHERE t.agent_type = ? AND t.created_at BETWEEN ? AND ? "
                "LIMIT 30",
                (agent, lo_ts, last_ts),
            )
            tks = [r[0] for r in cur.fetchall()]
            print("  tickers sample : %s" % tks)
        else:
            cur = conn.execute(
                "SELECT DISTINCT instrument_id FROM theses "
                "WHERE agent_type = ? AND created_at BETWEEN ? AND ? LIMIT 30",
                (agent, lo_ts, last_ts),
            )
            print(
                "  instrument_id sample : %s"
                % [r[0] for r in cur.fetchall()]
            )

        # Sample row complete
        cur = conn.execute(
            "SELECT * FROM theses "
            "WHERE agent_type = ? AND created_at BETWEEN ? AND ? LIMIT 1",
            (agent, lo_ts, last_ts),
        )
        row = cur.fetchone()
        if row:
            print("")
            print("  Sample row :")
            for i, c in enumerate(cols):
                val = row[i]
                keys = None
                if c == "key_drivers" or c.endswith("_json"):
                    keys = safe_json_keys(val)
                if keys:
                    print("    %-22s [JSON keys] %s" % (c, keys))
                    try:
                        obj = json.loads(val)
                        if isinstance(obj, dict):
                            for k in list(obj.keys())[:8]:
                                sub = obj[k]
                                if isinstance(sub, (dict, list)):
                                    print(
                                        "        [%s] = %s"
                                        % (k, truncate(json.dumps(sub), 140))
                                    )
                                else:
                                    print(
                                        "        [%s] = %s"
                                        % (k, truncate(sub, 140))
                                    )
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
                    for k in list(obj.keys())[:10]:
                        sub = obj[k]
                        if isinstance(sub, dict):
                            inner = sorted(list(sub.keys()))[:12]
                            print("      sub[%s] keys : %s" % (k, inner))
                        elif isinstance(sub, list):
                            if sub and isinstance(sub[0], dict):
                                inner = sorted(list(sub[0].keys()))[:12]
                                print(
                                    "      sub[%s][0] keys : %s" % (k, inner)
                                )
                            else:
                                print(
                                    "      sub[%s] : list[%d] %s"
                                    % (k, len(sub), truncate(sub, 80))
                                )
                        else:
                            print(
                                "      sub[%s] = %s" % (k, truncate(sub, 100))
                            )
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
        cur = conn.execute(
            "SELECT cycle_id, created_at FROM regime_log "
            "ORDER BY id DESC LIMIT 5"
        )
        print("Last 5 cycles (regime_log) :")
        for r in cur.fetchall():
            print("  %s @ %s" % (r[0], r[1]))

        diag_theses(conn)
        diag_aux(conn, "factor_quality")
        diag_aux(conn, "pplx_geo")
        diag_aux(conn, "crypto_context")

        section("DONE")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
