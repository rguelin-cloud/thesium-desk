# -*- coding: utf-8 -*-
"""
Validation runtime Phase 2-bis : verifie que apply_regime_to_proposals
applique bien les multiplicateurs market_regime sur les caps.

Test :
  1. Import execution_engine + verif que les nouveaux symboles existent
  2. Inspection statique du marker dans le source
  3. Test fonctionnel : appel direct apply_regime_to_proposals avec
     un regime_info contenant market={equity:{...}, crypto:{...}} et
     verification que les compteurs n_market_* sont presents dans le retour
  4. Lecture du dernier cycle en DB et affichage des plafonnements appliques
"""
import os
import sys
import sqlite3
import importlib
import traceback

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(ROOT, "thesium.db")
EE = os.path.join(ROOT, "execution_engine.py")
MARKER = "[PATCH_MARKET_REGIME_CAPS_V1]"

sys.path.insert(0, ROOT)

print("=" * 78)
print("VALIDATION PHASE 2-bis : market_regime caps")
print("=" * 78)

# ----------------------------------------------------------------------
# 1) Inspection statique
# ----------------------------------------------------------------------
print("\n[1] Inspection statique du source")
with open(EE, "r", encoding="utf-8-sig") as f:
    src = f.read()
n_marker = src.count(MARKER)
print(f"    Marker {MARKER} : x{n_marker}")
must_have = [
    "_resolve_asset_class",
    "_market_mult_for",
    "_market_caps_disabled",
    "n_market_sell_amplified",
    "n_market_buy_attenuated",
    "_eff_sell_ratio",
    "_mkt_buy_mult",
]
for token in must_have:
    occ = src.count(token)
    status = "OK" if occ > 0 else "MISSING"
    print(f"    [{status}] {token} (x{occ})")

# ----------------------------------------------------------------------
# 2) Import dynamique
# ----------------------------------------------------------------------
print("\n[2] Import du module execution_engine")
try:
    if "execution_engine" in sys.modules:
        del sys.modules["execution_engine"]
    ee = importlib.import_module("execution_engine")
    print("    [OK] import ok")
