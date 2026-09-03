# -*- coding: utf-8 -*-
"""
[SCHED_UNIVERSE_V2]
Ajoute le job mensuel UniverseExpansion dans le bon fichier.
Auto-detect : fichier qui contient 'BackgroundScheduler()' ou 'scheduler.add_job'.

Idempotent (marker [SCHED_UNIVERSE_V2_BEGIN]/_END).
Backup auto.

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-scheduler-universe-monthly-v2.py
"""
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

MARK_BEGIN = "# [SCHED_UNIVERSE_V2_BEGIN]"
MARK_END   = "# [SCHED_UNIVERSE_V2_END]"


def find_scheduler_file() -> Path | None:
    for py in ROOT.glob("*.py"):
        try:
            txt = py.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if re.search(r"BackgroundScheduler\(\)|scheduler\.add_job\(|scheduler\.start\(\)", txt):
            return py
    return None


JOB_BLOCK = '''
{MARK_BEGIN}
# Universe Expansion v1 - Job mensuel (Jalon 4)
def _universe_expansion_monthly_job():
    try:
        from universe_expansion_agent import run_scan
        print("[SCHED] universe_expansion_monthly: starting...")
        res = run_scan(top_n=5, dry_run=False)
        print(f"[SCHED] universe_expansion_monthly: done -> {{res}}")
    except Exception as _e:
        import traceback; traceback.print_exc()
        print(f"[SCHED] universe_expansion_monthly FAILED: {{_e}}")

try:
    scheduler.add_job(
        _universe_expansion_monthly_job,
        trigger="cron",
        day=1, hour=20, minute=0, timezone="UTC",
        id="universe_expansion_monthly",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    print("[SCHED] universe_expansion_monthly job registered (cron 0 20 1 * * UTC)")
except Exception as _e:
    print(f"[SCHED] failed to register universe_expansion_monthly: {{_e}}")
{MARK_END}
'''.format(MARK_BEGIN=MARK_BEGIN, MARK_END=MARK_END)


def main() -> int:
    target = find_scheduler_file()
    if not target:
        print("[FAIL] aucun fichier ne contient BackgroundScheduler / scheduler.add_job.")
        return 1
    print(f"[INFO] Cible: {target.name}")

    txt = target.read_text(encoding="utf-8-sig", errors="replace")

    if MARK_BEGIN in txt:
        start = txt.index(MARK_BEGIN)
        if MARK_END in txt[start:]:
            end_idx = txt.index(MARK_END, start) + len(MARK_END)
            txt = txt[:start] + JOB_BLOCK.strip() + txt[end_idx:]
            print("[INFO] bloc existant remplace.")
        else:
            print("[WARN] MARK_END manquant, append.")
            txt = txt.rstrip() + "\n\n" + JOB_BLOCK
    else:
        # Trouver la ligne 'scheduler.start()' et inserer JUSTE AVANT
        m = re.search(r"^([ \t]*)scheduler\.start\(\)", txt, re.MULTILINE)
        if m:
            indent = m.group(1)
            insert_pos = m.start()
            # indenter le bloc
            block_indented = "\n".join(indent + ln for ln in JOB_BLOCK.splitlines() if ln) + "\n"
            txt = txt[:insert_pos] + block_indented + "\n" + txt[insert_pos:]
            print(f"[INFO] insertion AVANT scheduler.start() (indent={len(indent)}).")
        else:
            print("[WARN] scheduler.start() introuvable, append a la fin du fichier.")
            txt = txt.rstrip() + "\n\n" + JOB_BLOCK

    # Backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = target.with_suffix(f".py.bak-{ts}-jalon4-sched-v2")
    shutil.copy2(target, bak)
    print(f"[BACKUP] {bak.name}")

    target.write_text(txt, encoding="utf-8")
    print(f"[OK] {target.name} patche.")

    import py_compile
    try:
        py_compile.compile(str(target), doraise=True)
        print(f"[OK] compile sans erreur.")
    except py_compile.PyCompileError as e:
        print(f"[FAIL] erreur de syntaxe : {e}")
        print(f"[ACTION] restaure depuis {bak.name}")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
