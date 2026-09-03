

===== nextones-broker-shadow-executor.py =====

# -*- coding: utf-8 -*-
# [NEXTONES-BROKER-SHADOW-EXECUTOR-V1]
# Execute en mode "shadow" (paper) les ordres acceptes par le translator :
#   - INSERT dans broker_shadow_orders avec entry_price, est_notional,
#     est_margin (option B2 : extended)
#   - JAMAIS d'envoi PineConnector ni MetaAPI execute_order
#   - mark-to-market sur demande via snapshot_pnl()
#
# Dependances:
#   - nextones-order-translator.py (translate)
#   - metaapi_provider.py (optionnel, pour entry_price)
#       -> si absent, on accepte un prix injecte ou on stocke entry_price=NULL
#
# Hypotheses de calcul :
#   notional = volume_lots * contract_size * entry_price
#   margin   = notional / leverage_assumed
#       leverage_assumed defaut par classe (cf. LEVERAGE_DEFAULTS)
#
# API publique:
#   execute_shadow(thesium_ticker, side, qty, *,
#                  cycle_id=None, asset_class=None,
#                  entry_price=None, leverage=None,
#                  sl=None, tp=None) -> dict
#   snapshot_pnl(open_only=True) -> int     # nb lignes inserees
#
# Usage CLI:
#   py -3.13 nextones-broker-shadow-executor.py exec CSCO buy 166 --cycle 20260530-1025
#   py -3.13 nextones-broker-shadow-executor.py snapshot

import os
import sys
import json
import sqlite3
import importlib.util
from datetime import datetime, timezone
from typing import Optional, Dict, Any

# [NEXTONES-BROKER-DB-HARDENED-V1]
import sqlite3 as _sq_nx_h
def _nx_open_db(_p, **_kw):
    _kw.setdefault('timeout', 10.0)
    _c = _sq_nx_h.connect(_p, **_kw)
    try:
        _c.execute('PRAGMA busy_timeout=10000')
    except Exception:
        pass
    return _c


DB_PATH = os.environ.get(
    "THESIUM_DB",
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db",
)

_TRANSLATOR_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "nextones-order-translator.py",
)

_T = None
_MP = None  # metaapi_provider

LEVERAGE_DEFAULTS = {
    "equity_us": 5.0,
    "etf_us": 5.0,
    "crypto": 2.0,
    "fx": 30.0,
    "metal": 20.0,
    "index": 20.0,
    "energy": 10.0,
    "soft": 10.0,
}


def _translator():
    global _T
    if _T is None:
        spec = importlib.util.spec_from_file_location(
            "_nx_order_translator", _TRANSLATOR_PATH
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _T = mod
    return _T


def _metaapi():
    global _MP
    if _MP is False:
        return None
    if _MP is not None:
        return _MP
    try:
        import metaapi_provider as mp
        if hasattr(mp, "is_configured") and mp.is_configured():
            _MP = mp
            return mp
    except Exception:
        pass
    _MP = False
    return None


def _entry_price(broker_symbol: str,
                 explicit: Optional[float] = None) -> Optional[float]:
    """Recupere le prix entree : explicit > MetaAPI getCurrentPrice > None."""
    if explicit is not None:
        try:
            return float(explicit)
        except Exception:
            return None
    mp = _metaapi()
    if mp is None:
        return None
    try:
        p = mp.get_current_price(broker_symbol)
        if isinstance(p, dict):
            # tente ask pour buy / bid pour sell -- ici on prend ask par defaut
            return float(p.get("ask") or p.get("bid") or p.get("price"))
        return float(p) if p is not None else None
    except Exception as e:
        print("[WARN] entry_price " + broker_symbol + ": " + str(e))
        return None


def _audit(con, action: str, cycle_id, ticker, broker_symbol, payload, notes):
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = con.cursor()
    cur.execute(
        "INSERT INTO broker_shadow_audit(ts, action, cycle_id, thesium_ticker, "
        "broker_symbol, payload_json, notes) VALUES(?, ?, ?, ?, ?, ?, ?)",
        (ts, action, cycle_id, ticker, broker_symbol,
         json.dumps(payload, default=str)[:4000], notes),
    )


def execute_shadow(thesium_ticker: str,
                   side: str,
                   qty: float,
                   cycle_id: Optional[str] = None,
                   asset_class: Optional[str] = None,
                   entry_price: Optional[float] = None,
                   leverage: Optional[float] = None,
                   sl: Optional[float] = None,
                   tp: Optional[float] = None,
                   db_path: Optional[str] = None) -> Dict[str, Any]:
    """Insere un ordre shadow et renvoie le dict resultat."""
    T = _translator()
    tr = T.translate(thesium_ticker, qty, side, asset_class=asset_class,
                     sl=sl, tp=tp)
    path = db_path or DB_PATH

    if not tr.accepted:
        try:
            con = _nx_open_db(path)
            _audit(con, "shadow_reject", cycle_id, thesium_ticker,
                   tr.broker_symbol, tr.to_dict(), tr.reason or "reject")
            con.commit()
            con.close()
        except Exception as e:
            print("[WARN] audit reject: " + str(e))
        return {"shadow_order_id": None, "accepted": False,
                "reason": tr.reason, "translator": tr.to_dict()}

    ac = (tr.diagnostics or {}).get("asset_class") or asset_class
    specs = (tr.diagnostics or {}).get("specs") or {}
    contract_size = float(specs.get("contract_size", 1.0))
    lev = float(leverage) if leverage else LEVERAGE_DEFAULTS.get(ac, 5.0)

    ep = _entry_price(tr.broker_symbol, entry_price)
    notional = None
    margin = None
    if ep is not None:
        notional = tr.volume_lots * contract_size * ep
        if lev > 0:
            margin = notional / lev

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    con = _nx_open_db(path)
    try:
        cur = con.cursor()
        cur.execute(
            "INSERT INTO broker_shadow_orders("
            "  ts, cycle_id, thesium_ticker, broker_symbol, side,"
            "  qty_requested, volume_lots, rounding_gap_pct, asset_class,"
            "  quote_ccy, contract_size, lot_step, entry_price_metaapi,"
            "  est_notional, est_margin, leverage_assumed, sl, tp,"
            "  status, notes"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ts, cycle_id, thesium_ticker, tr.broker_symbol, side.lower(),
                float(qty), tr.volume_lots, tr.rounding_gap_pct, ac,
                (tr.diagnostics or {}).get("quote_ccy"),
                contract_size, specs.get("lot_step"), ep,
                notional, margin, lev, sl, tp,
                "open", "shadow_phase2_v1",
            ),
        )
        shadow_id = cur.lastrowid
        _audit(con, "shadow_accept", cycle_id, thesium_ticker,
               tr.broker_symbol,
               {"shadow_order_id": shadow_id, "entry_price": ep,
                "notional": notional, "margin": margin, "leverage": lev,
                "translator": tr.to_dict()},
               "ok")
        con.commit()
    finally:
        con.close()

    return {
        "shadow_order_id": shadow_id,
        "accepted": True,
        "broker_symbol": tr.broker_symbol,
        "volume_lots": tr.volume_lots,
        "entry_price": ep,
        "est_notional": notional,
        "est_margin": margin,
        "leverage_assumed": lev,
    }


# ----------------------------------------------------------------------
# Snapshot P&L (mark-to-market)
# ----------------------------------------------------------------------

def snapshot_pnl(open_only: bool = True,
                 db_path: Optional[str] = None) -> int:
    """
    Pour chaque shadow order ouvert, recalcule le P&L au prix MetaAPI
    courant et insere une ligne dans broker_shadow_pnl.
    Retourne le nombre de lignes inserees.
    """
    path = db_path or DB_PATH
    con = _nx_open_db(path)
    cur = con.cursor()
    where = "WHERE status='open'" if open_only else ""
    cur.execute(
        "SELECT id, broker_symbol, side, volume_lots, entry_price_metaapi, "
        "       contract_size, quote_ccy "
        "FROM broker_shadow_orders " + where
    )
    rows = cur.fetchall()
    n = 0
    snap_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for (oid, sym, side, vol, entry, csize, ccy) in rows:
        mark = _entry_price(sym, None)
        if mark is None or entry is None:
            continue
        # P&L direction-aware
        direction = 1.0 if side == "buy" else -1.0
        pnl_q = direction * vol * (csize or 1.0) * (mark - entry)
        # conversion en EUR best-effort (suppose ccy=USD => taux ~1.07; en
        # absence de FX live, on stocke pnl_quote_ccy uniquement et on laisse
        # pnl_eur=NULL pour ne pas mentir)
        cur.execute(
            "INSERT INTO broker_shadow_pnl(snapshot_ts, shadow_order_id, "
            "broker_symbol, side, volume_lots, entry_price, mark_price, "
            "pnl_quote_ccy, pnl_eur, slippage_vs_thesium, notes) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (snap_ts, oid, sym, side, vol, entry, mark, pnl_q, None, None,
             "snapshot_v1_quote_only"),
        )
        n += 1
    con.commit()
    con.close()
    return n


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def _main_cli():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  exec <ticker> <side> <qty> [--cycle ID] [--price P] [--lev L]")
        print("  snapshot")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "exec":
        if len(sys.argv) < 5:
            print("Usage: exec <ticker> <side> <qty>"); sys.exit(1)
        tkr = sys.argv[2]; side = sys.argv[3]; qty = float(sys.argv[4])
        cycle = None; price = None; lev = None
        if "--cycle" in sys.argv:
            cycle = sys.argv[sys.argv.index("--cycle") + 1]
        if "--price" in sys.argv:
            price = float(sys.argv[sys.argv.index("--price") + 1])
        if "--lev" in sys.argv:
            lev = float(sys.argv[sys.argv.index("--lev") + 1])
        r = execute_shadow(tkr, side, qty, cycle_id=cycle,
                           entry_price=price, leverage=lev)
        print(json.dumps(r, indent=2, default=str))
    elif cmd == "snapshot":
        n = snapshot_pnl()
        print("[OK] " + str(n) + " lignes pnl inserees")
    else:
        print("Commande inconnue: " + cmd); sys.exit(1)


if __name__ == "__main__":
    _main_cli()



===== nextones-broker-shadow-schema.py =====

# -*- coding: utf-8 -*-
# [NEXTONES-BROKER-SHADOW-SCHEMA-V1]
# DDL pour les tables d'execution "shadow" (paper) cote broker:
#   - broker_shadow_orders : chaque ordre Thesium accepte par le translator
#                            est dedouble en shadow (sans envoi PineConnector)
#   - broker_shadow_pnl    : snapshot quotidien du P&L shadow (mark-to-market
#                            au prix MetaAPI courant)
#   - broker_shadow_audit  : trace d'execution + raisons rejets
#
# Idempotent. Aucun seed.
#
# Usage:
#   py -3.13 nextones-broker-shadow-schema.py

import os
import sys
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "THESIUM_DB",
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db",
)

DDL = {
    "broker_shadow_orders": """
CREATE TABLE IF NOT EXISTS broker_shadow_orders (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                    TEXT NOT NULL,
    cycle_id              TEXT,
    thesium_ticker        TEXT NOT NULL,
    broker_symbol         TEXT NOT NULL,
    side                  TEXT NOT NULL,
    qty_requested         REAL NOT NULL,
    volume_lots           REAL NOT NULL,
    rounding_gap_pct      REAL,
    asset_class           TEXT,
    quote_ccy             TEXT,
    contract_size         REAL,
    lot_step              REAL,
    entry_price_metaapi   REAL,
    est_notional          REAL,
    est_margin            REAL,
    leverage_assumed      REAL,
    sl                    REAL,
    tp                    REAL,
    status                TEXT NOT NULL DEFAULT 'open',
    notes                 TEXT
);
""",
    "broker_shadow_pnl": """
CREATE TABLE IF NOT EXISTS broker_shadow_pnl (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_ts           TEXT NOT NULL,
    shadow_order_id       INTEGER NOT NULL,
    broker_symbol         TEXT NOT NULL,
    side                  TEXT NOT NULL,
    volume_lots           REAL NOT NULL,
    entry_price           REAL,
    mark_price            REAL,
    pnl_quote_ccy         REAL,
    pnl_eur               REAL,
    slippage_vs_thesium   REAL,
    notes                 TEXT,
    FOREIGN KEY (shadow_order_id) REFERENCES broker_shadow_orders(id)
);
""",
    "broker_shadow_audit": """
CREATE TABLE IF NOT EXISTS broker_shadow_audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    action          TEXT NOT NULL,
    cycle_id        TEXT,
    thesium_ticker  TEXT,
    broker_symbol   TEXT,
    payload_json    TEXT,
    notes           TEXT
);
""",
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sso_ticker ON broker_shadow_orders(thesium_ticker);",
    "CREATE INDEX IF NOT EXISTS idx_sso_broker ON broker_shadow_orders(broker_symbol);",
    "CREATE INDEX IF NOT EXISTS idx_sso_status ON broker_shadow_orders(status);",
    "CREATE INDEX IF NOT EXISTS idx_sso_cycle  ON broker_shadow_orders(cycle_id);",
    "CREATE INDEX IF NOT EXISTS idx_spnl_order ON broker_shadow_pnl(shadow_order_id);",
    "CREATE INDEX IF NOT EXISTS idx_spnl_ts    ON broker_shadow_pnl(snapshot_ts);",
    "CREATE INDEX IF NOT EXISTS idx_ssa_cycle  ON broker_shadow_audit(cycle_id);",
]


def main():
    if not os.path.exists(DB_PATH):
        print("[ERR] DB introuvable: " + DB_PATH)
        sys.exit(2)
    print("[INFO] DB: " + DB_PATH)
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        for name, ddl in DDL.items():
            cur.execute(ddl)
        for idx in INDEXES:
            cur.execute(idx)
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cur.execute(
            "INSERT INTO broker_shadow_audit(ts, action, payload_json, notes) "
            "VALUES(?, ?, ?, ?)",
            (ts, "schema_init", "{}", "Phase 2 shadow DDL applied"),
        )
        con.commit()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND "
            "name IN ('broker_shadow_orders','broker_shadow_pnl','broker_shadow_audit')"
        )
        rows = [r[0] for r in cur.fetchall()]
        print("[OK] Tables presentes: " + ", ".join(sorted(rows)))
    finally:
        con.close()


if __name__ == "__main__":
    main()



===== nextones-diag-perf-rolling-prereq-v1.py =====

# -*- coding: utf-8 -*-
"""
DIAG PHASE 9.5 - Perf rolling J-30 prereq
- shadow_perf_rolling schema (DDL + columns)
- shadow_fills schema + sample row + date range
- prices schema + instrument_id mapping (ticker -> instrument_id)
- Estimation J-30 coverage : combien de cycles dans fenetre J-30 from 20260612
"""
import sqlite3
import sys
import os

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def header(title):
    print("=" * 78)
    print(title)
    print("=" * 78)

def main():
    if not os.path.exists(DB):
        print("[ERR] DB not found:", DB)
        sys.exit(1)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---------- shadow_perf_rolling ----------
    header("shadow_perf_rolling : DDL + columns")
    row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='shadow_perf_rolling'"
    ).fetchone()
    if row:
        print(row["sql"])
    else:
        print("[ERR] table shadow_perf_rolling not found")
    print()
    print("PRAGMA table_info :")
    for r in cur.execute("PRAGMA table_info(shadow_perf_rolling)").fetchall():
        print("  cid={} name={} type={} notnull={} dflt={} pk={}".format(
            r["cid"], r["name"], r["type"], r["notnull"], r["dflt_value"], r["pk"]
        ))
    n = cur.execute("SELECT COUNT(*) AS n FROM shadow_perf_rolling").fetchone()["n"]
    print()
    print("rows actuelles :", n)

    # ---------- shadow_fills ----------
    print()
    header("shadow_fills : DDL + columns + sample + range")
    row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='shadow_fills'"
    ).fetchone()
    print(row["sql"] if row else "[ERR] table shadow_fills not found")
    print()
    print("PRAGMA table_info :")
    for r in cur.execute("PRAGMA table_info(shadow_fills)").fetchall():
        print("  name={} type={} notnull={}".format(r["name"], r["type"], r["notnull"]))
    print()
    n = cur.execute("SELECT COUNT(*) AS n FROM shadow_fills").fetchone()["n"]
    print("rows totales :", n)
    print()
    print("Sample 3 rows :")
    for r in cur.execute("SELECT * FROM shadow_fills LIMIT 3").fetchall():
        print("  ", dict(r))
    print()
    print("Cycles distincts dans shadow_fills :")
    for r in cur.execute(
        "SELECT SUBSTR(cycle_id,1,8) AS day, COUNT(DISTINCT cycle_id) AS n_cyc, "
        "COUNT(*) AS n_fills FROM shadow_fills "
        "GROUP BY day ORDER BY day"
    ).fetchall():
        print("  day={} n_cyc={} n_fills={}".format(r["day"], r["n_cyc"], r["n_fills"]))

    # ---------- prices ----------
    print()
    header("prices : DDL + columns + sample")
    row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='prices'"
    ).fetchone()
    print(row["sql"] if row else "[ERR]")
    print()
    print("PRAGMA table_info :")
    for r in cur.execute("PRAGMA table_info(prices)").fetchall():
        print("  name={} type={}".format(r["name"], r["type"]))
    print()
    print("Sample 3 rows :")
    for r in cur.execute("SELECT * FROM prices LIMIT 3").fetchall():
        print("  ", dict(r))

    # ---------- instruments mapping ----------
    print()
    header("instruments : ticker -> instrument_id mapping")
    row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='instruments'"
    ).fetchone()
    print(row["sql"] if row else "[ERR]")
    print()
    print("Sample 5 rows :")
    for r in cur.execute("SELECT * FROM instruments LIMIT 5").fetchall():
        print("  ", dict(r))
    print()
    n = cur.execute("SELECT COUNT(*) AS n FROM instruments").fetchone()["n"]
    print("total instruments :", n)

    # ---------- J-30 coverage estimation ----------
    print()
    header("J-30 coverage from 20260612")
    print()
    print("Fenetre J-30 = 20260513 -> 20260612 (30 jours)")
    print()
    print("Cycles dans shadow_fills sur cette fenetre :")
    rows = cur.execute(
        "SELECT SUBSTR(cycle_id,1,8) AS day, COUNT(DISTINCT cycle_id) AS n_cyc "
        "FROM shadow_fills "
        "WHERE SUBSTR(cycle_id,1,8) >= '20260513' AND SUBSTR(cycle_id,1,8) <= '20260612' "
        "GROUP BY day ORDER BY day"
    ).fetchall()
    total = 0
    for r in rows:
        print("  day={} n_cyc={}".format(r["day"], r["n_cyc"]))
        total += r["n_cyc"]
    print()
    print("TOTAL cycles J-30 :", total)
    print()
    print("Variants actifs :")
    for r in cur.execute(
        "SELECT id, name, active FROM shadow_variants WHERE active=1 ORDER BY id"
    ).fetchall():
        print("  id={} name={} active={}".format(r["id"], r["name"], r["active"]))

    conn.close()
    print()
    print("=" * 78)
    print("DIAG DONE")
    print("=" * 78)

if __name__ == "__main__":
    main()



===== nextones-diag-pplx-for-shadow-memo-v1.py =====

# -*- coding: utf-8 -*-
"""
Diag prereq Jalon 9.5b LLM Memo Shadow :
  1. Confirm presence pplx_client.py et signature de la fonction principale
     (ex: ask_pplx, chat, query...)
  2. Confirm presence pplx_factor_agent.py / pplx_thesis_agent.py pour pattern reference
  3. Lister fichiers shadow_*.py existants (engine, perf_rolling, hook, backfill)
  4. Confirmer column recommendation_memo dans shadow_perf_rolling (PRAGMA)
"""
import os
import sqlite3

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

print("=" * 70)
print("[1] Fichiers pplx_*.py + shadow_*.py dans", ROOT)
print("=" * 70)
files = sorted(os.listdir(ROOT))
for f in files:
    fl = f.lower()
    if fl.startswith("pplx_") and fl.endswith(".py"):
        size = os.path.getsize(os.path.join(ROOT, f))
        print("  PPLX     | {:50s} {:>8} bytes".format(f, size))
    if fl.startswith("shadow_") and fl.endswith(".py"):
        size = os.path.getsize(os.path.join(ROOT, f))
        print("  SHADOW   | {:50s} {:>8} bytes".format(f, size))

print()
print("=" * 70)
print("[2] Signature pplx_client.py (def ...)")
print("=" * 70)
client = os.path.join(ROOT, "pplx_client.py")
if os.path.exists(client):
    with open(client, "r", encoding="utf-8-sig", errors="replace") as f:
        for i, line in enumerate(f, 1):
            s = line.strip()
            if s.startswith("def ") or s.startswith("class ") or s.startswith("async def "):
                print("  L{:5d} | {}".format(i, s))
else:
    print("  [ERR] pplx_client.py introuvable")

