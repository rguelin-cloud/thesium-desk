"""
reset_portfolio_demo.py
========================
Réinitialise le portefeuille demo Nextones Desk pour repartir sur des
métriques propres.

Actions:
  1. Sauvegarde la DB existante (thesium.db.bak.<timestamp>)
  2. Purge: portfolio_positions, orders, fills, portfolio_history, decision_log, risk_check_results
  3. Réinitialise portfolio_state à 1,000,000 USD cash (full cash)
  4. Conserve : instruments, prices, risk_config, users, theses, agent_outputs
  5. Recalcule la VAR (devrait être 0 sans positions)

Usage local Windows:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 reset_portfolio_demo.py
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DB_PATH = "thesium.db"   # même répertoire que le script
INITIAL_CASH = 1_000_000.0


def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Base introuvable : {DB_PATH}")
        sys.exit(1)

    # 1. Backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{DB_PATH}.bak.{ts}"
    shutil.copy2(DB_PATH, backup)
    print(f"[OK] Backup créé : {backup}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 2. Tables à purger (existantes seulement)
    tables_to_clear = [
        "portfolio_positions",
        "orders",
        "fills",
        "portfolio_history",
        "decision_log",
        "risk_check_results",
        "event_log",
    ]

    existing = {r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    cleared = []
    for t in tables_to_clear:
        if t in existing:
            cur.execute(f"DELETE FROM {t}")
            cleared.append(f"{t} ({cur.rowcount} lignes)")
    print(f"[OK] Tables purgées : {', '.join(cleared) if cleared else '(aucune)'}")

    # 3. Reset portfolio_state
    now_iso = datetime.utcnow().isoformat()
    cur.execute(
        """INSERT OR REPLACE INTO portfolio_state
               (id, cash, total_value, total_pnl, total_pnl_pct,
                daily_pnl, daily_pnl_pct, var_95, max_drawdown, updated_at)
           VALUES (1, ?, ?, 0, 0, 0, 0, 0, 0, ?)""",
        (INITIAL_CASH, INITIAL_CASH, now_iso)
    )
    print(f"[OK] portfolio_state réinitialisé à ${INITIAL_CASH:,.0f} cash")

    # 4. Première ligne d'historique (baseline pour daily P&L)
    if "portfolio_history" in existing:
        cur.execute(
            """INSERT INTO portfolio_history
                   (date, total_value, cash, total_pnl)
               VALUES (date('now', '-1 day'), ?, ?, 0)""",
            (INITIAL_CASH, INITIAL_CASH)
        )
        print("[OK] Baseline portfolio_history créée (J-1)")

    conn.commit()

    # 5. Vérification finale
    state = cur.execute("SELECT * FROM portfolio_state WHERE id=1").fetchone()
    print("\n=== ÉTAT FINAL ===")
    for k in state.keys():
        print(f"  {k}: {state[k]}")

    npos = cur.execute("SELECT COUNT(*) FROM portfolio_positions").fetchone()[0]
    nord = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0] if "orders" in existing else 0
    print(f"\n  positions: {npos}")
    print(f"  orders   : {nord}")

    conn.close()
    print("\n✅ Reset terminé. Redémarrez l'app (port 8000) et lancez un nouveau decision cycle.")
    print(f"   En cas de problème, restaurez : copy {backup} {DB_PATH}")


if __name__ == "__main__":
    main()
