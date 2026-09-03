"""
Diag prereq Phase 9.2 v2 - shadow_engine MVP
Fix : portfolio_targets utilise snapshot_id (pas cycle_id)
"""
import sqlite3, os, re

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def main():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("="*78)
    print("DIAG PREREQ PHASE 9.2 v2 - shadow_engine MVP")
    print("="*78)

    # 1. portfolio_targets : derniers snapshots
    print("\n[1/7] portfolio_targets - derniers snapshots")
    cur.execute("""
        SELECT snapshot_id, COUNT(*) as n, MAX(updated_at) as last_dt,
               SUM(active) as n_active
        FROM portfolio_targets
        GROUP BY snapshot_id
        ORDER BY last_dt DESC LIMIT 5
    """)
    snaps = cur.fetchall()
    last_snap = None
    for s in snaps:
        print(f"  snapshot={s['snapshot_id']:30s} n={s['n']:3d} active={s['n_active']:3d} dt={s['last_dt']}")
        if last_snap is None:
            last_snap = s['snapshot_id']

    # 2. Sample dernier snapshot
    print(f"\n[2/7] Sample portfolio_targets snapshot={last_snap}")
    if last_snap:
        cur.execute("SELECT * FROM portfolio_targets WHERE snapshot_id=? ORDER BY score DESC LIMIT 10", (last_snap,))
        for r in cur.fetchall():
            d = dict(r)
            print(f"  {d['ticker']:8s} w={d['target_weight_pct']:.4f} score={d['score']} active={d['active']} src={d['source']} agent={d['agent_decided']}")

    # 3. Mapping snapshot_id -> cycle_id : ou est stocke le lien ?
    print("\n[3/7] Tables qui referencent snapshot_id")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r['name'] for r in cur.fetchall()]
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [r['name'] for r in cur.fetchall()]
        if 'snapshot_id' in cols:
            cur.execute(f"SELECT COUNT(*) as n FROM {t}")
            n = cur.fetchone()['n']
            print(f"  {t:35s} cols={cols[:8]}... rows={n}")

    # 4. construction_snapshots ?
    print("\n[4/7] construction_snapshots schema (si existe)")
    if 'construction_snapshots' in tables:
        cur.execute("PRAGMA table_info(construction_snapshots)")
        for r in cur.fetchall():
            print(f"  {r['name']:25s} {r['type']}")
        cur.execute("SELECT * FROM construction_snapshots ORDER BY created_at DESC LIMIT 3")
        for r in cur.fetchall():
            d = dict(r)
            print(f"  sample : {dict((k, str(v)[:40]) for k,v in d.items())}")

    # 5. orders sample dernier cycle (cols dispo)
    print("\n[5/7] orders schema + dernier sample")
    cur.execute("PRAGMA table_info(orders)")
    cols = [(r['name'], r['type']) for r in cur.fetchall()]
    for nm, tp in cols:
        print(f"  {nm:25s} {tp}")
    cur.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 3")
    for r in cur.fetchall():
        d = dict(r)
        kept = {k: str(v)[:30] for k, v in d.items() if k in ('id','cycle_id','ticker','side','qty','status','price','notional','class','filled')}
        print(f"  sample : {kept}")

    # 6. convergence_snapshots dernier cycle prod
    print("\n[6/7] convergence_snapshots - derniers cycles")
    cur.execute("""
        SELECT cycle_id, COUNT(*) as n, SUM(forced_exit) as fe
        FROM convergence_snapshots
        GROUP BY cycle_id ORDER BY cycle_id DESC LIMIT 5
    """)
    last_cycle = None
    for r in cur.fetchall():
        print(f"  cycle={r['cycle_id']:25s} n={r['n']:3d} fe={r['fe']}")
        if last_cycle is None:
            last_cycle = r['cycle_id']
    if last_cycle:
        print(f"\n  Sample du cycle {last_cycle}:")
        cur.execute("""SELECT ticker, convergence_pct, sizing_multiplier, forced_exit, is_crypto, direction_consensus
                       FROM convergence_snapshots WHERE cycle_id=? LIMIT 10""", (last_cycle,))
        for r in cur.fetchall():
            print(f"    {r['ticker']:8s} conv={r['convergence_pct']:.2f} mult={r['sizing_multiplier']:.2f} fe={r['forced_exit']} crypto={r['is_crypto']} dir={r['direction_consensus']}")

    # 7. Localiser apply_convergence_sizing
    print("\n[7/7] Localiser apply_convergence_sizing")
    base = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
    found = []
    for root, dirs, files in os.walk(base):
        if "venv" in root or ".git" in root or "__pycache__" in root or "backup" in root.lower():
            continue
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(root, f)
                try:
                    with open(p, "rb") as fh:
                        data = fh.read()
                    if b"apply_convergence_sizing" in data:
                        try: txt = data.decode("utf-8", errors="replace")
                        except: txt = ""
                        n_def = len(re.findall(r"def\s+apply_convergence_sizing", txt))
                        n_call = txt.count("apply_convergence_sizing") - n_def
                        found.append((p, n_def, n_call, len(data)))
                except: pass
    for p, nd, nc, sz in found[:15]:
        rel = p.replace(base + "\\", "")
        print(f"  {rel:60s} def={nd} call={nc} sz={sz}")

    conn.close()
    print("\n" + "="*78)
    print("DIAG v2 DONE")
    print("="*78)

if __name__ == "__main__":
    main()
