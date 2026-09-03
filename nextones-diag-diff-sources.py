# -*- coding: utf-8 -*-
"""
Diag sources pour Diff J-1 / J-7 dans memo IC
=============================================

Objectif : recenser dans thesium.db les tables qui ont :
  1) un timestamp (created_at, run_at, cycle_ts...)
  2) des valeurs comparables d'un cycle a l'autre (scores, sentiments, regimes)

Cibles attendues :
  - cycles, theses, factor_quality, pplx_geo_context, pplx_crypto_context
  - portfolio_history, risk_pretrade
  - agents_results (si table dediee)

Sortie : pour chaque table candidate
  - schema (colonnes + types)
  - nb lignes total
  - 3 plus recentes lignes (date + 2-3 champs cles)
  - plage temporelle (min, max)

Lancement :
    py -3.13 .\nextones-diag-diff-sources.py
"""
from __future__ import annotations

import sys
import sqlite3
import json
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")

SEP = "=" * 78


def banner(t: str) -> None:
    print("\n" + SEP)
    print(t)
    print(SEP)


def list_tables(cur) -> list[str]:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [r[0] for r in cur.fetchall()]


def has_time_col(cols: list[tuple]) -> str | None:
    """Renvoie la 1ere colonne 'temporelle' detectee."""
    candidates = [
        "created_at",
        "cycle_ts",
        "run_at",
        "ts",
        "timestamp",
        "date",
        "as_of",
        "fetched_at",
        "updated_at",
    ]
    names = [c[1].lower() for c in cols]
    for cand in candidates:
        if cand in names:
            return cand
    return None


def main() -> int:
    if not DB.exists():
        print(f"[ERR] {DB} introuvable")
        return 2

    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    tables = list_tables(cur)
    print(f"[INFO] {len(tables)} tables dans {DB.name}")

    banner("1. Toutes les tables avec colonne temporelle detectee")
    candidates: list[tuple[str, str, int]] = []
    for t in tables:
        try:
            cur.execute(f"PRAGMA table_info({t})")
            cols = cur.fetchall()
            time_col = has_time_col(cols)
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            n = cur.fetchone()[0]
            if time_col:
                candidates.append((t, time_col, n))
                print(f"  {t:35} time_col={time_col:15} rows={n:,}")
        except sqlite3.Error as e:
            print(f"  [SKIP] {t}: {e}")

    banner("2. Detail des tables cles pour le DIFF")
    # On focalise sur les tables qui ont du signal comparable cycle a cycle
    interesting = [
        "cycles",
        "theses",
        "factor_quality",
        "pplx_geo_context",
        "pplx_crypto_context",
        "pplx_factor_quality",
        "pplx_thesis_challenges",
        "portfolio_history",
        "risk_pretrade",
        "orders",
        "macro_indicators",
        "sentiment_signals",
        "agent_outputs",
    ]

    for t, time_col, n in candidates:
        if t not in interesting and not any(k in t for k in interesting):
            continue
        print(f"\n--- {t} (time_col={time_col}, n={n:,}) ---")
        # Schema
        cur.execute(f"PRAGMA table_info({t})")
        cols = cur.fetchall()
        print(f"  colonnes : {', '.join(c[1] for c in cols)}")

        # Plage temporelle
        try:
            cur.execute(f"SELECT MIN({time_col}) AS mn, MAX({time_col}) AS mx FROM {t}")
            row = cur.fetchone()
            print(f"  plage    : {row['mn']}  ->  {row['mx']}")
        except sqlite3.Error as e:
            print(f"  [WARN] plage non calculable : {e}")

        # 3 dernieres lignes
        try:
            cur.execute(
                f"SELECT * FROM {t} ORDER BY {time_col} DESC LIMIT 3"
            )
            rows = cur.fetchall()
            for r in rows:
                d = dict(r)
                # On tronque les valeurs longues
                short = {
                    k: (v[:80] + "..." if isinstance(v, str) and len(v) > 80 else v)
                    for k, v in d.items()
                }
                print(f"    {json.dumps(short, ensure_ascii=False, default=str)[:240]}")
        except sqlite3.Error as e:
            print(f"  [WARN] echec last-3 : {e}")

    banner("3. Tables 'cycle' specifiques (cycles, cycle_*, run_*)")
    cycle_tables = [t for t in tables if "cycle" in t.lower() or "run" in t.lower()]
    for t in cycle_tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            n = cur.fetchone()[0]
            cur.execute(f"PRAGMA table_info({t})")
            cols = [c[1] for c in cur.fetchall()]
            print(f"  {t:35} rows={n:,} cols={cols}")
        except sqlite3.Error as e:
            print(f"  [SKIP] {t}: {e}")

    banner("4. Estimation du cycle 'maintenant' (latest snapshot)")
    # On essaie de savoir quel est le dernier "cycle" enregistre
    for guess in ["cycles", "agent_outputs", "cycle_results"]:
        if guess in tables:
            try:
                cur.execute(f"SELECT * FROM {guess} ORDER BY ROWID DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    print(f"  [{guess}] derniere ligne :")
                    for k, v in dict(row).items():
                        s = str(v)
                        if len(s) > 100:
                            s = s[:100] + "..."
                        print(f"     {k:25} = {s}")
            except sqlite3.Error as e:
                print(f"  [WARN] {guess}: {e}")

    con.close()
    banner("FIN diag")
    return 0


if __name__ == "__main__":
    sys.exit(main())
