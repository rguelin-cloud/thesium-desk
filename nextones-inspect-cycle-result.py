# -*- coding: utf-8 -*-
"""
[INSPECT_CYCLE_RESULT_V2]
Adapte aux vrais schemas de la DB :
  - portfolio_targets : id, ticker, target_weight_pct, active, source, updated_at,
                        snapshot_id, score, agent_decided
  - PAS de table reconciler_log -> on cherche d'autres tables liees
  - PAS de current_weight_pct -> on regarde si positions/portfolio_state existe
"""
import sys
import sqlite3
import datetime
from pathlib import Path

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")

TS_DEFAULT = (datetime.datetime.now() - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
ts_arg = sys.argv[1] if len(sys.argv) > 1 else TS_DEFAULT

print("=" * 70)
print(f"Inspection cycle - filtre temps : created_at >= '{ts_arg}'")
print("=" * 70)


def table_exists(conn, name):
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone())


def get_cols(conn, name):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({name})").fetchall()]


def list_tables(conn):
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]


def print_table(rows, cols, max_col_width=40):
    if not rows:
        print("  (vide)")
        return
    widths = []
    for i, c in enumerate(cols):
        w = max(len(str(c)),
                max((min(len(str(r.get(c, "") if isinstance(r, dict) else r[c]) if (r.get(c) if isinstance(r, dict) else r[c]) is not None else ""), max_col_width) for r in rows), default=0))
        widths.append(w)
    header = "  " + "  ".join(c.ljust(widths[i]) for i, c in enumerate(cols))
    print(header)
    print("  " + "  ".join("-" * widths[i] for i in range(len(cols))))
    for r in rows:
        line = []
        for i, c in enumerate(cols):
            v = r.get(c) if isinstance(r, dict) else r[c]
            s = "" if v is None else str(v)
            if len(s) > max_col_width:
                s = s[:max_col_width - 1] + "."
            line.append(s.ljust(widths[i]))
        print("  " + "  ".join(line))


conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row

# === Liste des tables pour reference ===
print()
print("[INFO] Tables existantes :")
for t in list_tables(conn):
    print(f"   - {t}")

# === STEP 2 : ordres ===
print()
print("[STEP 2] Nouveaux ordres depuis", ts_arg)
print("-" * 70)
if not table_exists(conn, "orders"):
    print("  Table 'orders' inexistante.")
else:
    cols = get_cols(conn, "orders")
    print(f"  Colonnes orders : {', '.join(cols)}")
    ts_col = "created_at" if "created_at" in cols else ("ts" if "ts" in cols else None)
    wanted = [c for c in ("id", "symbol", "ticker", "side", "qty", "conviction", "status", "created_at", "ts") if c in cols]
    if not wanted:
        wanted = cols[:8]
    sel = ", ".join(wanted)
    if ts_col:
        rows = conn.execute(
            f"SELECT {sel} FROM orders WHERE {ts_col} >= ? ORDER BY {ts_col} DESC LIMIT 50",
            (ts_arg,),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT {sel} FROM orders ORDER BY id DESC LIMIT 20"
        ).fetchall()
    print(f"  {len(rows)} ordre(s) trouve(s)")
    print_table([dict(r) for r in rows], wanted)

# === STEP 3 : reconciler / decisions / proposals ===
print()
print("[STEP 3] Logs decisions (reconciler / proposals / theses)")
print("-" * 70)
# Chercher tables avec 'recon', 'proposal', 'decision'
candidates = [t for t in list_tables(conn)
              if any(k in t.lower() for k in ("recon", "proposal", "decision", "thes"))]
print(f"  Tables candidates : {candidates}")
for t in candidates[:5]:
    cols = get_cols(conn, t)
    ts_col = "created_at" if "created_at" in cols else ("ts" if "ts" in cols else ("updated_at" if "updated_at" in cols else None))
    print()
    print(f"  --- {t} (cols: {', '.join(cols)}) ---")
    if ts_col:
        rows = conn.execute(
            f"SELECT * FROM {t} WHERE {ts_col} >= ? ORDER BY {ts_col} DESC LIMIT 10",
            (ts_arg,),
        ).fetchall()
    else:
        rows = conn.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 10").fetchall()
    print(f"  {len(rows)} ligne(s) recentes")
    if rows:
        # garde 6 cols les plus pertinentes
        wanted = [c for c in ("id", "ticker", "symbol", "side", "action", "decision", "status", "reason", "rationale", "conviction", "score", ts_col or "")
                  if c and c in cols][:6]
        if not wanted:
            wanted = cols[:6]
        print_table([dict(r) for r in rows], wanted)

