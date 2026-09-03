"""
_why_meta_sell.py — Diagnostic : pourquoi un SELL META a-t-il été émis ?

Usage (depuis C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk) :
    py -3.13 _why_meta_sell.py
"""
import sqlite3
import os

DB_PATH = "thesium.db"

if not os.path.exists(DB_PATH):
    print(f"ERREUR : {DB_PATH} introuvable dans {os.getcwd()}")
    raise SystemExit(1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

def section(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


# ---------------------------------------------------------------------------
# 1. ExitAgent — qu'a-t-il décidé pour META ?
# ---------------------------------------------------------------------------
section("1. exit_decisions_log — décisions ExitAgent sur META")
try:
    rows = conn.execute("""
        SELECT cycle_id, ticker, rule, action, pnl_pct,
               current_weight_pct, target_weight_pct, drift_rel_pct,
               days_held, qty_proposed, reason, created_at
        FROM exit_decisions_log
        WHERE ticker = 'META'
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()
    if not rows:
        print("(aucune entrée — ExitAgent n'a pas tourné ou pas évalué META)")
    for r in rows:
        print(f"  [{r['created_at']}] cycle={r['cycle_id']} "
              f"rule={r['rule']:12s} action={r['action']:10s} "
              f"pnl={r['pnl_pct']:+.2f}% "
              f"w={r['current_weight_pct']:.2f}%/{r['target_weight_pct']:.2f}% "
              f"drift={r['drift_rel_pct']:+.1f}% days={r['days_held']}")
        print(f"        → {r['reason']}")
except sqlite3.OperationalError as e:
    print(f"(table absente ou erreur : {e})")


# ---------------------------------------------------------------------------
# 2. OrderReconciler — qu'a-t-il fait pour META ?
# ---------------------------------------------------------------------------
section("2. cycle_reconciliation_log — passages Reconciler sur META")
try:
    rows = conn.execute("""
        SELECT cycle_id, ticker, action, reason,
               signals_in, qty_in, side_in, conviction_max,
               delta_signal_pct, delta_target_pct, created_at
        FROM cycle_reconciliation_log
        WHERE ticker = 'META'
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()
    if not rows:
        print("(aucune entrée)")
    for r in rows:
        print(f"  [{r['created_at']}] cycle={r['cycle_id']} "
              f"action={r['action']:11s} side={r['side_in']:6s} "
              f"qty={r['qty_in']} conv_max={r['conviction_max']:.0f} "
              f"signals_in={r['signals_in']}")
        print(f"        Δsignal={r['delta_signal_pct']:+.3f}%  "
              f"Δtarget={r['delta_target_pct']:+.3f}%")
        print(f"        → {r['reason']}")
except sqlite3.OperationalError as e:
    print(f"(table absente ou erreur : {e})")


# ---------------------------------------------------------------------------
# 3. Théses META récentes — qui a généré le signal ?
# ---------------------------------------------------------------------------
section("3. theses sur META (colonnes réelles : agent_type, conviction_score, proposed_action)")
# Schéma réel : agent_type, conviction_score, thesis_text, proposed_action, status
rows = conn.execute("""
    SELECT t.id, t.agent_type, t.conviction_score, t.proposed_action,
           t.thesis_text, t.key_drivers, t.horizon, t.status, t.created_at
    FROM theses t
    JOIN instruments i ON i.id = t.instrument_id
    WHERE i.ticker = 'META'
    ORDER BY t.id DESC LIMIT 8
""").fetchall()
for r in rows:
    print(f"  thesis_id={r['id']:5d}  agent_type={r['agent_type']!r:20s}  "
          f"conv={r['conviction_score']}  action={r['proposed_action']!r}  "
          f"status={r['status']!r}")
    print(f"        created_at: {r['created_at']}")
    if r['thesis_text']:
        print(f"        text: {str(r['thesis_text'])[:200]}")
    if r['key_drivers']:
        print(f"        drivers: {str(r['key_drivers'])[:200]}")
    print()


# ---------------------------------------------------------------------------
# 4. L'ordre SELL META filled + sa thèse liée (colonnes corrigées)
# ---------------------------------------------------------------------------
section("4. Ordres META filled — thesis_id et agent associé")
rows = conn.execute("""
    SELECT o.id, o.side, o.quantity, o.status, o.thesis_id, o.created_at,
           t.agent_type, t.conviction_score, t.proposed_action,
           t.thesis_text, t.key_drivers
    FROM orders o
    LEFT JOIN theses t ON t.id = o.thesis_id
    JOIN instruments i ON i.id = o.instrument_id
    WHERE i.ticker = 'META' AND o.status = 'filled'
    ORDER BY o.id DESC LIMIT 5
""").fetchall()
if not rows:
    print("(aucun ordre META filled)")
for r in rows:
    print(f"  order_id={r['id']} {r['side'].upper()} qty={r['quantity']} "
          f"thesis_id={r['thesis_id']} [{r['created_at']}]")
    print(f"        agent_type={r['agent_type']!r}  conv={r['conviction_score']}  "
          f"action={r['proposed_action']!r}")
    if r['thesis_text']:
        print(f"        text: {str(r['thesis_text'])[:300]}")
    if r['key_drivers']:
        print(f"        drivers: {str(r['key_drivers'])[:300]}")
    print()


# ---------------------------------------------------------------------------
# 5. Position META actuelle
# ---------------------------------------------------------------------------
section("5. Position META actuelle (devrait être vide après le SELL 16)")
row = conn.execute("""
    SELECT p.quantity, p.avg_cost, p.current_price, p.unrealized_pnl,
           p.weight_pct, p.updated_at
    FROM portfolio_positions p
    JOIN instruments i ON i.id = p.instrument_id
    WHERE i.ticker = 'META'
""").fetchone()
if row:
    print(f"  qty={row['quantity']} avg_cost={row['avg_cost']} "
          f"price={row['current_price']} pnl={row['unrealized_pnl']} "
          f"weight={row['weight_pct']}% updated={row['updated_at']}")
else:
    print("  (pas de position META — entièrement vendue)")


conn.close()
print()
print("=" * 80)
print("Diagnostic terminé.")
print("=" * 80)
