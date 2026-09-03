# -*- coding: utf-8 -*-
"""
nextones-fix-db-locks-v3-runtime.py

Patch v3 — corrige les défauts du v2 :
  - Regex robuste : gère sqlite3.connect(str(...)) (parenthèses imbriquées)
  - Cible UNIQUEMENT modules runtime (importés par api_server_with_static.py)
  - Ne touche pas les scripts utilitaires nextones-*.py / _*.py

Stratégie :
  1. Tokenize chaque fichier pour trouver les sqlite3.connect(...) avec leurs
     parenthèses correctement appariées (PAS de regex sur args).
  2. Identifie le LHS (var = sqlite3.connect(...)) via inspection avant la match.
  3. Si pas de LHS (ex: avec sqlite3.connect(...) as con), saute (le with block
     fermera automatiquement, mais on log).
  4. Injecte le bloc PRAGMA après la connexion, indenté correctement.
  5. Validation ast.parse + py_compile, rollback automatique en cas d'échec.
  6. Marker [DB_LOCK_FIX_V1] : on saute si déjà présent dans les 250 caractères
     suivants.

Cible runtime :
  - api_server.py
  - portfolio_construction_agent_jalon2.py
  - pplx_thesis_agent.py
  - pplx_memo_agent.py
  - pplx_crypto_agent.py
  - pplx_factor_agent.py
  - pplx_geo_agent.py
  - pplx_client.py
"""

from __future__ import annotations

import ast
import io
import py_compile
import sys
import time
import tokenize
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:
    pass

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

TARGETS = [
    "api_server.py",
    "portfolio_construction_agent_jalon2.py",
    "pplx_thesis_agent.py",
    "pplx_memo_agent.py",
    "pplx_crypto_agent.py",
    "pplx_factor_agent.py",
    "pplx_geo_agent.py",
    "pplx_client.py",
]

MARKER = "[DB_LOCK_FIX_V1]"