# === STEP 4 : snapshot targets ===
print()
print("[STEP 4] Targets actifs (dernier snapshot)")
print("-" * 70)
if not table_exists(conn, "portfolio_targets"):
    print("  Table portfolio_targets inexistante.")
else:
    cols = get_cols(conn, "portfolio_targets")
    print(f"  Colonnes : {', '.join(cols)}")
    # On utilise updated_at comme reference temporelle
    ts_col = "updated_at" if "updated_at" in cols else None
    # Trouver le snapshot_id le plus recent
    last = conn.execute(
        "SELECT snapshot_id, MAX(updated_at) AS ts "
        "FROM portfolio_targets GROUP BY snapshot_id ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    if last:
        sid = last["snapshot_id"]
        print(f"  Dernier snapshot_id : {sid}  (updated_at: {last['ts']})")
        rows = conn.execute(
            "SELECT ticker, target_weight_pct, active, source, score, agent_decided, updated_at "
            "FROM portfolio_targets WHERE snapshot_id = ? "
            "ORDER BY target_weight_pct DESC",
            (sid,),
        ).fetchall()
        wanted = ["ticker", "target_weight_pct", "active", "source", "score", "agent_decided", "updated_at"]
        print(f"  {len(rows)} ligne(s)")
        print_table([dict(r) for r in rows], wanted)
        # Stats
        actives = [r for r in rows if r["active"] in (1, "1", True)]
        zero_tgt = [r for r in rows if (r["target_weight_pct"] or 0) == 0]
        print()
        print(f"  Stats : {len(rows)} lignes / {len(actives)} actives / {len(zero_tgt)} a target=0")
    else:
        print("  Aucun snapshot trouve.")

# === STEP 5 : Coverage target_universe vs snapshot ===
print()
print("[STEP 5] Coverage target_universe vs dernier snapshot")
print("-" * 70)
if table_exists(conn, "target_universe"):
    tu_rows = conn.execute(
        "SELECT ticker, asset_class, sector, is_active FROM target_universe ORDER BY ticker"
    ).fetchall()
    print(f"  {len(tu_rows)} ticker(s) dans target_universe")
    # Symbols dans dernier snapshot
    snap_symbols = set()
    snap_targets = {}
    last = conn.execute(
        "SELECT snapshot_id FROM portfolio_targets ORDER BY updated_at DESC LIMIT 1"
    ).fetchone()
    if last:
        sid = last["snapshot_id"]
        for r in conn.execute(
            "SELECT ticker, target_weight_pct, active FROM portfolio_targets WHERE snapshot_id = ?",
            (sid,),
        ).fetchall():
            snap_symbols.add(r["ticker"])
            snap_targets[r["ticker"]] = (r["target_weight_pct"], r["active"])
    print(f"  {len(snap_symbols)} ticker(s) dans dernier snapshot")
    print()
    print(f"  {'Ticker':<10} {'Class':<10} {'Sector':<15} {'Active TU':<10} {'In Snap':<10} {'Target%':<10} {'Snap Act':<10}")
    print("  " + "-" * 80)
    for r in tu_rows:
        t = r["ticker"]
        snap_t, snap_a = snap_targets.get(t, (None, None))
        in_snap = "OK" if t in snap_symbols else "MIS"
        tgt_str = f"{snap_t*100:.2f}%" if (snap_t is not None) else "-"
        print(f"  {t:<10} {(r['asset_class'] or ''):<10} {(r['sector'] or ''):<15} "
              f"{str(r['is_active']):<10} {in_snap:<10} {tgt_str:<10} {str(snap_a or '-'):<10}")

# === STEP 6 : positions / portfolio actuel ===
print()
print("[STEP 6] Positions actuelles (recherche table positions/portfolio)")
print("-" * 70)
pos_tables = [t for t in list_tables(conn) if "position" in t.lower() or "portfolio" in t.lower()]
print(f"  Tables candidates : {pos_tables}")
for t in pos_tables[:3]:
    cols = get_cols(conn, t)
    print(f"  --- {t} ({', '.join(cols)}) ---")
    rows = conn.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 20").fetchall()
    print(f"  {len(rows)} ligne(s)")
    if rows:
        wanted = [c for c in ("ticker", "symbol", "qty", "quantity", "weight_pct", "weight", "value_usd", "value", "status", "updated_at")
                  if c in cols][:6]
        if not wanted:
            wanted = cols[:6]
        print_table([dict(r) for r in rows], wanted)

conn.close()
print()
print("=" * 70)
print("Termine.")
print("=" * 70)
