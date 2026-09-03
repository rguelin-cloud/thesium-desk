# -*- coding: utf-8 -*-
# [NEXTONES-VALIDATE-BROKER-PHASE2-V1]
# Smoke test bout-en-bout Phase 2 :
#   1. verifie que les tables shadow existent
#   2. fait passer 8 ordres du cycle 30/05 + HYPE + 1 BTC dans le pipeline
#      complet : risk_broker_check -> shadow_executor.execute_shadow
#   3. affiche un tableau recapitulatif
#   4. lance snapshot_pnl (no-op si MetaAPI absent)
#
# Ne modifie PAS risk_engine en production. Pose les fondations.

import os
import sys
import json
import sqlite3
import importlib.util
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "THESIUM_DB",
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db",
)

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def main():
    if not os.path.exists(DB_PATH):
        print("[ERR] DB introuvable: " + DB_PATH); sys.exit(2)

    print("[INFO] DB: " + DB_PATH)

    rbc = _load("rbc", "nextones-risk-broker-check.py")
    sx  = _load("sx",  "nextones-broker-shadow-executor.py")

    # 1. verif tables
    con = sqlite3.connect(DB_PATH); cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND "
                "name IN ('broker_shadow_orders','broker_shadow_pnl',"
                "         'broker_shadow_audit','broker_universe_activtrades',"
                "         'instrument_broker_mapping','broker_mapping_audit')")
    found = sorted([r[0] for r in cur.fetchall()])
    expected = ['broker_mapping_audit','broker_shadow_audit',
                'broker_shadow_orders','broker_shadow_pnl',
                'broker_universe_activtrades','instrument_broker_mapping']
    missing = [t for t in expected if t not in found]
    if missing:
        print("[ERR] tables manquantes: " + ", ".join(missing))
        sys.exit(3)
    print("[OK] 6 tables presentes (Phase 1 + Phase 2)")

    cycle = "smoke-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    proposals = [
        {"thesium_ticker": "CAT",  "side": "buy",  "qty": 22},
        {"thesium_ticker": "CSCO", "side": "buy",  "qty": 166},
        {"thesium_ticker": "TXN",  "side": "buy",  "qty": 65},
        {"thesium_ticker": "AMD",  "side": "buy",  "qty": 38},
        {"thesium_ticker": "PLD",  "side": "buy",  "qty": 139},
        {"thesium_ticker": "XLK",  "side": "buy",  "qty": 108},
        {"thesium_ticker": "AAPL", "side": "buy",  "qty": 13},
        {"thesium_ticker": "MSFT", "side": "sell", "qty": 22},
        {"thesium_ticker": "HYPE", "side": "buy",  "qty": 100},  # refus
        {"thesium_ticker": "BTC",  "side": "buy",  "qty": 0.05,
         "asset_class": "crypto"},
    ]

    print()
    print("ticker   side  qty    | check_ok | shadow_id | broker_symbol  | lots")
    print("-" * 80)

    ok_count = 0; rej_count = 0
    for p in proposals:
        check = rbc.check_broker_mapping(p)
        sid = "-"; sym = check.get("broker_symbol") or "-"
        lots = "-"
        if check["ok"]:
            x = sx.execute_shadow(
                p["thesium_ticker"], p["side"], p["qty"],
                cycle_id=cycle, asset_class=p.get("asset_class"),
            )
            sid = str(x.get("shadow_order_id") or "-")
            lots = str(x.get("volume_lots") or "-")
            ok_count += 1
        else:
            rej_count += 1
        print(
            "{tkr:8s} {side:5s} {qty:>6} | {ok:8s} | {sid:9s} | "
            "{sym:14s} | {lots}".format(
                tkr=p["thesium_ticker"], side=p["side"], qty=p["qty"],
                ok="OK" if check["ok"] else "REJET",
                sid=sid, sym=sym, lots=lots,
            )
        )

    print()
    print("Total: " + str(ok_count) + " acceptes, " + str(rej_count) + " rejetes")

    # Comptage final
    cur.execute("SELECT COUNT(*) FROM broker_shadow_orders WHERE cycle_id=?",
                (cycle,))
    n_shadow = cur.fetchone()[0]
    print("broker_shadow_orders inseres pour ce smoke: " + str(n_shadow))

    cur.execute("SELECT COUNT(*) FROM broker_mapping_audit WHERE ts >= datetime('now','-1 hour')")
    print("broker_mapping_audit derniere heure: " + str(cur.fetchone()[0]))

    cur.execute("SELECT COUNT(*) FROM broker_shadow_audit WHERE cycle_id=?",
                (cycle,))
    print("broker_shadow_audit pour ce smoke: " + str(cur.fetchone()[0]))

    con.close()

    # Snapshot P&L (no-op silencieux si MetaAPI absent)
    n = sx.snapshot_pnl()
    print("snapshot_pnl: " + str(n) + " lignes (0 attendu si MetaAPI non configure)")

    print()
    print("[VERDICT] Phase 2 OK si: 8 acceptes (cycle 30/05) + 1 BTC accepte + 1 HYPE rejete = 9 acceptes / 1 rejete")
    expected_ok = 9; expected_rej = 1
    if ok_count == expected_ok and rej_count == expected_rej:
        print("[VERDICT] PASS")
        sys.exit(0)
    else:
        print("[VERDICT] FAIL : attendu " + str(expected_ok) + " / "
              + str(expected_rej))
        sys.exit(4)


if __name__ == "__main__":
    main()
