"""Verifier la precision exacte de convergence_pct pour les fe=1 du cycle."""
import sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
CYCLE = "20260612-121958"
conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("""SELECT ticker, convergence_pct, forced_exit, n_aligned, n_present
               FROM convergence_snapshots WHERE cycle_id=? AND forced_exit=1
               ORDER BY ticker""", (CYCLE,))
print(f"{'ticker':8s} {'conv_pct':22s} {'n_al/n_pr':12s} test_<=_0.33  test_<=_0.33+eps")
for r in cur.fetchall():
    c = r['convergence_pct']
    print(f"  {r['ticker']:8s} {repr(c):22s} {r['n_aligned']}/{r['n_present']:8d} {str(c <= 0.33):12s} {str(c <= 0.33 + 1e-6):12s}")
conn.close()