print()
print("=" * 70)
print("[3] Pattern d'appel dans pplx_factor_agent.py (1eres 40 lignes utiles)")
print("=" * 70)
fa = os.path.join(ROOT, "pplx_factor_agent.py")
if os.path.exists(fa):
    with open(fa, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.readlines()
    # Cherche imports + 1er appel client
    shown = 0
    for i, line in enumerate(lines, 1):
        if "pplx_client" in line or "ask_pplx" in line or "from pplx" in line or "import pplx" in line or ".ask(" in line or ".chat(" in line or ".query(" in line:
            print("  L{:5d} | {}".format(i, line.rstrip()))
            shown += 1
            if shown > 25: break
else:
    print("  [WARN] pplx_factor_agent.py absent")

print()
print("=" * 70)
print("[4] Schema shadow_perf_rolling (PRAGMA table_info)")
print("=" * 70)
conn = sqlite3.connect(DB, timeout=10.0)
try:
    cur = conn.execute("PRAGMA table_info(shadow_perf_rolling)")
    for row in cur.fetchall():
        cid, name, ctype, notnull, dflt, pk = row
        print("  {:3d} {:30s} {:15s} notnull={} pk={}".format(cid, name, ctype, notnull, pk))
    print()
    cur = conn.execute("SELECT COUNT(*) FROM shadow_perf_rolling")
    print("  Total rows:", cur.fetchone()[0])
    cur = conn.execute("SELECT COUNT(*) FROM shadow_perf_rolling WHERE recommendation_memo IS NOT NULL")
    print("  Rows avec memo:", cur.fetchone()[0])
finally:
    conn.close()

print()
print("DONE")



===== nextones-diag-shadow-401-v1.py =====

# -*- coding: utf-8 -*-
"""
Diag 401 sur /api/shadow/perf-rolling depuis UI :
  1. Refait login JWT (rguelin / Thesium2026!)
  2. Appelle /api/shadow/perf-rolling AVEC token -> doit etre 200
  3. Appelle /api/shadow/perf-rolling SANS token -> doit etre 401
  4. Dump les premieres lignes du handler dans api_server.py pour voir si Depends(get_current_user) est bien la
  5. Dump le code dans app.js qui peuple state.token (login + localStorage)
"""
import urllib.request
import urllib.error
import json
import re

BASE = "http://127.0.0.1:8000"

def http(method, path, body=None, token=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")

# 1. Login
print("=== [1] Login ===")
code, body = http("POST", "/api/auth/login", {"username": "rguelin", "password": "Thesium2026!"})
print("status:", code)
print("body:", body[:300])
token = None
try:
    j = json.loads(body)
    token = j.get("access_token") or j.get("token")
except Exception as e:
    print("parse err:", e)
print("token len:", len(token) if token else "NONE")
print()

# 2. Avec token
print("=== [2] GET /api/shadow/perf-rolling AVEC token ===")
code, body = http("GET", "/api/shadow/perf-rolling?window=30", token=token)
print("status:", code)
print("body[:400]:", body[:400])
print()

# 3. Sans token
print("=== [3] GET /api/shadow/perf-rolling SANS token ===")
code, body = http("GET", "/api/shadow/perf-rolling?window=30", token=None)
print("status:", code)
print("body[:400]:", body[:400])
print()

# 4. Dump signature des handlers shadow dans api_server.py
print("=== [4] Signature handlers shadow dans api_server.py ===")
API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
with open(API, "r", encoding="utf-8-sig", errors="replace") as f:
    lines = f.readlines()
for i, line in enumerate(lines, 1):
    if "/api/shadow/" in line or "shadow_list_variants" in line or "shadow_perf_rolling" in line:
        print("  L{:5d} | {}".format(i, line.rstrip()))
print()

# 5. Dump login + state.token write sites dans app.js
print("=== [5] Sites qui ecrivent state.token dans app.js ===")
JS = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
    js_lines = f.readlines()
for i, line in enumerate(js_lines, 1):
    if "state.token" in line:
        print("  L{:5d} | {}".format(i, line.rstrip()))
print()

print("DONE")



===== nextones-diag-shadow-api-500-v1.py =====

# -*- coding: utf-8 -*-
"""
DIAG : pourquoi /api/shadow/variants retourne 500
Verifie :
- imports sqlite3, json dans api_server.py
- variable DB_PATH (existe ? quel nom exact ?)
- pattern utilise dans une route existante qui marche (ex /api/regime/current)
- bloc SHADOW_API_V1 actuellement en place
"""
import os
import re

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API = os.path.join(BASE, "api_server.py")


def header(t):
    print("=" * 78)
    print(t)
    print("=" * 78)


with open(API, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()
lines = src.split("\n")
print("Total lines :", len(lines))

# 1. Imports
header("[1] Imports en tete de api_server.py (top 50 lignes)")
for i, ln in enumerate(lines[:50], start=1):
    if ln.strip().startswith("import ") or ln.strip().startswith("from "):
        print("  L{:3d} | {}".format(i, ln.strip()))

# 2. Variables DB_PATH / db_path / DB / etc.
header("[2] Toutes occurrences de variables DB-path-like (top 100 lignes)")
db_candidates = []
for i, ln in enumerate(lines[:200], start=1):
    m = re.search(r'\b(DB_PATH|DB|db_path|DATABASE|database_path|DB_FILE)\s*=', ln)
    if m and not ln.strip().startswith("#"):
        db_candidates.append((i, ln.strip()))
for ln, txt in db_candidates[:20]:
    print("  L{:3d} | {}".format(ln, txt))

# 3. Usage de sqlite3.connect dans une route qui marche
header("[3] Pattern sqlite3.connect dans /api/regime/current ou similaire")
regime_lines = []
in_regime = False
for i, ln in enumerate(lines, start=1):
    if "/api/regime/current" in ln:
        in_regime = True
        regime_lines.append((i, ln))
        continue
    if in_regime:
        regime_lines.append((i, ln))
        if len(regime_lines) > 30:
            break
        if ln.startswith("@app.") or ln.startswith("def ") and len(regime_lines) > 5:
            break
for ln, txt in regime_lines[:25]:
    print("  L{:5d} | {}".format(ln, txt.rstrip()[:140]))

# 4. Toutes les occurrences de "sqlite3.connect(" (premiere)
header("[4] Pattern sqlite3.connect(...) - premiers 6 hits")
hits = []
for i, ln in enumerate(lines, start=1):
    if "sqlite3.connect" in ln:
        hits.append((i, ln.strip()))
for ln, txt in hits[:6]:
    print("  L{:5d} | {}".format(ln, txt[:140]))

# 5. Bloc SHADOW_API_V1 actuel
header("[5] Bloc [SHADOW_API_V1] tel qu'il est dans api_server.py")
begin_idx = None
end_idx = None
for i, ln in enumerate(lines, start=1):
    if "[SHADOW_API_V1] BEGIN" in ln and begin_idx is None:
        begin_idx = i
    if "[SHADOW_API_V1] END" in ln:
        end_idx = i

if begin_idx and end_idx:
    print("BEGIN L{} END L{}".format(begin_idx, end_idx))
    for k in range(begin_idx - 1, end_idx):
        print("  L{:5d} | {}".format(k + 1, lines[k]))
else:
    print("[ERR] markers non trouves")

# 6. Check imports JSON + sqlite3 explicites
header("[6] sqlite3 et json importes ?")
has_sqlite3 = any(re.match(r"^\s*import\s+sqlite3", ln) or
                  re.match(r"^\s*from\s+sqlite3\b", ln) for ln in lines)
has_json = any(re.match(r"^\s*import\s+json", ln) or
               re.match(r"^\s*from\s+json\b", ln) for ln in lines)
print("import sqlite3 :", has_sqlite3)
print("import json    :", has_json)

print()
print("=" * 78)
print("DIAG DONE")
print("=" * 78)



===== nextones-diag-shadow-context.py =====

# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-SHADOW-CONTEXT-V1]
#
# Diag pre-wiring du routeur Phase 3C etape 4.
#
# But : extraire le contexte exact autour du marker [NEXTONES-SHADOW-EXEC-V1]
# dans execution_engine.py pour preparer l'installeur du routeur.
#
# Sorties :
#   - 60 lignes de contexte autour du marker (le bloc shadow_executor wiring)
#   - signature de la fonction englobante
#   - variables disponibles dans le scope (ticker, side, qty, cycle_id, etc.)
#   - presence colonne is_live dans broker_shadow_orders

import os
import re
import sqlite3
import sys

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
ENGINE = os.path.join(PROD, "execution_engine.py")
DB = os.path.join(PROD, "thesium.db")

print("=" * 70)
print("DIAG SHADOW CONTEXT - prep wiring routeur Phase 3C etape 4")
print("=" * 70)

# 1. Lire engine et chercher le marker
if not os.path.exists(ENGINE):
    print(f"[FATAL] {ENGINE} introuvable")
    sys.exit(2)

with open(ENGINE, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()

marker_lines = []
for i, ln in enumerate(lines):
    if "NEXTONES-SHADOW-EXEC-V1" in ln:
        marker_lines.append(i)

print()
print(f"Marker [NEXTONES-SHADOW-EXEC-V1] trouve sur {len(marker_lines)} ligne(s)")
for ml in marker_lines:
    print(f"  L{ml+1}: {lines[ml].rstrip()}")

# 2. Pour chaque marker, dump 30 lignes avant + 30 apres
print()
for ml in marker_lines:
    print("-" * 70)
    print(f"CONTEXTE AUTOUR L{ml+1}")
    print("-" * 70)
    start = max(0, ml - 30)
    end = min(len(lines), ml + 31)
    for i in range(start, end):
        prefix = ">>>" if i == ml else "   "
        print(f"{prefix} L{i+1:5d} : {lines[i].rstrip()}")

# 3. Detecter la fonction englobante (def ... avant le marker)
print()
print("-" * 70)
print("FONCTION ENGLOBANTE")
print("-" * 70)
if marker_lines:
    ml = marker_lines[0]
    fn_pat = re.compile(r"^\s*def\s+(\w+)\s*\(([^)]*)\)")
    for i in range(ml, -1, -1):
        m = fn_pat.match(lines[i])
        if m:
            print(f"  L{i+1}: def {m.group(1)}({m.group(2)})")
            # Dump entete + 5 lignes
            for j in range(i, min(i + 6, len(lines))):
                print(f"    {lines[j].rstrip()}")
            break
    else:
        print("  Aucune def trouvee en remontant (peut etre module-level)")

# 4. Variables candidates (ticker, side, qty, cycle_id, asset_class)
print()
print("-" * 70)
print("VARIABLES SCOPE (recherche dans 80 lignes avant marker)")
print("-" * 70)
candidates = ["ticker", "side", "qty", "quantity", "cycle_id",
              "asset_class", "entry_price", "price", "thesium_ticker",
              "order_id", "proposal_id"]
if marker_lines:
    ml = marker_lines[0]
    block = "".join(lines[max(0, ml - 80):ml + 5])
    for var in candidates:
        # cherche affectation ou usage
        if re.search(rf"\b{var}\b\s*=", block):
            print(f"  [ASSIGNED] {var}")
        elif re.search(rf"\b{var}\b", block):
            print(f"  [USED]     {var}")

# 5. Schema broker_shadow_orders
print()
print("-" * 70)
print("SCHEMA broker_shadow_orders (focus is_live)")
print("-" * 70)
if os.path.exists(DB):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info(broker_shadow_orders)")
        cols = cur.fetchall()
        has_is_live = False
        for c in cols:
            cid, name, typ, notnull, dflt, pk = c
            mark = " <-- IS_LIVE" if name == "is_live" else ""
            print(f"  {cid:>3} {name:<22} {typ:<12} notnull={notnull} default={dflt}{mark}")
            if name == "is_live":
                has_is_live = True
        print()
        if has_is_live:
            print("  [OK] colonne is_live deja presente")
            cur.execute("""
                SELECT is_live, COUNT(*) FROM broker_shadow_orders
                GROUP BY is_live
            """)
            for row in cur.fetchall():
                print(f"     is_live={row[0]} count={row[1]}")
        else:
            print("  [TODO] colonne is_live ABSENTE - sera ajoutee par installeur")
    finally:
        conn.close()
else:
    print(f"  [WARN] DB {DB} introuvable")

# 6. Vue rapide insert shadow_executor (pour comprendre le pattern d'ecriture)
print()
print("-" * 70)
print("INSERT broker_shadow_orders (callsites)")
print("-" * 70)
insert_pat = re.compile(r"INSERT\s+INTO\s+broker_shadow_orders", re.IGNORECASE)
for i, ln in enumerate(lines):
    if insert_pat.search(ln):
        print(f"  L{i+1}: {ln.rstrip()[:120]}")

# Cherche aussi dans broker_shadow_executor.py si existe
SHADOW_EXEC = os.path.join(PROD, "nextones-broker-shadow-executor.py")
if os.path.exists(SHADOW_EXEC):
    print()
    print(f"  Dans {os.path.basename(SHADOW_EXEC)} :")
    with open(SHADOW_EXEC, "r", encoding="utf-8-sig") as f:
        slines = f.readlines()
    for i, ln in enumerate(slines):
        if insert_pat.search(ln):
            print(f"    L{i+1}: {ln.rstrip()[:120]}")

print()
print("=" * 70)
print("FIN DIAG - colle la sortie complete")
print("=" * 70)



===== nextones-diag-shadow-diff-log-schema-v1.py =====

"""Diag : schema shadow_diff_log + repere d'integration dans scheduler prod."""
import sqlite3, os, re

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

print("=== SCHEMA shadow_diff_log ===")
conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()
cur.execute("PRAGMA table_info(shadow_diff_log)")
for c in cur.fetchall():
    print(f"  {c[1]:30s} {c[2]:15s} nn={c[3]} pk={c[5]}")

cur.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='shadow_diff_log'")
print("\n=== INDEXES ===")
for r in cur.fetchall():
    print(f"  {r[0]}")

# Repere : ou est appele run_decision_cycle dans scheduler ?
print("\n=== SCHEDULER : appels run_decision_cycle / execute_cycle ===")
for fname in ["scheduler.py", "api_server_with_static.py"]:
    fpath = os.path.join(ROOT, fname)
    if not os.path.exists(fpath):
        continue
    print(f"\n--- {fname} ---")
    with open(fpath, "rb") as f:
        data = f.read().decode("utf-8-sig", errors="replace")
    lines = data.split("\n")
    for i, ln in enumerate(lines, 1):
        if re.search(r"(run_decision_cycle|execute_cycle|run_cycle)\s*\(", ln):
            print(f"  L{i}: {ln.strip()[:120]}")

# Last 2 cycles prod pour test Phase 9.4
print("\n=== 2 derniers cycles prod ===")
cur.execute("""
    SELECT cycle_id, COUNT(*) as n FROM convergence_snapshots
    GROUP BY cycle_id ORDER BY cycle_id DESC LIMIT 5
""")
for r in cur.fetchall():
    print(f"  {r[0]:25s} n={r[1]}")

conn.close()



===== nextones-diag-shadow-engine-prereq-v1.py =====

"""
Diag prereq Phase 9.2 - shadow_engine MVP
Verifier :
1. portfolio_targets schema + sample sur derniers cycles
2. convergence_snapshots disponibles sur cycles recents
3. Logique sizing : ou est applique le multiplicateur conv ?
"""
import sqlite3, sys, json

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def main():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("="*78)
    print("DIAG PREREQ PHASE 9.2 - shadow_engine MVP")
    print("="*78)

    # 1. portfolio_targets schema
    print("\n[1/6] portfolio_targets schema")
    cur.execute("PRAGMA table_info(portfolio_targets)")
    for r in cur.fetchall():
        print(f"  {r['name']:30s} {r['type']}")

    # 2. portfolio_targets sample dernier cycle
    print("\n[2/6] portfolio_targets dernier cycle (top 10 lignes)")
    cur.execute("""
        SELECT cycle_id, COUNT(*) as n, MAX(created_at) as last_dt
        FROM portfolio_targets
        GROUP BY cycle_id
        ORDER BY last_dt DESC LIMIT 5
    """)
    cycles = cur.fetchall()
    for c in cycles:
        print(f"  cycle={c['cycle_id']:25s} n={c['n']:3d} dt={c['last_dt']}")
    if cycles:
        last_cycle = cycles[0]['cycle_id']
        cur.execute("SELECT * FROM portfolio_targets WHERE cycle_id=? LIMIT 10", (last_cycle,))
        rows = cur.fetchall()
        if rows:
            print(f"\n  Sample cols dispo : {list(rows[0].keys())}")
            for r in rows[:5]:
                d = dict(r)
                print(f"    {d}")

    # 3. convergence_snapshots dernier cycle
    print("\n[3/6] convergence_snapshots dernier cycle prod")
    if cycles:
        cur.execute("""
            SELECT cycle_id, COUNT(*) as n
            FROM convergence_snapshots
            WHERE cycle_id=? GROUP BY cycle_id
        """, (last_cycle,))
        r = cur.fetchone()
        if r:
            print(f"  cycle={last_cycle} : {r['n']} snapshots")
            cur.execute("""
                SELECT ticker, convergence_pct, sizing_multiplier, forced_exit, is_crypto, direction_consensus
                FROM convergence_snapshots WHERE cycle_id=? LIMIT 10
            """, (last_cycle,))
            for s in cur.fetchall():
                print(f"    {s['ticker']:8s} conv={s['convergence_pct']:.2f} mult={s['sizing_multiplier']:.2f} fe={s['forced_exit']} crypto={s['is_crypto']} dir={s['direction_consensus']}")
        else:
            print(f"  Aucun snapshot pour cycle {last_cycle}")

    # 4. Verifier ou est apply_convergence_sizing
    print("\n[4/6] Localiser apply_convergence_sizing dans le code")
    import os, re
    base = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
    found = []
    for root, dirs, files in os.walk(base):
        if "venv" in root or ".git" in root or "__pycache__" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(root, f)
                try:
                    with open(p, "rb") as fh:
                        data = fh.read()
                    if b"apply_convergence_sizing" in data:
                        # compter occurrences def vs call
                        try:
                            txt = data.decode("utf-8", errors="replace")
                        except Exception:
                            txt = ""
                        n_def = len(re.findall(r"def\s+apply_convergence_sizing", txt))
                        n_call = txt.count("apply_convergence_sizing") - n_def
                        found.append((p, n_def, n_call))
                except Exception:
                    pass
    for p, nd, nc in found[:10]:
        rel = p.replace(base + "\\", "")
        print(f"  {rel:60s} def={nd} call={nc}")

    # 5. orders schema (pour shadow_orders comparable)
    print("\n[5/6] orders schema (cols cles pour shadow_orders)")
    cur.execute("PRAGMA table_info(orders)")
    for r in cur.fetchall():
        nm = r['name']
        if nm in ("id","cycle_id","ticker","side","qty","status","filled","created_at","instrument_id","price","stop_loss","take_profit","notional","class"):
            print(f"  {nm:20s} {r['type']}")

    # 6. Cycles disponibles sur fenetre 90j (pour future Phase 9.7)
    print("\n[6/6] Cycles prod fenetre 90j (sample)")
    cur.execute("""
        SELECT DATE(SUBSTR(cycle_id,1,8),'unixepoch') as dummy, COUNT(*) as n_cycles
        FROM (SELECT DISTINCT cycle_id FROM portfolio_targets
              WHERE SUBSTR(cycle_id,1,8) >= '20260314')
    """)
    r = cur.fetchone()
    if r:
        print(f"  total cycles distinct depuis 20260314 : {r['n_cycles']}")
    cur.execute("""
        SELECT SUBSTR(cycle_id,1,8) as day, COUNT(DISTINCT cycle_id) as n
        FROM portfolio_targets
        WHERE SUBSTR(cycle_id,1,8) >= '20260314'
        GROUP BY day ORDER BY day DESC LIMIT 10
    """)
    print("  Derniers 10 jours :")
    for r in cur.fetchall():
        print(f"    {r['day']} : {r['n']} cycles")

    conn.close()
    print("\n" + "="*78)
    print("DIAG DONE")
    print("="*78)

if __name__ == "__main__":
    main()



===== nextones-diag-shadow-engine-prereq-v2.py =====

"""
Diag prereq Phase 9.2 v2 - shadow_engine MVP
Fix : portfolio_targets utilise snapshot_id (pas cycle_id)
"""
import sqlite3, os, re

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def main():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("="*78)
    print("DIAG PREREQ PHASE 9.2 v2 - shadow_engine MVP")
    print("="*78)

    # 1. portfolio_targets : derniers snapshots
    print("\n[1/7] portfolio_targets - derniers snapshots")
    cur.execute("""
        SELECT snapshot_id, COUNT(*) as n, MAX(updated_at) as last_dt,
               SUM(active) as n_active
        FROM portfolio_targets
        GROUP BY snapshot_id
        ORDER BY last_dt DESC LIMIT 5
    """)
    snaps = cur.fetchall()
    last_snap = None
    for s in snaps:
        print(f"  snapshot={s['snapshot_id']:30s} n={s['n']:3d} active={s['n_active']:3d} dt={s['last_dt']}")
        if last_snap is None:
            last_snap = s['snapshot_id']

    # 2. Sample dernier snapshot
    print(f"\n[2/7] Sample portfolio_targets snapshot={last_snap}")
    if last_snap:
        cur.execute("SELECT * FROM portfolio_targets WHERE snapshot_id=? ORDER BY score DESC LIMIT 10", (last_snap,))
        for r in cur.fetchall():
            d = dict(r)
            print(f"  {d['ticker']:8s} w={d['target_weight_pct']:.4f} score={d['score']} active={d['active']} src={d['source']} agent={d['agent_decided']}")

    # 3. Mapping snapshot_id -> cycle_id : ou est stocke le lien ?
    print("\n[3/7] Tables qui referencent snapshot_id")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r['name'] for r in cur.fetchall()]
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [r['name'] for r in cur.fetchall()]
        if 'snapshot_id' in cols:
            cur.execute(f"SELECT COUNT(*) as n FROM {t}")
            n = cur.fetchone()['n']
            print(f"  {t:35s} cols={cols[:8]}... rows={n}")

    # 4. construction_snapshots ?
    print("\n[4/7] construction_snapshots schema (si existe)")
    if 'construction_snapshots' in tables:
        cur.execute("PRAGMA table_info(construction_snapshots)")
        for r in cur.fetchall():
            print(f"  {r['name']:25s} {r['type']}")
        cur.execute("SELECT * FROM construction_snapshots ORDER BY created_at DESC LIMIT 3")
        for r in cur.fetchall():
            d = dict(r)
            print(f"  sample : {dict((k, str(v)[:40]) for k,v in d.items())}")

    # 5. orders sample dernier cycle (cols dispo)
    print("\n[5/7] orders schema + dernier sample")
    cur.execute("PRAGMA table_info(orders)")
    cols = [(r['name'], r['type']) for r in cur.fetchall()]
    for nm, tp in cols:
        print(f"  {nm:25s} {tp}")
    cur.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 3")
    for r in cur.fetchall():
        d = dict(r)
        kept = {k: str(v)[:30] for k, v in d.items() if k in ('id','cycle_id','ticker','side','qty','status','price','notional','class','filled')}
        print(f"  sample : {kept}")

    # 6. convergence_snapshots dernier cycle prod
    print("\n[6/7] convergence_snapshots - derniers cycles")
    cur.execute("""
        SELECT cycle_id, COUNT(*) as n, SUM(forced_exit) as fe
        FROM convergence_snapshots
        GROUP BY cycle_id ORDER BY cycle_id DESC LIMIT 5
    """)
    last_cycle = None
    for r in cur.fetchall():
        print(f"  cycle={r['cycle_id']:25s} n={r['n']:3d} fe={r['fe']}")
        if last_cycle is None:
            last_cycle = r['cycle_id']
    if last_cycle:
        print(f"\n  Sample du cycle {last_cycle}:")
        cur.execute("""SELECT ticker, convergence_pct, sizing_multiplier, forced_exit, is_crypto, direction_consensus
                       FROM convergence_snapshots WHERE cycle_id=? LIMIT 10""", (last_cycle,))
        for r in cur.fetchall():
            print(f"    {r['ticker']:8s} conv={r['convergence_pct']:.2f} mult={r['sizing_multiplier']:.2f} fe={r['forced_exit']} crypto={r['is_crypto']} dir={r['direction_consensus']}")

    # 7. Localiser apply_convergence_sizing
    print("\n[7/7] Localiser apply_convergence_sizing")
    base = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
    found = []
    for root, dirs, files in os.walk(base):
        if "venv" in root or ".git" in root or "__pycache__" in root or "backup" in root.lower():
            continue
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(root, f)
                try:
                    with open(p, "rb") as fh:
                        data = fh.read()
                    if b"apply_convergence_sizing" in data:
                        try: txt = data.decode("utf-8", errors="replace")
                        except: txt = ""
                        n_def = len(re.findall(r"def\s+apply_convergence_sizing", txt))
                        n_call = txt.count("apply_convergence_sizing") - n_def
                        found.append((p, n_def, n_call, len(data)))
                except: pass
    for p, nd, nc, sz in found[:15]:
        rel = p.replace(base + "\\", "")
        print(f"  {rel:60s} def={nd} call={nc} sz={sz}")

    conn.close()
    print("\n" + "="*78)
    print("DIAG v2 DONE")
    print("="*78)

if __name__ == "__main__":
    main()



===== nextones-diag-shadow-engine-prereq-v3.py =====

"""
Diag prereq Phase 9.2 v3 - finaliser specs shadow_engine MVP
"""
import sqlite3, os, re

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def main():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("="*78)
    print("DIAG v3 - finalize shadow_engine specs")
    print("="*78)

    # 1. portfolio_targets_history schema COMPLET
    print("\n[1/5] portfolio_targets_history schema complet")
    cur.execute("PRAGMA table_info(portfolio_targets_history)")
    for r in cur.fetchall():
        print(f"  {r['name']:30s} {r['type']}")

    # 2. portfolio_targets_history derniers cycles (fenetre 90j)
    print("\n[2/5] portfolio_targets_history - cycles fenetre 90j")
    cur.execute("""
        SELECT cycle_id, COUNT(*) as n, MIN(score) as min_s, MAX(score) as max_s
        FROM portfolio_targets_history
        WHERE SUBSTR(cycle_id,1,8) >= '20260314'
        GROUP BY cycle_id ORDER BY cycle_id DESC LIMIT 10
    """)
    rows = cur.fetchall()
    print(f"  Derniers 10 cycles (sur 90j) :")
    for r in rows:
        print(f"    {r['cycle_id']:25s} n={r['n']:3d} score=[{r['min_s']:.3f}, {r['max_s']:.3f}]")

    # Sample d un cycle complet
    if rows:
        c = rows[0]['cycle_id']
        print(f"\n  Sample cycle {c} (top 5 score) :")
        cur.execute("""SELECT ticker, score, target_weight_pct, prev_target_weight_pct
                       FROM portfolio_targets_history WHERE cycle_id=?
                       ORDER BY score DESC LIMIT 5""", (c,))
        for r in cur.fetchall():
            print(f"    {r['ticker']:8s} score={r['score']:.3f} w={r['target_weight_pct']:.4f} prev_w={r['prev_target_weight_pct']}")

    # 3. Compter total cycles disponibles fenetre 90j
    print("\n[3/5] Cycles distincts fenetre 90j (portfolio_targets_history)")
    cur.execute("""
        SELECT COUNT(DISTINCT cycle_id) as n
        FROM portfolio_targets_history WHERE SUBSTR(cycle_id,1,8) >= '20260314'
    """)
    print(f"  Total cycles : {cur.fetchone()['n']}")

    cur.execute("""
        SELECT SUBSTR(cycle_id,1,8) as day, COUNT(DISTINCT cycle_id) as n
        FROM portfolio_targets_history WHERE SUBSTR(cycle_id,1,8) >= '20260601'
        GROUP BY day ORDER BY day DESC
    """)
    print(f"  Par jour (depuis 20260601) :")
    for r in cur.fetchall():
        print(f"    {r['day']} : {r['n']} cycles")

    # 4. Lire la def apply_convergence_sizing dans portfolio_construction_agent.py
    print("\n[4/5] Source apply_convergence_sizing dans portfolio_construction_agent.py")
    pca_path = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py"
    if os.path.exists(pca_path):
        with open(pca_path, "rb") as f:
            data = f.read().decode("utf-8", errors="replace")
        # trouver def
        m = re.search(r"def\s+apply_convergence_sizing\s*\([^)]*\)[^:]*:", data)
        if m:
            start = m.start()
            # extraire ~80 lignes a partir de la def
            lines = data[start:].split("\n")[:90]
            for i, ln in enumerate(lines):
                print(f"  {i:3d}| {ln[:130]}")
        else:
            print("  def apply_convergence_sizing NOT FOUND in portfolio_construction_agent.py")
            # cherche dans tout l arbre
            base = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
            for root, dirs, files in os.walk(base):
                if "venv" in root or "__pycache__" in root or "backup" in root.lower():
                    continue
                for fn in files:
                    if fn.endswith(".py") and not fn.startswith("nextones-diag"):
                        p = os.path.join(root, fn)
                        try:
                            with open(p,"rb") as fh: d = fh.read().decode("utf-8",errors="replace")
                            if re.search(r"def\s+apply_convergence_sizing", d):
                                rel = p.replace(base+"\\","")
                                print(f"  FOUND def in : {rel}")
                        except: pass
    else:
        print(f"  {pca_path} introuvable")

    # 5. orders cols actuelles vs shadow_orders (a verifier alignement)
    print("\n[5/5] shadow_orders schema actuel (Phase 9.1)")
    cur.execute("PRAGMA table_info(shadow_orders)")
    for r in cur.fetchall():
        print(f"  {r['name']:30s} {r['type']}")

    conn.close()
    print("\n" + "="*78)
    print("DIAG v3 DONE")
    print("="*78)

if __name__ == "__main__":
    main()



===== nextones-diag-shadow-engine-version-v1.py =====

"""Verifier la version reelle de shadow_engine.py sur disque."""
import os, hashlib, re

path = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\shadow_engine.py"
print(f"path = {path}")
print(f"exists = {os.path.exists(path)}")
print(f"size = {os.path.getsize(path)}")
print(f"mtime = {os.path.getmtime(path)}")

with open(path, "rb") as f:
    data = f.read()
print(f"sha256 = {hashlib.sha256(data).hexdigest()[:16]}")

text = data.decode("utf-8", errors="replace")

# Chercher la condition forced_exit
print("\n[Lignes contenant 'fe == 1' ou 'forced exit']")
for i, ln in enumerate(text.split("\n"), 1):
    if "fe == 1" in ln or "Forced exit" in ln or "EPSILON" in ln or "s_fe" in ln:
        print(f"  L{i:3d}: {ln.rstrip()}")

# Pycache
pycache = os.path.join(os.path.dirname(path), "__pycache__")
print(f"\n[__pycache__]")
if os.path.exists(pycache):
    for f in os.listdir(pycache):
        if "shadow" in f:
            p = os.path.join(pycache, f)
            print(f"  {f} mtime={os.path.getmtime(p)} size={os.path.getsize(p)}")
else:
    print("  pas de __pycache__")



===== nextones-diag-shadow-fills-rejected-v1.py =====

"""Diag : simule fills en memoire pour cycle 20260611-144234 et liste rejected detaille.

Ne touche pas la DB. Reproduit la logique shadow_simulate_fills mais affiche
chaque rejected avec ticker + side + rejection_reason.
"""
import os, sys, sqlite3
os.environ["NEXTONES_REPLAY_MODE"] = "1"

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
CYCLE = "20260611-144234"
NAV_PLACEHOLDER = 1_000_000.0

sys.path.insert(0, r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
from replay_adapters import MarketDataAdapter
from fill_simulator import simulate_fill

conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Recuperer day_t depuis snapshot
cur.execute("SELECT day_t FROM shadow_cycle_snapshots WHERE cycle_id=? LIMIT 1", (CYCLE,))
row = cur.fetchone()
if not row:
    print("Pas de snapshot pour ce cycle"); sys.exit(1)
day_decision = row["day_t"]
print(f"day_decision = {day_decision}")

# Charger orders
cur.execute("""
    SELECT o.id, o.variant_id, v.name as variant, o.ticker, o.side, o.qty,
           o.target_weight_pct, o.decision
    FROM shadow_orders o
    JOIN shadow_variants v ON v.variant_id = o.variant_id
    WHERE o.cycle_id = ?
    ORDER BY o.variant_id, o.ticker
""", (CYCLE,))
orders = cur.fetchall()
print(f"\n{len(orders)} shadow_orders chargees")

adapter = MarketDataAdapter(DB)

# Simuler chaque order, capturer rejected
rejected = []
filled = 0
skipped = 0

for o in orders:
    ticker = o["ticker"]
    side = o["side"]
    target_w = o["target_weight_pct"] or 0.0
    decision = o["decision"]

    # close pour calcul qty proxy
    close_raw = adapter.get_close_at(day_decision, ticker)
    if close_raw is None:
        rejected.append((o["variant"], ticker, side, decision, "no_close_decision_day"))
        continue
    # get_close_at peut retourner float OU dict selon adapter
    if isinstance(close_raw, dict):
        close_dec = close_raw.get("close")
    else:
        close_dec = float(close_raw)
    if not close_dec or close_dec <= 0:
        rejected.append((o["variant"], ticker, side, decision, "close_zero"))
        continue

    # Calcul qty proxy
    if side == "BUY":
        if target_w > 0:
            qty = NAV_PLACEHOLDER * (target_w / 100.0) / close_dec
        else:
            skipped += 1
            continue
    else:  # SELL
        if target_w == 0:  # exit
            qty = NAV_PLACEHOLDER * 0.05 / close_dec
        else:
            qty = NAV_PLACEHOLDER * 0.05 / close_dec  # proxy scale_down

    if qty <= 0:
        rejected.append((o["variant"], ticker, side, decision, "qty_zero"))
        continue

    # Simuler fill
    try:
        result = simulate_fill(adapter, ticker, side=side, qty=qty, day_decision=day_decision)
        if result.status == "filled":
            filled += 1
        else:
            rejected.append((o["variant"], ticker, side, decision,
                           getattr(result, "rejection_reason", "unknown")))
    except Exception as e:
        rejected.append((o["variant"], ticker, side, decision, f"exception:{e}"))

print(f"\nfilled={filled} rejected={len(rejected)} skipped={skipped}")
print(f"\n=== REJECTED DETAIL ===")
for variant, ticker, side, decision, reason in rejected:
    print(f"  {variant:20s} {ticker:8s} {side:5s} decision={decision:12s} reason={reason}")

conn.close()



===== nextones-diag-shadow-hook-location-v1.py =====

"""Diag : trouver OU le cycle prod se termine pour brancher shadow_hook."""
import os, re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# Lister les .py qui contiennent run_decision_cycle / execute_cycle
patterns = [r"run_decision_cycle", r"execute_cycle", r"def\s+run_cycle"]

print("=== FICHIERS contenant declencheurs cycle ===")
for fname in sorted(os.listdir(ROOT)):
    if not fname.endswith(".py"):
        continue
    fpath = os.path.join(ROOT, fname)
    if os.path.isdir(fpath):
        continue
    try:
        with open(fpath, "rb") as f:
            data = f.read().decode("utf-8-sig", errors="replace")
    except Exception:
        continue
    matches = []
    for pat in patterns:
        for m in re.finditer(pat, data):
            line_no = data[:m.start()].count("\n") + 1
            matches.append((line_no, pat))
    if matches:
        print(f"\n--- {fname} ({len(matches)} matches) ---")
        for ln, pat in matches[:5]:
            line = data.split("\n")[ln-1].strip()[:120]
            print(f"  L{ln}: [{pat}] {line}")

# Chercher specifiquement la def execute_cycle / run_decision_cycle
print("\n\n=== DEFINITIONS execute_cycle / run_decision_cycle ===")
for fname in sorted(os.listdir(ROOT)):
    if not fname.endswith(".py"):
        continue
    fpath = os.path.join(ROOT, fname)
    if os.path.isdir(fpath):
        continue
    try:
        with open(fpath, "rb") as f:
            data = f.read().decode("utf-8-sig", errors="replace")
    except Exception:
        continue
    for m in re.finditer(r"^(async\s+def|def)\s+(execute_cycle|run_decision_cycle)\b", data, re.M):
        line_no = data[:m.start()].count("\n") + 1
        line = data.split("\n")[line_no-1].strip()[:120]
        print(f"  {fname}:L{line_no}: {line}")

# Chercher returns dans execute_cycle (= point d'insertion hook)
print("\n\n=== RETURNS dans execute_cycle (point d'integration hook) ===")
target_file = os.path.join(ROOT, "scheduler.py")
if not os.path.exists(target_file):
    # Chercher tout fichier contenant def execute_cycle
    for fname in sorted(os.listdir(ROOT)):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(ROOT, fname)
        try:
            with open(fpath, "rb") as f:
                data = f.read().decode("utf-8-sig", errors="replace")
        except Exception:
            continue
        if re.search(r"^(async\s+def|def)\s+execute_cycle\b", data, re.M):
            target_file = fpath
            print(f"  -> target_file = {fname}")
            break

print(f"\n  scanning {os.path.basename(target_file)}...")
if os.path.exists(target_file):
    with open(target_file, "rb") as f:
        data = f.read().decode("utf-8-sig", errors="replace")
    lines = data.split("\n")
    in_func = False
    indent = 0
    for i, ln in enumerate(lines, 1):
        if re.match(r"^(async\s+def|def)\s+execute_cycle\b", ln):
            in_func = True
            indent = len(ln) - len(ln.lstrip())
            print(f"  L{i}: [DEF] {ln.strip()[:120]}")
            continue
        if in_func:
            cur_indent = len(ln) - len(ln.lstrip()) if ln.strip() else None
            if cur_indent is not None and cur_indent <= indent and ln.strip():
                in_func = False
                continue
            if "return" in ln and re.search(r"\breturn\b", ln):
                print(f"  L{i}: [RET] {ln.strip()[:120]}")
            if re.search(r"cycle_id\s*=", ln):
                print(f"  L{i}: [CID] {ln.strip()[:120]}")



===== nextones-diag-shadow-imports.py =====

# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-SHADOW-IMPORTS-V1]
# Verifie que les modules Phase 2/2.5 sont importables avant de wirer Phase 3A.
# Usage : py -3.13 nextones-diag-shadow-imports.py

import os
import sys
import traceback

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
sys.path.insert(0, PROD_DIR)


def check(modname, expected_attrs):
    print("-" * 60)
    print(f"Module: {modname}")
    try:
        m = __import__(modname)
    except Exception as e:
        print(f"  [ERR] import: {e}")
        traceback.print_exc(limit=3)
        return False
    print(f"  [OK] import (file={getattr(m, '__file__', '?')})")
    for a in expected_attrs:
        if hasattr(m, a):
            obj = getattr(m, a)
            print(f"  [OK] {a} -> {type(obj).__name__}")
        else:
            print(f"  [ERR] attribut manquant : {a}")
            return False
    return True


def show_signature(modname, funcname):
    try:
        import inspect
        m = __import__(modname)
        f = getattr(m, funcname, None)
        if f is None:
            print(f"  {modname}.{funcname} : ABSENT")
            return
        sig = inspect.signature(f)
        print(f"  {modname}.{funcname}{sig}")
    except Exception as e:
        print(f"  {modname}.{funcname} : ERR {e}")


def main():
    print(f"sys.path[0] = {sys.path[0]}")
    print()
    print("=" * 60)
    print("CHECK MODULES PHASE 2 / 2.5 / 3")
    print("=" * 60)

    ok1 = check("broker_shadow_executor", ["execute_shadow", "snapshot_pnl"])
    ok2 = check("risk_broker_check", ["check_broker_mapping"])
    ok3 = check("bridge_config", [
        "BROKER_SHADOW_ENABLED",
        "BROKER_LIVE_ENABLED",
        "MAX_LIVE_NAV",
        "BROKER_LIVE_ACCOUNT",
    ])
    ok4 = check("broker_resolver", ["resolve"])
    ok5 = check("order_translator", ["translate"])
    ok6 = check("risk_pretrade", ["run_pretrade_checks"])

    print()
    print("=" * 60)
    print("SIGNATURES DETAILLEES")
    print("=" * 60)
    show_signature("broker_shadow_executor", "execute_shadow")
    show_signature("broker_shadow_executor", "snapshot_pnl")
    show_signature("risk_broker_check", "check_broker_mapping")
    show_signature("broker_resolver", "resolve")
    show_signature("order_translator", "translate")

    print()
    print("=" * 60)
    print("VALEURS bridge_config")
    print("=" * 60)
    try:
        import bridge_config as bc
        for k in ("BROKER_SHADOW_ENABLED", "BROKER_LIVE_ENABLED",
                  "MAX_LIVE_NAV", "BROKER_LIVE_ACCOUNT"):
            print(f"  {k} = {getattr(bc, k, '<MISSING>')!r}")
    except Exception as e:
        print(f"  [ERR] {e}")

    print()
    print("=" * 60)
    verdict = all([ok1, ok2, ok3, ok4, ok5, ok6])
    print(f"VERDICT : {'PASS' if verdict else 'FAIL'} - "
          f"{'pret pour wiring Phase 3A' if verdict else 'corriger les imports avant patch'}")
    print("=" * 60)
    sys.exit(0 if verdict else 1)


if __name__ == "__main__":
    main()



===== nextones-diag-shadow-insertion-point.py =====

# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-SHADOW-INSERTION-POINT-V1]
# Diag complementaire : prepare le wiring Phase 3A.
#
# Sortie attendue :
#   1. Imports en tete de execution_engine.py (pour savoir ou ajouter
#      `from broker_shadow_executor import execute_shadow`)
#   2. Le bloc COMPLET de create_and_execute_order (L1172 a fin de fonction)
#      avec numeros de ligne -> point d'insertion exact entre pretrade V2
#      accept et INSERT orders
#   3. Recherche PineConnector / MT5Bridge / send_setup / webhook sur TOUS
#      les .py du dossier prod -> identifier ou l'envoi broker se fait
#   4. Verification que broker_shadow_executor.py et risk_pretrade.py sont
#      importables, et que execute_shadow + check_broker_mapping existent
#
# Usage : py -3.13 nextones-diag-shadow-insertion-point.py

import os
import re
import subprocess
import sys

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(PROD_DIR, "execution_engine.py")


def banner(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def section_imports():
    banner("[1] IMPORTS en tete de execution_engine.py (60 premieres lignes)")
    with open(TARGET, "r", encoding="utf-8-sig") as f:
        for i, line in enumerate(f, 1):
            if i > 60:
                break
            if line.strip().startswith(("import ", "from ")) or i <= 30:
                print(f"  L{i:4d} : {line.rstrip()}")


def find_function_block(src_lines, start_line):
    """
    A partir de la ligne start_line (1-based, def ...), retourne (start, end)
    en se basant sur la premiere ligne ayant l'indent <= def_indent qui suit
    une ligne non vide a l'interieur de la fonction.
    """
    idx = start_line - 1
    def_line = src_lines[idx]
    def_indent = len(def_line) - len(def_line.lstrip())
    end = len(src_lines)
    for j in range(idx + 1, len(src_lines)):
        line = src_lines[j]
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= def_indent and not stripped.startswith("#"):
            end = j
            break
    return idx + 1, end


def section_function_block():
    banner("[2] FONCTION create_and_execute_order (L1172 -> fin)")
    with open(TARGET, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    # Trouver def create_and_execute_order
    target_re = re.compile(r"^def\s+create_and_execute_order\s*\(")
    start = None
    for i, line in enumerate(lines, 1):
        if target_re.match(line):
            start = i
            break
    if start is None:
        print("  [ERR] def create_and_execute_order introuvable")
        return
    s, e = find_function_block(lines, start)
    print(f"  Bornes : L{s} -> L{e} ({e - s + 1} lignes)")
    print("-" * 72)
    for i in range(s, e + 1):
        if i - 1 >= len(lines):
            break
        marker = ""
        ln = lines[i - 1].rstrip("\n")
        if "run_pretrade_checks" in ln or "_rv2_run" in ln:
            marker = "  <-- PRETRADE V2"
        if "INSERT INTO orders" in ln:
            marker = "  <-- INSERT orders"
        if "risk_result" in ln and "blocked" in ln:
            marker = "  <-- RISK GATE"
        print(f"  L{i:4d} : {ln}{marker}")


def section_broker_send_search():
    banner("[3] Recherche envoi broker (PineConnector/MT5/webhook/send_setup)")
    patterns = [
        r"PineConnector",
        r"MT5Bridge",
        r"send_setup",
        r"pineconnector",
        r"webhook\.pineconnector",
        r"to_mt5_commands",
        r"send_raw",
        r"metaapi",
        r"MetaApi",
    ]
    py_files = []
    for name in os.listdir(PROD_DIR):
        if name.endswith(".py") and not name.endswith(".pyc"):
            py_files.append(os.path.join(PROD_DIR, name))
    print(f"  Fichiers scannes : {len(py_files)}")
    hits_by_file = {}
    for path in py_files:
        try:
            with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    for pat in patterns:
                        if re.search(pat, line):
                            hits_by_file.setdefault(path, []).append(
                                (i, pat, line.rstrip())
                            )
                            break
        except Exception as e:
            print(f"  [WARN] lecture {path} : {e}")
    if not hits_by_file:
        print("  (aucun match dans le dossier prod)")
        return
    for path, hits in sorted(hits_by_file.items()):
        rel = os.path.basename(path)
        print(f"\n  -- {rel} ({len(hits)} match)")
        # max 10 lignes par fichier pour eviter le bruit
        for i, (ln, pat, content) in enumerate(hits[:10]):
            print(f"     L{ln:4d} [{pat}] : {content[:140]}")
        if len(hits) > 10:
            print(f"     ... +{len(hits) - 10} autres")


def section_modules_check():
    banner("[4] Verifie que broker_shadow_executor.execute_shadow est dispo")
    code = (
        "import sys, importlib;"
        f"sys.path.insert(0, r'{PROD_DIR}');"
        "ok=True;"
        "try:\n"
        "    m1 = importlib.import_module('broker_shadow_executor');\n"
        "    print('broker_shadow_executor: OK, attrs=', "
        "[a for a in ['execute_shadow','snapshot_pnl'] if hasattr(m1,a)])\n"
        "except Exception as e:\n"
        "    ok=False; print('broker_shadow_executor: ERR', e)\n"
        "try:\n"
        "    m2 = importlib.import_module('risk_broker_check');\n"
        "    print('risk_broker_check: OK, attrs=', "
        "[a for a in ['check_broker_mapping','make_risk_decorator'] if hasattr(m2,a)])\n"
        "except Exception as e:\n"
        "    print('risk_broker_check: ERR', e)\n"
        "try:\n"
        "    m3 = importlib.import_module('bridge_config');\n"
        "    print('bridge_config: OK',"
        "{k: getattr(m3,k,'<MISSING>') for k in "
        "['BROKER_SHADOW_ENABLED','BROKER_LIVE_ENABLED','MAX_LIVE_NAV','BROKER_LIVE_ACCOUNT']})\n"
        "except Exception as e:\n"
        "    print('bridge_config: ERR', e)\n"
    )
    res = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=20,
    )
    print(res.stdout.rstrip())
    if res.stderr:
        print("--- STDERR ---")
        print(res.stderr.rstrip())


def main():
    if not os.path.exists(TARGET):
        print(f"[ERR] {TARGET} introuvable")
        sys.exit(2)
    section_imports()
    section_function_block()
    section_broker_send_search()
    section_modules_check()
    print()
    print("=" * 72)
    print("FIN diag insertion-point")
    print("=" * 72)


if __name__ == "__main__":
    main()



===== nextones-diag-shadow-perf-rolling-schema-v1.py =====

"""Diag : schemas shadow_perf_rolling + shadow_fills + samples.

Phase 9.5 : verifier ce dont on dispose pour calculer perf rolling.
"""
import sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

for table in ["shadow_perf_rolling", "shadow_fills", "shadow_cycle_snapshots", "shadow_orders"]:
    print(f"\n=== {table} columns ===")
    cur.execute(f"PRAGMA table_info({table})")
    for c in cur.fetchall():
        print(f"  {c[1]:30s} {c[2]:15s} nn={c[3]} pk={c[5]}")

print("\n=== shadow_fills sample (10 rows) ===")
cur.execute("SELECT * FROM shadow_fills ORDER BY cycle_id DESC, id LIMIT 10")
cols = [d[0] for d in cur.description]
print(" | ".join(cols))
for r in cur.fetchall():
    print(" | ".join(str(v)[:25] for v in r))

print("\n=== shadow_fills aggregate stats ===")
cur.execute("SELECT COUNT(*), COUNT(DISTINCT cycle_id), COUNT(DISTINCT variant_id), COUNT(DISTINCT ticker), MIN(fill_day), MAX(fill_day) FROM shadow_fills")
r = cur.fetchone()
print(f"  total_fills={r[0]} cycles={r[1]} variants={r[2]} tickers={r[3]} fill_day_min={r[4]} fill_day_max={r[5]}")

# Couverture prices pour fenetre J-30
print("\n=== Couverture prices (table prices ou ohlcv) ===")
for t in ["prices", "ohlcv", "instrument_prices", "etf_prices", "crypto_prices"]:
    try:
        cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT ticker), MIN(date), MAX(date) FROM {t}")
        r = cur.fetchone()
        print(f"  {t:20s} rows={r[0]} tickers={r[1]} min={r[2]} max={r[3]}")
    except Exception as e:
        print(f"  {t:20s} N/A ({e})")

conn.close()



===== nextones-diag-shadow-prod-exit-zero-v1.py =====

"""Pourquoi prod variant=1 a 0 exit alors que 7 fe=1 dans le cycle 20260612-121958 ?"""
import sqlite3, json
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
CYCLE = "20260612-121958"

conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Settings variant prod
print("[1] Settings variant prod")
cur.execute("SELECT settings_json FROM shadow_variants WHERE variant_id=1")
s = json.loads(cur.fetchone()['settings_json'])
for k,v in s.items(): print(f"  {k:20s} = {v}")

# 2. Tickers forced_exit du cycle
print(f"\n[2] Tickers forced_exit du cycle {CYCLE}")
cur.execute("""SELECT ticker, convergence_pct, forced_exit, is_crypto, direction_consensus, sizing_multiplier
               FROM convergence_snapshots WHERE cycle_id=? AND forced_exit=1""", (CYCLE,))
fe_tickers = cur.fetchall()
for r in fe_tickers:
    print(f"  {r['ticker']:8s} conv={r['convergence_pct']:.2f} fe={r['forced_exit']} crypto={r['is_crypto']} dir={r['direction_consensus']:6s} prod_mult={r['sizing_multiplier']:.2f}")

# 3. Pour chaque fe=1, verifier baseline portfolio_targets actuel
print(f"\n[3] Baseline portfolio_targets (dernier snapshot)")
cur.execute("SELECT snapshot_id FROM portfolio_targets ORDER BY updated_at DESC LIMIT 1")
snap = cur.fetchone()['snapshot_id']
print(f"  snapshot_id={snap}")
cur.execute("SELECT ticker, score, target_weight_pct FROM portfolio_targets WHERE snapshot_id=? AND active=1", (snap,))
baseline = {r['ticker']: dict(r) for r in cur.fetchall()}
print(f"  baseline tickers : {len(baseline)}")

print(f"\n[4] Pour chaque fe=1, simul logique variant prod (conv_thresh=0.6, fe_sc=0.33, score_cutoff=0.3)")
s_conv = 0.6
s_fe = 0.33
s_cutoff = 0.30
for r in fe_tickers:
    t = r['ticker']
    base = baseline.get(t, {'score': 0.0, 'target_weight_pct': 0.0})
    score = base['score']
    bw = base['target_weight_pct']
    conv = r['convergence_pct']
    fe = r['forced_exit']
    
    filtre_applique = (score < s_cutoff and bw == 0)
    fe_match = (fe == 1 and conv <= s_fe)
    
    note = ""
    if filtre_applique: note = "FILTER (score<0.30 AND bw==0)"
    elif fe_match: note = "EXIT"
    elif conv < s_conv: note = "scale_down (conv<0.6)"
    else: note = "keep ou scale"
    
    print(f"  {t:8s} score={score:.3f} bw={bw:.3f} conv={conv:.2f} -> filtre={filtre_applique} fe_match={fe_match} | {note}")

# 5. Verifier shadow_orders ecrits pour variant=1
print(f"\n[5] shadow_orders ecrits cycle {CYCLE} variant=1 (prod)")
cur.execute("""SELECT ticker, side, decision, convergence_pct, forced_exit, sizing_multiplier
               FROM shadow_orders WHERE cycle_id=? AND variant_id=1 ORDER BY decision, ticker""", (CYCLE,))
rows = cur.fetchall()
print(f"  total orders prod : {len(rows)}")
from collections import Counter
c = Counter(r['decision'] for r in rows)
print(f"  par decision : {dict(c)}")
print(f"\n  Orders fe=1 prod (devraient etre exit):")
for r in rows:
    if r['forced_exit'] == 1:
        print(f"    {r['ticker']:8s} side={r['side']:5s} decision={r['decision']:12s} conv={r['convergence_pct']:.2f} mult={r['sizing_multiplier']:.2f}")

conn.close()



===== nextones-diag-shadow-rows-keys-v1.py =====

# -*- coding: utf-8 -*-
"""
Dump le contenu complet d'une row de /api/shadow/perf-rolling
pour voir tous les noms de champs EXACTS retournes par l'API.
"""
import urllib.request
import urllib.error
import json

BASE = "http://127.0.0.1:8000"

def http(method, path, body=None, token=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")

# Login
_, body = http("POST", "/api/auth/login", {"username": "rguelin", "password": "Thesium2026!"})
token = json.loads(body).get("access_token")

# Perf rolling
code, body = http("GET", "/api/shadow/perf-rolling?window=30", token=token)
print("status:", code)
j = json.loads(body)
print("Top-level keys :", list(j.keys()))
print("Number of rows :", len(j.get("rows", [])))
print()
rows = j.get("rows", [])
if rows:
    print("=== Row[0] complet (prod) ===")
    print(json.dumps(rows[0], indent=2, ensure_ascii=False))
    print()
    print("=== Row[1] complet (tight_conv = champion attendu) ===")
    if len(rows) > 1:
        print(json.dumps(rows[1], indent=2, ensure_ascii=False))
print()

# Variants
code, body = http("GET", "/api/shadow/variants", token=token)
print("=== /api/shadow/variants Row[0] ===")
j2 = json.loads(body)
vs = j2.get("variants", [])
if vs:
    print(json.dumps(vs[0], indent=2, ensure_ascii=False))

print()
print("DONE")



===== nextones-diag-shadow-runtime-schemas-v1.py =====

"""Inventaire schemas reels des 5 tables runtime shadow_*."""
import sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
for t in ['shadow_cycle_snapshots','shadow_orders','shadow_fills','shadow_diff_log','shadow_perf_rolling']:
    print(f"\n[{t}]")
    cur.execute(f"PRAGMA table_info({t})")
    for r in cur.fetchall():
        print(f"  {r['name']:30s} {r['type']:12s} pk={r['pk']} notnull={r['notnull']} dflt={r['dflt_value']}")
conn.close()



===== nextones-diag-shadow-scripts-args-v1.py =====

"""Verifie que shadow_engine.py et shadow_simulate_fills.py acceptent --db."""
import subprocess, sys

for script in ["shadow_engine.py", "shadow_simulate_fills.py"]:
    print(f"\n=== {script} --help ===")
    try:
        r = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True, text=True, timeout=10
        )
        print(r.stdout)
        if r.stderr:
            print("STDERR:", r.stderr)
    except Exception as e:
        print(f"EXC: {e}")



===== nextones-diag-shadow-signature.py =====

# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-SHADOW-SIGNATURE-V1]
# Charge nextones-broker-shadow-executor.py par chemin de fichier
# (meme pattern que _nx_broker_check_load) et affiche les signatures
# exactes de execute_shadow et snapshot_pnl.
#
# Usage : py -3.13 nextones-diag-shadow-signature.py

import importlib.util
import inspect
import os
import sys

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGETS = [
    ("nextones-broker-shadow-executor.py", ["execute_shadow", "snapshot_pnl"]),
    ("nextones-risk-broker-check.py", ["check_broker_mapping"]),
    ("nextones-broker-resolver.py", ["resolve"]),
    ("nextones-order-translator.py", ["translate"]),
]


def load_by_path(filename, modname):
    p = os.path.join(PROD_DIR, filename)
    if not os.path.exists(p):
        return None, f"fichier absent: {p}"
    try:
        spec = importlib.util.spec_from_file_location(modname, p)
        if spec is None or spec.loader is None:
            return None, "spec invalide"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, None
    except Exception as e:
        return None, f"exec_module: {e}"


def show(filename, attrs):
    print("=" * 72)
    print(f"FICHIER: {filename}")
    print("-" * 72)
    modname = "_diag_" + filename.replace(".py", "").replace("-", "_")
    mod, err = load_by_path(filename, modname)
    if err:
        print(f"  [ERR] {err}")
        return
    print(f"  [OK] charge depuis {getattr(mod, '__file__', '?')}")
    for a in attrs:
        f = getattr(mod, a, None)
        if f is None:
            print(f"  [ERR] attribut absent : {a}")
            continue
        try:
            sig = inspect.signature(f)
            print(f"  {a}{sig}")
            doc = inspect.getdoc(f)
            if doc:
                head = doc.split("\n\n", 1)[0]
                print(f"    docstring (1er para) : {head[:300]}")
        except (ValueError, TypeError) as e:
            print(f"  {a} : signature inaccessible ({e})")
    # Liste aussi toutes les fonctions top-level pour reference
    print("  -- toutes les callables top-level :")
    for name in dir(mod):
        if name.startswith("_"):
            continue
        obj = getattr(mod, name)
        if callable(obj):
            try:
                sig = inspect.signature(obj)
                print(f"    {name}{sig}")
            except (ValueError, TypeError):
                print(f"    {name}(?)")
    print()


def main():
    print(f"PROD_DIR : {PROD_DIR}")
    print()
    for filename, attrs in TARGETS:
        show(filename, attrs)


if __name__ == "__main__":
    main()



===== nextones-diag-shadow-ui-markers-v1.py =====

"""
Diag: dump tous les markers SHADOW_UI dans app.js + contexte autour
des occurrences r.id / shadowRowsCache / recoBadge pour comprendre
la structure reelle.
"""
import os
import re

UI = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"

with open(UI, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

lines = src.splitlines()
print("[INFO] total lines:", len(lines))
print("[INFO] total bytes:", len(src))
print()

# 1) Toutes les lignes qui contiennent SHADOW_UI (case-insensitive)
print("=== Lignes contenant 'SHADOW_UI' (case-insensitive) ===")
for i, ln in enumerate(lines, 1):
    if re.search(r"SHADOW_UI", ln, re.IGNORECASE):
        # tronque a 200 chars
        s = ln if len(ln) <= 200 else ln[:200] + "...[TRUNC]"
        print(f"L{i}: {s}")
print()

# 2) Toutes les lignes contenant shadowRowsCache
print("=== Lignes contenant 'shadowRowsCache' ===")
for i, ln in enumerate(lines, 1):
    if "shadowRowsCache" in ln:
        s = ln if len(ln) <= 200 else ln[:200] + "...[TRUNC]"
        print(f"L{i}: {s}")
print()

# 3) Toutes les lignes contenant recoBadge
print("=== Lignes contenant 'recoBadge' ===")
for i, ln in enumerate(lines, 1):
    if "recoBadge" in ln:
        s = ln if len(ln) <= 200 else ln[:200] + "...[TRUNC]"
        print(f"L{i}: {s}")
print()

# 4) Toutes occurrences de r.id (en JS, donc avec un point devant id)
print("=== Lignes contenant 'r.id' (regex \\br\\.id\\b) ===")
for i, ln in enumerate(lines, 1):
    if re.search(r"\br\.id\b", ln):
        s = ln if len(ln) <= 200 else ln[:200] + "...[TRUNC]"
        print(f"L{i}: {s}")
print()

# 5) Comptes globaux
print("=== Counts globaux ===")
print("shadowRowsCache[r.id]:", src.count("shadowRowsCache[r.id]"))
print("shadowRowsCache[r.variant_id]:", src.count("shadowRowsCache[r.variant_id]"))
print("r.id count (regex):", len(re.findall(r"\br\.id\b", src)))
print("r.variant_id count:", src.count("r.variant_id"))



===== nextones-diag-shadow-variants-ddl-v1.py =====

# -*- coding: utf-8 -*-
"""
DIAG : shadow_variants DDL complet + toutes les rows
(pour corriger la colonne 'id' qui n'existe pas)
"""
import sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 78)
print("shadow_variants : DDL")
print("=" * 78)
row = cur.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='shadow_variants'"
).fetchone()
print(row["sql"] if row else "[ERR] not found")

print()
print("PRAGMA table_info :")
for r in cur.execute("PRAGMA table_info(shadow_variants)").fetchall():
    print("  cid={} name={} type={} notnull={} pk={}".format(
        r["cid"], r["name"], r["type"], r["notnull"], r["pk"]
    ))

print()
print("ALL ROWS :")
for r in cur.execute("SELECT * FROM shadow_variants").fetchall():
    print("  ", dict(r))

print()
print("=" * 78)
print("Cross-check : variant_id utilises dans shadow_fills")
print("=" * 78)
for r in cur.execute(
    "SELECT variant_id, COUNT(*) AS n_fills FROM shadow_fills "
    "GROUP BY variant_id ORDER BY variant_id"
).fetchall():
    print("  variant_id={} n_fills={}".format(r["variant_id"], r["n_fills"]))

conn.close()
print()
print("DONE")



===== nextones-diag-shadow-variants-json-v1.py =====

"""Affiche le settings_json COMPLET de chaque variant."""
import sqlite3, json
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT variant_id, name, settings_json FROM shadow_variants WHERE active=1")
for r in cur.fetchall():
    d = json.loads(r['settings_json'])
    print(f"\nvariant_id={r['variant_id']} name={r['name']}")
    for k, v in d.items():
        print(f"  {k:25s} = {v}")
conn.close()



===== nextones-diag-shadow-variants-load-v1.py =====

"""
Diag rapide : qu est-ce que load_variants renvoie vraiment ?
"""
import sqlite3, json

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row

cur = conn.cursor()
cur.execute("PRAGMA table_info(shadow_variants)")
print("[Schema shadow_variants]")
for r in cur.fetchall():
    print(f"  {r['name']:25s} {r['type']}")

print("\n[Sample rows]")
cur.execute("SELECT * FROM shadow_variants WHERE active=1")
rows = cur.fetchall()
print(f"  n_active = {len(rows)}")
for r in rows:
    d = dict(r)
    print(f"\n  keys = {list(d.keys())}")
    for k, v in d.items():
        sv = str(v)[:60]
        print(f"    {k:20s} = {sv}")

conn.close()



===== nextones-diag-shadow-variants-schema-v1.py =====

"""Diag : schema reel shadow_variants."""
import sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()
print("=== shadow_variants columns ===")
cur.execute("PRAGMA table_info(shadow_variants)")
for c in cur.fetchall():
    print(f"  {c[1]:25s} {c[2]:15s} nn={c[3]}")
print("\n=== sample rows ===")
cur.execute("SELECT * FROM shadow_variants")
cols = [d[0] for d in cur.description]
print(" | ".join(cols))
for r in cur.fetchall():
    print(" | ".join(str(v)[:30] for v in r))
conn.close()



===== nextones-diag-shadow-variants-settings-v1.py =====

"""
Diag: dump complet des 4 variantes shadow + leurs settings JSON.
Affiche variant_id, name, description, settings (parse JSON) en clair.
"""
import os
import sqlite3
import json

DB = os.environ.get("THESIUM_DB", r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")

conn = sqlite3.connect(DB, timeout=10.0)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 80)
print("TABLE shadow_variants - schema")
print("=" * 80)
cur.execute("PRAGMA table_info(shadow_variants)")
for r in cur.fetchall():
    print(f"  {r['cid']:2d} {r['name']:20s} {r['type']:15s} pk={r['pk']}")

print()
print("=" * 80)
print("CONTENU des 4 variantes")
print("=" * 80)
cur.execute("SELECT * FROM shadow_variants ORDER BY variant_id")
for r in cur.fetchall():
    d = dict(r)
    print()
    print(f"--- variant_id={d.get('variant_id')} name={d.get('name')} ---")
    for k, v in d.items():
        if k == "settings" and v:
            print(f"  {k}:")
            try:
                parsed = json.loads(v)
                print(json.dumps(parsed, indent=4, ensure_ascii=False, sort_keys=True))
            except Exception as e:
                print(f"  [parse error: {e}]")
                print(f"  raw: {v}")
        else:
            print(f"  {k}: {v}")

conn.close()



===== nextones-diag-shadow-vs-risk.py =====

# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-SHADOW-VS-RISK-V1]
# Diagnostic apres validator V3 :
#  - Pourquoi risk a refuse AAPL ?
#  - Le bloc shadow est-il avant ou apres le return success=False du risk ?
#  - Faut-il deplacer shadow ou bypass le risk pour le test ?

import os
import sys
import json
import sqlite3

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
sys.path.insert(0, PROD_DIR)
DB = os.path.join(PROD_DIR, "thesium.db")


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


# ------------------------- 1 -------------------------
banner("[1] Derniere ligne risk_pretrade_log")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cols = [r[1] for r in con.execute("PRAGMA table_info(risk_pretrade_log)").fetchall()]
print(f"  colonnes : {cols}")
for r in con.execute("SELECT * FROM risk_pretrade_log ORDER BY id DESC LIMIT 3"):
    d = dict(r)
    for k, v in list(d.items()):
        if v is not None and len(str(v)) > 500:
            d[k] = str(v)[:500] + "..."
    print()
    print("  --- row ---")
    for k, v in d.items():
        print(f"    {k} = {v}")


# ------------------------- 2 -------------------------
banner("[2] Ordre 177 cote orders (status, side, qty)")
o = con.execute("SELECT * FROM orders WHERE id=177").fetchone()
if o:
    d = dict(o)
    for k, v in d.items():
        sv = str(v)
        if len(sv) > 300:
            sv = sv[:300] + "..."
        print(f"  {k} = {sv}")
else:
    print("  pas d'ordre 177")


# ------------------------- 3 -------------------------
banner("[3] Localise le bloc [NEXTONES-SHADOW-EXEC-V1] dans execution_engine.py")
ee_path = os.path.join(PROD_DIR, "execution_engine.py")
with open(ee_path, "r", encoding="utf-8-sig") as f:
    src = f.read()

marker = "[NEXTONES-SHADOW-EXEC-V1]"
mpos = src.find(marker)
print(f"  marker char index : {mpos}")

# Quelle est la fonction qui contient le marker ?
# On cherche le 'def ' qui le precede le plus proche
def_idx = src.rfind("\ndef ", 0, mpos)
if def_idx >= 0:
    func_line = src[def_idx+1:src.find("\n", def_idx+1)]
    print(f"  fonction englobante : {func_line}")

# Y a-t-il un 'return' AVANT le marker dans la meme fonction ?
# (qui indiquerait que risk refuse en court-circuit avant le shadow)
slice_before = src[def_idx:mpos]
n_returns_before = slice_before.count("\n        return ") + slice_before.count("\n    return ")
print(f"  nombre de 'return' AVANT le marker dans la fonction : {n_returns_before}")

# Contexte autour du marker (-1000 / +500 chars)
banner("[4] Contexte autour du marker (-800 / +400 chars)")
start = max(0, mpos - 800)
end = min(len(src), mpos + 400)
ctx = src[start:end]
# Numerote chaque ligne
lines = ctx.split("\n")
# Trouver le numero de ligne du marker dans le fichier source
line_no_marker = src[:mpos].count("\n") + 1
print(f"  ligne marker dans le fichier : {line_no_marker}")
print()
print("--- DEBUT CONTEXTE ---")
print(ctx)
print("--- FIN CONTEXTE ---")


# ------------------------- 5 -------------------------
banner("[5] Snippet autour des returns success=False du risk dans create_and_execute_order")
# Trouver la fonction create_and_execute_order
fn_idx = src.find("def create_and_execute_order")
if fn_idx >= 0:
    # fin de la fonction = prochain def au meme niveau d'indentation
    fn_end = src.find("\ndef ", fn_idx + 5)
    if fn_end < 0:
        fn_end = len(src)
    fn_body = src[fn_idx:fn_end]
    print(f"  fonction longueur : {len(fn_body)} chars, def@char {fn_idx}, end@char {fn_end}")

    # Cherche occurrences de 'Risk check' et de 'reason' / return success
    for kw in ["Risk check", "risk_result", "approved", "return {", "success\": False", "approved_qty"]:
        idx = 0
        while True:
            j = fn_body.find(kw, idx)
            if j < 0:
                break
            ln = fn_body[:j].count("\n") + 1
            line_no_in_file = src[:fn_idx].count("\n") + ln
            print(f"  hit '{kw}' fnline={ln} fileline={line_no_in_file}")
            idx = j + 1


con.close()
print()
print("[DONE]")



===== nextones-fix-shadow-api-dbpath-v1.py =====

# -*- coding: utf-8 -*-
"""
FIX [SHADOW_API_V1_FIX_DBPATH] :
DB_PATH n'existe pas en module-level. On reproduit le pattern local
deja utilise a L3439-3440 :

    import sqlite3, os as _os
    DB = _os.environ.get("THESIUM_DB", r"C:\\...\\thesium.db")
    conn = sqlite3.connect(DB, timeout=10.0)

Strategie :
  1. Remplacer ligne 'conn = sqlite3.connect(DB_PATH, ...)' par
     'DB = ...\\n    conn = sqlite3.connect(DB, ...)'
  2. Idempotent : skip si '[SHADOW_API_V1_FIX_DBPATH]' present

Backup + ast + py_compile + marker check.
"""
import os
import sys
import time
import ast
import py_compile
import shutil

API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
MARKER = "[SHADOW_API_V1_FIX_DBPATH]"

OLD_LINE = 'conn = sqlite3.connect(DB_PATH, timeout=10.0)'
NEW_BLOCK = '''import os as _os_shadow  # {marker}
    DB = _os_shadow.environ.get("THESIUM_DB", r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\thesium.db")
    conn = sqlite3.connect(DB, timeout=10.0)'''.format(marker=MARKER)


def log(m):
    print(m, flush=True)


def main():
    if not os.path.exists(API):
        log("[ERR] api_server.py introuvable")
        sys.exit(1)

    with open(API, "rb") as f:
        raw = f.read()
    src = raw.decode("utf-8-sig")

    if MARKER in src:
        log("[SKIP] marker " + MARKER + " deja present.")
        sys.exit(0)

    # Verifier presence cible
    count_old = src.count(OLD_LINE)
    log("[INFO] occurrences de 'sqlite3.connect(DB_PATH, ...)': " + str(count_old))
    if count_old == 0:
        log("[ERR] cible introuvable. Patch deja applique ou code modifie.")
        sys.exit(2)
    if count_old != 2:
        log("[WARN] attendu 2 occurrences, trouve " + str(count_old))

    # Replace all
    new_src = src.replace(OLD_LINE, NEW_BLOCK)

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = API + ".bak." + ts
    shutil.copy2(API, bak)
    log("[OK] backup : " + bak)

    # Write tmp + validate
    tmp = API + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_src)

    try:
        with open(tmp, "rb") as f:
            d = f.read()
        non_ascii = sum(1 for b in d if b > 127)
        log("[CHECK] non-ASCII bytes : " + str(non_ascii))
        ast.parse(d.decode("utf-8"))
        log("[CHECK] ast.parse OK")
        py_compile.compile(tmp, doraise=True)
        log("[CHECK] py_compile OK")
    except Exception as e:
        log("[ERR] validation echouee : " + repr(e))
        os.remove(tmp)
        sys.exit(3)

    os.replace(tmp, API)
    log("[OK] api_server.py patche.")

    # Verifier marker present
    with open(API, "rb") as f:
        d2 = f.read()
    if MARKER.encode() in d2:
        n = d2.count(MARKER.encode())
        log("[OK] marker " + MARKER + " present " + str(n) + " fois.")
    else:
        log("[WARN] marker non trouve apres swap.")

    log("")
    log("FIX [SHADOW_API_V1_FIX_DBPATH] DONE")
    log("Backup     : " + bak)
    log("Action     : uvicorn auto-reload doit recharger automatiquement.")
    log("Si pas auto-reload, redemarrer uvicorn manuellement.")


if __name__ == "__main__":
    main()



===== nextones-fix-shadow-memo-sql-v1.py =====

# -*- coding: utf-8 -*-
"""
Fix bug SQL dans shadow_memo_generator.py :
  - shadow_variants n'a pas de col 'id', mais 'variant_id'.
  - JOIN doit etre v.variant_id = p.variant_id

Avant patch, dump PRAGMA shadow_variants pour confirmer.
"""
import os
import re
import shutil
import sqlite3
from datetime import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
SRC = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\shadow_memo_generator.py"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
MARK = "# [SHADOW_MEMO_SQL_FIX_V1]"

# 1. Confirm schema
print("=== PRAGMA table_info(shadow_variants) ===")
conn = sqlite3.connect(DB, timeout=10.0)
try:
    cur = conn.execute("PRAGMA table_info(shadow_variants)")
    cols = cur.fetchall()
    for c in cols:
        print("  ", c)
    col_names = [c[1] for c in cols]
    print("Cols :", col_names)
    pk_candidate = None
    for c in cols:
        if c[5] == 1:  # pk
            pk_candidate = c[1]
            break
    print("PK :", pk_candidate)
finally:
    conn.close()
print()

# 2. Patch source
with open(SRC, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

if MARK in src:
    print("[SKIP] marker fix deja present")
else:
    OLD = "LEFT JOIN shadow_variants v ON v.id = p.variant_id "
    NEW = "LEFT JOIN shadow_variants v ON v.variant_id = p.variant_id " + MARK + " "
    if OLD not in src:
        print("[ERR] bloc OLD introuvable")
        # Aide diagnostic
        for line in src.split("\n"):
            if "LEFT JOIN" in line or "shadow_variants v" in line:
                print("  found:", line.strip())
    else:
        bak = SRC + ".bak." + TS
        shutil.copy2(SRC, bak)
        print("[BAK]", bak)
        new = src.replace(OLD, NEW, 1)
        with open(SRC, "w", encoding="utf-8", newline="") as f:
            f.write(new)
        print("[OK] SQL patche, delta=", len(new) - len(src), "chars")

print()
print("Next : py -3.13 .\\shadow_memo_generator.py --force")
print("DONE")



===== nextones-fix-shadow-memo-sql-v2.py =====

# -*- coding: utf-8 -*-
"""
Fix bug v2 : le marker '# [SHADOW_MEMO_SQL_FIX_V1]' a ete injecte
DANS la chaine SQL, ce que SQLite refuse (# n'est pas un commentaire SQL).
Retire le marker de la chaine SQL et le laisse uniquement en commentaire Python.
"""
import os
import shutil
from datetime import datetime

SRC = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\shadow_memo_generator.py"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
MARK_V2 = "# [SHADOW_MEMO_SQL_FIX_V2]"

with open(SRC, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

if MARK_V2 in src:
    print("[SKIP] marker v2 deja present")
else:
    # Bloc actuel pollue
    OLD = '"LEFT JOIN shadow_variants v ON v.variant_id = p.variant_id # [SHADOW_MEMO_SQL_FIX_V1] "'
    NEW = '"LEFT JOIN shadow_variants v ON v.variant_id = p.variant_id "  ' + MARK_V2

    if OLD not in src:
        print("[ERR] bloc OLD introuvable - dump lignes LEFT JOIN :")
        for i, line in enumerate(src.split("\n"), 1):
            if "LEFT JOIN" in line:
                print("  L{} | {}".format(i, line.rstrip()))
    else:
        bak = SRC + ".bak." + TS
        shutil.copy2(SRC, bak)
        print("[BAK]", bak)
        new = src.replace(OLD, NEW, 1)
        with open(SRC, "w", encoding="utf-8", newline="") as f:
            f.write(new)
        print("[OK] SQL nettoye, delta=", len(new) - len(src), "chars")

# Validation post-patch
import ast, py_compile
try:
    with open(SRC, "rb") as f:
        d = f.read()
    ast.parse(d.decode("utf-8"))
    py_compile.compile(SRC, doraise=True)
    print("[OK] py validation")
except Exception as e:
    print("[ERR] py validation:", e)

print()
print("Next : py -3.13 .\\shadow_memo_generator.py --force")
print("DONE")



===== nextones-fix-shadow-ui-apifetch-v1.py =====

# -*- coding: utf-8 -*-
"""
Fix bug : apiFetch() retourne deja l'objet JSON parse, pas une Response.
Patch JS : remplace les 2 lignes "var perfResp = ..." + "var perf = await perfResp.json()"
par un seul appel direct "var perf = await apiFetch(...)".
Idempotent via marker [SHADOW_UI_V1_FIX_APIFETCH].
"""
import os
import shutil
from datetime import datetime

JS = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
MARK_FIX = "/* [SHADOW_UI_V1_FIX_APIFETCH] */"

OLD = (
    '      var perfResp = await apiFetch("/api/shadow/perf-rolling?window=30");\n'
    '      var perf = await perfResp.json();'
)
NEW = (
    '      ' + MARK_FIX + '\n'
    '      var perf = await apiFetch("/api/shadow/perf-rolling?window=30");'
)

with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

print("File size :", len(src))

if MARK_FIX in src:
    print("[SKIP] marker fix deja present")
elif OLD not in src:
    print("[ERR] bloc OLD introuvable - dump des lignes contenant perfResp :")
    for i, line in enumerate(src.split("\n"), 1):
        if "perfResp" in line:
            print("  L{} | {}".format(i, line.rstrip()))
else:
    bak = JS + ".bak." + TS
    shutil.copy2(JS, bak)
    print("[BAK]", bak)
    new = src.replace(OLD, NEW, 1)
    with open(JS, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("[OK] JS patche, delta={} chars".format(len(new) - len(src)))
    print("[INFO] count marker fix:", new.count(MARK_FIX))
    print("[INFO] count perfResp restant (doit etre 0):", new.count("perfResp"))

print()
print("Next : Ctrl+Shift+R sur navigateur, onglet Backtest, bouton Rafraichir")
print("DONE")



===== nextones-fix-shadow-ui-mapping-layout-v1.py =====

# -*- coding: utf-8 -*-
"""
Fix unifie Jalon 9.6 Patch 2 :
  1. HTML : deplace la card Shadow HORS du grid - retire l'ancienne insertion
     avant <h2>Backtest Portfolio</h2>, et re-insere tout en haut de
     <section id="tab-backtest"> (juste apres balise d'ouverture).
  2. JS : corrige le mapping des champs API :
       ret_pct       -> return_variant_pct
       sharpe        -> sharpe_variant
       max_dd_pct    -> max_dd_variant_pct
       n_orders      -> n_orders_variant
       reco          -> recommendation

Idempotent : markers
  [SHADOW_UI_V1_FIX_LAYOUT]  pour HTML
  [SHADOW_UI_V1_FIX_MAPPING] pour JS

Pas de heredoc, ASCII pur, validation stricte avant ecriture.
"""
import os
import re
import shutil
from datetime import datetime

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
HTML = os.path.join(ROOT, "index.html")
JS = os.path.join(ROOT, "app.js")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

MARK_OLD_BEGIN = "<!-- [SHADOW_UI_V1] BEGIN -->"
MARK_OLD_END = "<!-- [SHADOW_UI_V1] END -->"
MARK_LAYOUT_BEGIN = "<!-- [SHADOW_UI_V1_FIX_LAYOUT] BEGIN -->"
MARK_LAYOUT_END = "<!-- [SHADOW_UI_V1_FIX_LAYOUT] END -->"
MARK_MAP_FIX = "/* [SHADOW_UI_V1_FIX_MAPPING] */"

# -----------------------------------------------------------------------------
# Nouveau bloc HTML : en tete de <section id="tab-backtest"> + width:100%
# -----------------------------------------------------------------------------
HTML_BLOCK = (
    "        " + MARK_LAYOUT_BEGIN + "\n"
    '        <div id="shadow-variants-card" class="card" '
    'style="display:block;width:100%;clear:both;margin:0 0 16px 0;box-sizing:border-box;grid-column:1 / -1;">\n'
    '          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">\n'
    '            <h2 style="margin:0;">Shadow Variants - Perf J-30</h2>\n'
    '            <button id="shadow-refresh-btn" class="pplx-refresh-btn" type="button">Rafraichir</button>\n'
    '          </div>\n'
    '          <div id="shadow-variants-meta" style="font-size:12px;opacity:0.75;margin-bottom:8px;">Chargement...</div>\n'
    '          <div style="overflow-x:auto;">\n'
    '            <table id="shadow-variants-table" style="width:100%;border-collapse:collapse;font-size:13px;">\n'
    '              <thead>\n'
    '                <tr style="text-align:left;border-bottom:1px solid var(--border-color,#444);">\n'
    '                  <th style="padding:6px 8px;">Variant</th>\n'
    '                  <th style="padding:6px 8px;text-align:right;">Return</th>\n'
    '                  <th style="padding:6px 8px;text-align:right;">Delta</th>\n'
    '                  <th style="padding:6px 8px;text-align:right;">Sharpe</th>\n'
    '                  <th style="padding:6px 8px;text-align:right;">Max DD</th>\n'
    '                  <th style="padding:6px 8px;text-align:right;">N Orders</th>\n'
    '                  <th style="padding:6px 8px;text-align:center;">Reco</th>\n'
    '                </tr>\n'
    '              </thead>\n'
    '              <tbody id="shadow-variants-tbody">\n'
    '                <tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Chargement...</td></tr>\n'
    '              </tbody>\n'
    '            </table>\n'
    '          </div>\n'
    '        </div>\n'
    "        " + MARK_LAYOUT_END + "\n"
)

# -----------------------------------------------------------------------------
# Patch HTML
# -----------------------------------------------------------------------------
def patch_html():
    with open(HTML, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()

    if MARK_LAYOUT_BEGIN in src:
        print("[SKIP] HTML layout marker deja present")
        return False

    # 1. Retirer ancien bloc [SHADOW_UI_V1] BEGIN ... END
    pat = re.compile(
        r"\s*" + re.escape(MARK_OLD_BEGIN) + r".*?" + re.escape(MARK_OLD_END) + r"\s*",
        re.DOTALL
    )
    m = pat.search(src)
    if m:
        bak = HTML + ".bak." + TS
        shutil.copy2(HTML, bak)
        print("[BAK] HTML ->", bak)
        cleaned = pat.sub("\n      ", src, count=1)
        print("[OK] Ancien bloc retire ({} chars)".format(len(src) - len(cleaned)))
    else:
        cleaned = src
        bak = HTML + ".bak." + TS
        shutil.copy2(HTML, bak)
        print("[BAK] HTML ->", bak)
        print("[WARN] Ancien bloc [SHADOW_UI_V1] BEGIN/END introuvable - on insere quand meme")

    # 2. Inserer la nouvelle card juste APRES <section ... id="tab-backtest" ...>
    anchor_re = re.compile(r'(<section\b[^>]*\bid="tab-backtest"[^>]*>\s*\n)', re.IGNORECASE)
    m2 = anchor_re.search(cleaned)
    if not m2:
        print("[ERR] balise <section id=\"tab-backtest\"> introuvable - abort")
        return False
    new = cleaned[:m2.end()] + HTML_BLOCK + cleaned[m2.end():]

    with open(HTML, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("[OK] HTML patche, +{} chars".format(len(new) - len(src)))
    return True

# -----------------------------------------------------------------------------
# Patch JS : remplacer le forEach de mapping
# -----------------------------------------------------------------------------
def patch_js():
    with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()

    if MARK_MAP_FIX in src:
        print("[SKIP] JS mapping marker deja present")
        return False

    # Bloc OLD a remplacer : le forEach complet qui construit les cellules
    OLD = (
        "      rows.forEach(function(r){\n"
        "        html += '<tr style=\"border-bottom:1px solid var(--border-color,#333);\">';\n"
        "        html += '<td style=\"padding:6px 8px;font-weight:600;\">'+(r.variant_name || r.variant_id || \"?\")+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+fmtPct(r.ret_pct)+'</td>';\n"
        "        var deltaColor = r.delta_pct > 0 ? \"#22c55e\" : (r.delta_pct < 0 ? \"#ef4444\" : \"inherit\");\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;color:'+deltaColor+';\">'+fmtPct(r.delta_pct)+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+fmtNum(r.sharpe,2)+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+fmtPct(r.max_dd_pct)+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+(r.n_orders !== undefined ? r.n_orders : \"-\")+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:center;\">'+recoBadge(r.reco)+'</td>';\n"
        "        html += '</tr>';\n"
        "      });\n"
    )

    NEW = (
        "      " + MARK_MAP_FIX + "\n"
        "      rows.forEach(function(r){\n"
        "        html += '<tr style=\"border-bottom:1px solid var(--border-color,#333);\">';\n"
        "        html += '<td style=\"padding:6px 8px;font-weight:600;\">'+(r.variant_name || r.variant_id || \"?\")+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+fmtPct(r.return_variant_pct)+'</td>';\n"
        "        var deltaColor = r.delta_pct > 0 ? \"#22c55e\" : (r.delta_pct < 0 ? \"#ef4444\" : \"inherit\");\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;color:'+deltaColor+';\">'+fmtPct(r.delta_pct)+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+fmtNum(r.sharpe_variant,2)+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+fmtPct(r.max_dd_variant_pct)+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+(r.n_orders_variant !== undefined && r.n_orders_variant !== null ? r.n_orders_variant : \"-\")+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:center;\">'+recoBadge(r.recommendation)+'</td>';\n"
        "        html += '</tr>';\n"
        "      });\n"
    )

    if OLD not in src:
        print("[ERR] bloc OLD JS introuvable - dump zone autour de 'rows.forEach' :")
        idx = src.find("rows.forEach")
        if idx > 0:
            print(src[max(0, idx-100):idx+1200])
        return False

    bak = JS + ".bak." + TS
    shutil.copy2(JS, bak)
    print("[BAK] JS ->", bak)
    new = src.replace(OLD, NEW, 1)
    with open(JS, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("[OK] JS patche, delta={} chars".format(len(new) - len(src)))
    return True

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("FIX UNIFIE SHADOW UI V1 : layout + mapping API")
    print("=" * 70)
    h = patch_html()
    print()
    j = patch_js()
    print()
    print("HTML patched :", h)
    print("JS   patched :", j)
    print()
    print("Next :")
    print("  Ctrl+Shift+R sur navigateur puis tab Backtest")
    print("  Attendu : card en haut pleine largeur, 4 lignes remplies,")
    print("           v2 tight_conv badge VERT 'champion' delta +3,931%")
    print("DONE")



===== nextones-fix-shadow-ui-memo-cache-key-v1.py =====

"""
Fix: Shadow UI memo modal - cache key bug
=========================================

Symptome: quelque soit le badge Shadow Variant clique, le modal affiche
toujours le meme memo (celui du dernier variant: defensive_crypto).

Cause: dans le bloc IIFE [SHADOW_UI_V1] de app.js, on utilise `r.id` comme
cle de cache:
    shadowRowsCache[r.id] = r;
    recoBadge(r.recommendation, r.id, hasMemo)

Mais les rows JSON renvoyees par /api/shadow/perf-rolling n'ont PAS de
champ `id`. La cle primaire est `variant_id` (table shadow_variants).
Donc shadowRowsCache[undefined] = r pour les 4 rows, le dernier ecrase
tous les autres -> tous les clics ouvrent le memo de defensive_crypto.

Fix: remplacer `r.id` par `r.variant_id` aux 2 endroits dans le bloc
SHADOW_UI_V1 de app.js.

Idempotent via marker [SHADOW_UI_V1_FIX_CACHE_KEY].
"""

import os
import re
import shutil
import time
import sys

UI = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
MARK_BEGIN = "// [SHADOW_UI_V1] BEGIN"
MARK_END = "// [SHADOW_UI_V1] END"
MARK_FIX = "// [SHADOW_UI_V1_FIX_CACHE_KEY]"
TS = time.strftime("%Y%m%d_%H%M%S")


def main():
    if not os.path.exists(UI):
        print("[ERR] file not found:", UI)
        return 2

    with open(UI, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()

    if MARK_FIX in src:
        print("[SKIP] fix already applied (marker present)")
        return 0

    if MARK_BEGIN not in src or MARK_END not in src:
        print("[ERR] SHADOW_UI_V1 block markers not found")
        return 3

    i_begin = src.index(MARK_BEGIN)
    i_end = src.index(MARK_END, i_begin) + len(MARK_END)
    block = src[i_begin:i_end]

    # Compte les occurrences avant patch
    count_cache = block.count("shadowRowsCache[r.id]")
    count_badge = len(re.findall(r"recoBadge\(\s*r\.recommendation\s*,\s*r\.id\s*,", block))
    print("[INFO] occurrences shadowRowsCache[r.id]:", count_cache)
    print("[INFO] occurrences recoBadge(...r.id...):", count_badge)

    if count_cache == 0 and count_badge == 0:
        print("[ERR] no occurrence of r.id found in block - aborting")
        return 4

    # Patch 1: shadowRowsCache[r.id] -> shadowRowsCache[r.variant_id]
    new_block = block.replace(
        "shadowRowsCache[r.id]",
        "shadowRowsCache[r.variant_id]",
    )

    # Patch 2: recoBadge(r.recommendation, r.id, ...) -> r.variant_id
    new_block = re.sub(
        r"recoBadge\(\s*r\.recommendation\s*,\s*r\.id\s*,",
        "recoBadge(r.recommendation, r.variant_id,",
        new_block,
    )

    # Sanity check post-patch
    if "shadowRowsCache[r.id]" in new_block:
        print("[ERR] post-patch: shadowRowsCache[r.id] still present")
        return 5
    if re.search(r"recoBadge\(\s*r\.recommendation\s*,\s*r\.id\s*,", new_block):
        print("[ERR] post-patch: recoBadge(...r.id...) still present")
        return 6
    if "shadowRowsCache[r.variant_id]" not in new_block:
        print("[ERR] post-patch: shadowRowsCache[r.variant_id] not present")
        return 7

    # Inject marker fix (en commentaire JS) juste apres MARK_BEGIN
    new_block = new_block.replace(
        MARK_BEGIN,
        MARK_BEGIN + "\n" + MARK_FIX + " " + TS,
        1,
    )

    new_src = src[:i_begin] + new_block + src[i_end:]

    if new_src == src:
        print("[ERR] no change produced")
        return 8

    bak = UI + ".bak." + TS
    shutil.copy2(UI, bak)
    print("[BAK]", bak)

    with open(UI, "w", encoding="utf-8", newline="") as f:
        f.write(new_src)
    print("[OK] written:", UI)
    print("[OK] patched shadowRowsCache:", count_cache, "occurrence(s)")
    print("[OK] patched recoBadge:", count_badge, "occurrence(s)")
    print("[NEXT] Ctrl+Shift+R dans le navigateur puis clic sur chaque badge")
    return 0


if __name__ == "__main__":
    sys.exit(main())



===== nextones-fix-shadow-ui-memo-cache-key-v2.py =====

"""
Fix v2: Shadow UI memo modal - cache key bug
============================================

Diag confirme:
- L7481: shadowRowsCache[r.id] = r;
- L7492: ... recoBadge(r.recommendation, r.id, hasMemo) ...
- markers reels: /* [SHADOW_UI_V1] BEGIN */ ... /* [SHADOW_UI_V1] END */
  (C-style, pas //)

Strategie: remplacement de chaines textuelles uniques dans tout le fichier.
- "shadowRowsCache[r.id]" apparait 1 seule fois -> safe
- "recoBadge(r.recommendation, r.id, hasMemo)" apparait 1 seule fois -> safe

Les 2 autres r.id (L6121 risk-card, L6430 risks.find) sont sur un domaine
different (risks) et ne sont PAS touches.

Idempotent via marker /* [SHADOW_UI_V1_FIX_CACHE_KEY] */ insere apres
/* [SHADOW_UI_V1] BEGIN */.
"""

import os
import shutil
import time
import sys

UI = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
MARK_BEGIN = "/* [SHADOW_UI_V1] BEGIN */"
MARK_FIX = "/* [SHADOW_UI_V1_FIX_CACHE_KEY] */"
TS = time.strftime("%Y%m%d_%H%M%S")

OLD1 = "shadowRowsCache[r.id] = r;"
NEW1 = "shadowRowsCache[r.variant_id] = r;"

OLD2 = "recoBadge(r.recommendation, r.id, hasMemo)"
NEW2 = "recoBadge(r.recommendation, r.variant_id, hasMemo)"


def main():
    if not os.path.exists(UI):
        print("[ERR] file not found:", UI)
        return 2

    with open(UI, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()

    if MARK_FIX in src:
        print("[SKIP] fix already applied (marker present)")
        return 0

    if MARK_BEGIN not in src:
        print("[ERR] BEGIN marker not found:", MARK_BEGIN)
        return 3

    c1 = src.count(OLD1)
    c2 = src.count(OLD2)
    print("[INFO] occurrences OLD1 (shadowRowsCache[r.id]):", c1)
    print("[INFO] occurrences OLD2 (recoBadge ...):", c2)

    if c1 != 1:
        print("[ERR] expected exactly 1 occurrence of OLD1, got", c1)
        return 4
    if c2 != 1:
        print("[ERR] expected exactly 1 occurrence of OLD2, got", c2)
        return 5

    new_src = src.replace(OLD1, NEW1, 1).replace(OLD2, NEW2, 1)

    # Sanity post-patch
    if OLD1 in new_src:
        print("[ERR] post-patch: OLD1 still present")
        return 6
    if OLD2 in new_src:
        print("[ERR] post-patch: OLD2 still present")
        return 7
    if NEW1 not in new_src:
        print("[ERR] post-patch: NEW1 not present")
        return 8
    if NEW2 not in new_src:
        print("[ERR] post-patch: NEW2 not present")
        return 9

    # Inject marker fix juste apres MARK_BEGIN (sur sa propre ligne)
    new_src = new_src.replace(
        MARK_BEGIN,
        MARK_BEGIN + "\n" + MARK_FIX + " /* " + TS + " */",
        1,
    )

    if new_src == src:
        print("[ERR] no change produced")
        return 10

    bak = UI + ".bak." + TS
    shutil.copy2(UI, bak)
    print("[BAK]", bak)

    with open(UI, "w", encoding="utf-8", newline="") as f:
        f.write(new_src)
    print("[OK] written:", UI)
    print("[OK] patched shadowRowsCache: 1 occurrence")
    print("[OK] patched recoBadge: 1 occurrence")
    print("[NEXT] Ctrl+Shift+R puis clic sur chaque badge -> 4 memos differents")
    return 0


if __name__ == "__main__":
    sys.exit(main())



===== nextones-fix-shadow-ui-memo-modal-v1.py =====

# -*- coding: utf-8 -*-
"""
Jalon 9.5b UI : badge cliquable -> modal avec memo IA.

Modifie app.js :
  - recoBadge() : badge devient cliquable (cursor pointer + data-row-id)
  - Le forEach passe les rows complets via dataset
  - Ajout fonction openShadowMemoModal(row) qui affiche dans une modal
  - Marker [SHADOW_UI_V1_MEMO_MODAL]

Idempotent.
"""
import os
import re
import shutil
from datetime import datetime

JS = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
MARK_MEMO = "/* [SHADOW_UI_V1_MEMO_MODAL] */"
MARK_JS_BEGIN = "/* [SHADOW_UI_V1] BEGIN */"
MARK_JS_END = "/* [SHADOW_UI_V1] END */"

# Nouveau bloc IIFE complet (avec memo modal integre)
JS_NEW = r"""/* [SHADOW_UI_V1] BEGIN */
/* [SHADOW_UI_V1_POLISH] */
/* [SHADOW_UI_V1_MEMO_MODAL] */
(function(){
  var shadowRowsCache = {};

  function fmtPct(v){
    if (v === null || v === undefined || isNaN(v)) return "-";
    var sign = v > 0 ? "+" : "";
    return sign + Number(v).toFixed(3).replace(".",",") + "%";
  }
  function fmtNum(v, dec){
    if (v === null || v === undefined || isNaN(v)) return "-";
    return Number(v).toFixed(dec === undefined ? 2 : dec).replace(".",",");
  }
  function esc(s){
    if (s === null || s === undefined) return "";
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }
  function recoBadge(reco, rowId, hasMemo){
    var color = "#888"; var bg = "rgba(136,136,136,0.15)";
    var label = reco || "neutral";
    if (reco === "champion"){ color = "#22c55e"; bg = "rgba(34,197,94,0.15)"; }
    else if (reco === "reject"){ color = "#ef4444"; bg = "rgba(239,68,68,0.15)"; }
    var dot = hasMemo ? ' <span style="opacity:0.7;font-size:9px;">[Memo]</span>' : "";
    var tip = hasMemo ? "Cliquer pour lire le memo IA" : "Pas de memo IA generee";
    var cursor = hasMemo ? "pointer" : "default";
    return '<span class="shadow-reco-badge" data-row-id="'+rowId+'" title="'+esc(tip)+'" style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;color:'+color+';background:'+bg+';cursor:'+cursor+';">'+label+dot+'</span>';
  }

  function cleanupParasites(){
    var card = document.getElementById("shadow-variants-card");
    if (!card) return;
    card.querySelectorAll("button, a").forEach(function(el){
      if (el.id === "shadow-refresh-btn") return;
      if (el.classList && (el.classList.contains("shadow-reco-badge") || el.classList.contains("shadow-keep"))) return;
      if (el.closest("#shadow-variants-table") || (el.textContent && /memo/i.test(el.textContent))){
        el.remove();
      }
    });
  }

  function ensureModal(){
    var m = document.getElementById("shadow-memo-modal");
    if (m) return m;
    m = document.createElement("div");
    m.id = "shadow-memo-modal";
    m.style.cssText = "display:none;position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.6);z-index:9999;justify-content:center;align-items:center;";
    m.innerHTML = (
      '<div id="shadow-memo-modal-box" class="shadow-keep" style="background:var(--bg-card,#1a1a1f);color:var(--text-primary,#eee);max-width:720px;width:90%;max-height:85vh;overflow-y:auto;border-radius:12px;padding:24px;box-shadow:0 8px 40px rgba(0,0,0,0.5);">'
      + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">'
      + '<h3 id="shadow-memo-modal-title" style="margin:0;">Memo IA</h3>'
      + '<button id="shadow-memo-modal-close" class="shadow-keep" style="background:transparent;border:1px solid var(--border-color,#555);color:inherit;padding:4px 12px;border-radius:6px;cursor:pointer;">Fermer</button>'
      + '</div>'
      + '<div id="shadow-memo-modal-meta" style="font-size:11px;opacity:0.65;margin-bottom:12px;"></div>'
      + '<pre id="shadow-memo-modal-body" style="white-space:pre-wrap;word-wrap:break-word;font-family:inherit;font-size:13px;line-height:1.55;margin:0;background:rgba(255,255,255,0.03);padding:14px;border-radius:8px;"></pre>'
      + '</div>'
    );
    document.body.appendChild(m);
    m.addEventListener("click", function(ev){
      if (ev.target === m) closeModal();
    });
    document.getElementById("shadow-memo-modal-close").addEventListener("click", closeModal);
    document.addEventListener("keydown", function(ev){
      if (ev.key === "Escape" && m.style.display === "flex") closeModal();
    });
    return m;
  }
  function closeModal(){
    var m = document.getElementById("shadow-memo-modal");
    if (m) m.style.display = "none";
  }
  function openShadowMemoModal(row){
    if (!row) return;
    var m = ensureModal();
    document.getElementById("shadow-memo-modal-title").textContent =
      "Memo IA - " + (row.variant_name || ("variant " + row.variant_id));
    var metaParts = [];
    if (row.recommendation) metaParts.push("Reco : " + row.recommendation);
    if (row.memo_source) metaParts.push("Source : " + row.memo_source);
    if (row.memo_generated_at) metaParts.push("Genere le " + row.memo_generated_at);
    if (row.window_days) metaParts.push("Fenetre " + row.window_days + "j");
    document.getElementById("shadow-memo-modal-meta").textContent = metaParts.join(" | ");
    var body = row.recommendation_memo || "(Aucun memo genere - lancer shadow_memo_generator.py)";
    document.getElementById("shadow-memo-modal-body").textContent = body;
    m.style.display = "flex";
  }
  window.openShadowMemoModal = openShadowMemoModal;

  async function renderShadowVariants(){
    var meta = document.getElementById("shadow-variants-meta");
    var tbody = document.getElementById("shadow-variants-tbody");
    if (!meta || !tbody) return;
    meta.textContent = "Chargement...";
    tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Chargement...</td></tr>';
    try {
      var perf = await apiFetch("/api/shadow/perf-rolling?window=30");
      if (!perf || !perf.success){
        meta.textContent = "Erreur API perf-rolling";
        tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;color:#ef4444;">Erreur : '+(perf && perf.error ? perf.error : "inconnu")+'</td></tr>';
        return;
      }
      var rows = perf.rows || [];
      shadowRowsCache = {};
      var nCycles = rows[0] && rows[0].n_cycles !== undefined ? rows[0].n_cycles : "?";
      var createdAt = rows[0] && rows[0].created_at ? rows[0].created_at : "-";
      meta.innerHTML = 'Fenetre <strong>'+perf.window_days+'j</strong> | as_of_day=<strong>'+perf.as_of_day+'</strong> | <strong>'+rows.length+'</strong> variants | sur <strong>'+nCycles+'</strong> cycles | derniere maj '+esc(createdAt);
      if (rows.length === 0){
        tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Aucune donnee</td></tr>';
        return;
      }
      var html = "";
      rows.forEach(function(r){
        shadowRowsCache[r.id] = r;
        var desc = r.description || "";
        var hasMemo = !!(r.recommendation_memo);
        html += '<tr style="border-bottom:1px solid var(--border-color,#333);">';
        html += '<td style="padding:6px 8px;font-weight:600;" title="'+esc(desc)+'">'+esc(r.variant_name || r.variant_id || "?")+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtPct(r.return_variant_pct)+'</td>';
        var deltaColor = r.delta_pct > 0 ? "#22c55e" : (r.delta_pct < 0 ? "#ef4444" : "inherit");
        html += '<td style="padding:6px 8px;text-align:right;color:'+deltaColor+';font-weight:600;">'+fmtPct(r.delta_pct)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtNum(r.sharpe_variant,2)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtPct(r.max_dd_variant_pct)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+(r.n_orders_variant !== undefined && r.n_orders_variant !== null ? r.n_orders_variant : "-")+'</td>';
        html += '<td style="padding:6px 8px;text-align:center;">'+recoBadge(r.recommendation, r.id, hasMemo)+'</td>';
        html += '</tr>';
      });
      tbody.innerHTML = html;
      cleanupParasites();
      setTimeout(cleanupParasites, 200);
      setTimeout(cleanupParasites, 1000);

      // Click handlers sur badges
      tbody.querySelectorAll(".shadow-reco-badge").forEach(function(b){
        b.addEventListener("click", function(){
          var rid = b.getAttribute("data-row-id");
          var row = shadowRowsCache[rid];
          if (row && row.recommendation_memo){
            openShadowMemoModal(row);
          }
        });
      });
    } catch(e){
      meta.textContent = "Erreur reseau";
      tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;color:#ef4444;">Exception : '+(e && e.message ? e.message : String(e))+'</td></tr>';
    }
  }
  window.renderShadowVariants = renderShadowVariants;

  function bindShadowUI(){
    var btn = document.getElementById("shadow-refresh-btn");
    if (btn && !btn.dataset.shadowBound){
      btn.dataset.shadowBound = "1";
      btn.addEventListener("click", renderShadowVariants);
    }
    var tabLink = document.querySelector('a[data-tab="backtest"]');
    if (tabLink && !tabLink.dataset.shadowBound){
      tabLink.dataset.shadowBound = "1";
      tabLink.addEventListener("click", function(){ setTimeout(renderShadowVariants, 120); });
    }
    /* [SHADOW_UI_V1_FIX_WAIT_TOKEN] */
    function tryInitialLoad(attemptsLeft){
      if (typeof state === "undefined" || !state || !state.token){
        if (attemptsLeft > 0){ setTimeout(function(){ tryInitialLoad(attemptsLeft - 1); }, 500); }
        return;
      }
      if (document.querySelector("#tab-backtest.active") || (location.hash === "#backtest")){
        renderShadowVariants();
      }
    }
    tryInitialLoad(10);

    var card = document.getElementById("shadow-variants-card");
    if (card && !card.dataset.shadowObserver){
      card.dataset.shadowObserver = "1";
      var obs = new MutationObserver(function(muts){
        for (var i=0; i<muts.length; i++){
          var m = muts[i];
          for (var j=0; j<m.addedNodes.length; j++){
            var n = m.addedNodes[j];
            if (n.nodeType === 1){
              var tag = n.tagName;
              if ((tag === "BUTTON" || tag === "A") && n.id !== "shadow-refresh-btn"){
                if (n.textContent && /memo/i.test(n.textContent)){ n.remove(); }
              }
            }
          }
        }
      });
      obs.observe(card, { childList: true, subtree: true });
    }
  }
  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", bindShadowUI);
  } else {
    bindShadowUI();
  }
})();
/* [SHADOW_UI_V1] END */"""

with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

if MARK_MEMO in src:
    print("[SKIP] marker memo modal deja present")
else:
    pat = re.compile(
        re.escape(MARK_JS_BEGIN) + r".*?" + re.escape(MARK_JS_END),
        re.DOTALL
    )
    if not pat.search(src):
        print("[ERR] bloc [SHADOW_UI_V1] BEGIN ... END introuvable")
    else:
        bak = JS + ".bak." + TS
        shutil.copy2(JS, bak)
        print("[BAK]", bak)
        new = pat.sub(JS_NEW, src, count=1)
        with open(JS, "w", encoding="utf-8", newline="") as f:
            f.write(new)
        print("[OK] JS patche, delta={} chars".format(len(new) - len(src)))
        print("[INFO] marker memo modal :", new.count(MARK_MEMO))

print()
print("Next : Ctrl+Shift+R sur navigateur, tab Backtest")
print("DONE")



===== nextones-fix-shadow-ui-polish-v1.py =====

# -*- coding: utf-8 -*-
"""
Fix forme Shadow Variants (Jalon 9.6 polish) :
  1. Memo IA parasite : retire les boutons "Memo IA" injectes par un autre
     code dans la card via MutationObserver de nettoyage local.
  2. Bouton Rafraichir : style inline propre (cadre + hover).
  3. Tooltip RECO : title sur le <th> + abreviations expliquees.
  4. n_cycles dans meta : ajoute "| sur X cycles".
  5. Timestamp derniere maj : affiche created_at de la row.
  6. Description variant : title attribute (tooltip survol) sur nom.

Idempotent via marker [SHADOW_UI_V1_POLISH].
Remplace COMPLETEMENT le bloc IIFE shadow_variants (de [SHADOW_UI_V1] BEGIN
a [SHADOW_UI_V1] END) par une version polish.

Egalement remplace dans index.html le <th>RECO</th> par version avec tooltip
ET ajoute le bouton Rafraichir style.
"""
import os
import re
import shutil
from datetime import datetime

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
HTML = os.path.join(ROOT, "index.html")
JS = os.path.join(ROOT, "app.js")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

MARK_POLISH = "/* [SHADOW_UI_V1_POLISH] */"
MARK_HTML_POLISH = "<!-- [SHADOW_UI_V1_POLISH] -->"
MARK_JS_BEGIN = "/* [SHADOW_UI_V1] BEGIN */"
MARK_JS_END = "/* [SHADOW_UI_V1] END */"

# -----------------------------------------------------------------------------
# Nouveau bloc JS complet (remplace IIFE existant)
# -----------------------------------------------------------------------------
JS_NEW = r"""/* [SHADOW_UI_V1] BEGIN */
/* [SHADOW_UI_V1_POLISH] */
(function(){
  function fmtPct(v){
    if (v === null || v === undefined || isNaN(v)) return "-";
    var sign = v > 0 ? "+" : "";
    return sign + Number(v).toFixed(3).replace(".",",") + "%";
  }
  function fmtNum(v, dec){
    if (v === null || v === undefined || isNaN(v)) return "-";
    return Number(v).toFixed(dec === undefined ? 2 : dec).replace(".",",");
  }
  function recoBadge(reco){
    var color = "#888"; var bg = "rgba(136,136,136,0.15)";
    var label = reco || "neutral";
    if (reco === "champion"){ color = "#22c55e"; bg = "rgba(34,197,94,0.15)"; }
    else if (reco === "reject"){ color = "#ef4444"; bg = "rgba(239,68,68,0.15)"; }
    return '<span class="shadow-reco-badge" style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;color:'+color+';background:'+bg+';">'+label+'</span>';
  }
  function esc(s){
    if (s === null || s === undefined) return "";
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  function cleanupParasites(){
    var card = document.getElementById("shadow-variants-card");
    if (!card) return;
    // Retire tout bouton ou lien externe injecte dans la card qui n'a pas notre classe shadow-*
    card.querySelectorAll("button, a").forEach(function(el){
      if (el.id === "shadow-refresh-btn") return;
      if (el.classList && (el.classList.contains("shadow-reco-badge") || el.classList.contains("shadow-keep"))) return;
      // Si bouton hors de notre header -> suppression
      if (el.closest("#shadow-variants-table") || (el.textContent && /memo/i.test(el.textContent))){
        el.remove();
      }
    });
  }

  async function renderShadowVariants(){
    var meta = document.getElementById("shadow-variants-meta");
    var tbody = document.getElementById("shadow-variants-tbody");
    if (!meta || !tbody) return;
    meta.textContent = "Chargement...";
    tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Chargement...</td></tr>';
    try {
      var perf = await apiFetch("/api/shadow/perf-rolling?window=30");
      if (!perf || !perf.success){
        meta.textContent = "Erreur API perf-rolling";
        tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;color:#ef4444;">Erreur : '+(perf && perf.error ? perf.error : "inconnu")+'</td></tr>';
        return;
      }
      var rows = perf.rows || [];
      var nCycles = rows[0] && rows[0].n_cycles !== undefined ? rows[0].n_cycles : "?";
      var createdAt = rows[0] && rows[0].created_at ? rows[0].created_at : "-";
      meta.innerHTML = 'Fenetre <strong>'+perf.window_days+'j</strong> | as_of_day=<strong>'+perf.as_of_day+'</strong> | <strong>'+rows.length+'</strong> variants | sur <strong>'+nCycles+'</strong> cycles | derniere maj '+esc(createdAt);
      if (rows.length === 0){
        tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Aucune donnee</td></tr>';
        return;
      }
      var html = "";
      rows.forEach(function(r){
        var desc = r.description || "";
        html += '<tr style="border-bottom:1px solid var(--border-color,#333);">';
        html += '<td style="padding:6px 8px;font-weight:600;" title="'+esc(desc)+'">'+esc(r.variant_name || r.variant_id || "?")+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtPct(r.return_variant_pct)+'</td>';
        var deltaColor = r.delta_pct > 0 ? "#22c55e" : (r.delta_pct < 0 ? "#ef4444" : "inherit");
        html += '<td style="padding:6px 8px;text-align:right;color:'+deltaColor+';font-weight:600;">'+fmtPct(r.delta_pct)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtNum(r.sharpe_variant,2)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtPct(r.max_dd_variant_pct)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+(r.n_orders_variant !== undefined && r.n_orders_variant !== null ? r.n_orders_variant : "-")+'</td>';
        html += '<td style="padding:6px 8px;text-align:center;">'+recoBadge(r.recommendation)+'</td>';
        html += '</tr>';
      });
      tbody.innerHTML = html;
      cleanupParasites();
      setTimeout(cleanupParasites, 200);
      setTimeout(cleanupParasites, 1000);
    } catch(e){
      meta.textContent = "Erreur reseau";
      tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;color:#ef4444;">Exception : '+(e && e.message ? e.message : String(e))+'</td></tr>';
    }
  }
  window.renderShadowVariants = renderShadowVariants;

  function bindShadowUI(){
    var btn = document.getElementById("shadow-refresh-btn");
    if (btn && !btn.dataset.shadowBound){
      btn.dataset.shadowBound = "1";
      btn.addEventListener("click", renderShadowVariants);
    }
    var tabLink = document.querySelector('a[data-tab="backtest"]');
    if (tabLink && !tabLink.dataset.shadowBound){
      tabLink.dataset.shadowBound = "1";
      tabLink.addEventListener("click", function(){ setTimeout(renderShadowVariants, 120); });
    }
    /* [SHADOW_UI_V1_FIX_WAIT_TOKEN] */
    function tryInitialLoad(attemptsLeft){
      if (typeof state === "undefined" || !state || !state.token){
        if (attemptsLeft > 0){ setTimeout(function(){ tryInitialLoad(attemptsLeft - 1); }, 500); }
        return;
      }
      if (document.querySelector("#tab-backtest.active") || (location.hash === "#backtest")){
        renderShadowVariants();
      }
    }
    tryInitialLoad(10);

    // MutationObserver pour rejouer cleanup si un autre code injecte tardivement
    var card = document.getElementById("shadow-variants-card");
    if (card && !card.dataset.shadowObserver){
      card.dataset.shadowObserver = "1";
      var obs = new MutationObserver(function(muts){
        for (var i=0; i<muts.length; i++){
          var m = muts[i];
          for (var j=0; j<m.addedNodes.length; j++){
            var n = m.addedNodes[j];
            if (n.nodeType === 1){
              var tag = n.tagName;
              if ((tag === "BUTTON" || tag === "A") && n.id !== "shadow-refresh-btn"){
                if (n.textContent && /memo/i.test(n.textContent)){ n.remove(); }
              }
            }
          }
        }
      });
      obs.observe(card, { childList: true, subtree: true });
    }
  }
  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", bindShadowUI);
  } else {
    bindShadowUI();
  }
})();
/* [SHADOW_UI_V1] END */"""

# -----------------------------------------------------------------------------
# Patch JS
# -----------------------------------------------------------------------------
def patch_js():
    with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()
    if MARK_POLISH in src:
        print("[SKIP] JS polish marker deja present")
        return False
    # Trouver et remplacer le bloc complet [SHADOW_UI_V1] BEGIN ... END
    pat = re.compile(
        re.escape(MARK_JS_BEGIN) + r".*?" + re.escape(MARK_JS_END),
        re.DOTALL
    )
    if not pat.search(src):
        print("[ERR] bloc [SHADOW_UI_V1] BEGIN ... END introuvable dans app.js")
        return False
    bak = JS + ".bak." + TS
    shutil.copy2(JS, bak)
    print("[BAK] JS ->", bak)
    new = pat.sub(JS_NEW, src, count=1)
    with open(JS, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("[OK] JS patche, delta={} chars".format(len(new) - len(src)))
    print("[INFO] marker polish present:", new.count(MARK_POLISH))
    return True

# -----------------------------------------------------------------------------
# Patch HTML : remplace <th>Reco</th> + bouton Rafraichir style
# -----------------------------------------------------------------------------
def patch_html():
    with open(HTML, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()
    if MARK_HTML_POLISH in src:
        print("[SKIP] HTML polish marker deja present")
        return False

    bak = HTML + ".bak." + TS
    shutil.copy2(HTML, bak)
    print("[BAK] HTML ->", bak)

    # 1. <th> Reco -> tooltip
    OLD_TH = '<th style="padding:6px 8px;text-align:center;">Reco</th>'
    NEW_TH = '<th style="padding:6px 8px;text-align:center;" title="champion : delta > +2 pts et Sharpe > prod | reject : delta < -1 pt | sinon neutral">Reco</th>'
    if OLD_TH in src:
        src = src.replace(OLD_TH, NEW_TH, 1)
        print("[OK] <th>Reco</th> tooltip ajoute")
    else:
        print("[WARN] <th>Reco</th> introuvable - skip")

    # 2. Bouton Rafraichir : style inline propre
    OLD_BTN = '<button id="shadow-refresh-btn" class="pplx-refresh-btn" type="button">Rafraichir</button>'
    NEW_BTN = ('<button id="shadow-refresh-btn" class="pplx-refresh-btn shadow-keep" type="button" '
               'style="padding:6px 14px;border:1px solid var(--border-color,#555);'
               'background:transparent;color:inherit;border-radius:6px;cursor:pointer;font-size:12px;font-weight:500;">'
               'Rafraichir</button>')
    if OLD_BTN in src:
        src = src.replace(OLD_BTN, NEW_BTN, 1)
        print("[OK] bouton Rafraichir style applique")
    else:
        print("[WARN] bouton Rafraichir introuvable - skip")

    # 3. Marqueur polish
    # Inserer le marker au debut du bloc shadow-variants-card pour idempotence
    OLD_CARD = '<div id="shadow-variants-card"'
    NEW_CARD = MARK_HTML_POLISH + '\n        <div id="shadow-variants-card"'
    if OLD_CARD in src:
        src = src.replace(OLD_CARD, NEW_CARD, 1)
        print("[OK] marker polish HTML insere")

    with open(HTML, "w", encoding="utf-8", newline="") as f:
        f.write(src)
    return True

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("FIX FORME SHADOW UI V1 (polish)")
    print("=" * 70)
    j = patch_js()
    print()
    h = patch_html()
    print()
    print("JS   patched :", j)
    print("HTML patched :", h)
    print()
    print("Apres :")
    print("  Ctrl+Shift+R sur navigateur, tab Backtest")
    print("  Verifier : pas de 'Memo IA' a cote de prod-neutral,")
    print("             bouton Rafraichir avec cadre,")
    print("             survol 'tight_conv' montre la description,")
    print("             meta ligne 2 : 'sur 14 cycles | derniere maj 2026-06-12 ...'")
    print("DONE")



===== nextones-fix-shadow-ui-wait-token-v1.py =====

# -*- coding: utf-8 -*-
"""
Fix UI : renderShadowVariants() etait appele AVANT que state.token soit hydrate.
Resultat : 401 sur le 1er appel auto au load.

Patch chirurgical : remplace le bloc d'auto-init dans le JS shadow_variants par :
  - Check state.token avant le 1er call
  - Si absent, retry 500ms plus tard (jusqu'a 5s)
  - Le bouton Rafraichir reste manuel
  - Le tab click hook reste OK

Idempotent via marker [SHADOW_UI_V1_FIX_WAIT_TOKEN].
"""
import os
import shutil
from datetime import datetime

JS = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
MARK_FIX = "/* [SHADOW_UI_V1_FIX_WAIT_TOKEN] */"

OLD = (
    "    if (document.querySelector('#tab-backtest.active') || (location.hash === \"#backtest\")){\n"
    "      renderShadowVariants();\n"
    "    }\n"
)

NEW = (
    "    " + MARK_FIX + "\n"
    "    function tryInitialLoad(attemptsLeft){\n"
    "      if (typeof state === 'undefined' || !state || !state.token){\n"
    "        if (attemptsLeft > 0){\n"
    "          setTimeout(function(){ tryInitialLoad(attemptsLeft - 1); }, 500);\n"
    "        }\n"
    "        return;\n"
    "      }\n"
    "      if (document.querySelector('#tab-backtest.active') || (location.hash === \"#backtest\")){\n"
    "        renderShadowVariants();\n"
    "      }\n"
    "    }\n"
    "    tryInitialLoad(10);\n"
)

with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

print("File size :", len(src))

if MARK_FIX in src:
    print("[SKIP] marker fix wait_token deja present")
elif OLD not in src:
    print("[ERR] bloc OLD introuvable - dump des lignes contenant 'tab-backtest.active' :")
    for i, line in enumerate(src.split("\n"), 1):
        if "tab-backtest.active" in line or "location.hash" in line:
            print("  L{} | {}".format(i, line.rstrip()))
else:
    bak = JS + ".bak." + TS
    shutil.copy2(JS, bak)
    print("[BAK]", bak)
    new = src.replace(OLD, NEW, 1)
    with open(JS, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("[OK] JS patche, delta={} chars".format(len(new) - len(src)))
    print("[INFO] count marker fix:", new.count(MARK_FIX))

print()
print("Next : Ctrl+Shift+R sur navigateur, onglet Backtest")
print("DONE")



===== nextones-fix-shadow-wiring-commit.py =====

# -*- coding: utf-8 -*-
# [NEXTONES-FIX-SHADOW-WIRING-COMMIT-V1]
# Probleme : execute_shadow ouvre sa propre connexion mais la connexion
# 'conn' de create_and_execute_order tient encore une transaction ouverte
# (INSERT orders + UPDATE quantity). Le lock writer bloque execute_shadow
# pendant 10s puis fail "database is locked".
#
# Solution : injecter conn.commit() juste avant l'appel execute_shadow
# dans le bloc [NEXTONES-SHADOW-EXEC-V1].
#
# Idempotent : detecte la presence du commit via marker V2.

import argparse
import ast
import os
import py_compile
import shutil
import sys
import time

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
EE = os.path.join(PROD_DIR, "execution_engine.py")
MARKER_V1 = "[NEXTONES-SHADOW-EXEC-V1]"
MARKER_V2 = "[NEXTONES-SHADOW-EXEC-COMMIT-V2]"


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


def fail(msg):
    print(f"[FAIL] {msg}")
    sys.exit(1)


def ok(msg):
    print(f"[OK] {msg}")


def rollback():
    banner("[ROLLBACK]")
    candidates = sorted(
        [f for f in os.listdir(PROD_DIR)
         if f.startswith("execution_engine.py.bak.")],
        reverse=True,
    )
    if not candidates:
        fail("aucun backup execution_engine.py.bak.*")
    latest = os.path.join(PROD_DIR, candidates[0])
    shutil.copyfile(latest, EE)
    ok(f"restaure depuis {candidates[0]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rollback", action="store_true")
    args = ap.parse_args()

    if args.rollback:
        rollback()
        return

    banner("[1] Lecture execution_engine.py")
    with open(EE, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER_V1 not in src:
        fail("marker V1 absent : le wiring n'a pas ete installe")
    if MARKER_V2 in src:
        print("[INFO] marker V2 deja present : patch deja applique")
        return
    ok("wiring V1 present, V2 absent -> on patche")

    # ----------------------------- 2 -----------------------------
    banner("[2] Localise le bloc V1 et injecte conn.commit()")
    # On cherche le bloc qui commence par la ligne marker V1
    # Pattern attendu :
    #   # [NEXTONES-SHADOW-EXEC-V1] - shadow executor en parallele ...
    #   try:
    #       import bridge_config as _bc_sh
    #       if getattr(_bc_sh, "BROKER_SHADOW_ENABLED", False):
    #           ...
    #
    # On veut transformer en :
    #   # [NEXTONES-SHADOW-EXEC-COMMIT-V2] - commit conn avant shadow pour liberer le lock writer
    #   # [NEXTONES-SHADOW-EXEC-V1] - shadow executor en parallele ...
    #   try:
    #       try:
    #           conn.commit()
    #       except Exception:
    #           pass
    #       import bridge_config as _bc_sh
    #       ...

    # Trouve la ligne de marker V1
    pos = src.find(MARKER_V1)
    if pos < 0:
        fail("MARKER_V1 introuvable (apres check ?!)")

    # Remonter au debut de la ligne du marker
    line_start = src.rfind("\n", 0, pos) + 1
    # Indentation = caracteres jusqu'au # du marker
    indent = ""
    i = line_start
    while i < len(src) and src[i] in (" ", "\t"):
        indent += src[i]
        i += 1

    # Trouver le 'try:' qui suit le marker (sur les 3 lignes suivantes max)
    after_marker_line_end = src.find("\n", pos)
    rest = src[after_marker_line_end + 1:]
    # Le 'try:' doit etre la prochaine instruction non-vide a la meme indentation
    rest_lines = rest.split("\n")
    try_idx_in_rest = None
    for k, ln in enumerate(rest_lines):
        if ln.strip() == "":
            continue
        if ln.startswith(indent + "try:"):
            try_idx_in_rest = k
            break
        else:
            # Premiere ligne non-vide n'est pas le try -> structure inattendue
            print(f"[WARN] premiere ligne non-vide apres marker : {ln!r}")
            print(f"       attendu : {indent}try:")
            break

    if try_idx_in_rest is None:
        fail("'try:' non trouve juste apres le marker V1")

    # Detecte l'indentation interne du try (4 chars en plus)
    # Apres le 'try:' on doit voir les lignes plus indentees
    inner_indent = indent + "    "

    # On va modifier rest_lines :
    # - inserer juste apres 'try:' (donc en position try_idx_in_rest+1) 3 lignes :
    #     {inner_indent}try:
    #     {inner_indent}    conn.commit()
    #     {inner_indent}except Exception:
    #     {inner_indent}    pass
    # - ajouter le marker V2 en commentaire AVANT le marker V1 (au-dessus)
    inject = [
        inner_indent + "try:",
        inner_indent + "    conn.commit()  " + "# " + MARKER_V2,
        inner_indent + "except Exception:",
        inner_indent + "    pass",
    ]
    new_rest_lines = (
        rest_lines[: try_idx_in_rest + 1]
        + inject
        + rest_lines[try_idx_in_rest + 1 :]
    )
    new_rest = "\n".join(new_rest_lines)

    # Marker V2 en commentaire en haut, juste avant la ligne marker V1
    pre = src[:line_start]
    marker_v2_line = indent + "# " + MARKER_V2 + " - commit conn avant shadow pour liberer le lock writer\n"
    new_src = pre + marker_v2_line + src[line_start:after_marker_line_end + 1] + new_rest

    # ----------------------------- 3 -----------------------------
    banner("[3] Validation ast.parse + py_compile")
    tmp = EE + ".tmp.fix"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_src)
    try:
        ast.parse(new_src)
        py_compile.compile(tmp, doraise=True)
        ok("ast.parse + py_compile OK")
    except Exception as e:
        os.remove(tmp)
        fail(f"validation echouee : {e}")

    # ----------------------------- 4 -----------------------------
    banner("[4] Backup + apply")
    bak = f"{EE}.bak.{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copyfile(EE, bak)
    shutil.move(tmp, EE)
    ok(f"patch applique (backup : {os.path.basename(bak)})")

    # ----------------------------- 5 -----------------------------
    banner("[5] Smoke import en subprocess")
    import subprocess
    r = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, r'{PROD_DIR}'); "
         "import execution_engine; print('import OK')"],
        capture_output=True, text=True, timeout=30,
    )
    print(f"  stdout : {r.stdout.strip()}")
    if r.returncode != 0:
        print(f"  stderr : {r.stderr.strip()}")
        # rollback auto
        shutil.copyfile(bak, EE)
        fail("smoke import echoue -> rollback automatique")
    ok("smoke import OK")

    banner("[VERDICT]")
    print("  patch V2 (conn.commit() avant execute_shadow) applique")
    print("  re-lancer le validator :")
    print("    py -3.13 nextones-validate-shadow-wired.py")


if __name__ == "__main__":
    main()



===== nextones-install-shadow-api-v1.py =====

# -*- coding: utf-8 -*-
"""
PATCH PHASE 9.6 - Shadow API endpoints
[SHADOW_API_V1]

Injecte 2 endpoints GET dans api_server.py APRES @app.get("/api/backtest/presets")
(L2905), bien AVANT le mount commente L3395.

Routes ajoutees :
  GET /api/shadow/variants       -> liste 4 variants actifs
  GET /api/shadow/perf-rolling   -> derniere row par variant pour window=30

Anchor : '@app.get("/api/backtest/presets")' -> on remonte jusqu a la prochaine
ligne vide apres la fin du handler, puis on insere le bloc.

Strategie idempotente : skip si marker '[SHADOW_API_V1] BEGIN' present.

Backup : .py.bak.<timestamp>
"""
import os
import re
import sys
import time
import ast
import py_compile
import shutil

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API  = os.path.join(BASE, "api_server.py")

MARKER_BEGIN = "[SHADOW_API_V1] BEGIN"
MARKER_END   = "[SHADOW_API_V1] END"


def log(msg):
    print(msg, flush=True)


def main():
    if not os.path.exists(API):
        log("[ERR] api_server.py introuvable : " + API)
        sys.exit(1)

    # 1. Read
    with open(API, "rb") as f:
        raw = f.read()
    src = raw.decode("utf-8-sig")  # strip BOM si present

    # 2. Idempotence
    if MARKER_BEGIN in src:
        log("[SKIP] marker '{}' deja present : patch deja applique.".format(MARKER_BEGIN))
        sys.exit(0)

    # 3. Localiser anchor : ligne contenant @app.get("/api/backtest/presets")
    lines = src.split("\n")
    anchor_idx = None
    for i, ln in enumerate(lines):
        if '@app.get("/api/backtest/presets")' in ln:
            anchor_idx = i
            break

    if anchor_idx is None:
        log("[ERR] anchor '@app.get(\"/api/backtest/presets\")' introuvable.")
        sys.exit(2)

    log("[OK] anchor presets trouve a la ligne {} (1-based : {})".format(
        anchor_idx, anchor_idx + 1
    ))

    # 4. Trouver la fin du handler presets : on cherche la prochaine def/decorator
    #    de top-level (non indente) apres l'anchor. La ligne PRECEDENTE = insertion point.
    insert_after_idx = None
    for j in range(anchor_idx + 1, len(lines)):
        ln = lines[j]
        # Top-level statement : commence par '@app.' ou 'def ' ou '# ===' ou '# ---'
        # On veut la prochaine route ou la prochaine section
        if (ln.startswith("@app.") or
            ln.startswith("def ") or
            ln.startswith("async def ") or
            ln.startswith("class ") or
            (ln.startswith("# ") and ("=====" in ln or "-----" in ln))):
            insert_after_idx = j - 1
            break

    if insert_after_idx is None:
        log("[ERR] impossible de trouver la fin du handler presets.")
        sys.exit(3)

    # Reculer jusqu a la derniere ligne non vide
    while insert_after_idx > anchor_idx and lines[insert_after_idx].strip() == "":
        insert_after_idx -= 1

    log("[OK] insertion point apres ligne {} (1-based)".format(insert_after_idx + 1))
    log("     preview last 3 lines avant insertion :")
    for k in range(max(0, insert_after_idx - 2), insert_after_idx + 1):
        log("       L{:5d} | {}".format(k + 1, lines[k]))

    # 5. Construire le bloc a inserer (ASCII pur, no emoji)
    block = '''

# ===== [SHADOW_API_V1] BEGIN =====
# Phase 9.6 - Endpoints lecture shadow_variants + shadow_perf_rolling
# Affichage card "Shadow Variants J-30" dans onglet Backtest

@app.get("/api/shadow/variants")
def shadow_list_variants(user: dict = Depends(get_current_user)):
    """Liste tous les variants actifs (id, name, description, settings)."""
    import json
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT variant_id, name, description, settings_json, active "
            "FROM shadow_variants WHERE active=1 ORDER BY variant_id"
        ).fetchall()
        out = []
        for r in rows:
            try:
                settings = json.loads(r["settings_json"] or "{}")
            except Exception:
                settings = {}
            out.append({
                "variant_id": r["variant_id"],
                "name": r["name"],
                "description": r["description"],
                "settings": settings,
            })
        return {"success": True, "variants": out}
    finally:
        conn.close()


@app.get("/api/shadow/perf-rolling")
def shadow_perf_rolling(window: int = 30, user: dict = Depends(get_current_user)):
    """Latest as_of_day pour chaque variant sur la window donnee (default 30j)."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        # Latest as_of_day disponible
        row = conn.execute(
            "SELECT MAX(as_of_day) AS d FROM shadow_perf_rolling WHERE window_days=?",
            (window,),
        ).fetchone()
        latest = row["d"] if row else None
        if not latest:
            return {
                "success": True,
                "window_days": window,
                "as_of_day": None,
                "rows": [],
                "message": "Aucune donnee perf rolling - lancer shadow_perf_rolling_j30.py",
            }
        # Rows + join shadow_variants pour nom
        rows = conn.execute(
            "SELECT p.variant_id, v.name AS variant_name, v.description, "
            "p.window_days, p.as_of_day, "
            "p.nav_variant, p.nav_prod, "
            "p.return_variant_pct, p.return_prod_pct, p.delta_pct, "
            "p.sharpe_variant, p.sharpe_prod, "
            "p.max_dd_variant_pct, p.max_dd_prod_pct, "
            "p.n_cycles, p.n_orders_variant, p.n_orders_prod, "
            "p.recommendation, p.recommendation_memo, "
            "p.created_at "
            "FROM shadow_perf_rolling p "
            "LEFT JOIN shadow_variants v ON v.variant_id = p.variant_id "
            "WHERE p.window_days=? AND p.as_of_day=? "
            "ORDER BY p.variant_id",
            (window, latest),
        ).fetchall()
        out = [dict(r) for r in rows]
        return {
            "success": True,
            "window_days": window,
            "as_of_day": latest,
            "rows": out,
        }
    finally:
        conn.close()

# ===== [SHADOW_API_V1] END =====

'''

    # 6. Reconstruire le contenu
    new_lines = lines[:insert_after_idx + 1] + block.split("\n") + lines[insert_after_idx + 1:]
    new_src = "\n".join(new_lines)

    # 7. Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = API + ".bak." + ts
    shutil.copy2(API, bak)
    log("[OK] backup : " + bak)

    # 8. Ecriture temp + validation
    tmp = API + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_src)

    try:
        with open(tmp, "rb") as f:
            d = f.read()
        non_ascii = sum(1 for b in d if b > 127)
        log("[CHECK] non-ASCII bytes : {}".format(non_ascii))
        ast.parse(d.decode("utf-8"))
        log("[CHECK] ast.parse : OK")
        py_compile.compile(tmp, doraise=True)
        log("[CHECK] py_compile : OK")
    except Exception as e:
        log("[ERR] validation echouee : " + repr(e))
        log("[ERR] rollback : suppression tmp, fichier original intact.")
        os.remove(tmp)
        sys.exit(4)

    # 9. Swap
    os.replace(tmp, API)
    log("[OK] api_server.py patche.")

    # 10. Verifications post
    with open(API, "rb") as f:
        d2 = f.read()
    if MARKER_BEGIN.encode() in d2 and MARKER_END.encode() in d2:
        log("[OK] markers BEGIN + END verifies dans le fichier.")
    else:
        log("[WARN] markers non trouves apres swap !")

    log("")
    log("=" * 78)
    log("PATCH [SHADOW_API_V1] DONE")
    log("=" * 78)
    log("Backup     : " + bak)
    log("Routes ajoutees :")
    log("  GET /api/shadow/variants")
    log("  GET /api/shadow/perf-rolling?window=30")
    log("")
    log("Prochaine etape : redemarrer uvicorn pour charger les nouvelles routes.")


if __name__ == "__main__":
    main()



===== nextones-install-shadow-hook-v1.py =====

"""
nextones-install-shadow-hook-v1.py - Phase 9.4
Patch chirurgical api_server.py : insere appel shadow_hook.run_shadow_cycle()
juste avant le return final de execute_cycle (L897).

Idempotent (skip si marker [SHADOW_HOOK_V1] present).
Backup .py.bak.<timestamp>.
Validation ast.parse + py_compile post-patch.
"""
import os
import sys
import time
import ast
import py_compile
import shutil

FPATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
MARKER = "[SHADOW_HOOK_V1] BEGIN"

# Anchor : derniere ligne du bloc HISTORY_SNAPSHOT_V1 (fin du commentaire)
ANCHOR = "        # ===== /[HISTORY_SNAPSHOT_V1] =====\n        return {\"success\": True, \"cycle_result\": result}"

# Bloc a inserer ENTRE les 2 lignes du anchor (indentation 8 espaces)
HOOK_BLOCK = '''        # ===== [SHADOW_HOOK_V1] BEGIN =====
        # Phase 9.4 - Jalon 9 Shadow Overlap : engine + fills + diff_log post-cycle
        # Safe-fail : toute exception loggee, ne casse JAMAIS le return.
        try:
            import shadow_hook as _sh_v1
            _sh_res_v1 = _sh_v1.run_shadow_cycle(
                db_path=r"DB_PATH_PLACEHOLDER",
                cycle_id=_cid_hsv1,
                prev_cycle_id=None,
            )
            print(f"[SHADOW_HOOK_V1] result={_sh_res_v1}")
        except Exception as _e_sh_v1:
            print(f"[SHADOW_HOOK_V1] outer error: {_e_sh_v1}")
        # ===== [SHADOW_HOOK_V1] END =====
'''

HOOK_BLOCK = HOOK_BLOCK.replace("DB_PATH_PLACEHOLDER", DB_PATH)


def main():
    if not os.path.exists(FPATH):
        print(f"[ERR] fichier introuvable : {FPATH}")
        sys.exit(1)

    # Cleanup orphan .tmp si run precedent foire
    tmp_orphan = FPATH + ".tmp"
    if os.path.exists(tmp_orphan):
        os.remove(tmp_orphan)
        print(f"[cleanup] {tmp_orphan} (orphan)")

    with open(FPATH, "rb") as f:
        raw = f.read()
    src = raw.decode("utf-8-sig", errors="replace")

    # Idempotence
    if MARKER in src:
        print(f"[SKIP] marker {MARKER} deja present dans {FPATH}")
        sys.exit(0)

    # Verif anchor present
    if ANCHOR not in src:
        print(f"[ERR] anchor introuvable. Verifier L893-L897 manuellement.")
        sys.exit(2)

    # Backup
    ts = int(time.time())
    bak = f"{FPATH}.bak.{ts}"
    shutil.copy2(FPATH, bak)
    print(f"[backup] {bak}")

    # Patch : replace ANCHOR (= 2 lignes) par : ligne1 ANCHOR + HOOK_BLOCK + ligne2 ANCHOR
    # ANCHOR = HISTORY_SNAPSHOT_V1 closing comment + return
    # On insere HOOK_BLOCK entre les 2 lignes du ANCHOR.
    replacement = (
        "        # ===== /[HISTORY_SNAPSHOT_V1] =====\n"
        + HOOK_BLOCK
        + "        return {\"success\": True, \"cycle_result\": result}"
    )
    if src.count(ANCHOR) != 1:
        print(f"[ERR] ANCHOR count = {src.count(ANCHOR)} (attendu 1)")
        sys.exit(7)
    new_src = src.replace(ANCHOR, replacement)
    anchor_return = "        return {\"success\": True, \"cycle_result\": result}"

    # Verif marker bien injecte
    if MARKER not in new_src:
        print(f"[ERR] marker non injecte post-patch.")
        sys.exit(3)

    # Verif compte d'occurrences anchor_return : doit etre identique +/- 0
    if new_src.count(anchor_return) != src.count(anchor_return):
        print(f"[ERR] count return divergent : src={src.count(anchor_return)} new={new_src.count(anchor_return)}")
        sys.exit(4)

    # Write
    tmp = FPATH + ".tmp"
    with open(tmp, "wb") as f:
        f.write(new_src.encode("utf-8"))

    # Validation stricte
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print(f"[ERR] ast.parse FAIL : {e}")
        os.remove(tmp)
        sys.exit(5)

    try:
        py_compile.compile(tmp, doraise=True)
    except py_compile.PyCompileError as e:
        print(f"[ERR] py_compile FAIL : {e}")
        os.remove(tmp)
        sys.exit(6)

    # Atomic replace
    shutil.move(tmp, FPATH)

    # Stats
    n_lines_added = HOOK_BLOCK.count("\n")
    print(f"[OK] patch applique. +{n_lines_added} lignes injectees.")
    print(f"[OK] marker {MARKER} present.")
    print(f"[OK] ast.parse + py_compile OK.")
    print(f"\nNext step : redemarrer uvicorn pour activer le hook.")


if __name__ == "__main__":
    main()



===== nextones-install-shadow-schema-v1.py =====

"""
JALON 9 - Phase 9.1 - Install shadow overlap schema + seed 4 variants.

Tables creees :
  1. shadow_variants            (definition des variants + settings_json)
  2. shadow_cycle_snapshots     (snapshot NAV/cash/positions par cycle x variant)
  3. shadow_orders              (orders shadow non executes)
  4. shadow_fills               (fills shadow simules)
  5. shadow_diff_log            (diff per cycle vs prod)
  6. shadow_perf_rolling        (perf 7j/30j/90j + recommandation + memo LLM)

Indexes : 5 indexes pour performance des queries.

Seed 4 variants :
  - prod              (ref, settings courants)
  - tight_conv        (conv_thresh 0.65 + forced_exit_sc 0.40)
  - loose_score       (score_cutoff 0.20 au lieu de 0.30)
  - defensive_crypto  (cr_buy_mult 0.4, cr_sell_mult 1.8)

Idempotent :
  - CREATE TABLE IF NOT EXISTS
  - INSERT OR IGNORE pour les variants (sur name unique)
  - Verification post-execution

Usage :
  py -3.13 .\\nextones-install-shadow-schema-v1.py --dry-run
  py -3.13 .\\nextones-install-shadow-schema-v1.py --apply
"""
import sqlite3
import os
import sys
import argparse
import json
from datetime import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB_FILE = os.path.join(DB, "thesium.db")


SCHEMA_SQL = [
    # 1. shadow_variants
    """CREATE TABLE IF NOT EXISTS shadow_variants (
        variant_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        settings_json TEXT NOT NULL,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",

    # 2. shadow_cycle_snapshots
    """CREATE TABLE IF NOT EXISTS shadow_cycle_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle_id TEXT NOT NULL,
        variant_id INTEGER NOT NULL,
        day_t TEXT NOT NULL,
        nav REAL NOT NULL,
        cash REAL NOT NULL,
        n_positions INTEGER NOT NULL,
        invested_pct REAL NOT NULL,
        regime TEXT,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(cycle_id, variant_id),
        FOREIGN KEY(variant_id) REFERENCES shadow_variants(variant_id)
    )""",

    # 3. shadow_orders
    """CREATE TABLE IF NOT EXISTS shadow_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle_id TEXT NOT NULL,
        variant_id INTEGER NOT NULL,
        ticker TEXT NOT NULL,
        side TEXT NOT NULL,
        qty REAL NOT NULL,
        qty_current REAL,
        target_weight_pct REAL,
        convergence_pct REAL,
        forced_exit INTEGER DEFAULT 0,
        sizing_multiplier REAL DEFAULT 1.0,
        decision TEXT NOT NULL,
        rejection_reason TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY(variant_id) REFERENCES shadow_variants(variant_id)
    )""",

    # 4. shadow_fills
    """CREATE TABLE IF NOT EXISTS shadow_fills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle_id TEXT NOT NULL,
        variant_id INTEGER NOT NULL,
        shadow_order_id INTEGER NOT NULL,
        ticker TEXT NOT NULL,
        side TEXT NOT NULL,
        fill_price REAL NOT NULL,
        fill_quantity REAL NOT NULL,
        fees REAL NOT NULL DEFAULT 0,
        slippage_bps REAL NOT NULL DEFAULT 0,
        notional REAL NOT NULL,
        fill_day TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY(shadow_order_id) REFERENCES shadow_orders(id)
    )""",

    # 5. shadow_diff_log
    """CREATE TABLE IF NOT EXISTS shadow_diff_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle_id TEXT NOT NULL,
        variant_id INTEGER NOT NULL,
        day_t TEXT NOT NULL,
        n_orders_variant INTEGER NOT NULL DEFAULT 0,
        n_orders_prod INTEGER NOT NULL DEFAULT 0,
        n_blocked_by_convergence INTEGER NOT NULL DEFAULT 0,
        notional_variant REAL NOT NULL DEFAULT 0,
        notional_prod REAL NOT NULL DEFAULT 0,
        pnl_variant_cycle REAL DEFAULT 0,
        pnl_prod_cycle REAL DEFAULT 0,
        tickers_only_variant_json TEXT,
        tickers_only_prod_json TEXT,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(cycle_id, variant_id)
    )""",

    # 6. shadow_perf_rolling
    """CREATE TABLE IF NOT EXISTS shadow_perf_rolling (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        variant_id INTEGER NOT NULL,
        window_days INTEGER NOT NULL,
        as_of_day TEXT NOT NULL,
        nav_variant REAL,
        nav_prod REAL,
        return_variant_pct REAL,
        return_prod_pct REAL,
        delta_pct REAL,
        sharpe_variant REAL,
        sharpe_prod REAL,
        max_dd_variant_pct REAL,
        max_dd_prod_pct REAL,
        n_cycles INTEGER,
        n_orders_variant INTEGER,
        n_orders_prod INTEGER,
        significance_pvalue REAL,
        recommendation TEXT,
        recommendation_memo TEXT,
        memo_source TEXT,
        memo_generated_at TEXT,
        memo_cost_usd REAL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(variant_id, window_days, as_of_day)
    )""",
]


INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_shadow_orders_cycle_variant ON shadow_orders(cycle_id, variant_id)",
    "CREATE INDEX IF NOT EXISTS idx_shadow_fills_cycle_variant ON shadow_fills(cycle_id, variant_id)",
    "CREATE INDEX IF NOT EXISTS idx_shadow_diff_day ON shadow_diff_log(day_t, variant_id)",
    "CREATE INDEX IF NOT EXISTS idx_shadow_perf_asof ON shadow_perf_rolling(as_of_day, variant_id, window_days)",
    "CREATE INDEX IF NOT EXISTS idx_shadow_perf_reco ON shadow_perf_rolling(recommendation, as_of_day)",
]


# Seed 4 variants
SEED_VARIANTS = [
    {
        "name": "prod",
        "description": "Reference - settings prod actuels",
        "settings": {
            "conv_thresh": 0.60,
            "forced_exit_sc": 0.33,
            "eq_buy_mult": 1.0,
            "eq_sell_mult": 1.0,
            "cr_buy_mult": 0.7,
            "cr_sell_mult": 1.5,
            "score_cutoff": 0.30,
        },
    },
    {
        "name": "tight_conv",
        "description": "Convergence stricte - filtre signaux faibles",
        "settings": {
            "conv_thresh": 0.65,
            "forced_exit_sc": 0.40,
            "eq_buy_mult": 1.0,
            "eq_sell_mult": 1.0,
            "cr_buy_mult": 0.7,
            "cr_sell_mult": 1.5,
            "score_cutoff": 0.30,
        },
    },
    {
        "name": "loose_score",
        "description": "Score cutoff relache - plus d opportunites (test alloc 27% prod)",
        "settings": {
            "conv_thresh": 0.60,
            "forced_exit_sc": 0.33,
            "eq_buy_mult": 1.0,
            "eq_sell_mult": 1.0,
            "cr_buy_mult": 0.7,
            "cr_sell_mult": 1.5,
            "score_cutoff": 0.20,
        },
    },
    {
        "name": "defensive_crypto",
        "description": "Reduit exposition crypto (cr_buy 0.4, cr_sell 1.8)",
        "settings": {
            "conv_thresh": 0.60,
            "forced_exit_sc": 0.33,
            "eq_buy_mult": 1.0,
            "eq_sell_mult": 1.0,
            "cr_buy_mult": 0.4,
            "cr_sell_mult": 1.8,
            "score_cutoff": 0.30,
        },
    },
]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true",
                   help="executer creation + seed (sinon dry-run)")
    p.add_argument("--dry-run", action="store_true", help="dry-run (defaut)")
    return p.parse_args()


def main():
    args = parse_args()
    apply_changes = bool(args.apply)
    mode = "APPLY" if apply_changes else "DRY-RUN"

    print("=" * 78)
    print("JALON 9 Phase 9.1 - Install shadow overlap schema")
    print("MODE :", mode)
    print("DB   :", DB_FILE)
    print("=" * 78)

    if not os.path.exists(DB_FILE):
        print("DB introuvable :", DB_FILE)
        sys.exit(1)

    con = sqlite3.connect(DB_FILE, timeout=30.0)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Step 1 : inventaire pre-install
    print("\n[1/5] Inventaire pre-install")
    expected_tables = [
        "shadow_variants",
        "shadow_cycle_snapshots",
        "shadow_orders",
        "shadow_fills",
        "shadow_diff_log",
        "shadow_perf_rolling",
    ]
    existing = set(r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'shadow_%'"
    ).fetchall())
    for t in expected_tables:
        status = "EXISTS" if t in existing else "MISSING"
        n = "-"
        if t in existing:
            try:
                n = cur.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
            except sqlite3.Error:
                n = "ERR"
        print("  {:30s} {:8s} rows={}".format(t, status, n))

    # Step 2 : plan
    print("\n[2/5] Plan d execution")
    print("  Tables a creer (CREATE IF NOT EXISTS) :", len(SCHEMA_SQL))
    print("  Indexes a creer (CREATE IF NOT EXISTS) :", len(INDEXES_SQL))
    print("  Variants a seeder (INSERT OR IGNORE) :", len(SEED_VARIANTS))
    for v in SEED_VARIANTS:
        print("    - {:20s} : {}".format(v["name"], v["description"]))

    if not apply_changes:
        print("\n[DRY-RUN] Aucune execution. Relancer avec --apply.")
        con.close()
        return

    # Step 3 : creation tables
    print("\n[3/5] Creation tables")
    for sql in SCHEMA_SQL:
        # extraire nom table
        first_line = sql.strip().split("\n")[0]
        tname = first_line.split("IF NOT EXISTS")[1].split("(")[0].strip()
        try:
            cur.execute(sql)
            print("  CREATE", tname, "OK")
        except sqlite3.Error as e:
            print("  CREATE", tname, "ERR :", e)
            con.rollback()
            con.close()
            sys.exit(2)

    # Step 4 : creation indexes
    print("\n[4/5] Creation indexes")
    for sql in INDEXES_SQL:
        idx_name = sql.split("IF NOT EXISTS")[1].split("ON")[0].strip()
        try:
            cur.execute(sql)
            print("  INDEX", idx_name, "OK")
        except sqlite3.Error as e:
            print("  INDEX", idx_name, "ERR :", e)
            con.rollback()
            con.close()
            sys.exit(2)

    # Step 5 : seed variants
    print("\n[5/5] Seed variants")
    inserted = 0
    skipped = 0
    for v in SEED_VARIANTS:
        try:
            cur.execute(
                "INSERT OR IGNORE INTO shadow_variants (name, description, settings_json, active) "
                "VALUES (?, ?, ?, 1)",
                (v["name"], v["description"], json.dumps(v["settings"]))
            )
            if cur.rowcount > 0:
                inserted += 1
                print("  INSERT", v["name"], "OK")
            else:
                skipped += 1
                print("  SKIP  ", v["name"], "(deja present)")
        except sqlite3.Error as e:
            print("  INSERT", v["name"], "ERR :", e)
            con.rollback()
            con.close()
            sys.exit(2)

    con.commit()
    print("\n  Inserted :", inserted, " Skipped :", skipped)

    # Verification post-install
    print("\n[VERIFICATION post-apply]")
    for t in expected_tables:
        try:
            n = cur.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
            print("  {:30s} rows={}".format(t, n))
        except sqlite3.Error as e:
            print("  {:30s} ERR : {}".format(t, e))

    print("\n  Variants actifs :")
    rows = cur.execute(
        "SELECT variant_id, name, description, settings_json, active "
        "FROM shadow_variants WHERE active=1 ORDER BY variant_id"
    ).fetchall()
    for r in rows:
        s = json.loads(r["settings_json"])
        print("    id={} {:18s} conv={} fe_sc={} cr_buy={} score={}".format(
            r["variant_id"], r["name"],
            s["conv_thresh"], s["forced_exit_sc"],
            s["cr_buy_mult"], s["score_cutoff"]
        ))

    con.close()
    print("\n" + "=" * 78)
    print("DONE - Phase 9.1 install complete")
    print("Next : Phase 9.2 shadow_engine.py MVP")
    print("=" * 78)


if __name__ == "__main__":
    main()



===== nextones-install-shadow-ui-v1.py =====

# -*- coding: utf-8 -*-
"""
Installe le Patch 2 UI Shadow Variants (Jalon 9.6) :
  - index.html : <section id="shadow-variants-card"> avant <h2>Backtest Portfolio</h2>
  - app.js     : fonction renderShadowVariants() + hook tab change + bouton Rafraichir
Markers : [SHADOW_UI_V1] BEGIN / END
Idempotent : skip si marker present.
Backup .bak.<timestamp> avant ecriture.
ASCII pur, validation stricte avant write.
"""
import os
import shutil
from datetime import datetime

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
HTML = os.path.join(ROOT, "index.html")
JS = os.path.join(ROOT, "app.js")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

MARK_HTML_BEGIN = "<!-- [SHADOW_UI_V1] BEGIN -->"
MARK_HTML_END = "<!-- [SHADOW_UI_V1] END -->"
MARK_JS_BEGIN = "/* [SHADOW_UI_V1] BEGIN */"
MARK_JS_END = "/* [SHADOW_UI_V1] END */"

# -----------------------------------------------------------------------------
# HTML bloc a inserer juste AVANT <h2>Backtest Portfolio</h2>
# -----------------------------------------------------------------------------
HTML_BLOCK = """{begin}
      <div id="shadow-variants-card" class="card" style="margin-bottom:16px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <h2 style="margin:0;">Shadow Variants - Perf J-30</h2>
          <button id="shadow-refresh-btn" class="pplx-refresh-btn" type="button">Rafraichir</button>
        </div>
        <div id="shadow-variants-meta" style="font-size:12px;opacity:0.75;margin-bottom:8px;">Chargement...</div>
        <div style="overflow-x:auto;">
          <table id="shadow-variants-table" style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead>
              <tr style="text-align:left;border-bottom:1px solid var(--border-color,#444);">
                <th style="padding:6px 8px;">Variant</th>
                <th style="padding:6px 8px;text-align:right;">Return</th>
                <th style="padding:6px 8px;text-align:right;">Delta</th>
                <th style="padding:6px 8px;text-align:right;">Sharpe</th>
                <th style="padding:6px 8px;text-align:right;">Max DD</th>
                <th style="padding:6px 8px;text-align:right;">N Orders</th>
                <th style="padding:6px 8px;text-align:center;">Reco</th>
              </tr>
            </thead>
            <tbody id="shadow-variants-tbody">
              <tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Chargement...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      {end}
""".format(begin=MARK_HTML_BEGIN, end=MARK_HTML_END)

# -----------------------------------------------------------------------------
# JS bloc a inserer en fin de app.js (auto-init via DOMContentLoaded + tab hook)
# -----------------------------------------------------------------------------
JS_BLOCK = r"""
""" + MARK_JS_BEGIN + r"""
(function(){
  function fmtPct(v){
    if (v === null || v === undefined || isNaN(v)) return "-";
    var sign = v > 0 ? "+" : "";
    return sign + Number(v).toFixed(3).replace(".",",") + "%";
  }
  function fmtNum(v, dec){
    if (v === null || v === undefined || isNaN(v)) return "-";
    return Number(v).toFixed(dec === undefined ? 2 : dec).replace(".",",");
  }
  function recoBadge(reco){
    var color = "#888";
    var bg = "rgba(136,136,136,0.15)";
    var label = reco || "neutral";
    if (reco === "champion"){ color = "#22c55e"; bg = "rgba(34,197,94,0.15)"; }
    else if (reco === "reject"){ color = "#ef4444"; bg = "rgba(239,68,68,0.15)"; }
    return '<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;color:'+color+';background:'+bg+';">'+label+'</span>';
  }
  async function renderShadowVariants(){
    var meta = document.getElementById("shadow-variants-meta");
    var tbody = document.getElementById("shadow-variants-tbody");
    if (!meta || !tbody) return;
    meta.textContent = "Chargement...";
    tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Chargement...</td></tr>';
    try {
      var perfResp = await apiFetch("/api/shadow/perf-rolling?window=30");
      var perf = await perfResp.json();
      if (!perf || !perf.success){
        meta.textContent = "Erreur API perf-rolling";
        tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;color:#ef4444;">Erreur : '+(perf && perf.error ? perf.error : "inconnu")+'</td></tr>';
        return;
      }
      var rows = perf.rows || [];
      meta.textContent = "Fenetre " + perf.window_days + "j | as_of_day=" + perf.as_of_day + " | " + rows.length + " variants";
      if (rows.length === 0){
        tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Aucune donnee</td></tr>';
        return;
      }
      var html = "";
      rows.forEach(function(r){
        html += '<tr style="border-bottom:1px solid var(--border-color,#333);">';
        html += '<td style="padding:6px 8px;font-weight:600;">'+(r.variant_name || r.variant_id || "?")+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtPct(r.ret_pct)+'</td>';
        var deltaColor = r.delta_pct > 0 ? "#22c55e" : (r.delta_pct < 0 ? "#ef4444" : "inherit");
        html += '<td style="padding:6px 8px;text-align:right;color:'+deltaColor+';">'+fmtPct(r.delta_pct)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtNum(r.sharpe,2)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtPct(r.max_dd_pct)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+(r.n_orders !== undefined ? r.n_orders : "-")+'</td>';
        html += '<td style="padding:6px 8px;text-align:center;">'+recoBadge(r.reco)+'</td>';
        html += '</tr>';
      });
      tbody.innerHTML = html;
    } catch(e){
      meta.textContent = "Erreur reseau";
      tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;color:#ef4444;">Exception : '+e.message+'</td></tr>';
    }
  }
  window.renderShadowVariants = renderShadowVariants;

  function bindShadowUI(){
    var btn = document.getElementById("shadow-refresh-btn");
    if (btn && !btn.dataset.shadowBound){
      btn.dataset.shadowBound = "1";
      btn.addEventListener("click", renderShadowVariants);
    }
    var tabLink = document.querySelector('a[data-tab="backtest"]');
    if (tabLink && !tabLink.dataset.shadowBound){
      tabLink.dataset.shadowBound = "1";
      tabLink.addEventListener("click", function(){
        setTimeout(renderShadowVariants, 120);
      });
    }
    if (document.querySelector('#tab-backtest.active') || (location.hash === "#backtest")){
      renderShadowVariants();
    }
  }
  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", bindShadowUI);
  } else {
    bindShadowUI();
  }
})();
""" + MARK_JS_END + r"""
"""

# -----------------------------------------------------------------------------
# Patch HTML
# -----------------------------------------------------------------------------
def patch_html():
    with open(HTML, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()
    if MARK_HTML_BEGIN in src:
        print("[SKIP] HTML marker deja present")
        return False
    anchor = "<h2>Backtest Portfolio</h2>"
    if anchor not in src:
        print("[ERR] anchor HTML introuvable :", anchor)
        return False
    bak = HTML + ".bak." + TS
    shutil.copy2(HTML, bak)
    print("[BAK] HTML ->", bak)
    new = src.replace(anchor, HTML_BLOCK + "      " + anchor, 1)
    with open(HTML, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("[OK] HTML patche, +{} chars".format(len(new) - len(src)))
    return True

# -----------------------------------------------------------------------------
# Patch JS
# -----------------------------------------------------------------------------
def patch_js():
    with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()
    if MARK_JS_BEGIN in src:
        print("[SKIP] JS marker deja present")
        return False
    bak = JS + ".bak." + TS
    shutil.copy2(JS, bak)
    print("[BAK] JS ->", bak)
    new = src.rstrip() + "\n\n" + JS_BLOCK + "\n"
    with open(JS, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("[OK] JS patche, +{} chars".format(len(new) - len(src)))
    return True

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("INSTALL SHADOW UI V1 (Jalon 9.6 Patch 2)")
    print("=" * 70)
    h = patch_html()
    j = patch_js()
    print()
    print("HTML patched :", h)
    print("JS   patched :", j)
    print()
    print("Next steps :")
    print("  1. Hard reload navigateur (Ctrl+Shift+R) sur l'onglet Backtest")
    print("  2. Verifier card 'Shadow Variants - Perf J-30' visible")
    print("  3. Cliquer 'Rafraichir' -> 4 lignes (v1 v2 v3 v4)")
    print("  4. v2 tight_conv doit etre en badge vert 'champion' +3,931%")
    print("DONE")



===== nextones-install-shadow-wiring.py =====

# -*- coding: utf-8 -*-
# [NEXTONES-INSTALL-SHADOW-WIRING-V1]
# Phase 3A : cable execute_shadow() en parallele de l'insertion d'ordre
# dans execution_engine.create_and_execute_order().
#
# Point d'insertion :
#   - Ancre : la ligne contenant
#         conn.execute("UPDATE orders SET quantity = ? WHERE id = ?",
#                      (approved_qty, order_id))
#   - Bloc shadow injecte JUSTE APRES (entre UPDATE et le return final)
#
# A ce point :
#   - risk_result["approved"] == True (verifie L1247-L1252)
#   - approved_qty defini (L1254)
#   - order_id defini (L1232)
#   - _rv2_ticker defini si la branche RISK_V2 L1198 a tourne (sinon None)
#   - effective_price defini (L1187)
#
# Comportement :
#   - GARDE bridge_config.BROKER_SHADOW_ENABLED
#   - Charge nextones-broker-shadow-executor.py par chemin de fichier
#     (meme pattern que _nx_broker_check_load dans risk_pretrade.py)
#   - Appelle execute_shadow(thesium_ticker, side, qty, entry_price=..., cycle_id=order_id_str)
#   - FIRE-AND-FORGET : tout est dans un try/except, jamais d'exception remontee
#   - Trace warning stderr en cas d'echec
#
# Garde-fous :
#   - Backup .bak.{ts} de execution_engine.py
#   - Idempotent : refuse si marker [NEXTONES-SHADOW-EXEC-V1] deja present
#   - ast.parse + py_compile sur le resultat
#   - Smoke import via subprocess (import execution_engine)
#   - Rollback auto si l'une de ces validations echoue
#
# Modes :
#   py -3.13 nextones-install-shadow-wiring.py --dry-run
#   py -3.13 nextones-install-shadow-wiring.py
#   py -3.13 nextones-install-shadow-wiring.py --rollback

import argparse
import ast
import os
import py_compile
import re
import shutil
import subprocess
import sys
import time

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(PROD_DIR, "execution_engine.py")
MARKER = "[NEXTONES-SHADOW-EXEC-V1]"

# Ancre : ligne UPDATE orders SET quantity
# (regex tolerant aux espaces et au formatage)
ANCHOR_RE = re.compile(
    r'conn\.execute\(\s*"UPDATE\s+orders\s+SET\s+quantity\s*=\s*\?\s+WHERE\s+id\s*=\s*\?"',
    re.IGNORECASE,
)


SHADOW_BLOCK = '''
    # [NEXTONES-SHADOW-EXEC-V1] - shadow executor en parallele (fire-and-forget)
    try:
        import bridge_config as _bc_sh
        if getattr(_bc_sh, "BROKER_SHADOW_ENABLED", False):
            import importlib.util as _ilu_sh
            import os as _os_sh
            _p_sh = _os_sh.path.join(
                _os_sh.path.dirname(_os_sh.path.abspath(__file__)),
                "nextones-broker-shadow-executor.py",
            )
            if _os_sh.path.exists(_p_sh):
                _spec_sh = _ilu_sh.spec_from_file_location(
                    "_nx_shadow_exec", _p_sh
                )
                if _spec_sh is not None and _spec_sh.loader is not None:
                    _mod_sh = _ilu_sh.module_from_spec(_spec_sh)
                    _spec_sh.loader.exec_module(_mod_sh)
                    _ticker_sh = None
                    try:
                        _ticker_sh = _rv2_ticker
                    except NameError:
                        _row_sh = conn.execute(
                            "SELECT ticker FROM instruments WHERE id = ?",
                            (instrument_id,),
                        ).fetchone()
                        _ticker_sh = _row_sh[0] if _row_sh else None
                    if _ticker_sh:
                        _mod_sh.execute_shadow(
                            thesium_ticker=_ticker_sh,
                            side=side,
                            qty=float(approved_qty),
                            cycle_id="order_id=" + str(order_id),
                            entry_price=float(effective_price),
                        )
    except Exception as _sh_e:
        try:
            import sys as _sh_sys
            print(
                "[WARN] [NEXTONES-SHADOW-EXEC-V1] " + str(_sh_e)[:200],
                file=_sh_sys.stderr,
            )
        except Exception:
            pass
'''


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def read_src():
    with open(TARGET, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_src(content):
    with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def find_insertion_point(src):
    """
    Retourne l'index char juste apres la ligne contenant l'ancre UPDATE.
    On va jusqu'a la fin du statement (parenthese fermante du conn.execute).
    """
    m = ANCHOR_RE.search(src)
    if not m:
        return None, "ancre UPDATE orders SET quantity introuvable"

    # Trouver la fin du statement : on cherche la fin de la ligne contenant
    # ").lastrowid" n'est PAS notre cas (c'est INSERT). Ici c'est juste
    # un conn.execute(...) sans .lastrowid. On suit les parentheses.
    start = m.start()
    # Compteur parentheses depuis le debut du match
    depth = 0
    i = start
    n = len(src)
    while i < n:
        ch = src[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                # On est sur la parenthese fermante du conn.execute(...)
                # Aller jusqu'a la fin de la ligne (newline inclus)
                j = src.find("\n", i)
                if j == -1:
                    return n, None
                return j + 1, None
        i += 1
    return None, "parenthese fermante non trouvee"


def validate_python(src, label):
    try:
        ast.parse(src)
    except SyntaxError as e:
        return False, f"{label} ast.parse: {e}"
    return True, "OK"


def smoke_import():
    """Verifie que execution_engine s'importe sans erreur."""
    code = (
        "import sys\n"
        f"sys.path.insert(0, r'{PROD_DIR}')\n"
        "import execution_engine\n"
        "print('SMOKE_IMPORT_OK')\n"
    )
    res = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=60,
    )
    ok = (res.returncode == 0) and ("SMOKE_IMPORT_OK" in res.stdout)
    return ok, (res.stdout + res.stderr).strip()


def do_apply(dry_run):
    if not os.path.exists(TARGET):
        log(f"[ERR] {TARGET} introuvable")
        sys.exit(2)
    src = read_src()
    log(f"Fichier cible : {TARGET} ({len(src)} bytes)")

    if MARKER in src:
        log(f"[OK] marker {MARKER} deja present -> rien a faire (idempotent)")
        return

    ip, err = find_insertion_point(src)
    if err:
        log(f"[ERR] {err}")
        sys.exit(3)
    # Compute ligne approximative
    line_no = src.count("\n", 0, ip) + 1
    log(f"Point d'insertion : char {ip} (apres L{line_no - 1})")

    new_src = src[:ip] + SHADOW_BLOCK + src[ip:]

    ok, msg = validate_python(new_src, "post-patch")
    if not ok:
        log(f"[ERR] {msg}")
        sys.exit(4)
    log("Validation ast.parse : OK")

    if dry_run:
        log("DRY-RUN : extrait du bloc qui serait insere :")
        print("-" * 60)
        # Affiche 20 lignes autour du point d'insertion (avant + bloc + apres)
        before = new_src[max(0, ip - 200):ip]
        block_end = ip + len(SHADOW_BLOCK)
        after = new_src[block_end:block_end + 200]
        print("...AVANT (200 derniers chars)...")
        print(before)
        print(">>> BLOC INSERE <<<")
        print(SHADOW_BLOCK)
        print("...APRES (200 premiers chars)...")
        print(after)
        print("-" * 60)
        log("DRY-RUN termine, aucune ecriture.")
        return

    # Backup + ecriture
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = TARGET + f".bak.{ts}"
    shutil.copy2(TARGET, backup)
    log(f"[OK] backup -> {backup}")

    write_src(new_src)
    log("[OK] patch applique")

    # py_compile sur le fichier ecrit
    try:
        py_compile.compile(TARGET, doraise=True)
        log("[OK] py_compile")
    except Exception as e:
        log(f"[ERR] py_compile : {e}")
        shutil.copy2(backup, TARGET)
        log("[OK] rollback effectue")
        sys.exit(5)

    # Smoke import
    ok, info = smoke_import()
    if not ok:
        log(f"[ERR] smoke import : {info}")
        shutil.copy2(backup, TARGET)
        log("[OK] rollback effectue")
        sys.exit(6)
    log(f"[OK] smoke import : {info.splitlines()[-1]}")

    log("=" * 60)
    log("PHASE 3A SHADOW WIRING INSTALLE")
    log("=" * 60)
    log(f"Backup : {backup}")
    log(f"Marker : {MARKER}")
    log("")
    log("Etape suivante :")
    log("  py -3.13 nextones-validate-shadow-wired.py")


def do_rollback():
    """
    Restaure le backup le plus recent .bak.* de execution_engine.py.
    """
    d = os.path.dirname(TARGET)
    base = os.path.basename(TARGET)
    candidates = sorted(
        [f for f in os.listdir(d) if f.startswith(base + ".bak.")],
        reverse=True,
    )
    if not candidates:
        log("[ERR] aucun backup execution_engine.py.bak.* trouve")
        sys.exit(7)
    backup = os.path.join(d, candidates[0])
    shutil.copy2(backup, TARGET)
    log(f"[OK] rollback depuis {backup}")
    # Verif rapide
    ok, info = smoke_import()
    if ok:
        log("[OK] smoke import post-rollback")
    else:
        log(f"[WARN] smoke post-rollback : {info}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    args = ap.parse_args()
    if args.rollback:
        do_rollback()
    else:
        do_apply(dry_run=args.dry_run)


if __name__ == "__main__":
    main()



===== nextones-validate-shadow-hook-v1.py =====

"""Validation post-patch : verifie injection SHADOW_HOOK_V1 dans api_server.py.

1. Marker [SHADOW_HOOK_V1] BEGIN present
2. Bloc bien positionne entre /[HISTORY_SNAPSHOT_V1] et return
3. shadow_hook importable
4. Affiche le bloc injecte (L880-L915)
"""
import os, sys, ast

FPATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
sys.path.insert(0, ROOT)

with open(FPATH, "rb") as f:
    src = f.read().decode("utf-8-sig", errors="replace")

print("=== 1. Marker present ===")
print(f"  [SHADOW_HOOK_V1] BEGIN : count={src.count('[SHADOW_HOOK_V1] BEGIN')}")
print(f"  [SHADOW_HOOK_V1] END   : count={src.count('[SHADOW_HOOK_V1] END')}")
print(f"  shadow_hook import     : count={src.count('import shadow_hook')}")

print("\n=== 2. Bloc autour du SHADOW_HOOK_V1 ===")
lines = src.split("\n")
for i, ln in enumerate(lines, 1):
    if "[SHADOW_HOOK_V1] BEGIN" in ln:
        # Print 16 lines around
        for j in range(max(0, i-3), min(len(lines), i+15)):
            print(f"  L{j+1:4d}: {lines[j]}")
        break

print("\n=== 3. AST parse api_server.py ===")
try:
    ast.parse(src)
    print("  OK")
except SyntaxError as e:
    print(f"  FAIL: {e}")

print("\n=== 4. shadow_hook importable ===")
try:
    import shadow_hook
    print(f"  OK : module @ {shadow_hook.__file__}")
    print(f"  run_shadow_cycle present : {hasattr(shadow_hook, 'run_shadow_cycle')}")
except Exception as e:
    print(f"  FAIL : {e}")



===== nextones-validate-shadow-wired.py =====

# -*- coding: utf-8 -*-
# [NEXTONES-VALIDATE-SHADOW-WIRED-V4]
# Validation Phase 3A : V4 fait un SELL au lieu d'un BUY pour passer
# le risk check legacy de l'engine (les BUY sont bloques par single-name
# limit / sector / position limit sur les positions existantes).
# Strategie : trouve une position existante (qty > 0), fait SELL 1.

import json
import os
import sqlite3
import sys
import time

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
sys.path.insert(0, PROD_DIR)
DB = os.path.join(PROD_DIR, "thesium.db")


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


def fail(msg):
    print(f"[FAIL] {msg}")
    sys.exit(1)


def ok(msg):
    print(f"[OK] {msg}")


def col_names(con, table):
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]


def open_db():
    c = sqlite3.connect(DB, timeout=5.0)
    c.row_factory = sqlite3.Row
    return c


# ----------------------------- 1 -----------------------------
banner("[1] Verifie marker dans execution_engine.py")
ee_path = os.path.join(PROD_DIR, "execution_engine.py")
with open(ee_path, "r", encoding="utf-8-sig") as f:
    ee_src = f.read()
if "[NEXTONES-SHADOW-EXEC-V1]" not in ee_src:
    fail("marker [NEXTONES-SHADOW-EXEC-V1] absent de execution_engine.py")
ok("marker present")


# ----------------------------- 2 -----------------------------
banner("[2] Verifie bridge_config flags")
import bridge_config as bc
flags = {
    "BROKER_SHADOW_ENABLED": getattr(bc, "BROKER_SHADOW_ENABLED", None),
    "BROKER_LIVE_ENABLED": getattr(bc, "BROKER_LIVE_ENABLED", None),
    "MAX_LIVE_NAV": getattr(bc, "MAX_LIVE_NAV", None),
    "BROKER_LIVE_ACCOUNT": getattr(bc, "BROKER_LIVE_ACCOUNT", None),
}
print(json.dumps(flags, indent=2))
if not flags["BROKER_SHADOW_ENABLED"]:
    fail("BROKER_SHADOW_ENABLED != True")
if flags["BROKER_LIVE_ENABLED"]:
    fail("BROKER_LIVE_ENABLED doit etre False en Phase 3A")
ok("flags coherents (shadow on, live off)")


# ----------------------------- 3 -----------------------------
banner("[3] Snapshot broker_shadow_orders + selection position a vendre")
con = open_db()
n_before = con.execute("SELECT COUNT(*) AS n FROM broker_shadow_orders").fetchone()["n"]
print(f"  lignes broker_shadow_orders : {n_before}")

# Detecte le schema portfolio (positions)
portfolio_tables = [
    r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
        "('portfolio','positions','portfolio_positions')"
    )
]
print(f"  tables portfolio candidates : {portfolio_tables}")

# Cherche une position avec qty > 0 sur un ticker mappe au broker
# Pour AAPL on sait qu'il y a 173 units (vu dans details_json risk V2)
# On va chercher dynamiquement
positions_sql_candidates = [
    """
    SELECT i.id AS instrument_id, i.ticker, p.quantity AS qty
    FROM portfolio p
    JOIN instruments i ON i.id = p.instrument_id
    WHERE p.quantity > 1
    ORDER BY p.quantity DESC
    LIMIT 5
    """,
    """
    SELECT i.id AS instrument_id, i.ticker, p.qty AS qty
    FROM positions p
    JOIN instruments i ON i.id = p.instrument_id
    WHERE p.qty > 1
    ORDER BY p.qty DESC
    LIMIT 5
    """,
    """
    SELECT i.id AS instrument_id, i.ticker, p.quantity AS qty
    FROM portfolio_positions p
    JOIN instruments i ON i.id = p.instrument_id
    WHERE p.quantity > 1
    ORDER BY p.quantity DESC
    LIMIT 5
    """,
]

positions = []
for sql in positions_sql_candidates:
    try:
        positions = list(con.execute(sql))
        if positions:
            print(f"  source positions : {sql.strip().split(chr(10))[1].strip()}")
            break
    except sqlite3.OperationalError:
        continue

if not positions:
    # fallback : AAPL en dur (on sait qu'il y en a 173)
    print("  fallback : AAPL en dur (qty=173 connue)")
    row = con.execute("SELECT id, ticker FROM instruments WHERE ticker='AAPL'").fetchone()
    if row:
        positions = [{"instrument_id": row["id"], "ticker": row["ticker"], "qty": 173}]

if not positions:
    fail("aucune position existante trouvee pour faire un SELL")

print("  top 5 positions :")
for p in positions:
    print(f"    {p['ticker']:8} id={p['instrument_id']:4} qty={p['qty']}")

chosen = positions[0]
chosen_instrument_id = int(chosen["instrument_id"])
chosen_ticker = chosen["ticker"]
print(f"\n  selection : SELL 1 sur {chosen_ticker} (qty actuelle={chosen['qty']})")

theses_cols = col_names(con, "theses")
thesis_id = None
if "instrument_id" in theses_cols:
    row = con.execute(
        "SELECT id FROM theses WHERE instrument_id=? ORDER BY id DESC LIMIT 1",
        (chosen_instrument_id,),
    ).fetchone()
    if row:
        thesis_id = row["id"]
        print(f"  thesis_id : {thesis_id}")

if thesis_id is None:
    row = con.execute("SELECT id FROM theses ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        thesis_id = row["id"]
        print(f"  thesis_id (fallback) : {thesis_id}")

if thesis_id is None:
    fail("impossible de trouver une thesis")
thesis_id = int(thesis_id)

n_orders_before = con.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"]
print(f"  lignes orders avant : {n_orders_before}")

con.close()


# ----------------------------- 4 -----------------------------
banner("[4] Invoque create_and_execute_order (sell 1)")
for mod in list(sys.modules):
    if mod.startswith("execution_engine"):
        del sys.modules[mod]
import execution_engine as ee

call_con = open_db()
t0 = time.time()
result = ee.create_and_execute_order(
    conn=call_con,
    instrument_id=chosen_instrument_id,
    thesis_id=thesis_id,
    side="sell",
    quantity=1.0,
    order_type="market",
)
dt = time.time() - t0
try:
    call_con.commit()
except Exception:
    pass
call_con.close()

print(f"  duree appel : {dt:.3f}s")
print("  resultat complet :")
try:
    print(json.dumps(result, indent=2, default=str))
except Exception:
    print(repr(result))

if not result.get("success"):
    # Affiche le risk_check pour comprendre
    rc = result.get("risk_check", {})
    print()
    print("  ECHEC : risk_check detail :")
    print(json.dumps(rc, indent=2, default=str)[:2000])
    fail(f"create_and_execute_order a echoue : reason={result.get('reason')}")

order_id = result["order_id"]
ok(f"ordre approuve et execute order_id={order_id}")


# ----------------------------- 5 -----------------------------
banner("[5] Snapshot broker_shadow_orders apres + analyse")
time.sleep(0.5)

con = open_db()
n_after = con.execute("SELECT COUNT(*) AS n FROM broker_shadow_orders").fetchone()["n"]
print(f"  lignes broker_shadow_orders : {n_after} (avant : {n_before})")

if n_after <= n_before:
    print()
    print("--- DIAGNOSTIC : aucune ligne shadow inseree ---")
    print("L'ordre a ete approuve cote orders mais shadow n'a rien insere.")
    print("Hypotheses :")
    print(" 1) execute_shadow leve une exception silencieuse (try/except du wiring)")
    print(" 2) broker_resolver retourne unmapped pour ce ticker (policy A strict)")
    print(" 3) le bloc shadow n'est pas execute pour une raison de control flow")
    print()
    print("Inspecter manuellement execute_shadow avec :")
    print(f'  py -3.13 -c "import sys; sys.path.insert(0, r\\"{PROD_DIR}\\"); '
          f'import importlib.util as u, os; '
          f's=u.spec_from_file_location(\\"x\\", os.path.join(r\\"{PROD_DIR}\\", \\"nextones-broker-shadow-executor.py\\")); '
          f'm=u.module_from_spec(s); s.loader.exec_module(m); '
          f'print(m.execute_shadow(thesium_ticker=\\"{chosen_ticker}\\", side=\\"sell\\", '
          f'qty=1.0, cycle_id=\\"manual_test\\", entry_price=312.0))"')
    print()
    fail("aucune nouvelle ligne dans broker_shadow_orders")

ok(f"{n_after - n_before} nouvelle(s) ligne(s) shadow inseree(s)")

print()
print("Dernieres lignes broker_shadow_orders (top 3) :")
sh_cols = col_names(con, "broker_shadow_orders")
print(f"  (colonnes : {sh_cols})")
for r in con.execute("SELECT * FROM broker_shadow_orders ORDER BY id DESC LIMIT 3"):
    d = dict(r)
    for k, v in list(d.items()):
        if v is not None and len(str(v)) > 200:
            d[k] = str(v)[:200] + "..."
    print(f"  {d}")

expected_cycle = f"order_id={order_id}"
if "cycle_id" in sh_cols:
    matched = con.execute(
        "SELECT * FROM broker_shadow_orders WHERE cycle_id=? ORDER BY id DESC LIMIT 1",
        (expected_cycle,),
    ).fetchone()
    if matched is None:
        print(f"\n[WARN] Aucune ligne avec cycle_id={expected_cycle}")
    else:
        tk = matched["thesium_ticker"] if "thesium_ticker" in matched.keys() else "?"
        ok(f"correlation cycle_id OK : id={matched['id']} ticker={tk}")


# ----------------------------- 6 -----------------------------
banner("[6] Verifie cote orders (Thesium)")
o = con.execute(
    "SELECT id, instrument_id, side, quantity, status FROM orders WHERE id=?",
    (order_id,),
).fetchone()
if o is None:
    fail(f"order_id={order_id} introuvable")
print(f"  orders[{order_id}] : {dict(o)}")
ok("ordre Thesium persiste")


# ----------------------------- VERDICT -----------------------------
banner("[VERDICT] PASS - Phase 3A shadow wiring fonctionne")
print(f"  marker present dans execution_engine.py")
print(f"  flags : SHADOW=on LIVE=off MAX={flags['MAX_LIVE_NAV']}")
print(f"  shadow orders : {n_before} -> {n_after}  (+{n_after - n_before})")
print(f"  order_id Thesium : {order_id} ({chosen_ticker} sell 1)")
print(f"  cycle_id shadow attendu : {expected_cycle}")
print()
print("Etapes Phase 3 suivantes :")
print("  3B : reconciler ActivTrades vs Thesium")
print("  3C : flag bascule live + routeur live/shadow")

con.close()



===== shadow_backfill.py =====

"""
shadow_backfill.py - Phase 9.7 - Backfill historique shadow_engine + shadow_fills.

Strategie :
  1. Selectionne 1 cycle par jour (le DERNIER de chaque jour) depuis convergence_snapshots
  2. Pour chaque cycle :
     a. Lance shadow_engine (genere shadow_cycle_snapshots + shadow_orders)
     b. Lance shadow_simulate_fills (genere shadow_fills sur J+1)
  3. Stats finales : n_cycles, n_orders, n_fills total

Idempotent grace au DELETE WHERE des sous-scripts (engine + fills).
Safe-fail : log par cycle, continue si un fail.
"""
import sqlite3
import subprocess
import sys
import os
import time
import argparse

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_DEFAULT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"


def get_last_cycle_per_day(db_path, day_min=None, day_max=None):
    """Retourne liste de (day, cycle_id) : 1 cycle par jour (le plus tardif).

    Source : convergence_snapshots
    """
    conn = sqlite3.connect(db_path, timeout=30)
    cur = conn.cursor()
    sql = """
        SELECT SUBSTR(cycle_id,1,8) day, MAX(cycle_id) last_cycle
        FROM convergence_snapshots
        WHERE 1=1
    """
    params = []
    if day_min:
        sql += " AND SUBSTR(cycle_id,1,8) >= ?"
        params.append(day_min)
    if day_max:
        sql += " AND SUBSTR(cycle_id,1,8) <= ?"
        params.append(day_max)
    sql += " GROUP BY day ORDER BY day"
    cur.execute(sql, params)
    out = cur.fetchall()
    conn.close()
    return out


def run_subprocess(script_name, cycle_id, db_path, timeout=180):
    script_path = os.path.join(ROOT, script_name)
    if not os.path.exists(script_path):
        return -1, f"script not found: {script_path}"
    cmd = [sys.executable, script_path, "--cycle-id", cycle_id, "--db", db_path]
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace"
        )
        return r.returncode, (r.stderr[-300:] if r.stderr else "")
    except subprocess.TimeoutExpired:
        return -2, "TIMEOUT"
    except Exception as e:
        return -3, f"EXC {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--day-min", default=None, help="format YYYYMMDD")
    ap.add_argument("--day-max", default=None, help="format YYYYMMDD")
    ap.add_argument("--skip-fills", action="store_true",
                    help="ne lance pas shadow_simulate_fills (engine seulement)")
    args = ap.parse_args()

    print("=" * 78)
    print("SHADOW BACKFILL - Phase 9.7")
    print(f"DB      : {args.db}")
    print(f"Range   : {args.day_min or '(open)'} -> {args.day_max or '(open)'}")
    print(f"Fills   : {'SKIP' if args.skip_fills else 'YES'}")
    print("=" * 78)

    # 1. Selection cycles
    cycles = get_last_cycle_per_day(args.db, args.day_min, args.day_max)
    print(f"\n[INFO] {len(cycles)} cycles selectionnes (1/jour)")
    for d, c in cycles:
        print(f"  {d}  {c}")

    if not cycles:
        print("\n[WARN] aucun cycle a traiter")
        return 0

    # 2. Boucle
    t0 = time.time()
    n_engine_ok = 0
    n_fills_ok = 0
    n_fail = 0
    errors = []

    print(f"\n{'='*78}")
    print(f"PROCESSING {len(cycles)} cycles...")
    print("=" * 78)

    for idx, (day, cycle_id) in enumerate(cycles, 1):
        print(f"\n[{idx}/{len(cycles)}] day={day} cycle={cycle_id}")

        # a. shadow_engine
        rc, err = run_subprocess("shadow_engine.py", cycle_id, args.db)
        if rc == 0:
            print(f"  engine OK")
            n_engine_ok += 1
        else:
            print(f"  engine FAIL rc={rc} : {err[:150]}")
            n_fail += 1
            errors.append((cycle_id, "engine", rc, err[:100]))
            continue

        # b. shadow_simulate_fills (sauf si skip)
        if not args.skip_fills:
            rc, err = run_subprocess("shadow_simulate_fills.py", cycle_id, args.db)
            if rc == 0:
                print(f"  fills  OK")
                n_fills_ok += 1
            else:
                print(f"  fills  FAIL rc={rc} : {err[:150]}")
                errors.append((cycle_id, "fills", rc, err[:100]))

    elapsed = time.time() - t0

    # 3. Stats finales
    print(f"\n{'='*78}")
    print("BACKFILL DONE")
    print("=" * 78)
    print(f"  cycles processed   : {len(cycles)}")
    print(f"  engine OK          : {n_engine_ok}/{len(cycles)}")
    if not args.skip_fills:
        print(f"  fills OK           : {n_fills_ok}/{len(cycles)}")
    print(f"  failures           : {n_fail}")
    print(f"  elapsed            : {elapsed:.1f}s ({elapsed/max(len(cycles),1):.1f}s/cycle)")

    if errors:
        print(f"\n[ERRORS] {len(errors)} :")
        for cid, stage, rc, msg in errors[:10]:
            print(f"  {cid} [{stage}] rc={rc} : {msg}")

    # 4. Stats DB finales
    conn = sqlite3.connect(args.db, timeout=30)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM shadow_cycle_snapshots")
    n_snaps = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM shadow_orders")
    n_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM shadow_fills")
    n_fills = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT cycle_id) FROM shadow_cycle_snapshots")
    n_cycles_dist = cur.fetchone()[0]
    conn.close()

    print(f"\n[DB STATE] cycles_distinct={n_cycles_dist} snaps={n_snaps} orders={n_orders} fills={n_fills}")
    print("=" * 78)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())



