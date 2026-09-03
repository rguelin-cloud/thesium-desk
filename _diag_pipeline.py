"""
Diagnostic 2: pipeline Run Decision Cycle de bout en bout
Repond aux 3 questions:
  1. Comment instrument_id (INT) se mappe au ticker (TEXT) ?
  2. Le Reconciler recoit-il des propositions ?
  3. Le cycle 15:17:40 a-t-il sorti des orders ?
"""
import sqlite3
import os
import sys

DB_PATH = "thesium.db"
if not os.path.exists(DB_PATH):
    print(f"[ERREUR] {DB_PATH} introuvable. Lance depuis ThesiumDesk")
    sys.exit(1)

c = sqlite3.connect(DB_PATH)
c.row_factory = sqlite3.Row


def section(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


def dump_table(name, limit=20, where=""):
    section(f"TABLE: {name}")
    try:
        rows = c.execute(f"SELECT * FROM {name} {where} LIMIT {limit}").fetchall()
        if not rows:
            print("(vide)")
            return
        cols = rows[0].keys()
        widths = [max(len(col), max((len(str(r[col])) for r in rows), default=0)) for col in cols]
        widths = [min(w, 25) for w in widths]
        print(" | ".join(col.ljust(w) for col, w in zip(cols, widths)))
        print("-+-".join("-" * w for w in widths))
        for r in rows:
            print(" | ".join(str(r[col])[:25].ljust(w) for col, w in zip(cols, widths)))
        # total count
        n = c.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"\n[total: {n} lignes]")
    except sqlite3.OperationalError as e:
        print(f"[introuvable: {e}]")


# --- 1. instruments : mapping id <-> ticker ----------------------------------
section("1. MAPPING instrument_id -> ticker (table instruments)")
try:
    rows = c.execute("SELECT id, symbol, ticker, name FROM instruments ORDER BY id").fetchall()
except sqlite3.OperationalError:
    # essaie variantes
    try:
        rows = c.execute("SELECT * FROM instruments ORDER BY id LIMIT 30").fetchall()
    except sqlite3.OperationalError:
        rows = []

if rows:
    cols = rows[0].keys()
    print(" | ".join(cols))
    print("-" * 78)
    for r in rows:
        print(" | ".join(str(r[col])[:30] for col in cols))
else:
    print("[table instruments introuvable - essaie d'autres noms]")
    for tbl in ("tickers", "assets", "symbols"):
        try:
            rows = c.execute(f"SELECT * FROM {tbl} LIMIT 30").fetchall()
            print(f"\n[trouve: {tbl}]")
            if rows:
                cols = rows[0].keys()
                print(" | ".join(cols))
                print("-" * 78)
                for r in rows:
                    print(" | ".join(str(r[col])[:30] for col in cols))
            break
        except sqlite3.OperationalError:
            continue

# --- 2. Toutes les tables de la DB -------------------------------------------
section("2. LISTE COMPLETE DES TABLES")
rows = c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
for r in rows:
    n = c.execute(f"SELECT COUNT(*) FROM {r['name']}").fetchone()[0]
    print(f"  {r['name']:<40} {n:>8} lignes")

# --- 3. proposals / order_proposals (entrée du Reconciler) -------------------
for tname in ("proposals", "order_proposals", "agent_proposals", "trade_proposals"):
    dump_table(tname, limit=30)

# --- 4. orders / fills (sortie du Reconciler) --------------------------------
for tname in ("orders", "order_intents", "fills", "trades", "executions"):
    dump_table(tname, limit=20, where="ORDER BY rowid DESC")

# --- 5. portfolio_targets (cibles actives) -----------------------------------
dump_table("portfolio_targets", limit=20)

# --- 6. portfolio_positions (positions actuelles) ----------------------------
dump_table("portfolio_positions", limit=20)

# --- 7. logs / reconciler_log si existe --------------------------------------
for tname in ("reconciler_log", "cycle_log", "agent_log", "decisions"):
    dump_table(tname, limit=20, where="ORDER BY rowid DESC")

# --- 8. Schema theses (verifier le type de instrument_id) --------------------
section("8. SCHEMA TABLE theses")
rows = c.execute("PRAGMA table_info(theses)").fetchall()
for r in rows:
    print(f"  {r['name']:<25} {r['type']:<15} pk={r['pk']} notnull={r['notnull']}")

# --- 9. Schema portfolio_targets ---------------------------------------------
section("9. SCHEMA TABLE portfolio_targets")
rows = c.execute("PRAGMA table_info(portfolio_targets)").fetchall()
for r in rows:
    print(f"  {r['name']:<25} {r['type']:<15} pk={r['pk']} notnull={r['notnull']}")

# --- 10. Join theses x instruments ------------------------------------------
section("10. JOIN theses x instruments (derniere passe agents)")
try:
    rows = c.execute("""
        SELECT t.instrument_id, i.symbol AS ticker, t.agent_type,
               t.conviction_score, t.proposed_action, t.status,
               datetime(t.created_at) as ts
        FROM theses t
        LEFT JOIN instruments i ON i.id = t.instrument_id
        WHERE t.status='active'
        ORDER BY t.created_at DESC
        LIMIT 30
    """).fetchall()
    for r in rows:
        print(f"  id={r['instrument_id']:<4} ticker={(r['ticker'] or '?'):<6} {r['agent_type']:<22} "
              f"conv={r['conviction_score']:<4} action={r['proposed_action'][:60]}")
except sqlite3.OperationalError as e:
    print(f"[err: {e}]")

print()
print("=" * 78)
print("FIN DIAG 2")
print("=" * 78)
c.close()
