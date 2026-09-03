-- nextones-install-replay-schema-8b3-v1.sql
-- Schema 8B.3 : tables d'export execution engine
-- Tables : replay_orders, replay_fills, replay_positions, replay_nav_history

CREATE TABLE IF NOT EXISTS replay_orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES replay_runs(run_id),
    cycle_id_replay INTEGER NOT NULL REFERENCES replay_cycles(cycle_id),
    day_t           TEXT NOT NULL,
    cycle_id_prod   TEXT,
    ticker          TEXT NOT NULL,
    side            TEXT NOT NULL,
    qty             REAL NOT NULL,
    qty_target      REAL,
    qty_current     REAL,
    target_weight_pct REAL,
    status          TEXT NOT NULL,
    fill_price      REAL,
    slippage_bps    REAL,
    price_close_t   REAL,
    nav_before      REAL,
    risk_check_json TEXT,
    rejection_reason TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_replay_orders_run ON replay_orders(run_id);
CREATE INDEX IF NOT EXISTS idx_replay_orders_cycle ON replay_orders(cycle_id_replay);
CREATE INDEX IF NOT EXISTS idx_replay_orders_ticker ON replay_orders(run_id, ticker);

CREATE TABLE IF NOT EXISTS replay_fills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES replay_runs(run_id),
    cycle_id_replay INTEGER NOT NULL REFERENCES replay_cycles(cycle_id),
    day_t           TEXT NOT NULL,
    day_fill        TEXT,
    ticker          TEXT NOT NULL,
    side            TEXT NOT NULL,
    fill_price      REAL NOT NULL,
    fill_quantity   REAL NOT NULL,
    open_j1         REAL,
    slippage_bps    REAL,
    fees            REAL DEFAULT 0,
    notional        REAL,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_replay_fills_run ON replay_fills(run_id);
CREATE INDEX IF NOT EXISTS idx_replay_fills_cycle ON replay_fills(cycle_id_replay);

CREATE TABLE IF NOT EXISTS replay_positions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES replay_runs(run_id),
    cycle_id_replay INTEGER NOT NULL REFERENCES replay_cycles(cycle_id),
    day_t           TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    quantity        REAL NOT NULL,
    avg_cost        REAL,
    current_price   REAL,
    weight_pct      REAL,
    unrealized_pnl  REAL,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_replay_positions_run ON replay_positions(run_id);
CREATE INDEX IF NOT EXISTS idx_replay_positions_cycle ON replay_positions(cycle_id_replay);

CREATE TABLE IF NOT EXISTS replay_nav_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES replay_runs(run_id),
    cycle_id_replay INTEGER NOT NULL REFERENCES replay_cycles(cycle_id),
    day_t           TEXT NOT NULL,
    nav             REAL NOT NULL,
    cash            REAL NOT NULL,
    positions_value REAL NOT NULL,
    daily_pnl       REAL DEFAULT 0,
    daily_pnl_pct   REAL DEFAULT 0,
    cumul_pnl       REAL DEFAULT 0,
    cumul_pnl_pct   REAL DEFAULT 0,
    n_positions     INTEGER DEFAULT 0,
    n_orders        INTEGER DEFAULT 0,
    n_fills         INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(run_id, day_t)
);
CREATE INDEX IF NOT EXISTS idx_replay_nav_run ON replay_nav_history(run_id);
