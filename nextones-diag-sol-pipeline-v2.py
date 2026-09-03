# -*- coding: utf-8 -*-
"""
[DIAG_SOL_PIPELINE_V2]
Version corrigee : detecte automatiquement le schema reel des tables
theses et risk_pretrade_log avant de filtrer SOL.

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-diag-sol-pipeline-v2.py
"""
import sqlite3
from pathlib import Path

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")

def section(t):
    print("\n" + "="*70)
    print(f"  {t}")
    print("="*70)

def cols(conn, table):
    try:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    except Exception:
        return []

def main():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    # Recup id SOL
    inst = conn.execute("SELECT id FROM instruments WHERE ticker='SOL'").fetchone()
    if not inst:
        print("[FAIL] SOL absent de instruments.")
        return
    sol_id = inst["id"]
    print(f"[INFO] SOL instrument_id = {sol_id}")

    section("1) Schema des tables clefs")
    for t in ["theses", "orders", "risk_pretrade_log", "fills",
              "memos", "agent_proposals", "construction_targets",
              "portfolio_targets", "signals"]:
        c = cols(conn, t)
        marker = "OK" if c else "ABSENT"
        print(f"  [{marker:6s}] {t:25s} cols={c[:10] if c else '-'}")

    section("2) prices(SOL)")
    n = conn.execute("SELECT COUNT(*) c FROM prices WHERE instrument_id=?", (sol_id,)).fetchone()["c"]
    print(f"  total prix SOL : {n}")
    last = conn.execute(
        "SELECT MIN(date) min_d, MAX(date) max_d FROM prices WHERE instrument_id=?",
        (sol_id,)
    ).fetchone()
    print(f"  range          : {dict(last)}")

    section("3) theses SOL (avec colonne instrument_id ou ticker)")
    theses_cols = cols(conn, "theses")
    if "instrument_id" in theses_cols:
        rows = conn.execute(
            "SELECT * FROM theses WHERE instrument_id=? ORDER BY id DESC LIMIT 10",
            (sol_id,)
        ).fetchall()
    elif "ticker" in theses_cols:
        rows = conn.execute(
            "SELECT * FROM theses WHERE ticker='SOL' ORDER BY id DESC LIMIT 10"
        ).fetchall()
    else:
        rows = []
        print(f"  [WARN] colonnes inattendues : {theses_cols}")
    if rows:
        for r in rows:
            d = dict(r)
            # tronquer texte long
            for k, v in list(d.items()):
                if isinstance(v, str) and len(v) > 100:
                    d[k] = v[:100] + "..."
            print(f"  {d}")
    else:
        print("  Aucune these pour SOL.")

    section("4) DERNIERES theses tous tickers (verifier que CryptoAgent tourne)")
    if theses_cols:
        # Trouve la colonne agent ou source
        rows = conn.execute(
            f"SELECT * FROM theses ORDER BY id DESC LIMIT 5"
        ).fetchall()
        for r in rows:
            d = dict(r)
            for k, v in list(d.items()):
                if isinstance(v, str) and len(v) > 80:
                    d[k] = v[:80] + "..."
            print(f"  {d}")

    section("5) orders recents (5 derniers)")
    orders_cols = cols(conn, "orders")
    if orders_cols:
        rows = conn.execute("""
            SELECT o.id, o.side, o.quantity, o.status, o.created_at, i.ticker
            FROM orders o JOIN instruments i ON i.id=o.instrument_id
            ORDER BY o.id DESC LIMIT 10
        """).fetchall()
        for r in rows:
            print(f"  {dict(r)}")

    section("6) construction_targets / portfolio_targets SOL")
    for t in ["construction_targets", "portfolio_targets", "target_universe"]:
        c = cols(conn, t)
        if not c: continue
        if "instrument_id" in c:
            rows = conn.execute(
                f"SELECT * FROM {t} WHERE instrument_id=? ORDER BY id DESC LIMIT 5",
                (sol_id,)
            ).fetchall()
        elif "ticker" in c:
            rows = conn.execute(
                f"SELECT * FROM {t} WHERE ticker='SOL' ORDER BY id DESC LIMIT 5"
            ).fetchall()
        else:
            rows = []
        print(f"  --- {t} ---")
        if rows:
            for r in rows: print(f"    {dict(r)}")
        else:
            print(f"    (rien pour SOL)")

    section("7) memos recents (3 derniers)")
    mc = cols(conn, "memos")
    if mc:
        rows = conn.execute("SELECT id, created_at FROM memos ORDER BY id DESC LIMIT 3").fetchall()
        for r in rows:
            print(f"  {dict(r)}")
            # contenu memo si colonne content
            if "content" in mc:
                content = conn.execute("SELECT content FROM memos WHERE id=?", (r["id"],)).fetchone()["content"]
                # cherche SOL dans le memo
                if content and "SOL" in content:
                    print(f"    -> mentionne SOL")
                    # extrait 3 lignes autour
                    lines = content.splitlines()
                    for i, ln in enumerate(lines):
                        if "SOL" in ln:
                            print(f"    L{i}: {ln.strip()[:200]}")
                else:
                    print(f"    -> ne mentionne PAS SOL")

    conn.close()

if __name__ == "__main__":
    main()
