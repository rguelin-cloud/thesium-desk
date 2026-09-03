# -*- coding: utf-8 -*-
# nextones-diag-apply-convergence-sizing.py
# Localise apply_convergence_sizing dans portfolio_construction_agent.py
# Affiche le bloc autour de L595, identifie le calcul SOL 4.77 -> 2.77
# Cherche : sizing_multiplier, forced_exit, target, qty, position
# But : comprendre pourquoi sizing_multiplier=0 ne resulte pas en qty=0

import os
import sys
import sqlite3

PROD_ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
PCA_PATH = os.path.join(PROD_ROOT, "portfolio_construction_agent.py")
DB_PATH = os.path.join(PROD_ROOT, "thesium.db")


def main():
    print("=" * 70)
    print("DIAG apply_convergence_sizing - SOL 4.77 -> 2.77 au lieu de 0")
    print("=" * 70)

    if not os.path.exists(PCA_PATH):
        print("[FATAL] " + PCA_PATH + " introuvable")
        sys.exit(1)

    with open(PCA_PATH, "r", encoding="utf-8-sig") as f:
        src = f.read()
    lines = src.split("\n")
    print("Total lignes : " + str(len(lines)))

    # 1. Localiser apply_convergence_sizing
    print("\n--- 1. Definition apply_convergence_sizing ---")
    func_start = -1
    for i, ln in enumerate(lines, 1):
        if "def apply_convergence_sizing" in ln:
            func_start = i
            print("L" + str(i) + ": " + ln.rstrip())
            break

    if func_start < 0:
        print("[WARN] apply_convergence_sizing introuvable - cherche autres patterns")
        for i, ln in enumerate(lines, 1):
            if "convergence" in ln.lower() and ("sizing" in ln.lower() or "multiplier" in ln.lower()):
                print("L" + str(i) + ": " + ln.rstrip()[:160])
        # On essaie aussi sizing_multiplier
        print("\n--- sizing_multiplier occurrences ---")
        for i, ln in enumerate(lines, 1):
            if "sizing_multiplier" in ln:
                print("L" + str(i) + ": " + ln.rstrip()[:160])
        return

    # 2. Afficher fonction complete (max 80 lignes)
    print("\n--- 2. Corps apply_convergence_sizing ---")
    indent_base = None
    for j in range(func_start - 1, min(len(lines), func_start + 100)):
        ln = lines[j]
        # detecte fin de fonction
        if j > func_start and ln.strip() and not ln.startswith(" ") and not ln.startswith("\t") and not ln.startswith("#"):
            if "def " in ln or "class " in ln:
                print("...(fin de apply_convergence_sizing detectee)")
                break
        marker = ""
        if (j + 1) == 595:
            marker = " >>> L595 >>> "
        elif "sizing_multiplier" in ln or "forced_exit" in ln:
            marker = "     [SM/FE] "
        else:
            marker = "             "
        print(marker + "L" + str(j + 1) + ": " + ln.rstrip())

    # 3. Contexte autour de L595 specifiquement
    print("\n--- 3. Bloc precis autour de L595 (+/- 15 lignes) ---")
    for j in range(max(0, 595 - 15), min(len(lines), 595 + 15)):
        marker = " >>> " if (j + 1) == 595 else "     "
        print(marker + "L" + str(j + 1) + ": " + lines[j].rstrip())

    # 4. Donnees prod SOL : convergence snapshot + portfolio target
    print("\n--- 4. Donnees prod SOL ---")
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row

    # Convergence snapshot pour SOL
    try:
        rows = c.execute(
            """SELECT * FROM convergence_snapshot
               WHERE ticker = 'SOL'
               ORDER BY created_at DESC LIMIT 3"""
        ).fetchall()
        print("convergence_snapshot SOL (3 dernieres) :")
        for r in rows:
            print("  " + dict(r).__repr__()[:300])
    except Exception as e:
        print("  [ERR convergence_snapshot] " + str(e))

    # Position SOL
    try:
        row = c.execute(
            """SELECT pp.quantity, pp.avg_cost, pp.current_price, pp.weight_pct, pp.unrealized_pnl
               FROM portfolio_positions pp
               JOIN instruments i ON i.id = pp.instrument_id
               WHERE i.ticker = 'SOL'"""
        ).fetchone()
        if row:
            print("portfolio_positions SOL : " + dict(row).__repr__())
    except Exception as e:
        print("  [ERR position] " + str(e))

    # Target SOL (dernier cycle)
    try:
        rows = c.execute(
            """SELECT * FROM portfolio_targets
               WHERE ticker = 'SOL'
               ORDER BY created_at DESC LIMIT 3"""
        ).fetchall()
        print("portfolio_targets SOL (3 dernieres) :")
        for r in rows:
            print("  " + dict(r).__repr__()[:300])
    except Exception as e:
        print("  [ERR portfolio_targets] " + str(e))

    # Dernier order SOL
    try:
        rows = c.execute(
            """SELECT o.id, o.side, o.quantity, o.status, o.created_at, o.rejection_reason
               FROM orders o
               JOIN instruments i ON i.id = o.instrument_id
               WHERE i.ticker = 'SOL'
               ORDER BY o.created_at DESC LIMIT 5"""
        ).fetchall()
        print("Last orders SOL :")
        for r in rows:
            print("  " + dict(r).__repr__()[:250])
    except Exception as e:
        print("  [ERR orders] " + str(e))

    # 5. Tables presentes
    print("\n--- 5. Tables disponibles (filtre convergence/target) ---")
    try:
        rows = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%converg%' OR name LIKE '%target%' OR name LIKE '%construction%') ORDER BY name"
        ).fetchall()
        for r in rows:
            print("  " + r[0])
    except Exception as e:
        print("  [ERR] " + str(e))

    c.close()


if __name__ == "__main__":
    main()
