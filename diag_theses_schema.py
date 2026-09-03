# [DIAG_THESES_SCHEMA_V1] Verifie la structure exacte de la table theses
from __future__ import annotations
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent / "thesium.db"

cx = sqlite3.connect(str(DB), timeout=10)
cx.row_factory = sqlite3.Row
try:
    print("=" * 80)
    print("TABLE theses")
    print("=" * 80)
    cols = cx.execute("PRAGMA table_info(theses)").fetchall()
    for c in cols:
        print(f"  {c['name']:25} {c['type']:15} default={c['dflt_value']}")

    print("\nDistinct values:")
    for col in ("status", "agent_type", "proposed_action"):
        try:
            rows = cx.execute(f"SELECT DISTINCT {col} FROM theses LIMIT 20").fetchall()
            print(f"  {col}: {[r[col] for r in rows]}")
        except Exception as e:
            print(f"  {col}: ERREUR ({e})")

    print("\nDernieres theses (5):")
    cols_names = [c["name"] for c in cols]
    pick = [c for c in ("id", "instrument_id", "agent_type", "status", "proposed_action", "conviction", "created_at") if c in cols_names]
    sel = ", ".join(pick)
    rows = cx.execute(f"SELECT {sel} FROM theses ORDER BY id DESC LIMIT 5").fetchall()
    for r in rows:
        print(f"  {dict(r)}")

    # Count par status
    print("\nCount par status:")
    rows = cx.execute("SELECT status, COUNT(*) AS n FROM theses GROUP BY status").fetchall()
    for r in rows:
        print(f"  {r['status']}: {r['n']}")

    # Theses recentes (1 jour) par conviction
    print("\nTop-5 conviction des theses recentes (1j):")
    try:
        rows = cx.execute("""
            SELECT t.id, i.ticker, t.proposed_action, t.conviction, t.agent_type, t.status, t.created_at
            FROM theses t
            LEFT JOIN instruments i ON i.id = t.instrument_id
            WHERE t.created_at >= datetime('now', '-1 day')
            ORDER BY t.conviction DESC
            LIMIT 5
        """).fetchall()
        for r in rows:
            print(f"  {dict(r)}")
    except Exception as e:
        print(f"  ERREUR: {e}")
finally:
    cx.close()
