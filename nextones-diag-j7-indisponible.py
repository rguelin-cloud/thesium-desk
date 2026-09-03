"""
[DIAG_J7_INDISPONIBLE_V1]
Diagnostic : pourquoi factor_quality + geopolitical sont indisponibles vs J-7
dans le memo IC du 10/06/26.

Objectifs :
 1. Lister les snapshots factor_quality / geopolitical / sentiment present en DB
    sur la fenetre [J-10, J] (i.e. 31 mai -> 10 juin)
 2. Identifier les cycles autour de J-7 (03/06) et J-1 (09/06)
 3. Verifier la clef temporelle exacte utilisee par diff_engine
 4. Comparer la structure des snapshots present vs absent
"""
from __future__ import annotations
import os
import sys
import sqlite3
import datetime as dt
from pathlib import Path

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def main() -> int:
    if not os.path.exists(DB_PATH):
        print(f"[ERR] DB introuvable : {DB_PATH}")
        return 1
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("=" * 70)
    print("DIAG J-7 INDISPONIBLE - 10/06/2026")
    print("=" * 70)

    # ----------------------------------------------------------------------
    # 1. Liste des tables presentes
    # ----------------------------------------------------------------------
    print("\n[1] Tables candidates (factor / geo / sentiment / cycles)")
    print("-" * 70)
    tables = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND (name LIKE '%factor%' OR name LIKE '%geo%' OR name LIKE '%sentiment%' "
        "OR name LIKE '%cycle%' OR name LIKE '%narrative%') "
        "ORDER BY name"
    ).fetchall()
    for t in tables:
        try:
            n = cur.execute(f"SELECT COUNT(*) FROM {t['name']}").fetchone()[0]
        except Exception as e:
            n = f"ERR: {e}"
        print(f"  - {t['name']:40s} rows={n}")

    # ----------------------------------------------------------------------
    # 2. cycles : top 15 cycles par created_at desc
    # ----------------------------------------------------------------------
    print("\n[2] Derniers 15 cycles (table cycles)")
    print("-" * 70)
    try:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(cycles)").fetchall()]
        print(f"    colonnes: {cols}")
        # essayer plusieurs cles temporelles plausibles
        order_col = None
        for c in ("created_at", "ts", "timestamp", "cycle_ts", "run_at", "started_at"):
            if c in cols:
                order_col = c
                break
        if not order_col:
            print("    [WARN] pas de colonne temporelle reconnue")
        else:
            rows = cur.execute(
                f"SELECT id, {order_col} FROM cycles ORDER BY {order_col} DESC LIMIT 15"
            ).fetchall()
            for r in rows:
                print(f"    cycle_id={r['id']:<8} {order_col}={r[order_col]}")
    except Exception as e:
        print(f"    [ERR] {e}")

    # ----------------------------------------------------------------------
    # 3. factor_quality : couverture temporelle
    # ----------------------------------------------------------------------
    print("\n[3] factor_quality - dernieres 15 entrees")
    print("-" * 70)
    try:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(factor_quality)").fetchall()]
        print(f"    colonnes: {cols}")
        # candidates pour cle temporelle
        time_col = None
        for c in ("created_at", "ts", "cycle_ts", "timestamp", "snapshot_ts", "as_of"):
            if c in cols:
                time_col = c
                break
        cycle_col = "cycle_id" if "cycle_id" in cols else None
        if time_col:
            rows = cur.execute(
                f"SELECT * FROM factor_quality ORDER BY {time_col} DESC LIMIT 15"
            ).fetchall()
            for r in rows:
                cid = r["cycle_id"] if cycle_col else "?"
                print(f"    cycle_id={cid:<10} {time_col}={r[time_col]}")
        else:
            print("    [WARN] pas de colonne temporelle reconnue, dump 15 lignes")
            rows = cur.execute("SELECT * FROM factor_quality LIMIT 15").fetchall()
            for r in rows:
                print(f"    {dict(r)}")
    except Exception as e:
        print(f"    [ERR] {e}")

    # ----------------------------------------------------------------------
    # 4. geopolitical / geo / sentiment : meme exercice
    # ----------------------------------------------------------------------
    for table in ("geopolitical", "geo_snapshots", "sentiment", "narrative_snapshots", "pplx_geo_snapshots"):
        if not any(t["name"] == table for t in tables):
            continue
        print(f"\n[4] {table} - dernieres 15 entrees")
        print("-" * 70)
        try:
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
            print(f"    colonnes: {cols}")
            time_col = None
            for c in ("created_at", "ts", "cycle_ts", "timestamp", "snapshot_ts", "as_of"):
                if c in cols:
                    time_col = c
                    break
            if time_col:
                rows = cur.execute(
                    f"SELECT * FROM {table} ORDER BY {time_col} DESC LIMIT 15"
                ).fetchall()
                for r in rows:
                    cid = r["cycle_id"] if "cycle_id" in cols else "?"
                    print(f"    cycle_id={cid:<10} {time_col}={r[time_col]}")
            else:
                rows = cur.execute(f"SELECT * FROM {table} LIMIT 5").fetchall()
                for r in rows:
                    print(f"    {dict(r)}")
        except Exception as e:
            print(f"    [ERR] {e}")

    # ----------------------------------------------------------------------
    # 5. Reproduction du calcul J-1 / J-7 que fait diff_engine
    # ----------------------------------------------------------------------
    print("\n[5] Calcul des cibles J-1 et J-7")
    print("-" * 70)
    now = dt.datetime.utcnow()
    j_m_1 = now - dt.timedelta(days=1)
    j_m_7 = now - dt.timedelta(days=7)
    print(f"    now      = {now.isoformat()}")
    print(f"    J-1 cible= {j_m_1.isoformat()}")
    print(f"    J-7 cible= {j_m_7.isoformat()}")

    # Lookup du cycle le plus proche de J-1 et J-7 (table cycles)
    try:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(cycles)").fetchall()]
        order_col = None
        for c in ("created_at", "ts", "timestamp", "cycle_ts", "run_at", "started_at"):
            if c in cols:
                order_col = c
                break
        if order_col:
            for label, target in (("J-1", j_m_1), ("J-7", j_m_7)):
                # cycle le plus proche avant la cible
                r = cur.execute(
                    f"SELECT id, {order_col} FROM cycles "
                    f"WHERE {order_col} <= ? ORDER BY {order_col} DESC LIMIT 1",
                    (target.isoformat(),)
                ).fetchone()
                if r:
                    print(f"    cycle proche {label}: id={r['id']} {order_col}={r[order_col]}")
                else:
                    print(f"    cycle proche {label}: AUCUN")
    except Exception as e:
        print(f"    [ERR] {e}")

    conn.close()
    print("\n" + "=" * 70)
    print("FIN DIAG")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
