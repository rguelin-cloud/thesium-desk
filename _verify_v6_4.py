"""
Verification dry-run du patch v6.4 (TargetGap synthesizer).
Ne touche pas a la DB, simule juste l'appel de _build_target_gap_proposals
avec les donnees actuelles de la base.

Usage:
  py -3.13 _verify_v6_4.py
"""
import sqlite3
import os
import sys

if not os.path.exists("thesium.db"):
    print("[ERREUR] thesium.db introuvable. Lance depuis ThesiumDesk.")
    sys.exit(1)

# Importer la fonction sans declencher tout le pipeline
sys.path.insert(0, ".")
try:
    from execution_engine import (
        _build_target_gap_proposals,
        _load_target_weights,
        TARGET_GAP_MIN_DELTA_PCT,
        TARGET_GAP_CONVICTION,
    )
except ImportError as e:
    print(f"[ERREUR] execution_engine v6.4 non installe : {e}")
    print("Verifie que execution_engine.py est bien la copie de v6.4")
    sys.exit(1)

conn = sqlite3.connect("thesium.db")
conn.row_factory = sqlite3.Row

# NAV actuel
ps = conn.execute("SELECT total_value, cash FROM portfolio_state WHERE id=1").fetchone()
total_value = float(ps["total_value"]) if ps else 1_000_000.0
print(f"NAV = ${total_value:,.0f}")
print(f"Cash = ${ps['cash']:,.0f}\n" if ps else "")

# Targets actifs
print("=" * 78)
print("CIBLES ACTIVES (portfolio_targets)")
print("=" * 78)
targets = _load_target_weights(conn)
for t, w in targets.items():
    print(f"  {t:<6} {w:.2f}%")

print()
print("=" * 78)
print("SIMULATION _build_target_gap_proposals (regime BUILD)")
print("=" * 78)

# Simule un appel SANS proposition existante (worst case)
synth, _, stats = _build_target_gap_proposals(
    conn, total_value, existing_proposals=[], regime="BUILD"
)

print()
print("=" * 78)
print("RESULTAT")
print("=" * 78)
print(f"Propositions synthetiques generees : {len(synth)}")
for p in synth:
    print(f"  {p['ticker']:<6} {p['side'].upper():<4} qty_pct={p['quantity_pct']:.2f}% "
          f"conv={p['conviction']} \u2014 {p['reason']}")

print()
print(f"Stats : BUY={stats['n_buy_inj']}, SELL={stats['n_sell_inj']}, "
      f"merged={stats['n_merged']}, skipped<{TARGET_GAP_MIN_DELTA_PCT}%={stats['n_skipped_small']}")
print(f"Gap total |\u0394| = {stats['gap_total_pct']:.2f}% NAV")

# Simule maintenant avec META deja propose par FactorAgent (test du merge)
print()
print("=" * 78)
print("SIMULATION 2 : avec META deja propose par FactorAgent (quantity_pct=2.0)")
print("=" * 78)
fake_existing = [{
    "thesis_id": 999, "ticker": "META", "side": "buy",
    "quantity_pct": 2.0, "source": "FactorAgent",
    "conviction": 6.5,
}]
synth2, merged2, stats2 = _build_target_gap_proposals(
    conn, total_value, existing_proposals=fake_existing, regime="BUILD"
)
print(f"\nApres merge : META proposal modifiee ?")
print(f"  qty_pct = {merged2[0]['quantity_pct']:.2f}% (etait 2.0)")
print(f"  reason  = {merged2[0].get('reason', 'aucun')}")
print(f"  conv    = {merged2[0]['conviction']} (etait 6.5)")
print(f"Synthetiques additionnelles : {len(synth2)}")
print(f"Stats : merged={stats2['n_merged']}")

conn.close()
print()
print("=" * 78)
print("FIN VERIFICATION v6.4")
print("=" * 78)
