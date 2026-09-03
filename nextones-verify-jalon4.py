# -*- coding: utf-8 -*-
# [FIX_JALON4_IMPORTS_V1]
"""
NEXTONES - Jalon 4 - Verification deploiement
Marker: [VERIFY_JALON4_V1]

Verifie que les 4 sous-composants Jalon 4 sont en place :
  1. Table universe_candidates dans la DB
  2. Module universe_expansion_agent.py importable
  3. Markers [API_UNIVERSE_V1] dans api_server_with_static.py
  4. Markers [SCHED_UNIVERSE_V1] dans scheduler.py
  5. Markers [UI_UNIVERSE_V1] dans static/index.html

Usage:
    py -3.13 nextones-verify-jalon4.py
"""
from __future__ import annotations

import sqlite3
import sys
import importlib
from pathlib import Path

DB_PATH = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
API_PATH = ROOT / "api_server_with_static.py"
SCHED_PATH = ROOT / "scheduler.py"
HTML_PATH = ROOT / "static" / "index.html"
AGENT_PATH = ROOT / "agents" / "universe_expansion_agent.py"

RESULTS = []


def check(name: str, ok: bool, detail: str = ""):
    status = "OK " if ok else "FAIL"
    RESULTS.append((name, ok, detail))
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""))


def main():
    print("=== [VERIFY_JALON4_V1] ===\n")

    # 1) DB table
    print("1. DB - table universe_candidates")
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='universe_candidates';"
        )
        exists = cur.fetchone() is not None
        check("table_exists", exists)
        if exists:
            cur = conn.execute("PRAGMA table_info(universe_candidates);")
            cols = [r[1] for r in cur.fetchall()]
            need = ["id", "ticker", "asset_class", "score", "status", "rationale", "proposed_at", "scan_batch"]
            missing = [c for c in need if c not in cols]
            check("required_columns_present", not missing,
                  f"{len(cols)} colonnes" + (f", missing={missing}" if missing else ""))
            cur = conn.execute("SELECT COUNT(*) FROM universe_candidates;")
            n = cur.fetchone()[0]
            check("count_query_runs", True, f"{n} candidats actuels")
        conn.close()
    except Exception as exc:
        check("table_exists", False, str(exc))

    # 2) Agent module
    print("\n2. Agent - universe_expansion_agent.py")
    check("file_exists", AGENT_PATH.exists(), str(AGENT_PATH))
    if AGENT_PATH.exists():
        sys.path.insert(0, str(ROOT))
        try:
            mod = importlib.import_module("universe_expansion_agent")
            check("module_importable", True, f"marker={getattr(mod, 'MARKER', '?')}")
            for fn in ("run_scan", "approve_candidate", "reject_candidate"):
                check(f"function_{fn}", hasattr(mod, fn))
        except Exception as exc:
            check("module_importable", False, str(exc))

    # 3) API markers
    print("\n3. API - api_server_with_static.py markers")
    if API_PATH.exists():
        src = API_PATH.read_text(encoding="utf-8-sig")
        check("API_UNIVERSE_V1_BEGIN", "[API_UNIVERSE_V1] BEGIN" in src)
        check("API_UNIVERSE_V1_END", "[API_UNIVERSE_V1] END" in src)
        for ep in [
            "/api/universe/candidates",
            "/api/universe/scan",
            "approve_universe_candidate",
            "reject_universe_candidate",
        ]:
            check(f"endpoint_{ep}", ep in src)
    else:
        check("api_path_exists", False, str(API_PATH))

    # 4) Scheduler markers
    print("\n4. Scheduler - scheduler.py markers")
    if SCHED_PATH.exists():
        src = SCHED_PATH.read_text(encoding="utf-8-sig")
        check("SCHED_UNIVERSE_V1_BEGIN", "[SCHED_UNIVERSE_V1] BEGIN" in src)
        check("SCHED_UNIVERSE_V1_END", "[SCHED_UNIVERSE_V1] END" in src)
        check("job_id_present", 'id="universe_expansion_monthly"' in src or "'universe_expansion_monthly'" in src)
    else:
        check("scheduler_path_exists", False, str(SCHED_PATH))

    # 5) UI markers
    print("\n5. UI - static/index.html markers")
    if HTML_PATH.exists():
        src = HTML_PATH.read_text(encoding="utf-8-sig")
        check("UI_UNIVERSE_V1_BEGIN", "[UI_UNIVERSE_V1] BEGIN" in src)
        check("UI_UNIVERSE_V1_END", "[UI_UNIVERSE_V1] END" in src)
        check("card_div_present", 'id="univ-candidates-card"' in src)
        check("script_loaded_flag", "__univ_v1_loaded" in src)
    else:
        check("html_path_exists", False, str(HTML_PATH))

    # Summary
    n_total = len(RESULTS)
    n_ok = sum(1 for _, ok, _ in RESULTS if ok)
    n_fail = n_total - n_ok
    print(f"\n=== Summary ===")
    print(f"  OK    : {n_ok}")
    print(f"  FAIL  : {n_fail}")
    print(f"  Total : {n_total}")

    if n_fail > 0:
        print("\nFAILED checks:")
        for name, ok, detail in RESULTS:
            if not ok:
                print(f"  - {name}: {detail}")
        sys.exit(1)

    print("\n[VERIFY_JALON4_V1] ALL PASS")


if __name__ == "__main__":
    main()
