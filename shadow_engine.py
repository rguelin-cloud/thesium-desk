"""
shadow_engine.py - Phase 9.2 MVP

Calcule en parallele les decisions d allocation pour N variants de settings,
sans toucher la prod, en reutilisant convergence_snapshots existants.

Entree : conn DB, cycle_id (prod), variant_id (ou None pour tous)
Sortie : rows dans shadow_cycle_snapshots + shadow_orders

Logique apply_variant_sizing :
  - Lit convergence_pct, forced_exit, is_crypto, direction_consensus depuis convergence_snapshots
  - Recalcule un multiplicateur selon les seuils variant (au lieu d utiliser sizing_multiplier prod)
  - Applique multiplicateurs equity/crypto buy/sell + filtres conv + score
  - Genere une decision : keep / scale_up / scale_down / exit / filter

Markers : [SHADOW_ENGINE_V1]
"""

import sqlite3
import json
import sys
from datetime import datetime, timezone


# =============================================================================
# Loaders
# =============================================================================

def load_variants(conn, variant_id=None):
    """Retourne liste de dicts variants actifs.

    Si variant_id=None : tous les variants actifs.
    Settings stockes en JSON dans la colonne settings_json.
    """
    cur = conn.cursor()
    if variant_id is None:
        cur.execute("SELECT * FROM shadow_variants WHERE active=1")
    else:
        cur.execute("SELECT * FROM shadow_variants WHERE variant_id=? AND active=1", (variant_id,))
    rows = cur.fetchall()
    variants = []
    for r in rows:
        d = dict(r)
        try:
            d['settings'] = json.loads(d['settings_json'])
        except Exception:
            d['settings'] = {}
        variants.append(d)
    return variants


def load_convergence_for_cycle(conn, cycle_id):
    """Retourne dict {ticker: {convergence_pct, forced_exit, is_crypto, direction_consensus, sizing_multiplier_prod}}."""
    cur = conn.cursor()
    cur.execute("""
        SELECT ticker, convergence_pct, forced_exit, is_crypto, direction_consensus, sizing_multiplier
        FROM convergence_snapshots WHERE cycle_id=?
    """, (cycle_id,))
    out = {}
    for r in cur.fetchall():
        t = r['ticker']
        out[t] = {
            'convergence_pct': float(r['convergence_pct'] or 0.0),
            'forced_exit': int(r['forced_exit'] or 0),
            'is_crypto': int(r['is_crypto'] or 0),
            'direction_consensus': r['direction_consensus'] or 'long',
            'sizing_multiplier_prod': float(r['sizing_multiplier'] or 1.0),
        }
    return out


def load_baseline_allocations(conn, cycle_id):
    """Charge les allocations baseline (avant convergence) pour un cycle.

    Source primaire : portfolio_targets_history (cycle_id direct).
    Si vide : fallback sur portfolio_targets actuel (snapshot le plus recent).

    Retourne dict {ticker: {score, target_weight_pct}}.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT ticker, score, target_weight_pct
        FROM portfolio_targets_history WHERE cycle_id=?
    """, (cycle_id,))
    rows = cur.fetchall()
    if rows:
        return {r['ticker']: {
            'score': float(r['score'] or 0.0),
            'target_weight_pct': float(r['target_weight_pct'] or 0.0),
        } for r in rows}

    # Fallback : dernier snapshot portfolio_targets
    cur.execute("""
        SELECT snapshot_id FROM portfolio_targets
        ORDER BY updated_at DESC LIMIT 1
    """)
    row = cur.fetchone()
    if not row:
        return {}
    snap_id = row['snapshot_id']
    cur.execute("""
        SELECT ticker, score, target_weight_pct FROM portfolio_targets
        WHERE snapshot_id=? AND active=1
    """, (snap_id,))
    return {r['ticker']: {
        'score': float(r['score'] or 0.0),
        'target_weight_pct': float(r['target_weight_pct'] or 0.0),
    } for r in cur.fetchall()}


# =============================================================================
# Variant sizing logic
# =============================================================================

