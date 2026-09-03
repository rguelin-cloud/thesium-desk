# -*- coding: utf-8 -*-
# [FIX_JALON4_IMPORTS_V1]
"""
NEXTONES - Jalon 4 - Scheduler mensuel UniverseExpansionAgent
Marker: [SCHED_UNIVERSE_V1]

Ajoute un job APScheduler dans scheduler.py qui declenche un scan
mensuel le 1er du mois a 22:00 CEST (20:00 UTC).

Idempotent : detecte le marker et ne reinsere pas.
Backup automatique avant patch.

Usage:
    py -3.13 nextones-scheduler-universe-monthly.py
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

SCHED_PATH = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\scheduler.py")
MARKER_BEGIN = "# >>> [SCHED_UNIVERSE_V1] BEGIN <<<"
MARKER_END = "# >>> [SCHED_UNIVERSE_V1] END <<<"

BLOCK = '''
# >>> [SCHED_UNIVERSE_V1] BEGIN <<<
# Jalon 4 - Universe Expansion mensuelle (1er du mois 22h CEST / 20h UTC)
try:
    from universe_expansion_agent import run_scan as _universe_scan

    def _job_universe_expansion():
        import logging
        log = logging.getLogger("scheduler")
        try:
            result = _universe_scan(top_n=5, dry_run=False)
            log.info("[SCHED_UNIVERSE_V1] result: %s", result)
        except Exception as exc:
            log.exception("[SCHED_UNIVERSE_V1] failed: %s", exc)

    scheduler.add_job(
        _job_universe_expansion,
        trigger="cron",
        day=1,
        hour=20,
        minute=0,
        timezone="UTC",
        id="universe_expansion_monthly",
        replace_existing=True,
        misfire_grace_time=3600,
    )
except Exception as _exc:
    import logging
    logging.getLogger("scheduler").warning(
        "[SCHED_UNIVERSE_V1] not loaded: %s", _exc
    )
# >>> [SCHED_UNIVERSE_V1] END <<<
'''


def main():
    if not SCHED_PATH.exists():
        print(f"ERROR: scheduler.py introuvable - {SCHED_PATH}")
        sys.exit(1)

    src = SCHED_PATH.read_text(encoding="utf-8-sig")
    if MARKER_BEGIN in src:
        print("[SKIP] Marker [SCHED_UNIVERSE_V1] deja present.")
        return

    bak = SCHED_PATH.with_suffix(
        SCHED_PATH.suffix + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}-jalon4"
    )
    shutil.copy2(SCHED_PATH, bak)
    print(f"[BACKUP] {bak}")

    new_src = src.rstrip() + "\n\n" + BLOCK.strip() + "\n"
    SCHED_PATH.write_text(new_src, encoding="utf-8")

    n_begin = new_src.count(MARKER_BEGIN)
    n_end = new_src.count(MARKER_END)
    print(f"[OK] Patch applique. Markers BEGIN={n_begin} END={n_end}")
    if n_begin != 1 or n_end != 1:
        print("[ERR] Compte de markers inattendu.")
        sys.exit(2)
    print("[NEXT] Redemarre uvicorn pour activer le job mensuel.")


if __name__ == "__main__":
    main()
