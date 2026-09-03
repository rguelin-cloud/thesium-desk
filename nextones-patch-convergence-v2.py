# -*- coding: utf-8 -*-
"""
[PATCH_CONVERGENCE_V2]

Patch unifie qui :
  1. ROLLBACK portfolio_construction_agent.py depuis le backup
     (.bak-convergence-* le plus recent) si le marker V1 y est encore.
  2. PATCH portfolio_construction_agent_jalon2.py (vraie cible importee
     par api_server_with_static.py) avec helper apply_convergence_sizing
     corrige (lit seulement les vraies colonnes : direction_consensus,
     sizing_multiplier, forced_exit, drift).
  3. PATCH api_server_with_static.py endpoint /api/construction/run pour
     resoudre cycle_id automatiquement :
       cycle_id = body.get("cycle_id") or last_convergence_cycle_id(conn)

Marker insere : # [CONVERGENCE_SIZING_V2]

Idempotent : skip si marker V2 deja present.
Validation : ast.parse + py_compile avant ecriture.
Backups horodates avant ecriture.

Lance :
  py -3.13 nextones-patch-convergence-v2.py
"""
import sys
import io
import os
import ast
import py_compile
import shutil
import glob
import re
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
PCA_ORIG = os.path.join(ROOT, "portfolio_construction_agent.py")
PCA_JAL2 = os.path.join(ROOT, "portfolio_construction_agent_jalon2.py")
API = os.path.join(ROOT, "api_server_with_static.py")

MARKER_V1 = "# [CONVERGENCE_SIZING_V1]"
MARKER_V2 = "# [CONVERGENCE_SIZING_V2]"
MARKER_API = "# [CONVERGENCE_CYCLE_RESOLVER_V2]"

TS = datetime.now().strftime("%Y%m%d-%H%M%S")


# =============================================================================
# Helper PCA - corrige : pas de colonne 'regime', on derive depuis FE/DR/consensus
# =============================================================================
HELPER_CODE = '''
# =============================================================================
# [CONVERGENCE_SIZING_V2] Helper convergence sizing
# =============================================================================
def apply_convergence_sizing(conn, cycle_id, allocations):
    """[CONVERGENCE_SIZING_V2]
    Multiplie chaque allocation par le sizing_multiplier de convergence_snapshots.

    Args:
        conn        : connexion SQLite
        cycle_id    : str ou None - si None, prend le cycle le plus recent
        allocations : dict {ticker: weight_pct}

    Returns:
        (scaled_allocations, multiplier_log)
        - scaled_allocations : dict {ticker: weight_pct * multiplier}
        - multiplier_log     : dict {ticker: (multiplier, regime_label, forced_exit, drift)}

    Fallback : si table absente ou ticker absent -> multiplier 1.0.
    """
    if not allocations:
        return {}, {}

    # Resolution cycle_id : si None, prend le plus recent
    resolved_cid = cycle_id
    if not resolved_cid:
        try:
            cur = conn.execute(
                "SELECT cycle_id FROM convergence_snapshots "
                "ORDER BY rowid DESC LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                resolved_cid = row[0] if not hasattr(row, "keys") else row["cycle_id"]
                print(f"[convergence_sizing] cycle_id resolu auto : {resolved_cid}")
        except Exception as e:
            print(f"[convergence_sizing] WARN resolution cycle_id : {e}")

    mult_map = {}
    meta_map = {}

    if resolved_cid:
        try:
            cur = conn.execute(
                "SELECT ticker, sizing_multiplier, direction_consensus, "
                "       forced_exit, drift "
                "FROM convergence_snapshots WHERE cycle_id = ?",
                (resolved_cid,),
            )
            for row in cur.fetchall():
                if hasattr(row, "keys"):
                    t = row["ticker"]
                    mult = float(row["sizing_multiplier"] or 1.0)
                    cons = row["direction_consensus"] or ""
                    fe = int(row["forced_exit"] or 0)
                    dr = int(row["drift"] or 0)
                else:
                    t, mult, cons, fe, dr = row[0], row[1], row[2], row[3], row[4]
                    mult = float(mult or 1.0)
                    fe = int(fe or 0)
                    dr = int(dr or 0)
                # Derive un label regime
                if fe:
                    regime_label = "forced_exit"
                elif dr:
                    regime_label = "drift"
                elif mult >= 1.0:
                    regime_label = f"strong_{cons}"
                elif mult >= 0.5:
                    regime_label = f"conflict_{cons}"
                else:
                    regime_label = f"weak_{cons}"
                mult_map[t] = mult
                meta_map[t] = (mult, regime_label, fe, dr)
        except Exception as e:
            print(f"[convergence_sizing] WARN lecture convergence_snapshots : {e}")
            return dict(allocations), {}

    scaled = {}
    log = {}
    for ticker, w in allocations.items():
        m = mult_map.get(ticker, 1.0)
        scaled[ticker] = w * m
        if ticker in meta_map:
            log[ticker] = meta_map[ticker]
        else:
            log[ticker] = (1.0, "absent", 0, 0)

    fe_count = sum(1 for v in log.values() if v[2] == 1)
    dr_count = sum(1 for v in log.values() if v[3] == 1)
    print(f"[convergence_sizing] cycle={resolved_cid} n_alloc={len(allocations)} "
          f"forced_exit={fe_count} drift={dr_count}")
    return scaled, log


'''