def compute_variant_multiplier(conv_data, settings):
    """Calcule (multiplier, decision, side) pour un ticker selon les settings variant.

    conv_data : dict avec convergence_pct, forced_exit, is_crypto, direction_consensus
    settings  : dict avec conv, fe_sc, eq_buy, eq_sell, cr_buy, cr_sell, score

    Logique :
      - forced_exit=1 ET conv < fe_sc -> mult=0, decision=exit
      - conv < conv_threshold -> mult=0.5 (downscale), decision=scale_down
      - sinon mult = (eq|cr)_(buy|sell) selon side, decision=keep ou scale_up

    Retourne : (multiplier float, decision str, side str)
    """
    conv = conv_data['convergence_pct']
    fe = conv_data['forced_exit']
    is_crypto = conv_data['is_crypto']
    direction = (conv_data['direction_consensus'] or 'long').lower()

    side = 'buy' if direction == 'long' else 'sell'

    s_conv = float(settings.get('conv_thresh', 0.60))
    s_fe = float(settings.get('forced_exit_sc', 0.33))
    s_eq_buy = float(settings.get('eq_buy_mult', 1.0))
    s_eq_sell = float(settings.get('eq_sell_mult', 1.0))
    s_cr_buy = float(settings.get('cr_buy_mult', 0.7))
    s_cr_sell = float(settings.get('cr_sell_mult', 1.5))

    # Forced exit prioritaire : tolerance 0.01 (convergence_pct stocke a 3 decimales, ex 1/3=0.333)
    TOL = 0.01
    if fe == 1 and conv <= s_fe + TOL:
        return 0.0, 'exit', side

    # Filtre convergence basse (meme tolerance)
    if conv < s_conv - TOL:
        return 0.5, 'scale_down', side

    # Multiplicateur classe d actif
    if is_crypto:
        mult = s_cr_buy if side == 'buy' else s_cr_sell
    else:
        mult = s_eq_buy if side == 'buy' else s_eq_sell

    if abs(mult - 1.0) < 0.01:
        decision = 'keep'
    elif mult > 1.0:
        decision = 'scale_up'
    else:
        decision = 'scale_down'

    return mult, decision, side


