"""
nextones-install-risk-v1.py
[RISK_V1] installer - cible Windows / py 3.13
Roles :
  1. Backup ciblee de risk_engine.py / execution_engine.py / agents.py / api_server_with_static.py
  2. Copie risk_pretrade.py a la racine (s'il a ete telecharge dans le meme dossier que ce script)
  3. Ajoute un hook idempotent risk_v1_gate() a execution_engine.py
  4. Valide (count tags) et imprime le smoke test a lancer

Usage :
  py -3.13 nextones-install-risk-v1.py

ASCII only - aucun caractere accentue dans le source.
"""
from __future__ import annotations

import os
import shutil
import sys
import datetime as _dt
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
TS = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / f"_backups_risk_v1_{TS}"

TARGETS = [
    "risk_engine.py",
    "execution_engine.py",
    "agents.py",
    "api_server_with_static.py",
]

HOOK = '''

# [RISK_V1] Hook pre-trade - Concentration / VaR marginal / Correlation
try:
    from risk_pretrade import run_pretrade_checks as _risk_v1_run
    _RISK_V1_AVAILABLE = True
except Exception as _e:
    _RISK_V1_AVAILABLE = False

def risk_v1_gate(symbol, qty, price, side, db_path=None):
    """
    [RISK_V1] Garde pre-trade. Renvoie (allowed: bool, reason: str|None, details: dict).
    A appeler immediatement avant l'insertion d'un ordre dans la table orders.
    """
    if not _RISK_V1_AVAILABLE:
        return True, "risk_v1_unavailable", {}
    try:
        res = _risk_v1_run(symbol, qty, price, side, db_path=db_path)
        return bool(res.get("passed")), res.get("blocked_by"), res.get("details", {})
    except Exception as _e:
        return True, "risk_v1_error:" + str(_e)[:80], {}
'''


def info(msg: str) -> None:
    print(f"[INFO] {msg}")


def ok(msg: str) -> None:
    print(f"[OK]   {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def fatal(msg: str) -> None:
    print(f"[FATAL] {msg}")
    sys.exit(1)


def read_utf8(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig")


def write_utf8(p: Path, content: str) -> None:
    p.write_text(content, encoding="utf-8", newline="\n")


def step_backup() -> None:
    BACKUP.mkdir(parents=True, exist_ok=True)
    for fname in TARGETS:
        src = ROOT / fname
        if src.exists():
            shutil.copy2(src, BACKUP / fname)
            ok(f"backup : {fname}")
        else:
            warn(f"absent : {fname}")
    info(f"dossier backup : {BACKUP}")


def step_copy_risk_pretrade() -> None:
    """Cherche risk_pretrade.py dans le dossier du script et le copie a la racine."""
    here = Path(__file__).resolve().parent
    src = here / "risk_pretrade.py"
    dst = ROOT / "risk_pretrade.py"

    if not src.exists():
        # fallback : peut-etre deja en place
        if dst.exists():
            warn("risk_pretrade.py absent dans dossier script mais deja present a la racine.")
            return
        fatal("risk_pretrade.py introuvable - place-le dans le meme dossier que ce script.")

    # Idempotence : si deja present avec marker, on remplace quand meme (refresh)
    shutil.copy2(src, dst)
    ok(f"risk_pretrade.py copie vers {dst}")


def step_hook_execution_engine() -> None:
    p = ROOT / "execution_engine.py"
    if not p.exists():
        warn("execution_engine.py absent - module installe mais non cable.")
        return

    src = read_utf8(p)
    if "[RISK_V1]" in src:
        info("hook [RISK_V1] deja present dans execution_engine.py - skip.")
        return

    new_src = src.rstrip() + "\n" + HOOK
    write_utf8(p, new_src)
    ok("hook [RISK_V1] ajoute a execution_engine.py")


def step_validate() -> None:
    p = ROOT / "risk_pretrade.py"
    if not p.exists():
        fatal("risk_pretrade.py absent apres install.")
    src = read_utf8(p)
    count = src.count("[RISK_V1]")
    ok(f"[RISK_V1] markers dans risk_pretrade.py : {count}")

    exec_p = ROOT / "execution_engine.py"
    if exec_p.exists():
        src2 = read_utf8(exec_p)
        count2 = src2.count("[RISK_V1]")
        ok(f"[RISK_V1] markers dans execution_engine.py : {count2}")


def step_summary() -> None:
    print("")
    print("=" * 60)
    print(" [RISK_V1] install termine")
    print("=" * 60)
    print("")
    print("Smoke test :")
    print(f"  cd {ROOT}")
    print("  py -3.13 risk_pretrade.py NVDA 10 900 BUY")
    print("")
    print("Inspection du log :")
    db = ROOT / "thesium.db"
    print(f"  py -3.13 -c \"import sqlite3,json; c=sqlite3.connect(r'{db}'); "
          "rows=c.execute('SELECT * FROM risk_pretrade_log ORDER BY id DESC LIMIT 5').fetchall(); "
          "cols=[d[0] for d in c.execute('SELECT * FROM risk_pretrade_log LIMIT 1').description]; "
          "[print(json.dumps(dict(zip(cols,r)),indent=2,ensure_ascii=False)) for r in rows]\"")
    print("")


def main() -> None:
    if not ROOT.exists():
        fatal(f"ROOT introuvable : {ROOT}")
    print("=" * 60)
    print(" [RISK_V1] Risk engine pre-trade - installer")
    print("=" * 60)
    step_backup()
    step_copy_risk_pretrade()
    step_hook_execution_engine()
    step_validate()
    step_summary()


if __name__ == "__main__":
    main()
