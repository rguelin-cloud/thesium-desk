"""
Diag prereq Phase 9.2 - shadow_engine MVP
Verifier :
1. portfolio_targets schema + sample sur derniers cycles
2. convergence_snapshots disponibles sur cycles recents
3. Logique sizing : ou est applique le multiplicateur conv ?
"""
import sqlite3, sys, json

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def main():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("="*78)
    print("DIAG PREREQ PHASE 9.2 - shadow_engine MVP")
    print("="*78)

    # 1. portfolio_targets schema
    print("\n[1/6] portfolio_targets schema")
    cur.execute("PRAGMA table_info(portfolio_targets)")
    for r in cur.fetchall():
        print(f"  {r['name']:30s} {r['type']}")

    # 2. portfolio_targets sample dernier cycle
    print("\n[2/6] portfolio_targets dernier cycle (top 10 lignes)")
    cur.execute("""
        SELECT cycle_id, COUNT(*) as n, MAX(created_at) as last_dt
        FROM portfolio_targets
        GROUP BY cycle_id
        ORDER BY last_dt DESC LIMIT 5
    """)
    cycles = cur.fetchall()
    for c in cycles:
        print(f"  cycle={c['cycle_id']:25s} n={c['n']:3d} dt={c['last_dt']}")
    if cycles:
        last_cycle = cycles[0]['cycle_id']
        cur.execute("SELECT * FROM portfolio_targets WHERE cycle_id=? LIMIT 10", (last_cycle,))
        rows = cur.fetchall()
        if rows:
            print(f"\n  Sample cols dispo : {list(rows[0].keys())}")
            for r in rows[:5]:
                d = dict(r)
                print(f"    {d}")

    # 3. convergence_snapshots dernier cycle
    print("\n[3/6] convergence_snapshots dernier cycle prod")
    if cycles:
        cur.execute("""
            SELECT cycle_id, COUNT(*) as n
            FROM convergence_snapshots
            WHERE cycle_id=? GROUP BY cycle_id
        """, (last_cycle,))
        r = cur.fetchone()
        if r:
            print(f"  cycle={last_cycle} : {r['n']} snapshots")
            cur.execute("""
                SELECT ticker, convergence_pct, sizing_multiplier, forced_exit, is_crypto, direction_consensus
                FROM convergence_snapshots WHERE cycle_id=? LIMIT 10
            """, (last_cycle,))
            for s in cur.fetchall():
                print(f"    {s['ticker']:8s} conv={s['convergence_pct']:.2f} mult={s['sizing_multiplier']:.2f} fe={s['forced_exit']} crypto={s['is_crypto']} dir={s['direction_consensus']}")
        else:
            print(f"  Aucun snapshot pour cycle {last_cycle}")

    # 4. Verifier ou est apply_convergence_sizing
    print("\n[4/6] Localiser apply_convergence_sizing dans le code")
    import os, re
    base = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
    found = []
    for root, dirs, files in os.walk(base):
        if "venv" in root or ".git" in root or "__pycache__" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(root, f)
                try:
                    with open(p, "rb") as fh:
                        data = fh.read()
                    if b"apply_convergence_sizing" in data:
                        # compter occurrences def vs call
                        try:
                            txt = data.decode("utf-8", errors="replace")
                        except Exception:
                            txt = ""
                        n_def = len(re.findall(r"def\s+apply_convergence_sizing", txt))
                        n_call = txt.count("apply_convergence_sizing") - n_def
                        found.append((p, n_def, n_call))
                except Exception:
                    pass
    for p, nd, nc in found[:10]:
        rel = p.replace(base + "\\", "")
        print(f"  {rel:60s} def={nd} call={nc}")

    # 5. orders schema (pour shadow_orders comparable)
    print("\n[5/6] orders schema (cols cles pour shadow_orders)")
    cur.execute("PRAGMA table_info(orders)")
    for r in cur.fetchall():
        nm = r['name']
        if nm in ("id","cycle_id","ticker","side","qty","status","filled","created_at","instrument_id","price","stop_loss","take_profit","notional","class"):
            print(f"  {nm:20s} {r['type']}")

    # 6. Cycles disponibles sur fenetre 90j (pour future Phase 9.7)
    print("\n[6/6] Cycles prod fenetre 90j (sample)")
    cur.execute("""
        SELECT DATE(SUBSTR(cycle_id,1,8),'unixepoch') as dummy, COUNT(*) as n_cycles
        FROM (SELECT DISTINCT cycle_id FROM portfolio_targets
              WHERE SUBSTR(cycle_id,1,8) >= '20260314')
    """)
    r = cur.fetchone()
    if r:
        print(f"  total cycles distinct depuis 20260314 : {r['n_cycles']}")
    cur.execute("""
        SELECT SUBSTR(cycle_id,1,8) as day, COUNT(DISTINCT cycle_id) as n
        FROM portfolio_targets
        WHERE SUBSTR(cycle_id,1,8) >= '20260314'
        GROUP BY day ORDER BY day DESC LIMIT 10
    """)
    print("  Derniers 10 jours :")
    for r in cur.fetchall():
        print(f"    {r['day']} : {r['n']} cycles")

    conn.close()
    print("\n" + "="*78)
    print("DIAG DONE")
    print("="*78)

if __name__ == "__main__":
    main()