===== shadow_engine.py =====

"""
shadow_engine.py - Phase 9.2 MVP

Calcule en parallele les decisions d allocation pour N variants de settings,
sans toucher la prod, en reutilisant convergence_snapshots existants.

Entree : conn DB, cycle_id (prod), variant_id (ou None pour tous)
Sortie : rows dans shadow_cycle_snapshots + shadow_orders

Logique apply_variant_sizing :
  - Lit convergence_pct, forced_exit, is_crypto, direction_consensus depuis convergence_snapshots
  - Recalcule un multiplicateur selon les seuils variant (au lieu d utiliser sizing_multiplier prod)
  - Applique multiplicateurs equity/crypto buy/sell + filtres conv + score
  - Genere une decision : keep / scale_up / scale_down / exit / filter

Markers : [SHADOW_ENGINE_V1]
"""

import sqlite3
import json
import sys
from datetime import datetime, timezone


# =============================================================================
# Loaders
# =============================================================================

def load_variants(conn, variant_id=None):
    """Retourne liste de dicts variants actifs.

    Si variant_id=None : tous les variants actifs.
    Settings stockes en JSON dans la colonne settings_json.
    """
    cur = conn.cursor()
    if variant_id is None:
        cur.execute("SELECT * FROM shadow_variants WHERE active=1")
    else:
        cur.execute("SELECT * FROM shadow_variants WHERE variant_id=? AND active=1", (variant_id,))
    rows = cur.fetchall()
    variants = []
    for r in rows:
        d = dict(r)
        try:
            d['settings'] = json.loads(d['settings_json'])
        except Exception:
            d['settings'] = {}
        variants.append(d)
    return variants