def read_text(p: Path) -> str:
    with open(p, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_text(p: Path, content: str) -> None:
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(content)


def find_connect_calls(src: str) -> list[dict]:
    """
    Retourne une liste de dicts pour chaque `sqlite3.connect(...)` :
        {
            "start": int,        # offset début de 'sqlite3'
            "end": int,          # offset fin de la parenthèse fermante
            "lhs": str | None,   # nom de variable assignée
            "indent": str,       # indentation de la ligne
            "line": int,         # numéro de ligne
        }
    Utilise tokenize pour gérer parenthèses imbriquées proprement.
    """
    results = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except tokenize.TokenizeError:
        return results

    # On cherche la séquence : NAME('sqlite3'), OP('.'), NAME('connect'), OP('(')
    for i in range(len(tokens) - 3):
        t0, t1, t2, t3 = tokens[i], tokens[i + 1], tokens[i + 2], tokens[i + 3]
        if (
            t0.type == tokenize.NAME and t0.string == "sqlite3"
            and t1.type == tokenize.OP and t1.string == "."
            and t2.type == tokenize.NAME and t2.string == "connect"
            and t3.type == tokenize.OP and t3.string == "("
        ):
            # Trouver la parenthèse fermante en respectant l'imbrication
            depth = 1
            j = i + 4
            close_token = None
            while j < len(tokens) and depth > 0:
                tk = tokens[j]
                if tk.type == tokenize.OP and tk.string == "(":
                    depth += 1
                elif tk.type == tokenize.OP and tk.string == ")":
                    depth -= 1
                    if depth == 0:
                        close_token = tk
                        break
                j += 1
            if close_token is None:
                continue

            # Identifier le LHS : remonter pour trouver NAME '=' avant sqlite3
            lhs = None
            # Chercher dans les ~6 tokens précédents : NAME OP('=')
            k = i - 1
            while k >= max(0, i - 8):
                tk = tokens[k]
                if tk.type == tokenize.OP and tk.string == "=" and k > 0:
                    prev = tokens[k - 1]
                    if prev.type == tokenize.NAME:
                        lhs = prev.string
                    break
                if tk.type in (tokenize.NEWLINE, tokenize.NL, tokenize.INDENT, tokenize.DEDENT):
                    break
                k -= 1

            # Indentation : depuis la ligne de t0
            line_idx = t0.start[0] - 1
            lines = src.splitlines(keepends=True)
            if line_idx < len(lines):
                line_text = lines[line_idx]
                indent = line_text[: len(line_text) - len(line_text.lstrip())]
            else:
                indent = ""

            # Offsets en caractères dans src
            # Calculer offset de fin via tokens[j].end
            end_line, end_col = close_token.end
            # Convertir (line, col) en offset absolu
            offset = 0
            for li, line in enumerate(lines, start=1):
                if li < end_line:
                    offset += len(line)
                elif li == end_line:
                    offset += end_col
                    break

            # Offset de début
            start_line, start_col = t0.start
            soff = 0
            for li, line in enumerate(lines, start=1):
                if li < start_line:
                    soff += len(line)
                elif li == start_line:
                    soff += start_col
                    break

            results.append({
                "start": soff,
                "end": offset,
                "lhs": lhs,
                "indent": indent,
                "line": start_line,
            })

    return results


def already_patched_near(src: str, end_idx: int) -> bool:
    return MARKER in src[end_idx : end_idx + 250]


def patch_file(path: Path) -> tuple[int, int, str | None, list]:
    if not path.exists():
        return (0, 0, "FILE_NOT_FOUND", [])

    try:
        src = read_text(path)
    except Exception as e:
        return (0, 0, f"READ_ERROR: {e}", [])

    calls = find_connect_calls(src)
    if not calls:
        return (0, 0, None, [])

    details = []
    new_src = src
    # Itérer en sens inverse pour préserver les offsets
    n_patched = 0
    for c in reversed(calls):
        end = c["end"]
        if already_patched_near(new_src, end):
            details.append((c["line"], c["lhs"], "ALREADY"))
            continue
        if not c["lhs"]:
            details.append((c["line"], None, "NO_LHS_SKIP"))
            continue

        indent = c["indent"]
        lhs = c["lhs"]

        injection = (
            f"\n{indent}# {MARKER} busy_timeout + WAL + synchronous=NORMAL\n"
            f"{indent}try:\n"
            f'{indent}    {lhs}.execute("PRAGMA journal_mode=WAL")\n'
            f'{indent}    {lhs}.execute("PRAGMA busy_timeout=10000")\n'
            f'{indent}    {lhs}.execute("PRAGMA synchronous=NORMAL")\n'
            f"{indent}except Exception:\n"
            f"{indent}    pass"
        )

        new_src = new_src[:end] + injection + new_src[end:]
        n_patched += 1
        details.append((c["line"], lhs, "PATCHED"))

    if n_patched == 0:
        return (len(calls), 0, None, details)

    # Validation AST
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        return (len(calls), 0, f"AST_FAIL: {e}", details)

    # Backup
    ts = time.strftime("%Y%m%d%H%M%S")
    backup = path.with_suffix(path.suffix + f".bak.{ts}")
    try:
        backup.write_text(src, encoding="utf-8")
    except Exception as e:
        return (len(calls), 0, f"BACKUP_ERROR: {e}", details)

    # Write
    try:
        write_text(path, new_src)
    except Exception as e:
        return (len(calls), 0, f"WRITE_ERROR: {e}", details)

    # py_compile
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as e:
        write_text(path, src)
        return (len(calls), 0, f"PYCOMPILE_FAIL: {e}", details)

    return (len(calls), n_patched, None, details)


def coverage_report(path: Path) -> tuple[int, int, int]:
    if not path.exists():
        return (0, 0, 0)
    try:
        src = read_text(path)
    except Exception:
        return (0, 0, 0)
    n_connects = src.count("sqlite3.connect(")
    n_bt = src.count("busy_timeout=10000")
    n_marker = src.count(MARKER)
    return (n_connects, n_bt, n_marker)


def main() -> int:
    print("=" * 70)
    print("nextones-fix-db-locks-v3-runtime — regex robuste + cibles runtime")
    print("=" * 70)
    print(f"ROOT = {ROOT}")
    print()

    for fname in TARGETS:
        p = ROOT / fname
        n_calls, n_patched, err, details = patch_file(p)
        status = "OK" if err is None else f"ERR ({err})"
        print(f"  {fname:45s}  calls={n_calls:2d}  patched={n_patched:2d}  {status}")
        for line, lhs, action in details:
            lhs_s = lhs or "(no-lhs)"
            print(f"      L{line:5d}  lhs={lhs_s:20s}  {action}")

    print()
    print("=" * 70)
    print("Couverture finale")
    print("=" * 70)
    print(f"  {'fichier':45s}  {'conn':>4s}  {'bt':>4s}  {'mark':>4s}  cov")
    print(f"  {'-'*45}  {'-'*4}  {'-'*4}  {'-'*4}  ---")
    ok = 0
    total = 0
    for fname in TARGETS:
        p = ROOT / fname
        n_conn, n_bt, n_marker = coverage_report(p)
        if n_conn == 0:
            mark = "-"
        else:
            total += 1
            if n_bt >= n_conn:
                mark = "OK"
                ok += 1
            else:
                mark = "KO"
        print(f"  {fname:45s}  {n_conn:4d}  {n_bt:4d}  {n_marker:4d}  {mark:>3s}")

    print()
    print(f"Couverture finale : {ok}/{total} fichiers OK")
    print()
    print("Étapes suivantes :")
    print("  1. Stop uvicorn :")
    print("     Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |")
    print("       Select-Object OwningProcess |")
    print("       ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }")
    print("  2. Restart : py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print("  3. Observer logs : [CRYPTO-AGENT] Done sans 'database is locked'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