def compute_shadow_for_cycle(conn, cycle_id, variant_id=None):
    """Calcule les shadow snapshots + orders pour un cycle, un ou plusieurs variants.

    Retourne dict {variant_name: {n_keep, n_scale_up, n_scale_down, n_exit, n_filter}}.
    """
    variants = load_variants(conn, variant_id)
    if not variants:
        print(f"[shadow_engine] Aucun variant actif (id={variant_id})")
        return {}

    conv_map = load_convergence_for_cycle(conn, cycle_id)
    if not conv_map:
        print(f"[shadow_engine] Aucun convergence_snapshot pour cycle {cycle_id}")
        return {}

    baseline = load_baseline_allocations(conn, cycle_id)
    if not baseline:
        print(f"[shadow_engine] WARN Aucune baseline allocation trouvee, fallback weight=0")

    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    cur = conn.cursor()

    summary = {}

    # day_t derive du cycle_id (format YYYYMMDD-HHMMSS)
    day_t = cycle_id[:8] if len(cycle_id) >= 8 else now[:10].replace('-','')
    day_t_iso = f"{day_t[:4]}-{day_t[4:6]}-{day_t[6:8]}"

    # MVP placeholders : K_init=1M, pas de fills yet (Phase 9.3+)
    NAV_PLACEHOLDER = 1000000.0
    CASH_PLACEHOLDER = 1000000.0
    NOTES_MVP = 'mvp_phase92_no_fills'

    # Idempotence : purge rows existants pour (cycle_id, variant_id) avant re-insert
    variant_ids = [v['variant_id'] for v in variants]
    placeholders = ','.join('?' for _ in variant_ids)
    cur.execute(
        f"DELETE FROM shadow_cycle_snapshots WHERE cycle_id=? AND variant_id IN ({placeholders})",
        [cycle_id] + variant_ids
    )
    n_del_snaps = cur.rowcount
    cur.execute(
        f"DELETE FROM shadow_orders WHERE cycle_id=? AND variant_id IN ({placeholders})",
        [cycle_id] + variant_ids
    )
    n_del_orders = cur.rowcount
    if n_del_snaps or n_del_orders:
        print(f"[idempotence] purge {n_del_snaps} snapshots + {n_del_orders} orders existants")

    for v in variants:
        vid = v['variant_id']
        vname = v['name']
        settings = v['settings']
        s_score_cutoff = float(settings.get('score_cutoff', 0.30))

        stats = {'keep': 0, 'scale_up': 0, 'scale_down': 0, 'exit': 0, 'filter': 0}

        # Insert 1 portfolio snapshot par variant (niveau cycle)
        cur.execute("""
            INSERT INTO shadow_cycle_snapshots
              (cycle_id, variant_id, day_t, nav, cash, n_positions,
               invested_pct, regime, notes, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (cycle_id, vid, day_t_iso, NAV_PLACEHOLDER, CASH_PLACEHOLDER,
              0, 0.0, None, NOTES_MVP, now))

        for ticker, cd in conv_map.items():
            base = baseline.get(ticker, {'score': 0.0, 'target_weight_pct': 0.0})
            score = base['score']
            baseline_w = base['target_weight_pct']

            # Filtre score cutoff variant
            if score < s_score_cutoff and baseline_w == 0:
                # Ne pas creer d order si score trop bas ET pas de position baseline
                stats['filter'] += 1
                continue

            mult, decision, side = compute_variant_multiplier(cd, settings)
            shadow_w = baseline_w * mult

            stats[decision] = stats.get(decision, 0) + 1

            # Insert shadow_order si decision genere ordre (exit ou scale != 1)
            if decision in ('exit', 'scale_down', 'scale_up'):
                # qty_current placeholder : 0 (MVP, on n a pas encore positions snapshot)
                qty = 0.0
                cur.execute("""
                    INSERT INTO shadow_orders
                      (cycle_id, variant_id, ticker, side, qty, qty_current,
                       target_weight_pct, convergence_pct, forced_exit,
                       sizing_multiplier, decision, rejection_reason, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (cycle_id, vid, ticker, side, qty, 0.0,
                      shadow_w, cd['convergence_pct'], cd['forced_exit'],
                      mult, decision, None, now))

        summary[vname] = stats

    return summary


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse
    p = argparse.ArgumentParser(description="Shadow engine MVP")
    p.add_argument("--db", default=r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
    p.add_argument("--cycle-id", required=True, help="cycle_id prod a simuler")
    p.add_argument("--variant-id", type=int, default=None, help="Variant ID specifique (sinon tous)")
    p.add_argument("--dry-run", action="store_true", help="Calcule sans inserer")
    args = p.parse_args()

    print("="*78)
    print("SHADOW ENGINE MVP - Phase 9.2")
    print(f"DB        : {args.db}")
    print(f"Cycle ID  : {args.cycle_id}")
    print(f"Variant   : {args.variant_id if args.variant_id else 'ALL active'}")
    print(f"Mode      : {'DRY-RUN' if args.dry_run else 'APPLY'}")
    print("="*78)

    conn = sqlite3.connect(args.db, timeout=30)
    conn.row_factory = sqlite3.Row

    # Active WAL pour reads concurrents
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    conn.execute("BEGIN")
    try:
        summary = compute_shadow_for_cycle(conn, args.cycle_id, args.variant_id)
        if args.dry_run:
            conn.execute("ROLLBACK")
            print("\n[DRY-RUN] ROLLBACK effectue, aucune ecriture persistee")
        else:
            conn.execute("COMMIT")
            print("\n[APPLY] COMMIT effectue")
    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"\n[ERROR] {e} - ROLLBACK")
        raise

    print("\n[RESULTATS]")
    for vname, stats in summary.items():
        total = sum(stats.values())
        print(f"\n  Variant : {vname}")
        print(f"    Total decisions : {total}")
        for k, v in stats.items():
            pct = 100.0 * v / total if total else 0
            print(f"    {k:12s} : {v:3d} ({pct:5.1f}%)")

    # Verification post-insert
    if not args.dry_run:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as n FROM shadow_cycle_snapshots WHERE cycle_id=?", (args.cycle_id,))
        n_snaps = cur.fetchone()['n']
        cur.execute("SELECT COUNT(*) as n FROM shadow_orders WHERE cycle_id=?", (args.cycle_id,))
        n_orders = cur.fetchone()['n']
        print(f"\n[VERIFICATION]")
        print(f"  shadow_cycle_snapshots inserts : {n_snaps}")
        print(f"  shadow_orders inserts          : {n_orders}")

    conn.close()
    print("\n" + "="*78)
    print("DONE")
    print("="*78)


if __name__ == "__main__":
    main()
