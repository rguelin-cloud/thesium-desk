#!/usr/bin/env python3
# Collecte toutes les donnees factuelles pour le Verdict v4
# Genere un JSON avec les valeurs reelles (pas de blabla, que du factuel)

import sqlite3, json
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"
OUT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\nextones-verdict-v4-data.json")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

data = {
    "generated_at": datetime.now().isoformat(),
    "session_milestones": {},
    "controls": {},
    "config": {},
    "runtime": {},
    "universe": {},
}

# === 1. Risk config + risk_pretrade params ===
cur.execute("SELECT * FROM risk_config LIMIT 1")
r = cur.fetchone()
if r:
    data["controls"]["risk_engine_v1_legacy"] = {
        "max_position_pct": r["max_position_pct"],
        "max_sector_pct": r["max_sector_pct"],
        "max_single_name_pct": r["max_single_name_pct"],
        "max_var_pct": r["max_var_pct"],
        "stop_loss_pct": r["stop_loss_pct"],
        "updated_at": r["updated_at"],
    }

# === 2. Risk Engine v2 (depuis risk_pretrade.py DEFAULT_PARAMS) ===
# On lit le module directement
import sys
sys.path.insert(0, str(ROOT))
try:
    from risk_pretrade import DEFAULT_PARAMS as P
    data["controls"]["risk_engine_v2"] = {
        "marker": "[RISK_V2]",
        "params": dict(P) if hasattr(P, "items") else {},
        "fix_applied": "[RISK_V2_DBLOCK_FIX_V1]",
    }
except Exception as e:
    data["controls"]["risk_engine_v2"] = {"error": str(e)}

# === 3. Sample d'une entree risk_pretrade_log (smoke test reussi) ===
cur.execute("SELECT * FROM risk_pretrade_log ORDER BY id DESC LIMIT 1")
r = cur.fetchone()
if r:
    details = json.loads(r["details_json"]) if r["details_json"] else {}
    data["controls"]["risk_engine_v2_runtime_sample"] = {
        "ts": r["ts"],
        "symbol": r["symbol"],
        "side": r["side"],
        "passed": bool(r["passed"]),
        "details": details,
    }

# === 4. target_construction_config (config decision) ===
cur.execute("SELECT params_json, updated_at FROM target_construction_config LIMIT 1")
r = cur.fetchone()
if r:
    data["config"]["target_construction"] = {
        "params": json.loads(r["params_json"]),
        "updated_at": r["updated_at"],
    }

# === 5. target_universe (univers actuel + caps) ===
cur.execute("SELECT * FROM target_universe ORDER BY ticker")
data["universe"]["target_universe"] = [dict(r) for r in cur.fetchall()]

# === 6. instruments (univers brut) ===
cur.execute("SELECT id, ticker, name, sector, asset_class FROM instruments ORDER BY id")
data["universe"]["instruments"] = [dict(r) for r in cur.fetchall()]

# === 7. Snapshot actif + targets ===
cur.execute("SELECT * FROM portfolio_targets ORDER BY snapshot_id DESC, target_weight_pct DESC")
data["runtime"]["portfolio_targets_active"] = [dict(r) for r in cur.fetchall()]

# === 8. NAV courant + positions ===
try:
    cur.execute("SELECT * FROM portfolio_history ORDER BY date DESC LIMIT 1")
    r = cur.fetchone()
    if r:
        data["runtime"]["portfolio_latest"] = dict(r)
except Exception as e:
    data["runtime"]["portfolio_latest_err"] = str(e)

# === 9. Stats ordres 29/05 ===
cur.execute("""
    SELECT COUNT(*) AS n, SUM(quantity * COALESCE(limit_price, 0)) AS total_notional
    FROM orders WHERE created_at LIKE '2026-05-29%'
""")
r = cur.fetchone()
data["runtime"]["orders_today"] = {"count": r["n"], "approx_notional": r["total_notional"]}

cur.execute("""
    SELECT id, instrument_id, side, quantity, status, risk_check_result, created_at
    FROM orders WHERE created_at LIKE '2026-05-29%' ORDER BY id
""")
orders = []
for r in cur.fetchall():
    rc = json.loads(r["risk_check_result"]) if r["risk_check_result"] else {}
    orders.append({
        "id": r["id"],
        "instrument_id": r["instrument_id"],
        "side": r["side"],
        "quantity": r["quantity"],
        "status": r["status"],
        "approved": rc.get("approved"),
        "warnings_v2": [w for w in rc.get("warnings", []) if w.get("source") == "[RISK_V2]"],
        "metrics": rc.get("metrics", {}),
        "created_at": r["created_at"],
    })
data["runtime"]["orders_today_detail"] = orders

# === 10. Session milestones (recap des patches appliques) ===
data["session_milestones"] = {
    "fred_is_past_datetime": {"marker": "[FRED_IS_PAST_DATETIME_V1]", "status": "applied"},
    "fred_gdp_series": {"marker": "[FRED_GDP_SERIES_V1]", "status": "applied", "series": "A191RL1Q225SBEA", "fmt": "raw_pct"},
    "targets_caps_smoothing": {"marker": "[TARGETS_CAPS_SMOOTHING_V1]", "status": "applied"},
    "risk_v2_dblock_fix": {"marker": "[RISK_V2_DBLOCK_FIX_V1]", "status": "applied"},
    "build_qty1_override_removed": {"status": "applied"},
    "geo_panel_mutation_observer": {"status": "applied"},
}

# === 11. Ordres en stats globales ===
cur.execute("SELECT COUNT(*) AS n FROM orders")
data["runtime"]["orders_total_history"] = cur.fetchone()["n"]
cur.execute("SELECT COUNT(*) AS n FROM risk_pretrade_log")
data["runtime"]["risk_pretrade_log_count"] = cur.fetchone()["n"]

conn.close()

OUT.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
print(f"OK Donnees collectees -> {OUT}")
print(f"Total bytes: {OUT.stat().st_size}")

# Print summary
print("\n=== RESUME ===")
print(f"  Risk Engine v1 (legacy)     : {len(data['controls'].get('risk_engine_v1_legacy', {}))} params")
print(f"  Risk Engine v2              : {len(data['controls'].get('risk_engine_v2', {}).get('params', {}))} params")
print(f"  target_construction params  : {len(data['config'].get('target_construction', {}).get('params', {}))} keys")
print(f"  Univers (target_universe)   : {len(data['universe']['target_universe'])} tickers")
print(f"  Univers (instruments)       : {len(data['universe']['instruments'])} tickers")
print(f"  Targets actifs              : {len(data['runtime']['portfolio_targets_active'])} positions")
print(f"  Ordres 29/05                : {data['runtime']['orders_today']['count']}")
print(f"  risk_pretrade_log total     : {data['runtime']['risk_pretrade_log_count']}")
