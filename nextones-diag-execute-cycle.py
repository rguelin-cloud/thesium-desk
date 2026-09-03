# -*- coding: utf-8 -*-
"""
[DIAG_EXECUTE_CYCLE_V1]
Localise le handler POST /api/orders/execute-cycle, affiche son code et
identifie les sous-fonctions qu'il appelle apres run_all_agents (la phase
qui plante d'apres les logs).

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-diag-execute-cycle.py
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def section(t: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {t}")
    print("=" * 70)


def find_handler_in_files(route_path: str):
    """Cherche le decorateur correspondant a route_path dans tous les .py."""
    pat = re.compile(
        r'@(?:app|router)\.(get|post|put|delete|patch)\(\s*[\'"]'
        + re.escape(route_path)
        + r'[\'"]',
        re.IGNORECASE,
    )
    for py in sorted(ROOT.glob("*.py")):
        try:
            src = py.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        m = pat.search(src)
        if m:
            return py, src, m.start()
    return None, None, None


def show_handler(route_path: str, max_lines: int = 120) -> None:
    py, src, pos = find_handler_in_files(route_path)
    if py is None:
        print(f"[FAIL] Handler pour {route_path} introuvable.")
        return
    line_no = src[:pos].count("\n") + 1
    print(f"[OK] {route_path} trouve dans {py.name} L{line_no}")
    print()

    lines = src.splitlines()
    end_line = min(line_no - 1 + max_lines, len(lines))
    for i in range(line_no - 1, end_line):
        print(f"{i+1:5d}  {lines[i]}")


def find_function_def(name: str, py: Path) -> tuple[int, list[str]] | None:
    """Trouve 'def <name>(' dans le fichier py et renvoie (ligne, body)."""
    src = py.read_text(encoding="utf-8", errors="replace")
    pat = re.compile(rf"^\s*(?:async\s+)?def\s+{re.escape(name)}\s*\(", re.MULTILINE)
    m = pat.search(src)
    if not m:
        return None
    line_no = src[:m.start()].count("\n") + 1
    lines = src.splitlines()
    # extraire 100 lignes
    body = lines[line_no-1 : min(line_no-1+100, len(lines))]
    return line_no, body


def find_function_anywhere(name: str):
    """Cherche def <name>( dans tous les .py."""
    for py in sorted(ROOT.glob("*.py")):
        r = find_function_def(name, py)
        if r:
            return py, r[0], r[1]
    return None, None, None


def main() -> int:
    section("1) Handler POST /api/orders/execute-cycle (code source)")
    show_handler("/api/orders/execute-cycle", max_lines=120)

    section("2) Recherche de la fonction 'execute_cycle' / 'reconcile_orders'")
    for fn in ["execute_cycle", "reconcile_orders", "reconcile", "place_orders",
               "place_pending_orders", "run_execution_cycle", "run_decision_cycle",
               "run_reconciler", "build_targets", "promote_targets"]:
        py, line, body = find_function_anywhere(fn)
        if py:
            print(f"\n>>> def {fn}(...)  =>  {py.name} L{line}")
            for i, ln in enumerate(body[:30], start=line):
                print(f"  {i:5d}  {ln}")

    section("3) try/except qui masquent peut-etre la stack")
    api = ROOT / "api_server_with_static.py"
    src = api.read_text(encoding="utf-8", errors="replace")
    # Cherche les except sans logging.exception
    for m in re.finditer(r"except\s+Exception[^\n]*:\s*\n", src):
        line_no = src[:m.start()].count("\n") + 1
        # 5 lignes apres
        after = src[m.end() : m.end() + 400].splitlines()[:8]
        if not any("traceback" in ln or "logger" in ln or "exception(" in ln for ln in after):
            snippet = "\n      ".join(after[:6])
            print(f"  L{line_no}  except Exception silencieux ?")
            print(f"      {snippet}")
            print()

    section("FIN")
    print("Envoie:")
    print("  - section 1 (code du handler execute-cycle)")
    print("  - section 2 (fonction reconcile_orders / execute_cycle)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
