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
