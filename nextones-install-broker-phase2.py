# -*- coding: utf-8 -*-
# [NEXTONES-INSTALL-BROKER-PHASE2-V1]
# Patch idempotent de risk_pretrade.py (qui est la V2 en prod) :
#   - insere un import lazy du module broker_check
#   - injecte un hook "broker_mapping_ok" EN PREMIER dans
#     run_pretrade_checks(ticker, qty, price, side, db_path, params)
#   - si broker refuse : insert dans risk_pretrade_log avec
#     marker='[NEXTONES-BROKER-CHECK-V1]' et return dict aligne format V2
#
# Securites:
#   - backup horodate risk_pretrade.py -> risk_pretrade.py.bak.{ts}
#   - validation ast.parse du fichier patche
#   - smoke import subprocess (py_compile + import du module)
#   - rollback automatique si echec
#
# Idempotent : si marker NEXTONES-BROKER-CHECK-V1 deja present, no-op.
#
# Usage:
#   py -3.13 nextones-install-broker-phase2.py
#   py -3.13 nextones-install-broker-phase2.py --dry-run
#   py -3.13 nextones-install-broker-phase2.py --rollback   (restaure dernier bak)

import os
import sys
import re
import ast
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
TARGET = ROOT / "risk_pretrade.py"
MARKER = "NEXTONES-BROKER-CHECK-V1"
RISK_CHECK_MODULE_FILENAME = "nextones-risk-broker-check.py"

# ----------------------------------------------------------------------
# Patches a injecter
# ----------------------------------------------------------------------

# Patch 1 : import lazy (en tete du fichier, apres les imports existants).
# On utilise importlib.util pour gerer le tiret dans le nom du fichier.
IMPORT_BLOCK = '''

# [NEXTONES-BROKER-CHECK-V1] - import lazy du module broker_check
def _nx_broker_check_load():
    """Charge nextones-risk-broker-check.py si present. Fail-safe : None sinon."""
    try:
        import importlib.util as _ilu
        import os as _os
        _p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                           "nextones-risk-broker-check.py")
        if not _os.path.exists(_p):
            return None
        _spec = _ilu.spec_from_file_location("_nx_broker_check", _p)
        if _spec is None or _spec.loader is None:
            return None
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        return _mod
    except Exception as _e:
        try:
            import sys as _sys
            print("[WARN] nx_broker_check load: " + str(_e), file=_sys.stderr)
        except Exception:
            pass
        return None


_NX_BROKER_CHECK = None


def _nx_broker_precheck(ticker, qty, price, side, db_path):
    """
    Hook broker_mapping_ok EN PREMIER (Phase 2 - option A1, regle A strict).
    Renvoie:
      - None si broker autorise (le pretrade normal continue)
      - dict format risk_pretrade V2 si broker refuse l'instrument
    """
    global _NX_BROKER_CHECK
    if _NX_BROKER_CHECK is None:
        _NX_BROKER_CHECK = _nx_broker_check_load()
    if _NX_BROKER_CHECK is None:
        # module absent -> on n'interrompt pas la prod, mais on log warning
        try:
            import sys as _sys
            print("[WARN] [NEXTONES-BROKER-CHECK-V1] module absent, bypass",
                  file=_sys.stderr)
        except Exception:
            pass
        return None
    try:
        result = _NX_BROKER_CHECK.check_broker_mapping({
            "thesium_ticker": ticker,
            "side": side,
            "qty": qty,
        })
    except Exception as _e:
        try:
            import sys as _sys
            print("[WARN] [NEXTONES-BROKER-CHECK-V1] check error: " + str(_e),
                  file=_sys.stderr)
        except Exception:
            pass
        return None

    if result.get("ok"):
        return None  # broker OK -> on laisse pretrade continuer

    # Broker refuse : trace dans risk_pretrade_log + retour format V2
    import json as _json
    import sqlite3 as _sql
    from datetime import datetime as _dt, timezone as _tz
    details = {
        "broker_mapping_ok": {
            "ok": False,
            "reason": result.get("reason"),
            "broker_symbol": result.get("broker_symbol"),
            "volume_lots": result.get("volume_lots"),
            "diagnostics": result.get("diagnostics"),
            "policy": "A_strict_refuse",
        }
    }
    ts = _dt.now(_tz.utc).isoformat(timespec="seconds")
    try:
        _c = _sql.connect(db_path or _os.environ.get("THESIUM_DB",
                                                     r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\thesium.db"))
        _c.execute(
            "INSERT INTO risk_pretrade_log("
            "  ts, symbol, side, qty, price, passed, blocked_by,"
            "  details_json, marker"
            ") VALUES(?,?,?,?,?,?,?,?,?)",
            (ts, ticker, side, float(qty or 0), float(price or 0), 0,
             "broker_mapping_ok", _json.dumps(details),
             "[NEXTONES-BROKER-CHECK-V1]"),
        )
        _c.commit()
        _c.close()
    except Exception as _e:
        try:
            import sys as _sys
            print("[WARN] [NEXTONES-BROKER-CHECK-V1] log insert: " + str(_e),
                  file=_sys.stderr)
        except Exception:
            pass

    return {
        "passed": 0,
        "blocked_by": "broker_mapping_ok",
        "details_json": _json.dumps(details),
        "marker": "[NEXTONES-BROKER-CHECK-V1]",
    }
'''

