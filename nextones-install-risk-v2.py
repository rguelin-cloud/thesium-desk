"""
nextones-install-risk-v2.py
[RISK_V2] installer - schema-aware NEXTONES.

Roles :
  1. Backup horodate de risk_engine.py + execution_engine.py + risk_pretrade.py (precedent)
  2. Remplace risk_pretrade.py par la v2 (alignee schema NEXTONES)
  3. Met a jour le hook dans execution_engine.py (marker [RISK_V2])
  4. Valide les markers

Source du module : risk_pretrade_v2.py (dans le meme dossier que ce script)
Cible           : C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\risk_pretrade.py

Usage :
  py -3.13 nextones-install-risk-v2.py

ASCII only.
"""
from __future__ import annotations

import shutil
import sys
import datetime as _dt
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
TS = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / f"_backups_risk_v2_{TS}"

TARGETS_BACKUP = [
    "risk_pretrade.py",   # v1 a archiver
    "risk_engine.py",
    "execution_engine.py",
]

HOOK_V2 = '''

# [RISK_V2] Hook pre-trade - Concentration / VaR marginal / Correlation (schema-aware)
try:
    from risk_pretrade import run_pretrade_checks as _risk_v2_run
    _RISK_V2_AVAILABLE = True
except Exception as _e:
    _RISK_V2_AVAILABLE = False

def risk_v2_gate(ticker, qty, price, side, db_path=None):
    """
    [RISK_V2] Garde pre-trade. Renvoie (allowed, reason, details).
    A appeler immediatement avant l'insertion d'un ordre dans la table orders.
    """
    if not _RISK_V2_AVAILABLE:
        return True, "risk_v2_unavailable", {}
    try:
        res = _risk_v2_run(ticker, qty, price, side, db_path=db_path)
        return bool(res.get("passed")), res.get("blocked_by"), res.get("details", {})
    except Exception as _e:
        return True, "risk_v2_error:" + str(_e)[:80], {}
'''


def info(m): print(f"[INFO] {m}")
def ok(m): print(f"[OK]   {m}")
def warn(m): print(f"[WARN] {m}")
def fatal(m):
    print(f"[FATAL] {m}")
    sys.exit(1)


def read_utf8(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig")


def write_utf8(p: Path, content: str) -> None:
    p.write_text(content, encoding="utf-8", newline="\n")


def step_backup():
    BACKUP.mkdir(parents=True, exist_ok=True)
    for fname in TARGETS_BACKUP:
        src = ROOT / fname
        if src.exists():
            shutil.copy2(src, BACKUP / fname)
            ok(f"backup : {fname}")
        else:
            warn(f"absent (skip backup) : {fname}")
    info(f"dossier backup : {BACKUP}")


def step_install_module():
    here = Path(__file__).resolve().parent
    src = here / "risk_pretrade_v2.py"
    dst = ROOT / "risk_pretrade.py"

    if not src.exists():
        fatal("risk_pretrade_v2.py introuvable dans le meme dossier que ce script.")

    shutil.copy2(src, dst)
    ok(f"risk_pretrade.py (v2) installe a la racine : {dst}")


def step_hook_execution_engine():
    p = ROOT / "execution_engine.py"
    if not p.exists():
        warn("execution_engine.py absent - hook non ajoute.")
        return

    src = read_utf8(p)
    if "[RISK_V2]" in src:
        info("hook [RISK_V2] deja present dans execution_engine.py - skip.")
        return

    new_src = src.rstrip() + "\n" + HOOK_V2
    write_utf8(p, new_src)
    ok("hook [RISK_V2] ajoute a execution_engine.py")


def step_validate():
    p = ROOT / "risk_pretrade.py"
    if not p.exists():
        fatal("risk_pretrade.py absent apres install.")
    src = read_utf8(p)
    c1 = src.count("[RISK_V2]")
    ok(f"[RISK_V2] markers dans risk_pretrade.py : {c1}")

    exec_p = ROOT / "execution_engine.py"
    if exec_p.exists():
        src2 = read_utf8(exec_p)
        c2 = src2.count("[RISK_V2]")
        ok(f"[RISK_V2] markers dans execution_engine.py : {c2}")
        c1_old = src2.count("[RISK_V1]")
        if c1_old:
            info(f"[RISK_V1] toujours present dans execution_engine.py : {c1_old} (coexistence non bloquante)")


def step_summary():
    print("")
    print("=" * 60)
    print(" [RISK_V2] install termine - schema-aware NEXTONES")
    print("=" * 60)
    print("")
    print("Smoke test (NVDA 86j de prix disponibles) :")
    print(f"  cd {ROOT}")
    print("  py -3.13 risk_pretrade.py NVDA 10 900 BUY")
    print("  py -3.13 risk_pretrade.py BTC 0.5 60000 BUY")
    print("  py -3.13 risk_pretrade.py ETH 1 3000 SELL")
    print("")
    print("Inspection du log :")
    print("  py -3.13 -c \"import sqlite3,json; "
          "c=sqlite3.connect(r'C:\\\\Users\\\\RichardGUELIN\\\\Prod\\\\ThesiumDesk\\\\thesium.db'); "
          "c.row_factory=sqlite3.Row; "
          "[print(json.dumps(dict(r),indent=2,ensure_ascii=False)) "
          "for r in c.execute('SELECT * FROM risk_pretrade_log ORDER BY id DESC LIMIT 3').fetchall()]\"")
    print("")


def main():
    if not ROOT.exists():
        fatal(f"ROOT introuvable : {ROOT}")
    print("=" * 60)
    print(" [RISK_V2] installer - schema-aware NEXTONES")
    print("=" * 60)
    step_backup()
    step_install_module()
    step_hook_execution_engine()
    step_validate()
    step_summary()


if __name__ == "__main__":
    main()