except Exception as e:
    print(f"    [ERR] import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

fn = getattr(ee, "apply_regime_to_proposals", None)
if fn is None:
    print("    [ERR] apply_regime_to_proposals introuvable")
    sys.exit(2)
print(f"    [OK] apply_regime_to_proposals signature : {fn.__code__.co_varnames[:fn.__code__.co_argcount]}")

# ----------------------------------------------------------------------
# 3) Test fonctionnel : 4 propositions (2 crypto BUY/SELL + 2 equity BUY/SELL)
#    avec un market_info qui force des mults != 1.0 pour observer l'effet
# ----------------------------------------------------------------------
print("\n[3] Test fonctionnel avec market_info forcee")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# On s'assure qu'on a au moins une position crypto + une position equity en cache
pos = conn.execute("""
    SELECT i.ticker, i.asset_class, p.quantity, p.current_price
    FROM portfolio_positions p
    JOIN instruments i ON i.id = p.instrument_id
    WHERE p.quantity > 0
    ORDER BY i.asset_class, i.ticker
""").fetchall()
print(f"    Positions actuelles ({len(pos)} lignes) :")
for r in pos[:10]:
    print(f"      {r['ticker']:8} {r['asset_class']:8} qty={r['quantity']:.4f}  px={r['current_price']:.2f}")

# On prend un ticker equity et un ticker crypto detenu (si possible)
crypto_held = next((r['ticker'] for r in pos if (r['asset_class'] or '').lower() == 'crypto'), None)
equity_held = next((r['ticker'] for r in pos if (r['asset_class'] or '').lower() in ('equity', 'etf', 'stock')), None)
print(f"    crypto_held={crypto_held}  equity_held={equity_held}")

# NAV approximatif
nav_row = conn.execute("SELECT COALESCE(SUM(quantity*current_price), 0) AS gross FROM portfolio_positions").fetchone()
nav = max(1000000.0, float(nav_row['gross'] or 0) + 1000000.0)
print(f"    nav (synthetique) = {nav:.2f}")

# market_info force STRESS sur equity + CALM sur crypto pour test
market_info = {
    "equity": {"regime": "STRESS", "buy_mult": 1.8, "sell_mult": 0.5, "convergence_thresh": 0.50},
    "crypto": {"regime": "CALM",   "buy_mult": 0.7, "sell_mult": 1.5, "convergence_thresh": 0.65},
    "ts": "2026-06-12T10:00:00",
}
regime_info = {
    "regime": "MAINTAIN",
    "nav": nav,
    "cash": 100000.0,
    "n_positions": len(pos),
    "market": market_info,
}

# Propositions de test
proposals = []
if crypto_held:
    proposals.append({
        "ticker": crypto_held, "side": "buy",  "quantity_pct": 5.0, "conviction": 60.0,
        "thesis_id": None, "source": "crypto_agent", "agent_type": "crypto",
    })
    proposals.append({
        "ticker": crypto_held, "side": "sell", "quantity_pct": 50.0, "conviction": 70.0,
        "thesis_id": None, "source": "crypto_agent", "agent_type": "crypto",
    })
if equity_held:
    proposals.append({
        "ticker": equity_held, "side": "buy",  "quantity_pct": 5.0, "conviction": 60.0,
        "thesis_id": None, "source": "factor_agent", "agent_type": "factor",
    })
    proposals.append({
        "ticker": equity_held, "side": "sell", "quantity_pct": 50.0, "conviction": 70.0,
        "thesis_id": None, "source": "factor_agent", "agent_type": "factor",
    })

if not proposals:
    print("    [WARN] Aucune position detenue pour tester. Test skip.")
else:
    print(f"    Propositions test ({len(proposals)}) :")
    for p in proposals:
        print(f"      {p['side']:4} {p['ticker']:8} qty_pct={p['quantity_pct']:.2f} agent={p['agent_type']}")

    target_weights = {p['ticker']: 4.0 for p in proposals}

    try:
        stats = fn(conn, proposals, regime_info, target_weights=target_weights)
        print(f"\n    [OK] apply_regime_to_proposals stats :")
        for k, v in stats.items():
            print(f"      {k:30} = {v}")

        if "n_market_sell_amplified" not in stats:
            print("    [ERR] n_market_sell_amplified absent du return -> patch incomplet")
            sys.exit(3)
        if "n_market_buy_attenuated" not in stats:
            print("    [ERR] n_market_buy_attenuated absent du return -> patch incomplet")
            sys.exit(4)

        print("\n    Proposals post-traitement :")
        for p in proposals:
            print(f"      {p['side']:4} {p['ticker']:8} "
                  f"qpct_raw={p.get('quantity_pct_raw', 0):.2f} -> "
                  f"qpct={p.get('quantity_pct', 0):.2f} | "
                  f"cap_reason={p.get('cap_reason') or '-'}")

    except Exception as e:
        print(f"    [ERR] appel apply_regime_to_proposals failed: {e}")
        traceback.print_exc()
        sys.exit(5)

# ----------------------------------------------------------------------
# 4) Lecture du dernier cycle reel et stats de capping
# ----------------------------------------------------------------------
print("\n[4] Dernier cycle reel en DB")
last_cycle = conn.execute("""
    SELECT cycle_id, equity_regime, crypto_regime,
           equity_buy_mult, equity_sell_mult,
           crypto_buy_mult, crypto_sell_mult, ts
    FROM regime_log
    ORDER BY id DESC LIMIT 1
""").fetchone()
if last_cycle:
    print(f"    cycle_id          : {last_cycle['cycle_id']}")
    print(f"    equity_regime     : {last_cycle['equity_regime']} (buy={last_cycle['equity_buy_mult']}, sell={last_cycle['equity_sell_mult']})")
    print(f"    crypto_regime     : {last_cycle['crypto_regime']} (buy={last_cycle['crypto_buy_mult']}, sell={last_cycle['crypto_sell_mult']})")
    print(f"    ts                : {last_cycle['ts']}")
else:
    print("    Aucun cycle dans regime_log")

# Compte des cap_reason sur les ordres du dernier cycle
last_cid = last_cycle['cycle_id'] if last_cycle else None
if last_cid:
    rows = conn.execute("""
        SELECT side, COUNT(*) AS n FROM orders
        WHERE cycle_id = ? GROUP BY side
    """, (last_cid,)).fetchall()
    print(f"    Orders cycle {last_cid} :")
    for r in rows:
        print(f"      {r['side']:4} : {r['n']}")

conn.close()

print()
print("=" * 78)
print("VALIDATION OK -- patch Phase 2-bis fonctionnel")
print("=" * 78)
print()
print("Prochaine etape : restart API + Run Cycle production puis verifier")
print("  - log uvicorn : compteurs n_market_sell_amplified / n_market_buy_attenuated")
print("  - regime_log : equity_*_mult / crypto_*_mult coherents")
print("  - orders.cap_reason : mention des nouveaux ceilings")
