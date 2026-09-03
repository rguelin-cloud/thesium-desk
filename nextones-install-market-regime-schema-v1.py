# -*- coding: utf-8 -*-
"""
[INSTALL_MARKET_REGIME_SCHEMA_V1]
Cree la table market_regime_log et ajoute colonnes equity_regime/crypto_regime
dans regime_log. Idempotent.

Schema :
  market_regime_log
    id                  PK
    cycle_id            TEXT
    asset_class         TEXT  ('equity' | 'crypto')
    regime              TEXT  ('CALM' | 'NORMAL' | 'STRESS')
    vix_value           REAL  (uniquement equity, NULL pour crypto)
    realized_vol_pct    REAL  (volatilite realisee 20j annualisee, en %)
    drawdown_5d_pct     REAL  (drawdown 5j en %)
    score               REAL  (score composite 0-100)
    buy_mult            REAL  (multiplicateur cap BUY)
    sell_mult           REAL  (multiplicateur cap SELL)
    convergence_thresh  REAL  (seuil convergence ajuste)
    details_json        TEXT  (raw signals pour audit)
    notes               TEXT
    created_at          TEXT  default datetime('now')
"""
import sqlite3
import sys

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("[INSTALL_MARKET_REGIME_SCHEMA_V1] DEBUT")

# 1. Table market_regime_log
existing = cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='market_regime_log'"
).fetchone()
if existing:
    print("  [SKIP] Table market_regime_log existe deja")
else:
    cur.execute("""
        CREATE TABLE market_regime_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_id TEXT,
            asset_class TEXT NOT NULL,
            regime TEXT NOT NULL,
            vix_value REAL,
            realized_vol_pct REAL,
            drawdown_5d_pct REAL,
            score REAL,
            buy_mult REAL,
            sell_mult REAL,
            convergence_thresh REAL,
            details_json TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute("CREATE INDEX idx_market_regime_log_cycle ON market_regime_log(cycle_id)")
    cur.execute("CREATE INDEX idx_market_regime_log_class_date ON market_regime_log(asset_class, created_at)")
    print("  [OK] Table market_regime_log creee + indexes")

# 2. Colonnes equity_regime + crypto_regime dans regime_log
existing_cols = [r["name"] for r in cur.execute("PRAGMA table_info(regime_log)").fetchall()]
new_cols = [
    ("equity_regime", "TEXT"),
    ("crypto_regime", "TEXT"),
    ("equity_buy_mult", "REAL"),
    ("equity_sell_mult", "REAL"),
    ("crypto_buy_mult", "REAL"),
    ("crypto_sell_mult", "REAL"),
]
for col_name, col_type in new_cols:
    if col_name in existing_cols:
        print(f"  [SKIP] regime_log.{col_name} existe deja")
    else:
        cur.execute(f"ALTER TABLE regime_log ADD COLUMN {col_name} {col_type}")
        print(f"  [OK] regime_log.{col_name} ({col_type}) ajoute")

con.commit()

# 3. Verification
print("\n  Verification finale :")
cols = [r["name"] for r in cur.execute("PRAGMA table_info(market_regime_log)").fetchall()]
print(f"    market_regime_log : {len(cols)} colonnes = {cols}")
cols = [r["name"] for r in cur.execute("PRAGMA table_info(regime_log)").fetchall()]
print(f"    regime_log : {len(cols)} colonnes")
for c in new_cols:
    status = "OK" if c[0] in cols else "MANQUE"
    print(f"      {c[0]:<20} [{status}]")

con.close()
print("\n[INSTALL_MARKET_REGIME_SCHEMA_V1] FIN")
