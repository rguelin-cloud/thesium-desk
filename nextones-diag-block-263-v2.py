"""
[DIAG_BLOCK_263_V2]
Le diag v1 a revele :
 - orders.id=263 : status=filled, risk_check_result.approved=true
 - risk_pretrade_log : 44 rows mais aucun hit sur order_id=263

Donc le memo affiche un BLOCK qui n'existe pas reellement en base.
Objectifs v2 :
 1. Schema complet de risk_pretrade_log + 5 dernieres entrees
 2. Schema complet de broker_shadow_audit + 5 dernieres entrees pour ZEC / order 263
 3. Schema portfolio_positions + recherche ZEC dans toutes les colonnes
 4. Lecture full du risk_check_result pour order 263 (sans troncature)
 5. Localiser la source memo Pre-trade Controls (chemin de code)
"""
from __future__ import annotations
import os
import sys
import sqlite3
import json

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"


def dump_schema(cur, table):
    print(f"\n[SCHEMA] {table}")
    print("-" * 70)
    cols = cur.execute(f"PRAGMA table_info({table})").fetchall()
    for c in cols:
        print(f"   {c[1]:30s} {c[2]:15s} pk={c[5]}")
    return [c[1] for c in cols]


def main() -> int:
    if not os.path.exists(DB_PATH):
        print(f"[ERR] DB introuvable : {DB_PATH}")
        return 1
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("=" * 70)
    print("DIAG BLOCK #263 V2 - chasser le faux BLOCK")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. risk_pretrade_log : schema + 5 dernieres entrees + recherche ZEC
    # ------------------------------------------------------------------
    cols = dump_schema(cur, "risk_pretrade_log")
    print(f"\n[risk_pretrade_log] 5 dernieres entrees")
    print("-" * 70)
    order_clause = "ORDER BY rowid DESC"
    for c in ("created_at", "ts", "timestamp", "checked_at"):
        if c in cols:
            order_clause = f"ORDER BY {c} DESC"
            break
    rows = cur.execute(f"SELECT * FROM risk_pretrade_log {order_clause} LIMIT 5").fetchall()
    for r in rows:
        d = dict(r)
        for k, v in d.items():
            s = str(v)
            if len(s) > 300:
                s = s[:300] + "..."
            print(f"   {k:25s} = {s}")
        print("   ---")

    # recherche ZEC dans risk_pretrade_log
    print(f"\n[risk_pretrade_log] hits ZEC")
    print("-" * 70)
    for tcol in ("ticker", "symbol", "instrument", "asset"):
        if tcol in cols:
            try:
                rows = cur.execute(
                    f"SELECT * FROM risk_pretrade_log WHERE {tcol} LIKE '%ZEC%' "
                    f"{order_clause} LIMIT 5"
                ).fetchall()
                for r in rows:
                    print(f"   [{tcol}] {dict(r)}")
            except Exception as e:
                print(f"   [{tcol}] ERR: {e}")

    # ------------------------------------------------------------------
    # 2. broker_shadow_audit : schema + recherche ZEC / order 263
    # ------------------------------------------------------------------
    cols = dump_schema(cur, "broker_shadow_audit")
    print(f"\n[broker_shadow_audit] 5 dernieres entrees")
    print("-" * 70)
    order_clause = "ORDER BY rowid DESC"
    for c in ("created_at", "ts", "timestamp"):
        if c in cols:
            order_clause = f"ORDER BY {c} DESC"
            break
    rows = cur.execute(f"SELECT * FROM broker_shadow_audit {order_clause} LIMIT 5").fetchall()
    for r in rows:
        d = dict(r)
        for k, v in d.items():
            s = str(v)
            if len(s) > 300:
                s = s[:300] + "..."
            print(f"   {k:25s} = {s}")
        print("   ---")

    # recherche ZEC + order_id=263
    print(f"\n[broker_shadow_audit] hits ZEC / order 263")
    print("-" * 70)
    for tcol in ("ticker", "symbol", "instrument", "asset"):
        if tcol in cols:
            try:
                rows = cur.execute(
                    f"SELECT * FROM broker_shadow_audit WHERE {tcol} LIKE '%ZEC%' "
                    f"{order_clause} LIMIT 5"
                ).fetchall()
                for r in rows:
                    d = dict(r)
                    print(f"   [{tcol}=ZEC]")
                    for k, v in d.items():
                        s = str(v)
                        if len(s) > 200:
                            s = s[:200] + "..."
                        print(f"      {k:25s} = {s}")
                    print("      ---")
            except Exception as e:
                print(f"   [{tcol}] ERR: {e}")
    for id_col in ("order_id", "proposal_id"):
        if id_col in cols:
            try:
                rows = cur.execute(
                    f"SELECT * FROM broker_shadow_audit WHERE {id_col}=? LIMIT 5",
                    (263,)
                ).fetchall()
                for r in rows:
                    print(f"   [{id_col}=263] {dict(r)}")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 3. broker_shadow_orders : recherche ZEC / order 263
    # ------------------------------------------------------------------
    cols = dump_schema(cur, "broker_shadow_orders")
    print(f"\n[broker_shadow_orders] hits ZEC / order 263")
    print("-" * 70)
    for id_col in ("order_id", "proposal_id"):
        if id_col in cols:
            try:
                rows = cur.execute(
                    f"SELECT * FROM broker_shadow_orders WHERE {id_col}=? LIMIT 5",
                    (263,)
                ).fetchall()
                for r in rows:
                    d = dict(r)
                    print(f"   [{id_col}=263]")
                    for k, v in d.items():
                        s = str(v)
                        if len(s) > 200:
                            s = s[:200] + "..."
                        print(f"      {k:25s} = {s}")
                    print("      ---")
            except Exception:
                pass
    for tcol in ("ticker", "symbol", "instrument"):
        if tcol in cols:
            try:
                rows = cur.execute(
                    f"SELECT * FROM broker_shadow_orders WHERE {tcol} LIKE '%ZEC%' "
                    f"ORDER BY rowid DESC LIMIT 5"
                ).fetchall()
                for r in rows:
                    d = dict(r)
                    print(f"   [{tcol}=ZEC]")
                    for k, v in d.items():
                        s = str(v)
                        if len(s) > 200:
                            s = s[:200] + "..."
                        print(f"      {k:25s} = {s}")
                    print("      ---")
            except Exception as e:
                print(f"   [{tcol}] ERR: {e}")

    # ------------------------------------------------------------------
    # 4. Position ZEC : chercher dans portfolio_positions + instruments
    # ------------------------------------------------------------------
    cols = dump_schema(cur, "portfolio_positions")
    print(f"\n[portfolio_positions] toutes positions actives")
    print("-" * 70)
    try:
        rows = cur.execute("SELECT * FROM portfolio_positions LIMIT 30").fetchall()
        for r in rows:
            print(f"   {dict(r)}")
    except Exception as e:
        print(f"   ERR: {e}")

    # ------------------------------------------------------------------
    # 5. risk_check_result complet (sans troncature) pour order 263
    # ------------------------------------------------------------------
    print(f"\n[orders #263] risk_check_result COMPLET (sans troncature)")
    print("-" * 70)
    row = cur.execute(
        "SELECT risk_check_result FROM orders WHERE id=?", (263,)
    ).fetchone()
    if row and row[0]:
        try:
            parsed = json.loads(row[0])
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"  [parse err] {e}")
            print(f"  raw = {row[0]}")

    # ------------------------------------------------------------------
    # 6. Localiser la source du panneau "Pre-trade Controls" UI
    # ------------------------------------------------------------------
    print(f"\n[6] Sources potentielles du panneau memo Pre-trade Controls")
    print("-" * 70)
    import re
    from pathlib import Path
    ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
    hits = []
    for ext in ("*.py", "*.js", "*.html"):
        for p in ROOT.rglob(ext):
            sp = str(p).lower()
            if any(x in sp for x in ("\\venv", "__pycache__", "\\backup", "\\.git", "\\node_modules")):
                continue
            try:
                src = p.read_text(encoding="utf-8-sig", errors="replace")
            except Exception:
                continue
            if "Pre-trade" in src or "RISK_V2" in src or "broker_mapping_ok" in src:
                hits.append(p)
    for h in hits[:20]:
        print(f"   {h}")
        try:
            src = h.read_text(encoding="utf-8-sig", errors="replace")
            for i, ln in enumerate(src.splitlines(), 1):
                if any(k in ln for k in ("Pre-trade", "RISK_V2", "broker_mapping_ok",
                                          "verdict", "BLOCK")):
                    print(f"     L{i:4d}: {ln.strip()[:160]}")
        except Exception:
            pass
        print("   ---")

    conn.close()
    print("\n" + "=" * 70)
    print("FIN DIAG V2")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
