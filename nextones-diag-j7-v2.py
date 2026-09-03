"""
[DIAG_J7_V2]
Diagnostic v2 - on connait les vraies tables :
  - factor_quality_history (7 rows)
  - factor_quality_context (18 rows)
  - pplx_geo_history (7 rows)
  - pplx_geo_context (5 rows)

Objectifs :
 1. Schemas exacts + colonnes temporelles
 2. Dates couvertes (J-1 = 09/06 OK, J-7 = 03/06 ?)
 3. Comparer ce que cherche diff_engine.py vs ce qui existe
 4. Localiser diff_engine.py et dumper la fonction compute_cycle_diff
"""
from __future__ import annotations
import os
import sys
import re
import sqlite3
from pathlib import Path

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
ROOT    = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")


def schema_dump(cur, table: str):
    print(f"\n[SCHEMA] {table}")
    print("-" * 70)
    cols = cur.execute(f"PRAGMA table_info({table})").fetchall()
    for c in cols:
        print(f"   col: {c[1]:30s} type={c[2]:15s} pk={c[5]}")
    return [c[1] for c in cols]


def dump_recent(cur, table: str, cols: list, n: int = 12):
    print(f"\n[RECENT] {table} (jusqu'a {n})")
    print("-" * 70)
    # cle temporelle plausible
    time_col = None
    for c in ("created_at", "ts", "cycle_ts", "timestamp", "snapshot_ts",
              "as_of", "snapshot_date", "date", "snap_ts", "updated_at"):
        if c in cols:
            time_col = c
            break
    cycle_col = "cycle_id" if "cycle_id" in cols else None
    if time_col:
        rows = cur.execute(
            f"SELECT * FROM {table} ORDER BY {time_col} DESC LIMIT {n}"
        ).fetchall()
        for r in rows:
            d = dict(r)
            tc = d.get(time_col)
            cid = d.get("cycle_id", "?")
            # extraire un signal lisible
            preview_keys = [k for k in d.keys() if k not in (time_col, "cycle_id", "id")][:3]
            preview = " | ".join(f"{k}={str(d.get(k))[:30]}" for k in preview_keys)
            print(f"   cycle_id={cid!s:<10} {time_col}={tc!s:<22} {preview}")
    else:
        print(f"   [WARN] pas de colonne temporelle, dump 5 lignes brutes")
        rows = cur.execute(f"SELECT * FROM {table} LIMIT 5").fetchall()
        for r in rows:
            print(f"   {dict(r)}")


def main() -> int:
    if not os.path.exists(DB_PATH):
        print(f"[ERR] DB introuvable : {DB_PATH}")
        return 1
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("=" * 70)
    print("DIAG J-7 V2 - schemas reels + diff_engine")
    print("=" * 70)

    # 1. Schemas + recent rows
    for table in (
        "factor_quality_history",
        "factor_quality_context",
        "pplx_geo_history",
        "pplx_geo_context",
    ):
        cols = schema_dump(cur, table)
        dump_recent(cur, table, cols, 12)

    # 2. Localiser diff_engine.py
    print("\n" + "=" * 70)
    print("[DIFF_ENGINE] Localisation + tables referencees")
    print("=" * 70)
    found = []
    for p in ROOT.rglob("diff_engine.py"):
        # skip env / venv / __pycache__
        sp = str(p).lower()
        if any(x in sp for x in ("\\venv\\", "\\.venv\\", "\\env\\", "__pycache__", "\\backup")):
            continue
        found.append(p)

    for fp in found:
        print(f"\n  fichier: {fp}")
        try:
            src = fp.read_text(encoding="utf-8-sig", errors="replace")
        except Exception as e:
            print(f"    [ERR] read: {e}")
            continue
        # tables referencees
        refs = re.findall(r"\bFROM\s+(\w+)|\bJOIN\s+(\w+)|['\"](factor_quality\w*|pplx_geo\w*|geopolitical\w*|sentiment\w*|cycles?)['\"]", src, re.IGNORECASE)
        flat = set()
        for tup in refs:
            for v in tup:
                if v:
                    flat.add(v.lower())
        print(f"    tables referencees: {sorted(flat)}")
        # extraire signatures de fonctions cle
        for m in re.finditer(r"^\s*def\s+(\w+)\s*\([^)]*\)\s*:", src, re.MULTILINE):
            print(f"    def {m.group(1)}()")

    if not found:
        print("    [WARN] diff_engine.py introuvable !")

    # 3. Dumper la fonction principale (compute_cycle_diff) de chaque fichier trouve
    print("\n" + "=" * 70)
    print("[DIFF_ENGINE] Source - compute_cycle_diff + helpers factor/geo")
    print("=" * 70)
    for fp in found:
        try:
            src = fp.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        print(f"\n>>> {fp.name}")
        # extraire blocs contenant 'factor_quality' ou 'geo'
        lines = src.splitlines()
        for i, ln in enumerate(lines):
            low = ln.lower()
            if any(k in low for k in ("factor_quality", "pplx_geo", "geopolitical", "compute_cycle_diff", "_diff_factor", "_diff_geo", "indisponible")):
                # afficher la ligne + 2 lignes de contexte
                start = max(0, i - 1)
                end = min(len(lines), i + 4)
                for j in range(start, end):
                    marker = ">>" if j == i else "  "
                    print(f"    {marker} L{j+1:4d}: {lines[j][:180]}")
                print("    ---")

    conn.close()
    print("\n" + "=" * 70)
    print("FIN DIAG V2")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