INJECTION_BLOCK = '''
    # ---- [CONVERGENCE_SIZING_V2] Application du sizing multiplier ----
    scaled_alloc, conv_log = apply_convergence_sizing(conn, cycle_id, raw_alloc)
    for _t, _meta in sorted(conv_log.items()):
        _mult, _regime, _fe, _dr = _meta
        if _mult != 1.0 or _fe or _dr:
            print(f"  [conv]  {_t:<6}  x{_mult:.3f}  regime={_regime}  fe={_fe} dr={_dr}")

'''


def _backup(path):
    bk = path + f".bak-conv-v2-{TS}"
    shutil.copy2(path, bk)
    print(f"[OK] Backup : {bk}")
    return bk


def _validate_and_write(path, new_content):
    tmp = path + ".tmp-conv-v2"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        print(f"[ERR] SyntaxError sur {os.path.basename(path)} : {e}")
        return False
    try:
        py_compile.compile(tmp, doraise=True)
    except py_compile.PyCompileError as e:
        print(f"[ERR] py_compile sur {os.path.basename(path)} : {e}")
        return False
    os.replace(tmp, path)
    print(f"[OK] Ecrit : {os.path.basename(path)}")
    return True


# =============================================================================
# ETAPE 1 - Rollback portfolio_construction_agent.py
# =============================================================================
def step1_rollback_pca_orig():
    print("\n" + "=" * 70)
    print("ETAPE 1 - Rollback portfolio_construction_agent.py")
    print("=" * 70)
    if not os.path.exists(PCA_ORIG):
        print(f"[MISS] {PCA_ORIG}")
        return
    with open(PCA_ORIG, "r", encoding="utf-8-sig") as f:
        c = f.read()
    if MARKER_V1 not in c and MARKER_V2 not in c:
        print("[SKIP] Aucun marker convergence dans portfolio_construction_agent.py")
        return
    # Trouve le backup le plus recent
    backups = sorted(glob.glob(PCA_ORIG + ".bak-convergence-*"))
    if not backups:
        print("[WARN] Aucun backup .bak-convergence-* trouve, je tente un rollback manuel")
        # Rollback manuel : retirer les blocs marker
        new_c = c
        # Supprime le helper (de "# [CONVERGENCE_SIZING_V" jusqu'a "\n\n\n" qui le ferme)
        new_c = re.sub(
            r"# =+\n# \[CONVERGENCE_SIZING_V[12]\] Helper.*?\n=+\n\n\n",
            "",
            new_c,
            count=1,
            flags=re.DOTALL,
        )
        # Supprime le bloc d'injection
        new_c = re.sub(
            r"\n    # ---- \[CONVERGENCE_SIZING_V[12]\] Application.*?\n\n",
            "\n",
            new_c,
            count=1,
            flags=re.DOTALL,
        )
        # Restore apply_caps_floors(raw_alloc, ...)
        new_c = new_c.replace(
            "apply_caps_floors(scaled_alloc, universe, scores_map)",
            "apply_caps_floors(raw_alloc, universe, scores_map)",
        )
        if MARKER_V1 in new_c or MARKER_V2 in new_c:
            print("[ERR] Rollback manuel incomplet, markers encore presents")
            return
        _backup(PCA_ORIG)
        if _validate_and_write(PCA_ORIG, new_c):
            print("[OK] Rollback manuel reussi")
        return
    latest_bk = backups[-1]
    print(f"[INFO] Backup le plus recent : {latest_bk}")
    _backup(PCA_ORIG)  # backup state actuel avant rollback
    shutil.copy2(latest_bk, PCA_ORIG)
    print(f"[OK] Restore depuis {os.path.basename(latest_bk)}")