def load_convergence_for_cycle(conn, cycle_id):
    """Retourne dict {ticker: {convergence_pct, forced_exit, is_crypto, direction_consensus, sizing_multiplier_prod}}."""
    cur = conn.cursor()
    cur.execute("""
        SELECT ticker, convergence_pct, forced_exit, is_crypto, direction_consensus, sizing_multiplier
        FROM convergence_snapshots WHERE cycle_id=?
    """, (cycle_id,))
    out = {}
    for r in cur.fetchall():
        t = r['ticker']
        out[t] = {
            'convergence_pct': float(r['convergence_pct'] or 0.0),
            'forced_exit': int(r['forced_exit'] or 0),
            'is_crypto': int(r['is_crypto'] or 0),
            'direction_consensus': r['direction_consensus'] or 'long',
            'sizing_multiplier_prod': float(r['sizing_multiplier'] or 1.0),
        }
    return out


def load_baseline_allocations(conn, cycle_id):
    """Charge les allocations baseline (avant convergence) pour un cycle.

    Source primaire : portfolio_targets_history (cycle_id direct).
    Si vide : fallback sur portfolio_targets actuel (snapshot le plus recent).

    Retourne dict {ticker: {score, target_weight_pct}}.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT ticker, score, target_weight_pct
        FROM portfolio_targets_history WHERE cycle_id=?
    """, (cycle_id,))
    rows = cur.fetchall()
    if rows:
        return {r['ticker']: {
            'score': float(r['score'] or 0.0),
            'target_weight_pct': float(r['target_weight_pct'] or 0.0),
        } for r in rows}

    # Fallback : dernier snapshot portfolio_targets
    cur.execute("""
        SELECT snapshot_id FROM portfolio_targets
        ORDER BY updated_at DESC LIMIT 1
    """)
    row = cur.fetchone()
    if not row:
        return {}
    snap_id = row['snapshot_id']
    cur.execute("""
        SELECT ticker, score, target_weight_pct FROM portfolio_targets
        WHERE snapshot_id=? AND active=1
    """, (snap_id,))
    return {r['ticker']: {
        'score': float(r['score'] or 0.0),
        'target_weight_pct': float(r['target_weight_pct'] or 0.0),
    } for r in cur.fetchall()}


