"""
nextones-diag-insert-and-memo.py
Localise :
  1. La (ou les) fonction(s) qui insere(nt) dans la table orders
  2. Le generateur d'IC Memo (ic_memo, generate_memo, etc.)
  3. La structure de la table orders pour comprendre le payload a passer au gate

Usage : py -3.13 nextones-diag-insert-and-memo.py
"""
from __future__ import annotations
import re
import sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"

SOURCES = [
    "execution_engine.py",
    "agents.py",
    "risk_engine.py",
    "portfolio_construction_agent.py",
    "api_server_with_static.py",
    "reconciler.py",
]

INSERT_PAT = re.compile(r"INSERT\s+INTO\s+orders\b", re.IGNORECASE)
FUNCTION_PAT = re.compile(r"^\s*def\s+(\w+)\s*\(", re.MULTILINE)
MEMO_PAT = re.compile(r"(ic[_-]?memo|generate[_-]?memo|memo[_-]?(generate|build|render)|render[_-]?memo)", re.IGNORECASE)
MEMO_INSERT_PAT = re.compile(r"INSERT\s+INTO\s+(ic_memos|memos|ic_memo)\b", re.IGNORECASE)


def find_enclosing_function(src: str, idx: int) -> str:
    """Cherche le 'def xxx(' le plus proche au-dessus de idx."""
    fns = list(FUNCTION_PAT.finditer(src))
    nearest = "<module-level>"
    for m in fns:
        if m.start() <= idx:
            nearest = m.group(1)
        else:
            break
    return nearest


def line_no(src: str, idx: int) -> int:
    return src.count("\n", 0, idx) + 1


def scan_file_for_insert_orders(path: Path):
    if not path.exists():
        print(f"  [MISS] {path.name}")
        return
    src = path.read_text(encoding="utf-8-sig")
    hits = list(INSERT_PAT.finditer(src))
    if not hits:
        return
    print(f"\n[INSERT INTO orders] dans {path.name} : {len(hits)} occurrence(s)")
    for h in hits:
        fn = find_enclosing_function(src, h.start())
        ln = line_no(src, h.start())
        # extrait 200 chars autour
        s = max(0, h.start() - 100)
        e = min(len(src), h.end() + 200)
        snippet = src[s:e].replace("\n", " | ")
        print(f"   - line {ln}  fn={fn}")
        print(f"     ...{snippet[:300]}...")


def scan_file_for_memo(path: Path):
    if not path.exists():
        return
    src = path.read_text(encoding="utf-8-sig")
    hits = list(MEMO_PAT.finditer(src))
    inserts = list(MEMO_INSERT_PAT.finditer(src))
    fn_hits = []
    # Restreindre aux def memo*
    for m in FUNCTION_PAT.finditer(src):
        if MEMO_PAT.search(m.group(1)):
            fn_hits.append(m)
    if not (fn_hits or inserts):
        return
    print(f"\n[MEMO] dans {path.name} :")
    if fn_hits:
        for m in fn_hits:
            ln = line_no(src, m.start())
            print(f"   - def {m.group(1)} (line {ln})")
    if inserts:
        for m in inserts:
            ln = line_no(src, m.start())
            fn = find_enclosing_function(src, m.start())
            print(f"   - INSERT memo line {ln} dans fn={fn}")


def main():
    print("=" * 60)
    print(" Diag INSERT INTO orders + IC Memo + table orders")
    print("=" * 60)

    print("\n[1] Schema table orders :")
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row
    try:
        cols = c.execute("PRAGMA table_info(orders)").fetchall()
        for col in cols:
            print(f"   {col['name']:25s} {col['type']}")
        n = c.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"]
        print(f"   rows total : {n}")
        rows = c.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 3").fetchall()
        print("   3 derniers :")
        for r in rows:
            print(f"     {dict(r)}")
    except Exception as e:
        print(f"   [ERR] {e}")
    finally:
        c.close()

    # Tables IC Memos candidates
    print("\n[2] Tables memo candidates :")
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row
    try:
        rows = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND (name LIKE '%memo%' OR name LIKE '%ic_%')"
        ).fetchall()
        for r in rows:
            print(f"   - {r['name']}")
            try:
                cols = c.execute(f"PRAGMA table_info({r['name']})").fetchall()
                for col in cols:
                    print(f"       {col['name']:25s} {col['type']}")
                n = c.execute(f"SELECT COUNT(*) AS n FROM {r['name']}").fetchone()["n"]
                print(f"       rows : {n}")
            except Exception as e2:
                print(f"       [ERR] {e2}")
    except Exception as e:
        print(f"   [ERR] {e}")
    finally:
        c.close()

    print("\n[3] Scan code source pour INSERT INTO orders :")
    for fname in SOURCES:
        scan_file_for_insert_orders(ROOT / fname)

    print("\n[4] Scan code source pour IC Memo (def + INSERT) :")
    for fname in SOURCES:
        scan_file_for_memo(ROOT / fname)

    # Bonus : chercher les fichiers *.py qui contiennent memo
    print("\n[5] Tous les .py contenant 'memo' (top-level root) :")
    for p in ROOT.glob("*.py"):
        try:
            src = p.read_text(encoding="utf-8-sig", errors="ignore")
        except Exception:
            continue
        n = len(MEMO_PAT.findall(src))
        if n > 0:
            print(f"   {p.name:40s} matches={n}")


if __name__ == "__main__":
    main()