# Patch 2 : injection EN PREMIER dans run_pretrade_checks
HOOK_CALL = '''    # [NEXTONES-BROKER-CHECK-V1] - 5e controle broker_mapping_ok EN PREMIER
    _nx_pre = _nx_broker_precheck(ticker, qty, price, side, db_path)
    if _nx_pre is not None:
        return _nx_pre
'''


# ----------------------------------------------------------------------
# Logique de patch
# ----------------------------------------------------------------------

def _ts():
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _read(path):
    with open(path, "rb") as f:
        raw = f.read()
    return raw.decode("utf-8-sig", errors="replace")


def _write_ascii_no_bom(path, text):
    # Le hook IMPORT_BLOCK est ASCII pur, on l'ecrit en utf-8 sans BOM
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def _backup(path):
    bak = str(path) + ".bak." + _ts()
    shutil.copy2(path, bak)
    return bak


def _has_marker(text):
    return MARKER in text


def _find_run_pretrade_checks_def(text):
    """Retourne (start_line_idx, end_of_signature_line_idx) pour
    'def run_pretrade_checks(' (qui peut etre multi-lignes)."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if re.match(r"^\s*def\s+run_pretrade_checks\s*\(", ln):
            # cherche la ligne contenant le ':' final de la signature
            j = i
            depth = 0
            saw_open = False
            while j < len(lines):
                for ch in lines[j]:
                    if ch == "(":
                        depth += 1; saw_open = True
                    elif ch == ")":
                        depth -= 1
                if saw_open and depth == 0:
                    # ligne avec ':' final
                    if lines[j].rstrip().endswith(":"):
                        return i, j
                    # le ':' peut etre sur la ligne suivante
                    k = j + 1
                    while k < len(lines) and not lines[k].rstrip().endswith(":"):
                        k += 1
                    return i, k
                j += 1
    return None, None


def patch_file(path, dry_run=False):
    text = _read(path)
    if _has_marker(text):
        print("[INFO] Marker " + MARKER + " deja present : no-op")
        return None, False

    sig_start, sig_end = _find_run_pretrade_checks_def(text)
    if sig_start is None:
        print("[ERR] Impossible de localiser 'def run_pretrade_checks('")
        sys.exit(2)

    lines = text.splitlines(keepends=True)

    # 1. Ajout IMPORT_BLOCK : on l'insere juste AVANT 'def run_pretrade_checks'
    insert_idx = sig_start

    # 2. Hook call : on l'insere juste APRES la ligne de fermeture ':' de la sig
    #    + on saute une eventuelle docstring
    body_start = sig_end + 1

    # detecte docstring
    if body_start < len(lines):
        stripped = lines[body_start].lstrip()
        if stripped.startswith(('"""', "'''")):
            quote = stripped[:3]
            # docstring single-line ?
            if stripped.count(quote) >= 2:
                body_start += 1
            else:
                # multi-line : avance jusqu'a la prochaine occurrence
                k = body_start + 1
                while k < len(lines) and quote not in lines[k]:
                    k += 1
                body_start = k + 1

    new_lines = (
        lines[:insert_idx]
        + [IMPORT_BLOCK + "\n\n"]
        + lines[insert_idx:body_start]
        + [HOOK_CALL]
        + lines[body_start:]
    )

    new_text = "".join(new_lines)

    # Validation ast
    try:
        ast.parse(new_text)
    except SyntaxError as e:
        print("[ERR] ast.parse fail apres patch : " + str(e))
        sys.exit(3)

    if dry_run:
        print("[DRY-RUN] patch valide ast.parse OK ; aucune ecriture")
        return None, False

    bak = _backup(path)
    print("[OK] backup -> " + bak)
    _write_ascii_no_bom(path, new_text)
    print("[OK] patch applique sur " + str(path))
    return bak, True


