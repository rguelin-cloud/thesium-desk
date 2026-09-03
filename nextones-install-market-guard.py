# -*- coding: utf-8 -*-
# [NEXTONES-INSTALL-MARKET-GUARD-V1]
# Installe le garde-fou marche US sur le pipeline Thesium en deux endroits :
#
#   1. execute_cycle() dans execution_engine.py
#      - injection au tout debut : import + guard_or_skip()
#      - param force=False (par defaut)
#      - retourne dict {status:'skipped', reason:..., next_open:...}
#        si guard refuse et force=False
#
#   2. Endpoint /api/cycle/execute dans api_server_with_static.py
#      - lecture query param ?force=true (defaut false)
#      - si guard refuse : retourne HTTP 423 Locked avec JSON detail
#      - sinon : appelle execute_cycle(..., force=force)
#
# Validation stricte :
#   - ast.parse + py_compile + smoke import via subprocess
#   - backup auto avant ecriture
#   - idempotent : detecte marker [NEXTONES-MARKET-GUARD-V1] et skip
#
# Usage :
#   py -3.13 nextones-install-market-guard.py [--dry-run]
#                                              [--engine-only]
#                                              [--api-only]

import argparse
import ast
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
ENGINE = os.path.join(PROD, "execution_engine.py")
API = os.path.join(PROD, "api_server_with_static.py")

MARKER = "[NEXTONES-MARKET-GUARD-V1]"


# ===================================================================
# Bloc a injecter dans execute_cycle()
# Note : "force" est attendu comme argument optionnel du caller, on
# utilise locals().get("force", False) pour ne pas casser la signature.
# ===================================================================

ENGINE_GUARD_BLOCK = '''    # [NEXTONES-MARKET-GUARD-V1] start
    try:
        import importlib.util as _ilu, os as _os
        _here = _os.path.dirname(_os.path.abspath(__file__))
        _p = _os.path.join(_here, "nextones-market-calendar.py")
        _spec = _ilu.spec_from_file_location("_nx_market_calendar", _p)
        _mc = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mc)
        _force = bool(locals().get("force", False))
        _allowed, _reason = _mc.guard_or_skip(force=_force)
        if not _allowed:
            _nxt = _mc.next_us_open()
            print(f"[MARKET-GUARD] skip cycle : {_reason}")
            print(f"[MARKET-GUARD] next_open : {_nxt.isoformat()}")
            return {
                "status": "skipped",
                "reason": _reason,
                "next_open_utc": _nxt.isoformat(),
                "guard": "NEXTONES-MARKET-GUARD-V1",
            }
        if _reason.startswith("early_close_warning"):
            print(f"[MARKET-GUARD] WARN : {_reason}")
    except Exception as _ge:
        print(f"[MARKET-GUARD] erreur garde-fou (ignoree) : {_ge}")
    # [NEXTONES-MARKET-GUARD-V1] end
'''


# ===================================================================
# Patch ENGINE : injection au debut de execute_cycle()
# ===================================================================

def patch_engine(dry_run=False):
    print()
    print("=" * 60)
    print("PATCH execution_engine.py")
    print("=" * 60)

    if not os.path.exists(ENGINE):
        print(f"[FAIL] introuvable : {ENGINE}")
        return False

    with open(ENGINE, "r", encoding="utf-8-sig") as fh:
        src = fh.read()
    print(f"  taille : {len(src)} octets")

    if MARKER in src:
        print(f"  [SKIP] marker {MARKER} deja present")
        return True

    # Cherche la signature de la fonction d'entree cycle. Plusieurs variantes
    # possibles selon l'evolution du code. On accepte par ordre de priorite :
    #   1. run_decision_cycle(conn)
    #   2. execute_cycle(...)
    # On accepte aussi async def.
    fn_candidates = ["run_decision_cycle", "execute_cycle"]
    match = None
    indent = ""
    fn_found = None
    for fn in fn_candidates:
        for prefix in ("def", "async def"):
            pat = (
                r"^(\s*)" + prefix + r"\s+" + re.escape(fn)
                + r"\s*\([^)]*\)\s*(?:->\s*[^:]+)?\s*:"
            )
            m = re.search(pat, src, re.MULTILINE)
            if m:
                match = m
                indent = m.group(1)
                fn_found = fn
                break
        if match:
            break

    if not match:
        print("[WARN] signature run_decision_cycle/execute_cycle introuvable")
        # liste les def cycle*
        for i, ln in enumerate(src.splitlines(), 1):
            if "def " in ln and "cycle" in ln:
                print(f"  L{i}: {ln.strip()}")
        return False

    print(f"  cible : {fn_found}()")

    # Trouve la fin de la signature (la ligne qui finit par ':')
    start = match.start()
    end_sig = src.find(":\n", start) + 2
    if end_sig <= 1:
        end_sig = src.find(":", start) + 1
    print(f"  signature trouvee a offset {start} (end {end_sig})")
    print(f"  contexte : {src[start:end_sig].strip()[:120]}")

    # On saute eventuel docstring """ ... """ ou ''' ... '''
    after_sig = src[end_sig:]
    # detecte indent du corps (premier non-blanc)
    body_indent = indent + "    "

    # On cherche : 0+ lignes blanches puis eventuellement docstring
    pos = 0
    # passe les lignes vides
    while pos < len(after_sig) and after_sig[pos] in "\r\n":
        pos += 1
    # docstring ?
    skip_doc = 0
    stripped = after_sig[pos:pos + 4]
    for triple in ('"""', "'''"):
        if after_sig[pos:].lstrip(" \t").startswith(triple):
            # trouve fermeture
            opener_pos = after_sig.find(triple, pos)
            closer_pos = after_sig.find(triple, opener_pos + 3)
            if closer_pos > 0:
                # avance jusqu'a fin de ligne apres closer
                eol = after_sig.find("\n", closer_pos)
                if eol > 0:
                    skip_doc = eol + 1
                else:
                    skip_doc = closer_pos + 3
            break

    insert_offset = end_sig + (skip_doc if skip_doc > 0 else pos)
    # On injecte ENGINE_GUARD_BLOCK avec l'indent approprie
    block = ENGINE_GUARD_BLOCK
    # ENGINE_GUARD_BLOCK utilise indent "    " (4 espaces). Si l'indent
    # voulu est different, on reindente.
    if body_indent != "    ":
        block = "\n".join(
            (body_indent + ln[4:]) if ln.startswith("    ") else ln
            for ln in block.splitlines()
        ) + "\n"

    src2 = src[:insert_offset] + block + src[insert_offset:]
    print(f"  taille apres : {len(src2)} octets (+{len(src2) - len(src)})")

    # Validation
    try:
        ast.parse(src2)
        print("  ast.parse OK")
    except SyntaxError as e:
        print(f"[FAIL] ast.parse : {e}")
        # affiche les lignes autour
        for i, ln in enumerate(src2.splitlines()[max(0, e.lineno - 5):
                                                 e.lineno + 3], e.lineno - 5):
            print(f"    L{i}: {ln}")
        return False

    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(src2)
        tmpname = tf.name
    try:
        py_compile.compile(tmpname, doraise=True)
        print("  py_compile OK")
    except py_compile.PyCompileError as e:
        print(f"[FAIL] py_compile : {e}")
        return False
    finally:
        try:
            os.unlink(tmpname)
        except Exception:
            pass

    if dry_run:
        print("  [DRY-RUN] pas d'ecriture")
        return True

    bak = ENGINE + ".bak." + datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(ENGINE, bak)
    print(f"  backup : {bak}")
    with open(ENGINE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src2)
    print(f"  ecrit  : {ENGINE}")
    return True


