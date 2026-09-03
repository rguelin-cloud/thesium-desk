# -*- coding: utf-8 -*-
"""
nextones-diag-syntax-errors-v1.py

Diagnostique les erreurs de syntaxe signalées par le patch v2 :
  - api_server.py ligne 3270
  - portfolio_construction_agent_jalon2.py ligne 1156

Pour chaque fichier :
  1. Lit en utf-8-sig
  2. Tente ast.parse → affiche l'erreur exacte + offset
  3. Dump les 30 lignes autour de l'erreur
  4. Cherche les markers [DB_LOCK_FIX_V1] dans le fichier pour voir si v1 a déjà patché

Aussi : liste TOUS les fichiers .py à la racine qui matchent un pattern broker_* / scheduler_*.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:
    pass

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

TARGETS_SYNTAX = [
    ("api_server.py", 3270),
    ("portfolio_construction_agent_jalon2.py", 1156),
]


def diag_syntax(fname: str, hint_line: int) -> None:
    p = ROOT / fname
    print(f"\n{'=' * 70}")
    print(f"  {fname}  (hint ligne {hint_line})")
    print("=" * 70)
    if not p.exists():
        print("  FILE NOT FOUND")
        return
    with open(p, "r", encoding="utf-8-sig") as f:
        src = f.read()
    lines = src.splitlines()
    print(f"  Total lines: {len(lines)}")

    # AST parse
    try:
        ast.parse(src)
        print("  AST: OK (pas d'erreur)")
    except SyntaxError as e:
        print(f"  AST FAIL:")
        print(f"    msg     = {e.msg}")
        print(f"    lineno  = {e.lineno}")
        print(f"    offset  = {e.offset}")
        print(f"    text    = {repr(e.text)}")
        err_line = e.lineno or hint_line
    else:
        err_line = hint_line

    # Dump 30 lignes autour de l'erreur
    start = max(1, err_line - 15)
    end = min(len(lines), err_line + 15)
    print(f"\n  Lignes {start}..{end}:")
    print("  " + "-" * 68)
    for i in range(start, end + 1):
        marker = " >>>" if i == err_line else "    "
        print(f"  {marker} {i:5d} | {lines[i-1]}")

    # Markers DB_LOCK_FIX_V1
    n_markers = src.count("[DB_LOCK_FIX_V1]")
    n_connects = src.count("sqlite3.connect(")
    n_bt = src.count("busy_timeout=10000")
    print(f"\n  Markers [DB_LOCK_FIX_V1] : {n_markers}")
    print(f"  sqlite3.connect(         : {n_connects}")
    print(f"  busy_timeout=10000       : {n_bt}")


def list_brokers_schedulers() -> None:
    print(f"\n{'=' * 70}")
    print("  Fichiers .py broker_* / scheduler_* / *broker* / *scheduler* à la racine")
    print("=" * 70)
    files = sorted(ROOT.glob("*.py"))
    for kw in ("broker", "scheduler", "reconciler", "shadow"):
        print(f"\n  Pattern '*{kw}*' :")
        matches = [f.name for f in files if kw in f.name.lower()]
        if not matches:
            print("    (aucun)")
        for m in matches:
            print(f"    - {m}")


def list_files_with_sqlite_connect() -> None:
    print(f"\n{'=' * 70}")
    print("  TOP 20 fichiers .py contenant sqlite3.connect( (encore non couverts)")
    print("=" * 70)
    rows = []
    for p in sorted(ROOT.glob("*.py")):
        try:
            with open(p, "r", encoding="utf-8-sig") as f:
                src = f.read()
        except Exception:
            continue
        n_conn = src.count("sqlite3.connect(")
        if n_conn == 0:
            continue
        n_bt = src.count("busy_timeout=10000")
        n_marker = src.count("[DB_LOCK_FIX_V1]")
        rows.append((p.name, n_conn, n_bt, n_marker))

    rows.sort(key=lambda r: (-(r[1] - r[2]), -r[1]))
    print(f"  {'fichier':50s}  {'conn':>4s}  {'bt':>4s}  {'mark':>4s}  cov")
    print(f"  {'-'*50}  {'-'*4}  {'-'*4}  {'-'*4}  ---")
    for fname, n_conn, n_bt, n_marker in rows[:30]:
        cov = "OK" if n_bt >= n_conn else "KO"
        print(f"  {fname:50s}  {n_conn:4d}  {n_bt:4d}  {n_marker:4d}  {cov}")


def main() -> int:
    print("=" * 70)
    print("nextones-diag-syntax-errors-v1")
    print("=" * 70)
    print(f"ROOT = {ROOT}")

    for fname, hint in TARGETS_SYNTAX:
        diag_syntax(fname, hint)

    list_brokers_schedulers()
    list_files_with_sqlite_connect()

    return 0


if __name__ == "__main__":
    sys.exit(main())
