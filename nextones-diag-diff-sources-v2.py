# -*- coding: utf-8 -*-
"""
Diag complementaire pour le DIFF :
1) Schema + 5 dernieres lignes de regime_log (pour diff regime macro)
2) Distribution des cycle_id dans cycle_reconciliation_log + theses
   (combien de cycles distincts, quel est le pattern d'ID)
3) theses : top 5 derniers cycles (groupes par 'created_at' au jour pres)
   avec count et liste tickers/agents
4) Echantillon de risk_pretrade_log + crypto_context (pour diff sentiment crypto)
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


def schema(cur, t):
    cur.execute(f"PRAGMA table_info({t})")
    return cur.fetchall()


def main() -> int:
    if not DB.exists():
        print(f"[ERR] {DB} introuvable")
        return 2

    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    banner("1. regime_log : schema + 5 dernieres lignes")
    cols = schema(cur, "regime_log")
    print(f"  cols : {', '.join(c[1] for c in cols)}")
    cur.execute("SELECT * FROM regime_log ORDER BY created_at DESC LIMIT 5")
    for r in cur.fetchall():
        d = dict(r)
        s = json.dumps(d, ensure_ascii=False, default=str)
        print(f"    {s[:240]}")

    banner("2. cycle_reconciliation_log : distribution cycle_id (top 8 cycles)")
    cur.execute(
        """SELECT cycle_id, MIN(created_at) AS started, MAX(created_at) AS ended,
                  COUNT(*) AS n
           FROM cycle_reconciliation_log
           GROUP BY cycle_id
           ORDER BY started DESC
           LIMIT 8"""
    )
    for r in cur.fetchall():
        print(
            f"  cycle_id={r['cycle_id']:>10}  started={r['started']}  ended={r['ended']}  rows={r['n']}"
        )

    banner("3. theses : derniers 7 jours, count par jour + agents distincts")
    cur.execute(
        """SELECT substr(created_at, 1, 10) AS d,
                  agent_type,
                  COUNT(*) AS n
           FROM theses
           WHERE created_at >= '2026-06-02'
           GROUP BY substr(created_at, 1, 10), agent_type
           ORDER BY d DESC, agent_type"""
    )
    cur_day = None
    for r in cur.fetchall():
        if r["d"] != cur_day:
            print(f"\n  {r['d']}")
            cur_day = r["d"]
        print(f"    {r['agent_type']:25} n={r['n']}")

    banner("4. theses : 1 exemple par agent_type pour le 2026-06-09")
    cur.execute(
        """SELECT MIN(id) AS id, agent_type
           FROM theses
           WHERE substr(created_at, 1, 10) = '2026-06-09'
           GROUP BY agent_type"""
    )
    sample_ids = [(r["id"], r["agent_type"]) for r in cur.fetchall()]
    for tid, atype in sample_ids:
        cur.execute("SELECT * FROM theses WHERE id = ?", (tid,))
        r = cur.fetchone()
        if r:
            d = dict(r)
            d["thesis_text"] = (d.get("thesis_text") or "")[:120] + "..."
            d["key_drivers"] = (d.get("key_drivers") or "")[:80] + "..."
            print(f"\n  --- {atype} (id={tid}) ---")
            for k, v in d.items():
                s = str(v)
                if len(s) > 200:
                    s = s[:200] + "..."
                print(f"    {k:20} = {s}")

    banner("5. crypto_context : schema + lignes (6 lignes au total)")
    cols = schema(cur, "crypto_context")
    print(f"  cols : {', '.join(c[1] for c in cols)}")
    cur.execute("SELECT * FROM crypto_context ORDER BY ts DESC")
    for r in cur.fetchall():
        d = dict(r)
        d_str = {
            k: (v[:80] + "..." if isinstance(v, str) and len(v) > 80 else v)
            for k, v in d.items()
        }
        print(f"    {json.dumps(d_str, ensure_ascii=False, default=str)[:240]}")

    banner("6. portfolio_targets_history : schema + 5 derniers cycles")
    cols = schema(cur, "portfolio_targets_history")
    print(f"  cols : {', '.join(c[1] for c in cols)}")
    cur.execute(
        "SELECT * FROM portfolio_targets_history ORDER BY created_at DESC LIMIT 5"
    )
    for r in cur.fetchall():
        d = dict(r)
        d_str = {
            k: (v[:80] + "..." if isinstance(v, str) and len(v) > 80 else v)
            for k, v in d.items()
        }
        print(f"    {json.dumps(d_str, ensure_ascii=False, default=str)[:240]}")

    banner("7. ic_memos : schema + 5 derniers")
    cols = schema(cur, "ic_memos")
    print(f"  cols : {', '.join(c[1] for c in cols)}")
    cur.execute("SELECT id, created_at, substr(memo_md, 1, 80) AS extract FROM ic_memos ORDER BY id DESC LIMIT 5")
    for r in cur.fetchall():
        print(f"  id={r['id']}  created={r['created_at']}  extract={r['extract']}")

    con.close()
    banner("FIN diag v2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
