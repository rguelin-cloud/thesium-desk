"""
_show_cycle.py — Vue complète d'un cycle de décision (v6)

Joint regime_log + cycle_reconciliation_log + theses + exit_decisions_log + orders
pour un cycle_id donné, et affiche un rapport lisible.

Usage :
    py -3.13 _show_cycle.py                  # dernier cycle
    py -3.13 _show_cycle.py 20260524-113931  # cycle spécifique
"""
import sqlite3
import sys
import os

DB_PATH = "thesium.db"

if not os.path.exists(DB_PATH):
    print(f"ERREUR : {DB_PATH} introuvable dans {os.getcwd()}")
    raise SystemExit(1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# ---------------------------------------------------------------------------
# 1. Choix du cycle
# ---------------------------------------------------------------------------
if len(sys.argv) > 1:
    cycle_id = sys.argv[1]
else:
    try:
        row = conn.execute(
            "SELECT cycle_id FROM regime_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        cycle_id = row["cycle_id"] if row else None
    except sqlite3.OperationalError:
        cycle_id = None

if not cycle_id:
    print("Aucun cycle trouvé. Lance d'abord un RUN CYCLE depuis l'UI.")
    raise SystemExit(0)

print()
print("#" * 80)
print(f"#  CYCLE : {cycle_id}")
print("#" * 80)


def section(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


# ---------------------------------------------------------------------------
# 2. Régime du cycle
# ---------------------------------------------------------------------------
section("1. REGIME DU PORTEFEUILLE")
try:
    row = conn.execute("""
        SELECT regime, invested_pct, nav, cash, n_positions,
               n_proposals_in, n_proposals_attenuated,
               n_sell_capped, n_buy_capped, notes, created_at
        FROM regime_log
        WHERE cycle_id = ?
        ORDER BY id DESC LIMIT 1
    """, (cycle_id,)).fetchone()
    if row:
        print(f"  Régime         : {row['regime']}")
        print(f"  Invested       : {row['invested_pct']:.2f} % du NAV")
        print(f"  NAV            : {row['nav']:.2f}")
        print(f"  Cash           : {row['cash']:.2f}")
        print(f"  Positions      : {row['n_positions']}")
        print(f"  Proposals in   : {row['n_proposals_in']}")
        print(f"  Atténués       : {row['n_proposals_attenuated']}")
        print(f"  SELL plafonnés : {row['n_sell_capped']}")
        print(f"  BUY plafonnés  : {row['n_buy_capped']}")
        print(f"  Heure          : {row['created_at']}")
        print(f"  Notes          : {row['notes']}")
    else:
        print("  (pas de regime_log pour ce cycle — v5 ou antérieur ?)")
except sqlite3.OperationalError as e:
    print(f"  (table regime_log absente : {e})")


# ---------------------------------------------------------------------------
# 3. Thèses générées pendant ce cycle
# ---------------------------------------------------------------------------
section("2. THESES GENEREES (agents → propositions brutes)")
# On utilise une fenêtre temporelle autour du cycle (cycle_id = YYYYMMDD-HHMMSS UTC)
try:
    # Parse cycle_id pour extraire la datetime
    yyyymmdd, hhmmss = cycle_id.split("-")
    cycle_dt = f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]} {hhmmss[:2]}:{hhmmss[2:4]}:{hhmmss[4:6]}"
    # fenêtre +/- 30 secondes
    from datetime import datetime, timedelta
    t = datetime.strptime(cycle_dt, "%Y-%m-%d %H:%M:%S")
    t_start = (t - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%S")
    t_end = (t + timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%S")
except Exception as e:
    print(f"  (erreur parsing cycle_id : {e})")
    t_start = t_end = None

if t_start:
    rows = conn.execute("""
        SELECT t.id, i.ticker, t.agent_type, t.conviction_score,
               t.proposed_action, t.status, t.created_at
        FROM theses t
        JOIN instruments i ON i.id = t.instrument_id
        WHERE t.created_at >= ? AND t.created_at <= ?
        ORDER BY t.id
    """, (t_start, t_end)).fetchall()
    if not rows:
        print(f"  (aucune thèse dans la fenêtre {t_start} → {t_end})")
    for r in rows:
        action = (r['proposed_action'] or '')[:80]
        print(f"  #{r['id']:5d} {r['ticker']:6s} {r['agent_type']:20s} "
              f"conv={r['conviction_score']:.1f} status={r['status']}")
        print(f"         → {action}")


# ---------------------------------------------------------------------------
# 4. Réconciliation des proposals
# ---------------------------------------------------------------------------
section("3. RECONCILIATION (conflits & filtres)")
try:
    rows = conn.execute("""
        SELECT ticker, action, side_in, qty_in, conviction_max,
               signals_in, delta_signal_pct, delta_target_pct, reason
        FROM cycle_reconciliation_log
        WHERE cycle_id = ?
        ORDER BY id
    """, (cycle_id,)).fetchall()
    if not rows:
        print("  (aucune entrée pour ce cycle)")
    for r in rows:
        print(f"  {r['ticker']:6s} {r['action']:11s} side={r['side_in']:6s} "
              f"qty={r['qty_in']} conv_max={r['conviction_max']:.2f} signals_in={r['signals_in']}")
        print(f"         Δsignal={r['delta_signal_pct']:+.3f} %  "
              f"Δtarget={r['delta_target_pct']:+.3f} %")
        print(f"         → {r['reason']}")
except sqlite3.OperationalError as e:
    print(f"  (table absente : {e})")


# ---------------------------------------------------------------------------
# 5. Décisions ExitAgent
# ---------------------------------------------------------------------------
section("4. EXIT AGENT (sorties temporelles)")
try:
    rows = conn.execute("""
        SELECT ticker, rule, action, pnl_pct, current_weight_pct,
               target_weight_pct, drift_rel_pct, days_held, qty_proposed, reason
        FROM exit_decisions_log
        WHERE cycle_id = ?
        ORDER BY id
    """, (cycle_id,)).fetchall()
    if not rows:
        print("  (aucune entrée — ExitAgent n'a pas tourné ou aucune position)")
    for r in rows:
        print(f"  {r['ticker']:6s} rule={r['rule']:12s} action={r['action']:11s} "
              f"pnl={r['pnl_pct']:+.2f} % w={r['current_weight_pct']:.2f}/"
              f"{r['target_weight_pct']:.2f} % days={r['days_held']}")
        print(f"         → {r['reason']}")
except sqlite3.OperationalError as e:
    print(f"  (table absente : {e})")


# ---------------------------------------------------------------------------
# 6. Ordres créés (résultat final)
# ---------------------------------------------------------------------------
section("5. ORDRES CREES (résultat du cycle)")
if t_start:
    rows = conn.execute("""
        SELECT o.id, i.ticker, o.side, o.quantity, o.status, o.thesis_id,
               t.agent_type, t.conviction_score, o.created_at
        FROM orders o
        LEFT JOIN theses t ON t.id = o.thesis_id
        JOIN instruments i ON i.id = o.instrument_id
        WHERE o.created_at >= ? AND o.created_at <= ?
        ORDER BY o.id
    """, (t_start.replace("T", " "), t_end.replace("T", " "))).fetchall()
    if not rows:
        print("  (aucun ordre)")
    for r in rows:
        print(f"  Ordre #{r['id']:5d} {r['side'].upper():4s} {r['quantity']:>6} "
              f"{r['ticker']:6s} status={r['status']:11s} "
              f"agent={r['agent_type'] or '?'} conv={r['conviction_score'] or '?'}")


conn.close()
print()
print("#" * 80)
print("Fin du rapport.")
print("#" * 80)
