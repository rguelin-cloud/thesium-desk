"""Inventaire schemas reels des 5 tables runtime shadow_*."""
import sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
for t in ['shadow_cycle_snapshots','shadow_orders','shadow_fills','shadow_diff_log','shadow_perf_rolling']:
    print(f"\n[{t}]")
    cur.execute(f"PRAGMA table_info({t})")
    for r in cur.fetchall():
        print(f"  {r['name']:30s} {r['type']:12s} pk={r['pk']} notnull={r['notnull']} dflt={r['dflt_value']}")
conn.close()
