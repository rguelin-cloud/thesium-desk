# -*- coding: utf-8 -*-
"""
nextones-fix-db-locks-v2-scheduler.py

Patch DB lock v2 — cible le scheduler (api_server.py) et les modules
data/risk encore non couverts par le v1.

Stratégie :
  - Pour chaque sqlite3.connect(...) trouvé, on ajoute APRES la connexion :
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA synchronous=NORMAL")
  - On ne touche pas si déjà patché (marker [DB_LOCK_FIX_V1] sur la même connexion).
  - Validation ast.parse + py_compile avant écriture.
  - Backup .bak.YYYYmmddHHMMSS

Cible :
  - api_server.py           (BackgroundScheduler + jobs refresh_*)
  - data_crypto.py
  - data_ingestion.py
  - risk_engine.py
  - (et tout fichier listé dans TARGETS encore non couvert)
"""

from __future__ import annotations

import ast
import io
import os
import py_compile
import re
import sys
import time
from pathlib import Path

# Stdout UTF-8 tolerant
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:
    pass

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

TARGETS = [
    "api_server.py",
    "api_server_with_static.py",
    "data_crypto.py",
    "data_ingestion.py",
    "data_macro.py",
    "data_sentiment.py",
    "risk_engine.py",
    "execution_engine.py",
    "portfolio_construction_agent_jalon2.py",
    "scheduler_universe.py",
    "broker_reconciler.py",
    "broker_shadow_executor.py",
    "memo_generator.py",
]

MARKER = "[DB_LOCK_FIX_V1]"

# Regex : capture l'assignation `var = sqlite3.connect(...)` (multi-ligne autorisée)
RE_CONNECT = re.compile(
    r"(?P<indent>[ \t]*)(?P<lhs>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*sqlite3\.connect\((?P<args>[^)]*)\)",
    re.MULTILINE,
)


def read_text(p: Path) -> str:
    with open(p, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_text(p: Path, content: str) -> None:
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(content)


def already_patched_near(text: str, end_idx: int) -> bool:
    """Regarde dans les ~250 caractères suivants si MARKER est présent."""
    window = text[end_idx : end_idx + 250]
    return MARKER in window


def patch_file(path: Path) -> tuple[int, int, str | None]:
    """
    Retourne (n_connects, n_patched, error_or_None).
    """
    if not path.exists():
        return (0, 0, "FILE_NOT_FOUND")

    try:
        src = read_text(path)
    except Exception as e:
        return (0, 0, f"READ_ERROR: {e}")

    matches = list(RE_CONNECT.finditer(src))
    if not matches:
        return (0, 0, None)

    n_connects = len(matches)
    n_patched = 0

    # On itère en sens inverse pour ne pas casser les offsets
    new_src = src
    for m in reversed(matches):
        end = m.end()
        if already_patched_near(new_src, end):
            continue

        indent = m.group("indent")
        lhs = m.group("lhs")

        injection = (
            f"\n{indent}# {MARKER} busy_timeout + WAL + synchronous=NORMAL\n"
            f'{indent}try:\n'
            f'{indent}    {lhs}.execute("PRAGMA journal_mode=WAL")\n'
            f'{indent}    {lhs}.execute("PRAGMA busy_timeout=10000")\n'
            f'{indent}    {lhs}.execute("PRAGMA synchronous=NORMAL")\n'
            f'{indent}except Exception:\n'
            f'{indent}    pass'
        )

        new_src = new_src[:end] + injection + new_src[end:]
        n_patched += 1

    if n_patched == 0:
        return (n_connects, 0, None)

    # Validation AST
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        return (n_connects, 0, f"AST_FAIL: {e}")

    # Backup
    ts = time.strftime("%Y%m%d%H%M%S")
    backup = path.with_suffix(path.suffix + f".bak.{ts}")
    try:
        backup.write_text(src, encoding="utf-8")
    except Exception as e:
        return (n_connects, 0, f"BACKUP_ERROR: {e}")

    # Write
    try:
        write_text(path, new_src)
    except Exception as e:
        return (n_connects, 0, f"WRITE_ERROR: {e}")

    # py_compile
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as e:
        # Rollback
        write_text(path, src)
        return (n_connects, 0, f"PYCOMPILE_FAIL: {e}")

    return (n_connects, n_patched, None)


def coverage_report(path: Path) -> tuple[int, int]:
    """Retourne (n_connects, n_busy_timeout) pour reporting final."""
    if not path.exists():
        return (0, 0)
    try:
        src = read_text(path)
    except Exception:
        return (0, 0)
    n_connects = len(RE_CONNECT.findall(src))
    n_bt = src.count("busy_timeout=10000")
    return (n_connects, n_bt)


def main() -> int:
    print("=" * 70)
    print("nextones-fix-db-locks-v2-scheduler — patch DB locks (scheduler)")
    print("=" * 70)
    print(f"ROOT = {ROOT}")
    print()

    results = []
    for fname in TARGETS:
        p = ROOT / fname
        n_conn, n_patched, err = patch_file(p)
        status = "OK" if err is None else f"ERR ({err})"
        print(f"  {fname:50s}  connects={n_conn:2d}  patched={n_patched:2d}  {status}")
        results.append((fname, n_conn, n_patched, err))

    print()
    print("=" * 70)
    print("Couverture finale (busy_timeout >= connects)")
    print("=" * 70)
    print(f"  {'fichier':50s}  {'connects':>8s}  {'busy_to':>8s}  {'cov':>3s}")
    print(f"  {'-'*50}  {'-'*8}  {'-'*8}  {'-'*3}")
    ok_count = 0
    total = 0
    for fname in TARGETS:
        p = ROOT / fname
        n_conn, n_bt = coverage_report(p)
        if n_conn == 0:
            mark = "-"
        else:
            total += 1
            if n_bt >= n_conn:
                mark = "OK"
                ok_count += 1
            else:
                mark = "KO"
        print(f"  {fname:50s}  {n_conn:8d}  {n_bt:8d}  {mark:>3s}")

    print()
    print(f"Couverture finale : {ok_count}/{total} fichiers OK")
    print()
    print("Étapes suivantes :")
    print("  1. Stop uvicorn :")
    print("     Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |")
    print("       Select-Object OwningProcess |")
    print("       ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }")
    print("  2. Restart : py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print("  3. Observer logs : [CRYPTO-AGENT] Done | OK=6 FAIL=0 (sans 'database is locked')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