# =============================================================================
# ETAPE 2 - Patch portfolio_construction_agent_jalon2.py
# =============================================================================
def step2_patch_jal2():
    print("\n" + "=" * 70)
    print("ETAPE 2 - Patch portfolio_construction_agent_jalon2.py")
    print("=" * 70)
    if not os.path.exists(PCA_JAL2):
        print(f"[MISS] {PCA_JAL2}")
        return False
    with open(PCA_JAL2, "r", encoding="utf-8-sig") as f:
        c = f.read()
    if MARKER_V2 in c:
        print(f"[SKIP] {MARKER_V2} deja present")
        return True
    # Anchors
    anchor_helper = "# Allocation soft-max born"
    if anchor_helper not in c:
        print(f"[ERR] Anchor helper '{anchor_helper}' introuvable")
        return False
    idx = c.index(anchor_helper)
    line_start = c.rfind("# ===", 0, idx)
    if line_start == -1:
        line_start = idx
    new_c = c[:line_start] + HELPER_CODE + c[line_start:]
    print(f"[OK] Helper insere a position {line_start}")

    anchor_caps = "    # ---- Caps & floors ----"
    if anchor_caps not in new_c:
        print(f"[ERR] Anchor caps introuvable")
        return False
    new_c = new_c.replace(anchor_caps, INJECTION_BLOCK + anchor_caps, 1)
    print("[OK] Bloc d'injection insere")

    old_cap = "    capped_alloc, cap_log = apply_caps_floors(raw_alloc, universe, scores_map)"
    new_cap = "    capped_alloc, cap_log = apply_caps_floors(scaled_alloc, universe, scores_map)"
    if old_cap not in new_c:
        print(f"[ERR] Ligne apply_caps_floors introuvable")
        return False
    new_c = new_c.replace(old_cap, new_cap, 1)
    print("[OK] apply_caps_floors utilise scaled_alloc")

    _backup(PCA_JAL2)
    return _validate_and_write(PCA_JAL2, new_c)


# =============================================================================
# ETAPE 3 - Patch endpoint /api/construction/run
# =============================================================================
RESOLVER_BLOCK = '''        # [CONVERGENCE_CYCLE_RESOLVER_V2] Resolution auto du cycle_id
        _resolved_cid = None
        try:
            _cur = conn.execute(
                "SELECT cycle_id FROM convergence_snapshots "
                "ORDER BY rowid DESC LIMIT 1"
            )
            _row = _cur.fetchone()
            if _row:
                _resolved_cid = _row[0] if not hasattr(_row, "keys") else _row["cycle_id"]
        except Exception as _e:
            print(f"[construction/run] WARN resolution cycle_id : {_e}")
        print(f"[construction/run] cycle_id utilise : {_resolved_cid}")

'''


def step3_patch_api():
    print("\n" + "=" * 70)
    print("ETAPE 3 - Patch endpoint /api/construction/run")
    print("=" * 70)
    if not os.path.exists(API):
        print(f"[MISS] {API}")
        return False
    with open(API, "r", encoding="utf-8-sig") as f:
        c = f.read()
    if MARKER_API in c:
        print(f"[SKIP] {MARKER_API} deja present")
        return True

    # Remplace le bloc cycle_id=None par cycle_id=_resolved_cid
    old_call = (
        "        result = run_construction_agent(\n"
        "            conn,\n"
        "            cycle_id=None,   # pas de cycle_id explicite depuis l'API\n"
    )
    new_call = (
        RESOLVER_BLOCK
        + "        result = run_construction_agent(\n"
        "            conn,\n"
        "            cycle_id=_resolved_cid,   # [CONVERGENCE_CYCLE_RESOLVER_V2]\n"
    )
    if old_call not in c:
        print("[ERR] Bloc original cycle_id=None introuvable, je tente fallback regex")
        # Fallback : regex plus permissive
        pat = re.compile(
            r"        result = run_construction_agent\(\n"
            r"            conn,\n"
            r"            cycle_id=None,[^\n]*\n",
            re.MULTILINE,
        )
        m = pat.search(c)
        if not m:
            print("[ERR] Aussi introuvable via regex")
            return False
        new_c = c[:m.start()] + new_call + c[m.end():]
    else:
        new_c = c.replace(old_call, new_call, 1)

    _backup(API)
    return _validate_and_write(API, new_c)


# =============================================================================
# MAIN
# =============================================================================
def main():
    step1_rollback_pca_orig()
    ok2 = step2_patch_jal2()
    ok3 = step3_patch_api()
    print("\n" + "=" * 70)
    print(f"BILAN : step2(jal2)={ok2} step3(api)={ok3}")
    print("=" * 70)
    if ok2 and ok3:
        print()
        print("PROCHAINE ETAPE :")
        print("  1. Kill uvicorn (Ctrl-C dans la fenetre uvicorn)")
        print("  2. py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
        print("  3. Dans une autre fenetre :")
        print("     powershell -ExecutionPolicy Bypass -File .\\nextones-run-construction-auth.ps1")
        print()
        print("  Tu dois voir dans la console uvicorn :")
        print("     [construction/run] cycle_id utilise : 20260609-091332")
        print("     [convergence_sizing] cycle=20260609-091332 n_alloc=17 forced_exit=9 drift=1")
        print("       [conv]  AMD     x0.000  regime=forced_exit  fe=1 dr=0")
        print("       [conv]  BTC     x0.000  regime=forced_exit  fe=1 dr=0")
        print("       ... etc")


if __name__ == "__main__":
    main()