# =============================================================================
# Variant sizing logic
# =============================================================================

def compute_variant_multiplier(conv_data, settings):
    """Calcule (multiplier, decision, side) pour un ticker selon les settings variant.

    conv_data : dict avec convergence_pct, forced_exit, is_crypto, direction_consensus
    settings  : dict avec conv, fe_sc, eq_buy, eq_sell, cr_buy, cr_sell, score

    Logique :
      - forced_exit=1 ET conv < fe_sc -> mult=0, decision=exit
      - conv < conv_threshold -> mult=0.5 (downscale), decision=scale_down
      - sinon mult = (eq|cr)_(buy|sell) selon side, decision=keep ou scale_up

    Retourne : (multiplier float, decision str, side str)
    """
    conv = conv_data['convergence_pct']
    fe = conv_data['forced_exit']
    is_crypto = conv_data['is_crypto']
    direction = (conv_data['direction_consensus'] or 'long').lower()

    side = 'buy' if direction == 'long' else 'sell'

    s_conv = float(settings.get('conv_thresh', 0.60))
    s_fe = float(settings.get('forced_exit_sc', 0.33))
    s_eq_buy = float(settings.get('eq_buy_mult', 1.0))
    s_eq_sell = float(settings.get('eq_sell_mult', 1.0))
    s_cr_buy = float(settings.get('cr_buy_mult', 0.7))
    s_cr_sell = float(settings.get('cr_sell_mult', 1.5))

    # Forced exit prioritaire : tolerance 0.01 (convergence_pct stocke a 3 decimales, ex 1/3=0.333)
    TOL = 0.01
    if fe == 1 and conv <= s_fe + TOL:
        return 0.0, 'exit', side

    # Filtre convergence basse (meme tolerance)
    if conv < s_conv - TOL:
        return 0.5, 'scale_down', side

    # Multiplicateur classe d actif
    if is_crypto:
        mult = s_cr_buy if side == 'buy' else s_cr_sell
    else:
        mult = s_eq_buy if side == 'buy' else s_eq_sell

    if abs(mult - 1.0) < 0.01:
        decision = 'keep'
    elif mult > 1.0:
        decision = 'scale_up'
    else:
        decision = 'scale_down'

    return mult, decision, side