# ----------------------------------------------------------------------
# Smoke import
# ----------------------------------------------------------------------

def smoke_import():
    cmd = [sys.executable, "-c",
           "import importlib, importlib.util, os; "
           "spec = importlib.util.spec_from_file_location('rp', "
           "    os.path.join(os.getcwd(), 'risk_pretrade.py')); "
           "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
           "print('SMOKE_IMPORT_OK')"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode != 0 or "SMOKE_IMPORT_OK" not in r.stdout:
        print("[ERR] smoke import FAIL")
        print(r.stdout); print(r.stderr)
        return False
    print("[OK] " + r.stdout.strip())
    return True


def smoke_compile():
    r = subprocess.run([sys.executable, "-m", "py_compile",
                        str(TARGET)], capture_output=True, text=True)
    if r.returncode != 0:
        print("[ERR] py_compile FAIL")
        print(r.stderr)
        return False
    print("[OK] py_compile OK")
    return True


# ----------------------------------------------------------------------
# Rollback
# ----------------------------------------------------------------------

def rollback_last():
    baks = sorted(ROOT.glob("risk_pretrade.py.bak.*"))
    if not baks:
        print("[ERR] aucun backup risk_pretrade.py.bak.* trouve")
        sys.exit(4)
    last = baks[-1]
    shutil.copy2(last, TARGET)
    print("[OK] rollback depuis " + str(last))


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    if "--rollback" in sys.argv:
        rollback_last()
        return

    if not TARGET.exists():
        print("[ERR] " + str(TARGET) + " introuvable")
        sys.exit(5)

    # Verifie la presence du module broker_check
    mod_path = ROOT / RISK_CHECK_MODULE_FILENAME
    if not mod_path.exists():
        print("[ERR] " + RISK_CHECK_MODULE_FILENAME + " absent du repertoire")
        sys.exit(6)
    print("[OK] " + RISK_CHECK_MODULE_FILENAME + " present")

    dry = "--dry-run" in sys.argv
    bak, patched = patch_file(TARGET, dry_run=dry)
    if dry:
        return
    if not patched:
        return  # idempotence

    if not smoke_compile():
        print("[!] rollback auto")
        shutil.copy2(bak, TARGET)
        sys.exit(7)

    if not smoke_import():
        print("[!] rollback auto")
        shutil.copy2(bak, TARGET)
        sys.exit(8)

    print()
    print("=" * 60)
    print("PHASE 2.5 INSTALLEE")
    print("=" * 60)
    print("Backup : " + str(bak))
    print("Marker : " + MARKER)
    print()
    print("Etape suivante :")
    print("  py -3.13 nextones-validate-broker-phase2-wired.py")


if __name__ == "__main__":
    main()