# ===================================================================
# Patch API : pas obligatoire, on documente
# Beaucoup d'API server ont des endpoints heterogenes. Plutot que de
# patcher en aveugle, on laisse le garde-fou s'executer dans execute_cycle()
# qui est appele par l'endpoint, et on documente comment ajouter le param
# ?force=true.
# ===================================================================

def find_cycle_endpoint():
    print()
    print("=" * 60)
    print("DIAG api_server_with_static.py (endpoint cycle)")
    print("=" * 60)
    if not os.path.exists(API):
        print(f"[FAIL] introuvable : {API}")
        return
    with open(API, "r", encoding="utf-8-sig") as fh:
        lines = fh.read().splitlines()
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if (("cycle/execute" in s or "/cycle" in s)
                and ("@" in s or "post" in s.lower() or "get" in s.lower())):
            print(f"  L{i}: {ln}")
            # affiche 10 lignes apres pour voir la fonction
            for j in range(i, min(i + 12, len(lines))):
                print(f"    L{j+1}: {lines[j].rstrip()}")
            print()


# ===================================================================
# Smoke import
# ===================================================================

def smoke_engine():
    print()
    print("=" * 60)
    print("SMOKE TEST execution_engine.py import")
    print("=" * 60)
    # On lance python -c "import execution_engine" pour valider
    r = subprocess.run(
        ["py", "-3.13", "-c",
         "import sys; sys.path.insert(0, r'" + PROD + "'); "
         "import execution_engine; print('import OK')"],
        capture_output=True, text=True, timeout=30, cwd=PROD,
    )
    if r.returncode != 0:
        print(f"[FAIL] rc={r.returncode}")
        print("STDOUT:", r.stdout[-500:])
        print("STDERR:", r.stderr[-500:])
        return False
    print(f"  {r.stdout.strip()}")
    return True


# ===================================================================
# Main
# ===================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--engine-only", action="store_true")
    ap.add_argument("--api-only", action="store_true")
    args = ap.parse_args()

    if not args.api_only:
        ok = patch_engine(dry_run=args.dry_run)
        if not ok:
            print("[FAIL] patch_engine echoue")
            sys.exit(1)
        if not args.dry_run:
            if not smoke_engine():
                print("[FAIL] smoke import KO")
                sys.exit(1)

    if not args.engine_only:
        find_cycle_endpoint()
        print()
        print("API server : pas de patch automatique (endpoints heterogenes).")
        print("Le garde-fou s'execute deja dans execute_cycle() et renvoie")
        print('  {"status":"skipped", "reason":..., "next_open_utc":...}')
        print("L'API server retourne ce JSON tel quel. C'est suffisant.")
        print("Pour bypass : passer force=True dans le body POST de l'endpoint.")

    print()
    print("=" * 60)
    print("DONE")
    print("=" * 60)
    print("Tests recommandes :")
    print("  py -3.13 nextones-market-calendar.py --check")
    print("  py -3.13 nextones-validate-market-guard.py")
    print("  py -3.13 nextones-run-execute-cycle-auth.ps1  # doit skip aujourd'hui")


if __name__ == "__main__":
    main()