def compute_shadow_for_cycle(conn, cycle_id, variant_id=None):
    """Calcule les shadow snapshots + orders pour un cycle, un ou plusieurs variants.

    Retourne dict {variant_name: {n_keep, n_scale_up, n_scale_down, n_exit, n_filter}}.
    """
    variants = load_variants(conn, variant_id)
    if not variants:
        print(f"[shadow_engine] Aucun variant actif (id={variant_id})")
        return {}

    conv_map = load_convergence_for_cycle(conn, cycle_id)
    if not conv_map:
        print(f"[shadow_engine] Aucun convergence_snapshot pour cycle {cycle_id}")
        return {}

    baseline = load_baseline_allocations(conn, cycle_id)
    if not baseline:
        print(f"[shadow_engine] WARN Aucune baseline allocation trouvee, fallback weight=0")

    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    cur = conn.cursor()

    summary = {}

    # day_t derive du cycle_id (format YYYYMMDD-HHMMSS)
    day_t = cycle_id[:8] if len(cycle_id) >= 8 else now[:10].replace('-','')
    day_t_iso = f"{day_t[:4]}-{day_t[4:6]}-{day_t[6:8]}"

    # MVP placeholders : K_init=1M, pas de fills yet (Phase 9.3+)
    NAV_PLACEHOLDER = 1000000.0
    CASH_PLACEHOLDER = 1000000.0
    NOTES_MVP = 'mvp_phase92_no_fills'

    # Idempotence : purge rows existants pour (cycle_id, variant_id) avant re-insert
    variant_ids = [v['variant_id'] for v in variants]
    placeholders = ','.join('?' for _ in variant_ids)
    cur.execute(
        f"DELETE FROM shadow_cycle_snapshots WHERE cycle_id=? AND variant_id IN ({placeholders})",
        [cycle_id] + variant_ids
    )
    n_del_snaps = cur.rowcount
    cur.execute(
        f"DELETE FROM shadow_orders WHERE cycle_id=? AND variant_id IN ({placeholders})",
        [cycle_id] + variant_ids
    )
    n_del_orders = cur.rowcount
    if n_del_snaps or n_del_orders:
        print(f"[idempotence] purge {n_del_snaps} snapshots + {n_del_orders} orders existants")

    for v in variants:
        vid = v['variant_id']
        vname = v['name']
        settings = v['settings']
        s_score_cutoff = float(settings.get('score_cutoff', 0.30))

        stats = {'keep': 0, 'scale_up': 0, 'scale_down': 0, 'exit': 0, 'filter': 0}

        # Insert 1 portfolio snapshot par variant (niveau cycle)
        cur.execute("""
            INSERT INTO shadow_cycle_snapshots
              (cycle_id, variant_id, day_t, nav, cash, n_positions,
               invested_pct, regime, notes, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (cycle_id, vid, day_t_iso, NAV_PLACEHOLDER, CASH_PLACEHOLDER,
              0, 0.0, None, NOTES_MVP, now))

        for ticker, cd in conv_map.items():
            base = baseline.get(ticker, {'score': 0.0, 'target_weight_pct': 0.0})
            score = base['score']
            baseline_w = base['target_weight_pct']

            # Filtre score cutoff variant
            if score < s_score_cutoff and baseline_w == 0:
                # Ne pas creer d order si score trop bas ET pas de position baseline
                stats['filter'] += 1
                continue

            mult, decision, side = compute_variant_multiplier(cd, settings)
            shadow_w = baseline_w * mult

            stats[decision] = stats.get(decision, 0) + 1

            # Insert shadow_order si decision genere ordre (exit ou scale != 1)
            if decision in ('exit', 'scale_down', 'scale_up'):
                # qty_current placeholder : 0 (MVP, on n a pas encore positions snapshot)
                qty = 0.0
                cur.execute("""
                    INSERT INTO shadow_orders
                      (cycle_id, variant_id, ticker, side, qty, qty_current,
                       target_weight_pct, convergence_pct, forced_exit,
                       sizing_multiplier, decision, rejection_reason, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (cycle_id, vid, ticker, side, qty, 0.0,
                      shadow_w, cd['convergence_pct'], cd['forced_exit'],
                      mult, decision, None, now))

        summary[vname] = stats

    return summary


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse
    p = argparse.ArgumentParser(description="Shadow engine MVP")
    p.add_argument("--db", default=r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
    p.add_argument("--cycle-id", required=True, help="cycle_id prod a simuler")
    p.add_argument("--variant-id", type=int, default=None, help="Variant ID specifique (sinon tous)")
    p.add_argument("--dry-run", action="store_true", help="Calcule sans inserer")
    args = p.parse_args()

    print("="*78)
    print("SHADOW ENGINE MVP - Phase 9.2")
    print(f"DB        : {args.db}")
    print(f"Cycle ID  : {args.cycle_id}")
    print(f"Variant   : {args.variant_id if args.variant_id else 'ALL active'}")
    print(f"Mode      : {'DRY-RUN' if args.dry_run else 'APPLY'}")
    print("="*78)

    conn = sqlite3.connect(args.db, timeout=30)
    conn.row_factory = sqlite3.Row

    # Active WAL pour reads concurrents
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    conn.execute("BEGIN")
    try:
        summary = compute_shadow_for_cycle(conn, args.cycle_id, args.variant_id)
        if args.dry_run:
            conn.execute("ROLLBACK")
            print("\n[DRY-RUN] ROLLBACK effectue, aucune ecriture persistee")
        else:
            conn.execute("COMMIT")
            print("\n[APPLY] COMMIT effectue")
    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"\n[ERROR] {e} - ROLLBACK")
        raise

    print("\n[RESULTATS]")
    for vname, stats in summary.items():
        total = sum(stats.values())
        print(f"\n  Variant : {vname}")
        print(f"    Total decisions : {total}")
        for k, v in stats.items():
            pct = 100.0 * v / total if total else 0
            print(f"    {k:12s} : {v:3d} ({pct:5.1f}%)")

    # Verification post-insert
    if not args.dry_run:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as n FROM shadow_cycle_snapshots WHERE cycle_id=?", (args.cycle_id,))
        n_snaps = cur.fetchone()['n']
        cur.execute("SELECT COUNT(*) as n FROM shadow_orders WHERE cycle_id=?", (args.cycle_id,))
        n_orders = cur.fetchone()['n']
        print(f"\n[VERIFICATION]")
        print(f"  shadow_cycle_snapshots inserts : {n_snaps}")
        print(f"  shadow_orders inserts          : {n_orders}")

    conn.close()
    print("\n" + "="*78)
    print("DONE")
    print("="*78)


if __name__ == "__main__":
    main()



===== shadow_hook.py =====

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



===== shadow_memo_generator.py =====

# -*- coding: utf-8 -*-
"""
Jalon 9.5b - Generateur de memo IA pour shadow_perf_rolling.

Pour chaque variant de la derniere as_of_day (window=30) :
  - Build prompt avec description + stats prod/variant + delta + n_orders + n_cycles
  - Appel pplx_query (MODEL_FAST) avec JSON schema strict
  - UPDATE shadow_perf_rolling : recommendation_memo, memo_source, memo_generated_at, memo_cost_usd

Usage :
  py -3.13 .\\shadow_memo_generator.py
  py -3.13 .\\shadow_memo_generator.py --force         # bypass cache PPLX (TTL=0)
  py -3.13 .\\shadow_memo_generator.py --variant 2     # une seule variante

Idempotent : skip si memo deja present (sauf --force).
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime

# pplx_client est dans le meme dir
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pplx_client import pplx_query, MODEL_FAST  # noqa: E402

DB = os.environ.get("THESIUM_DB", r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
WINDOW_DAYS = 30

# JSON Schema strict pour le memo - le modele doit produire ces 4 champs
MEMO_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict_court", "justification", "risques", "action_recommandee"],
    "properties": {
        "verdict_court": {
            "type": "string",
            "description": "Phrase tres courte (max 80 caracteres) qui resume le verdict"
        },
        "justification": {
            "type": "string",
            "description": "Analyse 3-5 phrases sur la performance vs prod : delta, sharpe, drawdown, fiabilite"
        },
        "risques": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Liste 2-4 risques identifies (data, regime, taille echantillon, etc.)"
        },
        "action_recommandee": {
            "type": "string",
            "description": "Une action concrete : Promouvoir / Rejeter / Continuer observation / Allonger fenetre"
        }
    }
}

SYSTEM_PROMPT = (
    "Tu es analyste quantitatif senior. Tu evalues une variante d'algorithme de trading "
    "shadow (paper-trading) vs la prod live. Reponds en francais, factuel, sans emoji. "
    "Reponds UNIQUEMENT en JSON conforme au schema fourni."
)


def fetch_latest_rows(conn, variant_filter=None):
    """Recupere les rows shadow_perf_rolling de la derniere as_of_day (window=30)."""
    cur = conn.execute(
        "SELECT MAX(as_of_day) FROM shadow_perf_rolling WHERE window_days=?",
        (WINDOW_DAYS,)
    )
    last = cur.fetchone()
    if not last or not last[0]:
        return None, []
    as_of = last[0]

    sql = (
        "SELECT p.id, p.variant_id, v.name AS variant_name, v.description AS variant_desc, "
        "       p.return_variant_pct, p.return_prod_pct, p.delta_pct, "
        "       p.sharpe_variant, p.sharpe_prod, "
        "       p.max_dd_variant_pct, p.max_dd_prod_pct, "
        "       p.n_cycles, p.n_orders_variant, p.n_orders_prod, "
        "       p.recommendation, p.recommendation_memo "
        "FROM shadow_perf_rolling p "
        "LEFT JOIN shadow_variants v ON v.variant_id = p.variant_id "  # [SHADOW_MEMO_SQL_FIX_V2]
        "WHERE p.window_days=? AND p.as_of_day=? "
    )
    params = [WINDOW_DAYS, as_of]
    if variant_filter is not None:
        sql += "AND p.variant_id=? "
        params.append(variant_filter)
    sql += "ORDER BY p.variant_id"

    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return as_of, rows


def fmt_num(v, dec=3):
    if v is None:
        return "?"
    try:
        return ("{:." + str(dec) + "f}").format(float(v))
    except Exception:
        return str(v)


def build_prompt(row, as_of_day):
    """Construit un prompt riche avec toutes les stats."""
    name = row.get("variant_name") or ("variant_" + str(row.get("variant_id")))
    desc = row.get("variant_desc") or "(pas de description)"
    p = (
        "Tu evalues la variante shadow '" + name + "' sur " + str(WINDOW_DAYS)
        + " jours (as_of_day=" + str(as_of_day) + ").\n"
        "\n"
        "## Description variante\n"
        + desc + "\n"
        "\n"
        "## Statistiques fenetre J-" + str(WINDOW_DAYS) + " (sur "
        + str(row.get("n_cycles") or "?") + " cycles)\n"
        "| Metrique          | Prod           | Variante       | Delta          |\n"
        "|-------------------|----------------|----------------|----------------|\n"
        "| Retour (%)        | " + fmt_num(row.get("return_prod_pct")) + "        | "
        + fmt_num(row.get("return_variant_pct")) + "        | "
        + fmt_num(row.get("delta_pct")) + " pts |\n"
        "| Sharpe ratio      | " + fmt_num(row.get("sharpe_prod"), 2) + "         | "
        + fmt_num(row.get("sharpe_variant"), 2) + "         | "
        + fmt_num((row.get("sharpe_variant") or 0) - (row.get("sharpe_prod") or 0), 2) + "          |\n"
        "| Max Drawdown (%)  | " + fmt_num(row.get("max_dd_prod_pct")) + "       | "
        + fmt_num(row.get("max_dd_variant_pct")) + "       | "
        + fmt_num((row.get("max_dd_variant_pct") or 0) - (row.get("max_dd_prod_pct") or 0)) + " pts  |\n"
        "| Nombre d'ordres   | " + str(row.get("n_orders_prod") or "?") + "            | "
        + str(row.get("n_orders_variant") or "?") + "            | "
        + str((row.get("n_orders_variant") or 0) - (row.get("n_orders_prod") or 0)) + "             |\n"
        "\n"
        "## Recommandation algo\n"
        "Le moteur a classe cette variante comme : **" + str(row.get("recommendation") or "neutral") + "**\n"
        "(Regles : champion si delta > +2 pts ET Sharpe variant > Sharpe prod ; "
        "reject si delta < -1 pt ; sinon neutral.)\n"
        "\n"
        "## Ta mission\n"
        "1. Verdict court (max 80 caracteres).\n"
        "2. Justification factuelle 3-5 phrases : performance vs prod, qualite (sharpe), risque (DD), fiabilite (taille echantillon).\n"
        "3. 2 a 4 risques identifies (regime de marche, sample size, biais, etc.).\n"
        "4. Action recommandee concrete (Promouvoir / Rejeter / Continuer observation / Allonger fenetre).\n"
        "Soit factuel. N'invente pas de donnees externes.\n"
    )
    return p


def estimate_cost_usd(usage):
    """Estimation cout USD : sonar = $1/M input, $1/M output (approx)."""
    if not isinstance(usage, dict):
        return 0.0
    pt = usage.get("prompt_tokens", 0) or 0
    ct = usage.get("completion_tokens", 0) or 0
    return round((pt + ct) / 1_000_000.0, 6)


def update_memo(conn, row_id, memo_text, model, cost_usd):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE shadow_perf_rolling "
        "SET recommendation_memo=?, memo_source=?, memo_generated_at=?, memo_cost_usd=? "
        "WHERE id=?",
        (memo_text, "pplx:" + model, now, cost_usd, row_id)
    )
    conn.commit()


def generate_for_row(row, as_of_day, force=False):
    if row.get("recommendation_memo") and not force:
        print("  [SKIP] memo deja present (id={}, variant={})".format(
            row["id"], row.get("variant_name")))
        return None

    prompt = build_prompt(row, as_of_day)
    ttl = 0 if force else 24 * 3600  # 24h cache par defaut

    name = row.get("variant_name") or str(row.get("variant_id"))
    res = pplx_query(
        agent="shadow_memo_" + name,
        prompt=prompt,
        schema=MEMO_SCHEMA,
        ttl=ttl,
        model=MODEL_FAST,
        timeout=60,
        system=SYSTEM_PROMPT,
    )
    if not res or not res.get("data"):
        print("  [ERR] pplx_query a retourne None pour variant", name)
        return None

    data = res["data"]
    # Format memo lisible
    memo_lines = []
    memo_lines.append("VERDICT : " + str(data.get("verdict_court", "?")))
    memo_lines.append("")
    memo_lines.append("JUSTIFICATION")
    memo_lines.append(str(data.get("justification", "?")))
    memo_lines.append("")
    risques = data.get("risques", []) or []
    if risques:
        memo_lines.append("RISQUES")
        for r in risques:
            memo_lines.append("- " + str(r))
        memo_lines.append("")
    memo_lines.append("ACTION RECOMMANDEE")
    memo_lines.append(str(data.get("action_recommandee", "?")))

    citations = res.get("citations", []) or []
    if citations:
        memo_lines.append("")
        memo_lines.append("SOURCES")
        for i, c in enumerate(citations[:5], 1):
            memo_lines.append("[" + str(i) + "] " + str(c))

    memo_text = "\n".join(memo_lines)
    return {
        "memo_text": memo_text,
        "model": res.get("model", MODEL_FAST),
        "cost_usd": 0.0,  # cost reel pas expose, on laisse 0
        "data": data,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Regenere meme si memo present")
    ap.add_argument("--variant", type=int, default=None, help="Filtrer un variant_id")
    args = ap.parse_args()

    print("=" * 70)
    print("SHADOW MEMO GENERATOR - Jalon 9.5b")
    print("DB :", DB)
    print("Force :", args.force, "| Variant filter :", args.variant)
    print("=" * 70)

    conn = sqlite3.connect(DB, timeout=15.0)
    try:
        as_of, rows = fetch_latest_rows(conn, args.variant)
        if not rows:
            print("[ERR] Aucune row trouvee pour window=", WINDOW_DAYS)
            return 2
        print("as_of_day :", as_of, "| rows a traiter :", len(rows))
        print()

        n_ok = 0
        n_skip = 0
        n_err = 0
        for row in rows:
            print("[VARIANT {}] {}".format(row["variant_id"], row.get("variant_name")))
            try:
                result = generate_for_row(row, as_of, force=args.force)
                if result is None:
                    if row.get("recommendation_memo") and not args.force:
                        n_skip += 1
                    else:
                        n_err += 1
                    continue
                update_memo(conn, row["id"], result["memo_text"],
                            result["model"], result["cost_usd"])
                n_ok += 1
                # Affiche les 3 premieres lignes pour controle
                preview = result["memo_text"].split("\n")[:3]
                for ln in preview:
                    print("    | " + ln)
                print()
            except Exception as e:
                n_err += 1
                print("  [EXC] {}: {}".format(type(e).__name__, e))
                print()

        print("=" * 70)
        print("OK : {} | SKIP : {} | ERR : {}".format(n_ok, n_skip, n_err))
        print("=" * 70)
        return 0 if n_err == 0 else 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())



===== shadow_perf_rolling_j30.py =====

# -*- coding: utf-8 -*-
"""
shadow_perf_rolling_j30.py - Phase 9.5

Calcule la perf rolling J-30 pour chaque variant actif et insere dans
shadow_perf_rolling.

Architecture :
- Pour chaque variant : reconstruire les positions cumulees depuis shadow_fills
  sur fenetre [as_of_day - 30 jours, as_of_day]
- Calculer NAV journaliere par mark-to-market simple :
    NAV(d) = cash_residuel + somme(position_qty_ticker(d) * close_ticker(d))
  cash_residuel = K0 - notional_net (achats - ventes)
- Computer return_pct, sharpe (daily returns), max_dd
- Variant_id=1 (prod) sert de baseline : delta_pct = return_variant - return_prod
- UNIQUE(variant_id, window_days, as_of_day) -> idempotent via DELETE WHERE

Usage :
  py -3.13 shadow_perf_rolling_j30.py [--as-of YYYYMMDD] [--db PATH] [--window 30]

Default as-of = aujourd hui (UTC), default window = 30 jours.
"""
import argparse
import math
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

K0 = 1_000_000.0  # capital initial $1M strict (regle utilisateur)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
    p.add_argument("--as-of", default=None, help="YYYYMMDD ; default = aujourd hui UTC")
    p.add_argument("--window", type=int, default=30)
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def as_of_day_iso(yyyymmdd):
    return "{}-{}-{}".format(yyyymmdd[0:4], yyyymmdd[4:6], yyyymmdd[6:8])


def daterange_iso(start_iso, end_iso):
    s = datetime.strptime(start_iso, "%Y-%m-%d").date()
    e = datetime.strptime(end_iso, "%Y-%m-%d").date()
    cur = s
    out = []
    while cur <= e:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def get_close_for_day(cur, ticker, day_iso):
    """
    Retourne le close du ticker au jour donne ou au dernier jour < day_iso
    si non dispo (weekend / jour ferie).
    """
    row = cur.execute(
        "SELECT p.close FROM prices p "
        "JOIN instruments i ON i.id = p.instrument_id "
        "WHERE i.ticker = ? AND p.date <= ? "
        "ORDER BY p.date DESC LIMIT 1",
        (ticker, day_iso),
    ).fetchone()
    if row and row[0] is not None:
        return float(row[0])
    return None


def compute_variant_nav_series(cur, variant_id, start_iso, end_iso, verbose=False):
    """
    Reconstruit la serie NAV journaliere pour le variant donne sur [start, end].

    Logique :
      - On part de cash = K0 et positions = {}
      - On rejoue les fills jour apres jour (en ordre fill_day)
        BUY  : cash -= notional + fees ; positions[ticker] += qty
        SELL : cash += notional - fees ; positions[ticker] -= qty
      - Pour chaque jour de la fenetre, on calcule
          nav = cash + sum(pos_qty * close)
      - On retourne la liste [(day_iso, nav), ...]

    Note : les fills d avant start_iso doivent etre integres pour avoir l etat
    initial correct ; on commence donc par charger TOUS les fills du variant
    jusqu a end_iso, puis on filtre la serie NAV sur [start, end].
    """
    fills = cur.execute(
        "SELECT fill_day, side, ticker, fill_price, fill_quantity, fees, notional "
        "FROM shadow_fills WHERE variant_id=? AND fill_day <= ? "
        "ORDER BY fill_day ASC, id ASC",
        (variant_id, end_iso),
    ).fetchall()

    if verbose:
        print("  variant={} : {} fills loaded (jusqu a {})".format(
            variant_id, len(fills), end_iso
        ))

    cash = K0
    positions = {}  # ticker -> qty
    fills_by_day = {}
    for f in fills:
        d = f[0]
        fills_by_day.setdefault(d, []).append(f)

    # Pour chaque jour de [start_iso, end_iso], appliquer les fills du jour
    # puis snapshot NAV au close.
    # On etend la plage en arriere pour englober tous les fills anterieurs.
    all_days = sorted(set([f[0] for f in fills] + daterange_iso(start_iso, end_iso)))
    series = []
    for d in all_days:
        for f in fills_by_day.get(d, []):
            side = f[1]
            ticker = f[2]
            qty = float(f[4])
            fees = float(f[5])
            notional = float(f[6])
            if side == "BUY":
                cash -= notional + fees
                positions[ticker] = positions.get(ticker, 0.0) + qty
            elif side == "SELL":
                cash += notional - fees
                positions[ticker] = positions.get(ticker, 0.0) - qty
        # NAV au close du jour
        if d >= start_iso and d <= end_iso:
            mkt = 0.0
            for tk, q in positions.items():
                if abs(q) < 1e-12:
                    continue
                c = get_close_for_day(cur, tk, d)
                if c is None:
                    # pas de prix dispo -> on ignore cette position pour ce jour
                    continue
                mkt += q * c
            nav = cash + mkt
            series.append((d, nav))

    return series


def compute_metrics(series, k0=K0):
    """
    A partir de la serie [(day, nav), ...] :
      - return_pct  = (nav_final - K0) / K0 * 100
      - sharpe annualise sur daily returns
      - max_dd_pct sur la serie
    """
    if not series:
        return {
            "nav_final": None, "return_pct": None,
            "sharpe": None, "max_dd_pct": None,
        }
    nav_final = series[-1][1]
    return_pct = (nav_final - k0) / k0 * 100.0

    # Daily returns
    rets = []
    for i in range(1, len(series)):
        prev = series[i - 1][1]
        cur = series[i][1]
        if prev and prev > 0:
            rets.append((cur - prev) / prev)
    if len(rets) >= 2:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        std = math.sqrt(var)
        sharpe = (mean / std * math.sqrt(252.0)) if std > 1e-12 else None
    else:
        sharpe = None

    # Max drawdown
    peak = series[0][1]
    max_dd = 0.0
    for _, nav in series:
        if nav > peak:
            peak = nav
        if peak > 0:
            dd = (nav - peak) / peak * 100.0
            if dd < max_dd:
                max_dd = dd

    return {
        "nav_final": nav_final,
        "return_pct": return_pct,
        "sharpe": sharpe,
        "max_dd_pct": max_dd,
    }


def get_n_cycles_n_orders(cur, variant_id, start_iso, end_iso):
    row = cur.execute(
        "SELECT COUNT(DISTINCT cycle_id) AS n_cyc, COUNT(*) AS n_ord "
        "FROM shadow_fills "
        "WHERE variant_id=? AND fill_day >= ? AND fill_day <= ?",
        (variant_id, start_iso, end_iso),
    ).fetchone()
    return int(row[0] or 0), int(row[1] or 0)


def recommendation(delta_pct):
    if delta_pct is None:
        return "no_data"
    if delta_pct >= 1.0:
        return "champion"
    if delta_pct <= -1.0:
        return "reject"
    return "neutral"


def main():
    args = parse_args()
    db = args.db
    if not os.path.exists(db):
        print("[ERR] DB not found:", db)
        sys.exit(1)

    if args.as_of is None:
        as_of = datetime.now(timezone.utc).strftime("%Y%m%d")
    else:
        as_of = args.as_of

    as_of_iso = as_of_day_iso(as_of)
    start_dt = datetime.strptime(as_of_iso, "%Y-%m-%d") - timedelta(days=args.window)
    start_iso = start_dt.strftime("%Y-%m-%d")

    print("=" * 78)
    print("SHADOW PERF ROLLING J-{}".format(args.window))
    print("DB        :", db)
    print("Window    : {} -> {} ({} jours)".format(start_iso, as_of_iso, args.window))
    print("=" * 78)

    conn = sqlite3.connect(db, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    variants = cur.execute(
        "SELECT variant_id, name FROM shadow_variants WHERE active=1 ORDER BY variant_id"
    ).fetchall()
    print()
    print("Variants actifs :", [(v["variant_id"], v["name"]) for v in variants])
    print()

    # Compute prod (variant_id=1) en premier pour servir de baseline
    print("[1/2] Compute baseline (variant_id=1 = prod)")
    prod_series = compute_variant_nav_series(cur, 1, start_iso, as_of_iso, args.verbose)
    prod_metrics = compute_metrics(prod_series)
    prod_n_cyc, prod_n_ord = get_n_cycles_n_orders(cur, 1, start_iso, as_of_iso)
    print("  prod : nav_final={} return={:.3f}% sharpe={} max_dd={:.3f}% n_cyc={} n_ord={}".format(
        prod_metrics["nav_final"], prod_metrics["return_pct"] or 0.0,
        prod_metrics["sharpe"], prod_metrics["max_dd_pct"] or 0.0,
        prod_n_cyc, prod_n_ord
    ))

    # Compute pour tous les variants
    print()
    print("[2/2] Compute variants + insert")
    print()

    # Idempotence : DELETE WHERE puis INSERT
    cur.execute(
        "DELETE FROM shadow_perf_rolling WHERE window_days=? AND as_of_day=?",
        (args.window, as_of_iso),
    )

    inserted = 0
    for v in variants:
        vid = v["variant_id"]
        vname = v["name"]
        if vid == 1:
            series = prod_series
            metrics = prod_metrics
            n_cyc = prod_n_cyc
            n_ord = prod_n_ord
        else:
            series = compute_variant_nav_series(cur, vid, start_iso, as_of_iso, args.verbose)
            metrics = compute_metrics(series)
            n_cyc, n_ord = get_n_cycles_n_orders(cur, vid, start_iso, as_of_iso)

        if metrics["return_pct"] is not None and prod_metrics["return_pct"] is not None:
            delta = metrics["return_pct"] - prod_metrics["return_pct"]
        else:
            delta = None

        reco = recommendation(delta)

        cur.execute(
            "INSERT INTO shadow_perf_rolling ("
            "  variant_id, window_days, as_of_day, "
            "  nav_variant, nav_prod, "
            "  return_variant_pct, return_prod_pct, delta_pct, "
            "  sharpe_variant, sharpe_prod, "
            "  max_dd_variant_pct, max_dd_prod_pct, "
            "  n_cycles, n_orders_variant, n_orders_prod, "
            "  recommendation"
            ") VALUES (?, ?, ?,  ?, ?,  ?, ?, ?,  ?, ?,  ?, ?,  ?, ?, ?,  ?)",
            (
                vid, args.window, as_of_iso,
                metrics["nav_final"], prod_metrics["nav_final"],
                metrics["return_pct"], prod_metrics["return_pct"], delta,
                metrics["sharpe"], prod_metrics["sharpe"],
                metrics["max_dd_pct"], prod_metrics["max_dd_pct"],
                n_cyc, n_ord, prod_n_ord,
                reco,
            ),
        )
        inserted += 1
        print("  v{} ({}) : ret={:.3f}% delta={} sharpe={} dd={:.3f}% n_cyc={} n_ord={} reco={}".format(
            vid, vname,
            metrics["return_pct"] or 0.0,
            "{:.3f}%".format(delta) if delta is not None else "N/A",
            "{:.3f}".format(metrics["sharpe"]) if metrics["sharpe"] is not None else "N/A",
            metrics["max_dd_pct"] or 0.0,
            n_cyc, n_ord, reco,
        ))

    conn.commit()
    conn.close()

    print()
    print("=" * 78)
    print("PERF ROLLING DONE")
    print("  rows inserted :", inserted)
    print("  as_of_day     :", as_of_iso)
    print("  window_days   :", args.window)
    print("=" * 78)


if __name__ == "__main__":
    main()



===== shadow_simulate_fills.py =====

"""
shadow_simulate_fills.py - Phase 9.3

Pour un cycle prod donne, lit shadow_orders (genere par shadow_engine Phase 9.2)
et simule les fills via fill_simulator (slip + open J+1). Ecrit dans shadow_fills.

Difference avec prod : ici on travaille en parallele, sans toucher les positions
reelles. NAV/cash placeholders (1M) tant que Phase 9.4 n a pas wire le scheduler.

Markers : [SHADOW_FILLS_V1]
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone

# Active le mode replay AVANT import fill_simulator
os.environ["NEXTONES_REPLAY_MODE"] = "1"

from fill_simulator import simulate_fill, FillResult
from replay_adapters import MarketDataAdapter


DB_DEFAULT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
NAV_PLACEHOLDER = 1000000.0
FEE_BPS = 1.0  # 1 bp commission par defaut, modifiable plus tard


def cycle_to_day(cycle_id):
    """Cycle YYYYMMDD-HHMMSS -> YYYY-MM-DD."""
    if len(cycle_id) < 8:
        return None
    d = cycle_id[:8]
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def load_shadow_orders(conn, cycle_id, variant_id=None):
    """Lit shadow_orders du cycle. variant_id=None -> tous variants actifs."""
    cur = conn.cursor()
    if variant_id is None:
        cur.execute("""
            SELECT o.* FROM shadow_orders o
            JOIN shadow_variants v ON v.variant_id = o.variant_id
            WHERE o.cycle_id=? AND v.active=1
            ORDER BY o.variant_id, o.ticker
        """, (cycle_id,))
    else:
        cur.execute("""
            SELECT * FROM shadow_orders
            WHERE cycle_id=? AND variant_id=?
            ORDER BY ticker
        """, (cycle_id, variant_id))
    return [dict(r) for r in cur.fetchall()]


def purge_existing_fills(conn, cycle_id, variant_ids):
    """Idempotence : purge fills existants pour ce cycle x variants."""
    if not variant_ids:
        return 0
    cur = conn.cursor()
    placeholders = ','.join('?' for _ in variant_ids)
    cur.execute(
        f"DELETE FROM shadow_fills WHERE cycle_id=? AND variant_id IN ({placeholders})",
        [cycle_id] + variant_ids
    )
    return cur.rowcount


def compute_qty_from_weight(target_weight_pct, nav, price):
    """qty = (target_weight_pct/100) * NAV / price.

    Pour exit/scale_down avec shadow_weight=0 : qty=0 cote shadow_orders, mais on a
    besoin d une qty positive pour le fill. En MVP, on simule qty = baseline_weight
    (10% par defaut) / price * NAV pour avoir un volume non-nul.
    """
    if price <= 0:
        return 0.0
    w = max(target_weight_pct, 0.0) / 100.0
    return (nav * w) / price


def simulate_fills_for_cycle(conn, cycle_id, variant_id=None):
    """Boucle principale. Retourne stats par variant."""
    orders = load_shadow_orders(conn, cycle_id, variant_id)
    if not orders:
        print(f"[shadow_fills] Aucun shadow_order pour cycle {cycle_id}")
        return {}

    # Variants concernes par cette execution
    variant_ids = sorted(set(o['variant_id'] for o in orders))
    n_purged = purge_existing_fills(conn, cycle_id, variant_ids)
    if n_purged:
        print(f"[idempotence] purge {n_purged} shadow_fills existants")

    day_t = cycle_to_day(cycle_id)
    print(f"day_decision (= cycle day) : {day_t}")

    adapter = MarketDataAdapter(db_path=DB_DEFAULT)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    # Map variant_id -> name
    cur.execute("SELECT variant_id, name FROM shadow_variants")
    vmap = {r['variant_id']: r['name'] for r in cur.fetchall()}

    stats = {}
    for o in orders:
        vid = o['variant_id']
        vname = vmap.get(vid, f"v{vid}")
        stats.setdefault(vname, {'filled': 0, 'rejected': 0, 'skipped_zero_w': 0, 'total_notional': 0.0})

        ticker = o['ticker']
        side_raw = o['side']
        # Pour exit/scale_down, target_weight_pct=0 -> on simule la qty depuis position implicite
        # MVP : pour vendre, qty = NAV * (10% / price) defaut (proxy position)
        # pour acheter, qty = NAV * (target_w/100) / price
        side = side_raw.upper() if side_raw else "BUY"

        # Recupere close au jour de decision pour estimer qty (proxy)
        close_dec = adapter.get_close_at(day_t, ticker)
        if close_dec is None or close_dec <= 0:
            stats[vname]['rejected'] += 1
            continue

        target_w = o['target_weight_pct'] or 0.0
        if side == "SELL" and target_w == 0:
            # exit : on simule la vente d une position proxy 5% NAV
            qty = compute_qty_from_weight(5.0, NAV_PLACEHOLDER, close_dec)
        elif side == "BUY" and target_w == 0:
            stats[vname]['skipped_zero_w'] += 1
            continue
        else:
            qty = compute_qty_from_weight(target_w, NAV_PLACEHOLDER, close_dec)

        if qty <= 0:
            stats[vname]['skipped_zero_w'] += 1
            continue

        # simulate_fill
        try:
            fr = simulate_fill(adapter, ticker, side, qty, day_t)
        except Exception as e:
            print(f"  WARN simulate_fill {ticker} {side} qty={qty}: {e}")
            stats[vname]['rejected'] += 1
            continue

        if fr.status != "filled":
            stats[vname]['rejected'] += 1
            continue

        notional = fr.price_filled * fr.qty
        fees = abs(notional) * (FEE_BPS / 10000.0)

        cur.execute("""
            INSERT INTO shadow_fills
              (cycle_id, variant_id, shadow_order_id, ticker, side,
               fill_price, fill_quantity, fees, slippage_bps, notional, fill_day, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (cycle_id, vid, o['id'], ticker, side,
              fr.price_filled, fr.qty, fees, fr.slippage_bps, notional, fr.day_fill, now))

        stats[vname]['filled'] += 1
        stats[vname]['total_notional'] += abs(notional)

    return stats


def main():
    import argparse
    p = argparse.ArgumentParser(description="Shadow fills simulator MVP")
    p.add_argument("--db", default=DB_DEFAULT)
    p.add_argument("--cycle-id", required=True)
    p.add_argument("--variant-id", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    print("="*78)
    print("SHADOW FILLS SIMULATOR - Phase 9.3")
    print(f"DB        : {args.db}")
    print(f"Cycle ID  : {args.cycle_id}")
    print(f"Variant   : {args.variant_id if args.variant_id else 'ALL active'}")
    print(f"Mode      : {'DRY-RUN' if args.dry_run else 'APPLY'}")
    print("="*78)

    conn = sqlite3.connect(args.db, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    conn.execute("BEGIN")
    try:
        stats = simulate_fills_for_cycle(conn, args.cycle_id, args.variant_id)
        if args.dry_run:
            conn.execute("ROLLBACK")
            print("\n[DRY-RUN] ROLLBACK effectue")
        else:
            conn.execute("COMMIT")
            print("\n[APPLY] COMMIT effectue")
    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"\n[ERROR] {e}")
        raise

    print("\n[RESULTATS]")
    for vname, s in stats.items():
        print(f"\n  Variant : {vname}")
        for k, v in s.items():
            if isinstance(v, float):
                print(f"    {k:20s} : {v:,.2f}")
            else:
                print(f"    {k:20s} : {v}")

    if not args.dry_run:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as n FROM shadow_fills WHERE cycle_id=?", (args.cycle_id,))
        n = cur.fetchone()['n']
        print(f"\n[VERIFICATION] shadow_fills total cycle : {n}")

    conn.close()
    print("\n" + "="*78)
    print("DONE")
    print("="*78)


if __name__ == "__main__":
    main()

