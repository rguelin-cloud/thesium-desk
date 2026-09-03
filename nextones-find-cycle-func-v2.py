# -*- coding: utf-8 -*-
"""
[FIND_CYCLE_FUNC_V2]
Localise la vraie route /api/... qui declenche le cycle multi-agents
et execute agents.run_all_agents en local pour capter la stack du 500.

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-find-cycle-func-v2.py
"""
import os
import re
import sys
import sqlite3
import traceback
import inspect
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def section(t: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {t}")
    print("=" * 70)


# ---------------------------------------------------------------------------
# 1) Lister toutes les routes du fichier api_server_with_static.py
# ---------------------------------------------------------------------------
def list_all_routes() -> list[tuple[str, str, int]]:
    src = (ROOT / "api_server_with_static.py").read_text(encoding="utf-8", errors="replace")
    pat = re.compile(r'@app\.(get|post|put|delete)\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
    routes = []
    for m in pat.finditer(src):
        method = m.group(1).upper()
        path = m.group(2)
        line_no = src[:m.start()].count("\n") + 1
        routes.append((method, path, line_no))
    return routes


# ---------------------------------------------------------------------------
# 2) Trouver les routes qui appellent run_all_agents / cycle / agents
# ---------------------------------------------------------------------------
def find_cycle_routes() -> list[tuple[str, str, int, str]]:
    """Retourne (method, path, line, snippet) pour les handlers qui parlent
    de run_all_agents / decision / cycle / agents."""
    src = (ROOT / "api_server_with_static.py").read_text(encoding="utf-8", errors="replace")
    pat = re.compile(r'@app\.(get|post|put|delete)\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
    hits = []
    matches = list(pat.finditer(src))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else min(start + 3000, len(src))
        body = src[start:end]
        if re.search(r"run_all_agents|run_decision_cycle|run_cycle|run-agents|cycle\(", body):
            method = m.group(1).upper()
            path = m.group(2)
            line_no = src[:start].count("\n") + 1
            snippet = "\n".join(body.splitlines()[:40])
            hits.append((method, path, line_no, snippet))
    return hits


# ---------------------------------------------------------------------------
# 3) Executer agents.run_all_agents (et variantes) en local
# ---------------------------------------------------------------------------
def run_inproc() -> None:
    try:
        import agents
    except Exception:
        print("[FAIL] import agents impossible:")
        traceback.print_exc()
        return

    target = getattr(agents, "run_all_agents", None)
    if not callable(target):
        print("[FAIL] agents.run_all_agents introuvable.")
        # Liste tout ce qui ressemble
        cands = [n for n in dir(agents) if "agent" in n.lower() or "cycle" in n.lower() or n.startswith("run_")]
        print(f"Candidats dans agents.*: {cands}")
        return

    sig = inspect.signature(target)
    print(f"[OK] agents.run_all_agents{sig}")
    print(f"Doc: {(target.__doc__ or '').strip()[:300]}")

    # Strategies d'appel
    attempts = []
    params = list(sig.parameters.values())

    # 1) sans arg
    attempts.append(("()", lambda: target()))
    # 2) avec user_id=1
    if any(p.name in ("user_id", "uid") for p in params):
        attempts.append(("(user_id=1)", lambda: target(user_id=1)))
    # 3) avec db connection
    if any(p.name in ("conn", "db", "connection") for p in params):
        def with_conn():
            conn = sqlite3.connect(str(ROOT / "thesium.db"))
            return target(conn)
        attempts.append(("(conn)", with_conn))

    for label, call in attempts:
        print(f"\n>>> Essai run_all_agents{label}")
        try:
            res = call()
            print(f"[OK] retour: {type(res).__name__}")
            if isinstance(res, dict):
                for k, v in list(res.items())[:20]:
                    s = str(v)
                    if len(s) > 200:
                        s = s[:200] + "..."
                    print(f"  {k}: {s}")
            return  # succes -> stop
        except Exception:
            print("[STACK]")
            traceback.print_exc()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main() -> int:
    section("1) Toutes les routes definies")
    routes = list_all_routes()
    print(f"Total: {len(routes)} routes")
    for method, path, line in routes:
        if any(k in path.lower() for k in ("agent", "cycle", "construction", "run", "execute")):
            print(f"  L{line:5d}  {method:6s} {path}")

    section("2) Routes qui declenchent run_all_agents / cycle")
    hits = find_cycle_routes()
    for method, path, line, snippet in hits:
        print(f"\n>>> L{line}  {method} {path}")
        for ln in snippet.splitlines()[:35]:
            print(f"     {ln}")

    section("3) Execution de agents.run_all_agents EN LOCAL")
    run_inproc()

    section("FIN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
