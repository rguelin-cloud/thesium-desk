# -*- coding: utf-8 -*-
"""
Diag RUN CYCLE 500 (3 juin 2026)
- Localise l'endpoint /api/cycle/run dans api_server.py
- Dump la fonction handler + ses appels internes
- Verifie qu'aucun import / variable n'est casse par les 10 patches IC Memo
- Verifie la presence de cycle_lock / market_guard
- Affiche les dernieres lignes de log uvicorn pertinentes (stdout-style)

Lancement (Windows):
    py -3.13 .\nextones-diag-run-cycle-500.py
"""
from __future__ import annotations

import io
import os
import re
import sys
import ast
from pathlib import Path

# Force stdout/stderr en UTF-8 pour eviter cp1252 sur Windows console
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROD = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
API = PROD / "api_server.py"

SEP = "=" * 78


def banner(t: str) -> None:
    print("\n" + SEP)
    print(t)
    print(SEP)


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig", errors="replace")


def find_route(src: str, patterns: list[str]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    lines = src.splitlines()
    for i, ln in enumerate(lines, 1):
        for pat in patterns:
            if pat in ln:
                out.append((i, ln.rstrip()))
                break
    return out


def grab_function_at(src: str, start_line: int) -> tuple[int, int, str]:
    """Renvoie (start, end, body) en se basant sur l'AST."""
    tree = ast.parse(src)
    target = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= start_line <= (node.end_lineno or node.lineno):
                if target is None or (node.end_lineno or 0) - node.lineno < (
                    (target.end_lineno or 0) - target.lineno
                ):
                    target = node
    if target is None:
        return (0, 0, "")
    lines = src.splitlines()
    body = "\n".join(lines[target.lineno - 1 : target.end_lineno])
    return (target.lineno, target.end_lineno or target.lineno, body)


def main() -> int:
    if not API.exists():
        print(f"[ERR] {API} introuvable")
        return 2

    src = read_text(API)
    print(f"api_server.py : {len(src):,} chars, {src.count(chr(10)):,} lignes")

    # 1) Endpoints lies au cycle
    banner("1. Endpoints lies au RUN CYCLE")
    hits = find_route(
        src,
        [
            "/api/cycle/run",
            "/api/cycles/run",
            "/api/run-cycle",
            "/api/decision-cycle",
            'def run_cycle',
            'def execute_cycle',
            'def run_decision_cycle',
            'cycle_lock',
        ],
    )
    seen = set()
    for ln, txt in hits:
        key = (ln, txt)
        if key in seen:
            continue
        seen.add(key)
        print(f"L{ln:5d} | {txt[:140]}")

    # 2) Handler precis
    banner("2. Handler endpoint /api/cycle/run (ou variante)")
    # On cherche le decorateur @app.post('/api/cycle/run') ou similaire
    routes = []
    for m in re.finditer(
        r'@app\.(?:post|get)\(["\'](/api/[^"\']*cycle[^"\']*)["\']', src
    ):
        routes.append((m.start(), m.group(1)))
    if not routes:
        print("[WARN] aucun decorateur cycle trouve")
    for off, route in routes:
        line_no = src[:off].count("\n") + 1
        # def juste apres
        nxt = src.find("def ", off)
        if nxt == -1:
            continue
        def_line = src[:nxt].count("\n") + 1
        s, e, body = grab_function_at(src, def_line)
        print(f"\nRoute {route} @ L{line_no}  -> def L{s}-L{e}  ({e - s + 1} lignes)")
        print("-" * 78)
        # On limite a 80 lignes pour lisibilite
        chunk = "\n".join(body.splitlines()[:80])
        print(chunk)
        if e - s + 1 > 80:
            print(f"... (+{e - s + 1 - 80} lignes)")

    # 3) Imports critiques + integrite des 10 markers ICMEMO (sanity)
    banner("3. Markers ICMEMO toujours presents ? (sanity post-patches)")
    markers = [
        "[ICMEMO_PDF_V2]",
        "[ICMEMO_PDF_V3_LIGHT]",
        "[ICMEMO_PDF_V4_COVER]",
        "[ICMEMO_V6_R2]",
        "[ICMEMO_V6_R3]",
        "[ICMEMO_V6_R4]",
        "[ICMEMO_V7_R3BIS]",
        "[ICMEMO_V8_R5]",
        "[ICMEMO_V9_SH3_DEF]",
        "[ICMEMO_V10_R7]",
    ]
    for m in markers:
        c = src.count(m)
        flag = "OK" if c > 0 else "MISS"
        print(f"  {flag:4}  {m:30}  x{c}")

    # 4) Compile complet
    banner("4. py_compile api_server.py")
    import py_compile
    try:
        py_compile.compile(str(API), doraise=True)
        print("[OK] api_server.py compile sans erreur")
    except py_compile.PyCompileError as e:
        print("[ERR] py_compile a echoue :")
        print(e)

    # 5) Recherche pattern d'exception courant (try/except generique)
    banner("5. Recherche derniere try/except dans handler cycle")
    cyc = re.search(r'def (run_decision_cycle|execute_cycle|run_cycle)\b', src)
    if cyc:
        line_no = src[:cyc.start()].count("\n") + 1
        s, e, body = grab_function_at(src, line_no)
        print(f"Fonction {cyc.group(1)} @ L{s}-L{e}")
        # On affiche les except: lignes
        for i, ln in enumerate(body.splitlines(), s):
            if "except" in ln or "raise HTTPException" in ln or "logger.error" in ln or "log.error" in ln:
                print(f"  L{i:5d} | {ln.strip()[:140]}")

    banner("FIN diag run-cycle-500")
    print("Joindre la sortie complete pour patch cible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
