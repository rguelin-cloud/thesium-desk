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
