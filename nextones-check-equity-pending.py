# -*- coding: utf-8 -*-
# [CHECK_EQUITY_PENDING_V1]
# Verification rapide post-scan : repartition universe_candidates pending
# + detail equity + derniers scan_batch
import sqlite3
import sys

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    print("=" * 70)
    print("  Repartition pending par asset_class")
    print("=" * 70)
    rows = cur.execute(
        "SELECT asset_class, COUNT(*) FROM universe_candidates "
        "WHERE status='pending' GROUP BY asset_class ORDER BY 2 DESC"
    ).fetchall()
    if not rows:
        print("  (aucun candidat pending)")
    for ac, n in rows:
        print("  - {:10s} : {}".format(ac or "(null)", n))

    print()
    print("=" * 70)
    print("  Derniers scan_batch")
    print("=" * 70)
    rows = cur.execute(
        "SELECT scan_batch, COUNT(*), MAX(proposed_at) "
        "FROM universe_candidates WHERE status='pending' "
        "GROUP BY scan_batch ORDER BY MAX(proposed_at) DESC LIMIT 8"
    ).fetchall()
    for sb, n, t in rows:
        print("  {} n={} t={}".format(sb, n, t))

    print()
    print("=" * 70)
    print("  Detail equity pending (top 30)")
    print("=" * 70)
    rows = cur.execute(
        "SELECT ticker, score, scan_batch, proposed_at "
        "FROM universe_candidates WHERE status='pending' AND asset_class='equity' "
        "ORDER BY proposed_at DESC LIMIT 30"
    ).fetchall()
    if not rows:
        print("  AUCUN equity pending en base.")
    for t, s, sb, ts in rows:
        print("  {:8s} score={} batch={} t={}".format(t, s, sb, ts))

    print()
    print("=" * 70)
    print("  Detail equity (tous status) - histoire complete")
    print("=" * 70)
    rows = cur.execute(
        "SELECT ticker, status, score, scan_batch, proposed_at "
        "FROM universe_candidates WHERE asset_class='equity' "
        "ORDER BY proposed_at DESC LIMIT 30"
    ).fetchall()
    if not rows:
        print("  AUCUN equity n'a jamais ete insere (toutes statuts confondus).")
    for t, st, s, sb, ts in rows:
        print("  {:8s} {:10s} score={} batch={} t={}".format(t, st, s, sb, ts))

    con.close()

if __name__ == "__main__":
    main()
