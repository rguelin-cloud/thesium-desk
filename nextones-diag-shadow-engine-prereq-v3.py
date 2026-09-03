"""
Diag prereq Phase 9.2 v3 - finaliser specs shadow_engine MVP
"""
import sqlite3, os, re

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def main():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("="*78)
    print("DIAG v3 - finalize shadow_engine specs")
    print("="*78)

    # 1. portfolio_targets_history schema COMPLET
    print("\n[1/5] portfolio_targets_history schema complet")
    cur.execute("PRAGMA table_info(portfolio_targets_history)")
    for r in cur.fetchall():
        print(f"  {r['name']:30s} {r['type']}")

    # 2. portfolio_targets_history derniers cycles (fenetre 90j)
    print("\n[2/5] portfolio_targets_history - cycles fenetre 90j")
    cur.execute("""
        SELECT cycle_id, COUNT(*) as n, MIN(score) as min_s, MAX(score) as max_s
        FROM portfolio_targets_history
        WHERE SUBSTR(cycle_id,1,8) >= '20260314'
        GROUP BY cycle_id ORDER BY cycle_id DESC LIMIT 10
    """)
    rows = cur.fetchall()
    print(f"  Derniers 10 cycles (sur 90j) :")
    for r in rows:
        print(f"    {r['cycle_id']:25s} n={r['n']:3d} score=[{r['min_s']:.3f}, {r['max_s']:.3f}]")

    # Sample d un cycle complet
    if rows:
        c = rows[0]['cycle_id']
        print(f"\n  Sample cycle {c} (top 5 score) :")
        cur.execute("""SELECT ticker, score, target_weight_pct, prev_target_weight_pct
                       FROM portfolio_targets_history WHERE cycle_id=?
                       ORDER BY score DESC LIMIT 5""", (c,))
        for r in cur.fetchall():
            print(f"    {r['ticker']:8s} score={r['score']:.3f} w={r['target_weight_pct']:.4f} prev_w={r['prev_target_weight_pct']}")

    # 3. Compter total cycles disponibles fenetre 90j
    print("\n[3/5] Cycles distincts fenetre 90j (portfolio_targets_history)")
    cur.execute("""
        SELECT COUNT(DISTINCT cycle_id) as n
        FROM portfolio_targets_history WHERE SUBSTR(cycle_id,1,8) >= '20260314'
    """)
    print(f"  Total cycles : {cur.fetchone()['n']}")

    cur.execute("""
        SELECT SUBSTR(cycle_id,1,8) as day, COUNT(DISTINCT cycle_id) as n
        FROM portfolio_targets_history WHERE SUBSTR(cycle_id,1,8) >= '20260601'
        GROUP BY day ORDER BY day DESC
    """)
    print(f"  Par jour (depuis 20260601) :")
    for r in cur.fetchall():
        print(f"    {r['day']} : {r['n']} cycles")

    # 4. Lire la def apply_convergence_sizing dans portfolio_construction_agent.py
    print("\n[4/5] Source apply_convergence_sizing dans portfolio_construction_agent.py")
    pca_path = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py"
    if os.path.exists(pca_path):
        with open(pca_path, "rb") as f:
            data = f.read().decode("utf-8", errors="replace")
        # trouver def
        m = re.search(r"def\s+apply_convergence_sizing\s*\([^)]*\)[^:]*:", data)
        if m:
            start = m.start()
            # extraire ~80 lignes a partir de la def
            lines = data[start:].split("\n")[:90]
            for i, ln in enumerate(lines):
                print(f"  {i:3d}| {ln[:130]}")
        else:
            print("  def apply_convergence_sizing NOT FOUND in portfolio_construction_agent.py")
            # cherche dans tout l arbre
            base = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
            for root, dirs, files in os.walk(base):
                if "venv" in root or "__pycache__" in root or "backup" in root.lower():
                    continue
                for fn in files:
                    if fn.endswith(".py") and not fn.startswith("nextones-diag"):
                        p = os.path.join(root, fn)
                        try:
                            with open(p,"rb") as fh: d = fh.read().decode("utf-8",errors="replace")
                            if re.search(r"def\s+apply_convergence_sizing", d):
                                rel = p.replace(base+"\\","")
                                print(f"  FOUND def in : {rel}")
                        except: pass
    else:
        print(f"  {pca_path} introuvable")

    # 5. orders cols actuelles vs shadow_orders (a verifier alignement)
    print("\n[5/5] shadow_orders schema actuel (Phase 9.1)")
    cur.execute("PRAGMA table_info(shadow_orders)")
    for r in cur.fetchall():
        print(f"  {r['name']:30s} {r['type']}")

    conn.close()
    print("\n" + "="*78)
    print("DIAG v3 DONE")
    print("="*78)

if __name__ == "__main__":
    main()
