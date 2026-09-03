"""Pourquoi prod variant=1 a 0 exit alors que 7 fe=1 dans le cycle 20260612-121958 ?"""
import sqlite3, json
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
CYCLE = "20260612-121958"

conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Settings variant prod
print("[1] Settings variant prod")
cur.execute("SELECT settings_json FROM shadow_variants WHERE variant_id=1")
s = json.loads(cur.fetchone()['settings_json'])
for k,v in s.items(): print(f"  {k:20s} = {v}")

# 2. Tickers forced_exit du cycle
print(f"\n[2] Tickers forced_exit du cycle {CYCLE}")
cur.execute("""SELECT ticker, convergence_pct, forced_exit, is_crypto, direction_consensus, sizing_multiplier
               FROM convergence_snapshots WHERE cycle_id=? AND forced_exit=1""", (CYCLE,))
fe_tickers = cur.fetchall()
for r in fe_tickers:
    print(f"  {r['ticker']:8s} conv={r['convergence_pct']:.2f} fe={r['forced_exit']} crypto={r['is_crypto']} dir={r['direction_consensus']:6s} prod_mult={r['sizing_multiplier']:.2f}")

# 3. Pour chaque fe=1, verifier baseline portfolio_targets actuel
print(f"\n[3] Baseline portfolio_targets (dernier snapshot)")
cur.execute("SELECT snapshot_id FROM portfolio_targets ORDER BY updated_at DESC LIMIT 1")
snap = cur.fetchone()['snapshot_id']
print(f"  snapshot_id={snap}")
cur.execute("SELECT ticker, score, target_weight_pct FROM portfolio_targets WHERE snapshot_id=? AND active=1", (snap,))
baseline = {r['ticker']: dict(r) for r in cur.fetchall()}
print(f"  baseline tickers : {len(baseline)}")

print(f"\n[4] Pour chaque fe=1, simul logique variant prod (conv_thresh=0.6, fe_sc=0.33, score_cutoff=0.3)")
s_conv = 0.6
s_fe = 0.33
s_cutoff = 0.30
for r in fe_tickers:
    t = r['ticker']
    base = baseline.get(t, {'score': 0.0, 'target_weight_pct': 0.0})
    score = base['score']
    bw = base['target_weight_pct']
    conv = r['convergence_pct']
    fe = r['forced_exit']
    
    filtre_applique = (score < s_cutoff and bw == 0)
    fe_match = (fe == 1 and conv <= s_fe)
    
    note = ""
    if filtre_applique: note = "FILTER (score<0.30 AND bw==0)"
    elif fe_match: note = "EXIT"
    elif conv < s_conv: note = "scale_down (conv<0.6)"
    else: note = "keep ou scale"
    
    print(f"  {t:8s} score={score:.3f} bw={bw:.3f} conv={conv:.2f} -> filtre={filtre_applique} fe_match={fe_match} | {note}")

# 5. Verifier shadow_orders ecrits pour variant=1
print(f"\n[5] shadow_orders ecrits cycle {CYCLE} variant=1 (prod)")
cur.execute("""SELECT ticker, side, decision, convergence_pct, forced_exit, sizing_multiplier
               FROM shadow_orders WHERE cycle_id=? AND variant_id=1 ORDER BY decision, ticker""", (CYCLE,))
rows = cur.fetchall()
print(f"  total orders prod : {len(rows)}")
from collections import Counter
c = Counter(r['decision'] for r in rows)
print(f"  par decision : {dict(c)}")
print(f"\n  Orders fe=1 prod (devraient etre exit):")
for r in rows:
    if r['forced_exit'] == 1:
        print(f"    {r['ticker']:8s} side={r['side']:5s} decision={r['decision']:12s} conv={r['convergence_pct']:.2f} mult={r['sizing_multiplier']:.2f}")

conn.close()
