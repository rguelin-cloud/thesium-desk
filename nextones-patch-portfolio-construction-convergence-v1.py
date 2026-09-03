# -*- coding: utf-8 -*-
"""
[PATCH_CONVERGENCE_SIZING_V1]

Patch portfolio_construction_agent.py pour injecter le sizing_multiplier
de la table convergence_snapshots entre softmax_allocate (L948) et
apply_caps_floors (L952).

Comportement :
  - Avant : raw_alloc = softmax(scores)  ->  capped = apply_caps_floors(raw_alloc)
  - Apres : raw_alloc = softmax(scores)  ->  scaled = apply_convergence_sizing(conn, cycle_id, raw_alloc)
            ->  capped = apply_caps_floors(scaled)

Marker insere : # [CONVERGENCE_SIZING_V1]

Helper top-level ajoute (apres les imports, avant la premiere def) :
  def apply_convergence_sizing(conn, cycle_id, allocations):
      ...

Idempotent : si le marker est deja present, le script ne re-patche pas.

Validation : ast.parse + py_compile avant ecriture.

Lance :
  py -3.13 nextones-patch-portfolio-construction-convergence-v1.py
"""
import sys
import io
import os
import ast
import py_compile
import shutil
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py"
MARKER = "# [CONVERGENCE_SIZING_V1]"
HELPER_NAME = "apply_convergence_sizing"

HELPER_CODE = '''
# =============================================================================
# [CONVERGENCE_SIZING_V1] Helper convergence sizing
# =============================================================================
def apply_convergence_sizing(conn, cycle_id, allocations):
    """[CONVERGENCE_SIZING_V1]
    Multiplie chaque allocation par le sizing_multiplier de convergence_snapshots.

    Args:
        conn        : connexion SQLite
        cycle_id    : str ou None
        allocations : dict {ticker: weight_pct}

    Returns:
        (scaled_allocations, multiplier_log)
        - scaled_allocations : dict {ticker: weight_pct * multiplier}
        - multiplier_log     : dict {ticker: (multiplier, regime, forced_exit, drift)}

    Fallback : si cycle_id None ou table absente ou ticker absent -> multiplier 1.0.
    """
    if not allocations:
        return {}, {}

    mult_map = {}
    meta_map = {}

    if cycle_id:
        try:
            cur = conn.execute(
                "SELECT ticker, sizing_multiplier, regime, forced_exit, drift "
                "FROM convergence_snapshots WHERE cycle_id = ?",
                (cycle_id,),
            )
            for row in cur.fetchall():
                # Compatible Row factory et tuple
                if hasattr(row, "keys"):
                    t = row["ticker"]
                    mult_map[t] = float(row["sizing_multiplier"] or 1.0)
                    meta_map[t] = (
                        float(row["sizing_multiplier"] or 1.0),
                        row["regime"] or "",
                        int(row["forced_exit"] or 0),
                        int(row["drift"] or 0),
                    )
                else:
                    t, mult, regime, forced, drift = row[0], row[1], row[2], row[3], row[4]
                    mult_map[t] = float(mult or 1.0)
                    meta_map[t] = (float(mult or 1.0), regime or "", int(forced or 0), int(drift or 0))
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

    # Trace concise
    forced_count = sum(1 for v in log.values() if v[2] == 1)
    drift_count = sum(1 for v in log.values() if v[3] == 1)
    print(f"[convergence_sizing] cycle={cycle_id} n_alloc={len(allocations)} "
          f"forced_exit={forced_count} drift={drift_count}")
    return scaled, log


'''

INJECTION_BLOCK = '''
    # ---- [CONVERGENCE_SIZING_V1] Application du sizing multiplier ----
    scaled_alloc, conv_log = apply_convergence_sizing(conn, cycle_id, raw_alloc)
    for _t, _meta in sorted(conv_log.items()):
        _mult, _regime, _fe, _dr = _meta
        if _mult != 1.0 or _fe or _dr:
            print(f"  [conv]  {_t:<6}  x{_mult:.3f}  regime={_regime}  fe={_fe} dr={_dr}")

'''

OLD_CAP_LINE = "    capped_alloc, cap_log = apply_caps_floors(raw_alloc, universe, scores_map)"
NEW_CAP_LINE = "    capped_alloc, cap_log = apply_caps_floors(scaled_alloc, universe, scores_map)"


def main():
    if not os.path.exists(TARGET):
        print(f"[ERR] Fichier introuvable : {TARGET}")
        sys.exit(1)

    # Backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = TARGET + f".bak-convergence-{ts}"
    shutil.copy2(TARGET, backup)
    print(f"[OK] Backup : {backup}")

    with open(TARGET, "r", encoding="utf-8-sig") as f:
        content = f.read()

    # Idempotence
    if MARKER in content:
        print(f"[SKIP] Marker {MARKER} deja present. Aucun changement.")
        sys.exit(0)

    # --- 1. Inserer le helper top-level juste APRES la premiere def
    #     On le met avant la section "ALLOCATION SOFT-MAX BORNEE" (L614)
    anchor_helper = "# Allocation soft-max born"
    if anchor_helper not in content:
        print(f"[ERR] Anchor helper introuvable : {anchor_helper}")
        sys.exit(1)
    idx = content.index(anchor_helper)
    # On remonte jusqu'au debut de la ligne de commentaire "# ====" qui precede
    line_start = content.rfind("# ===", 0, idx)
    if line_start == -1:
        line_start = idx
    new_content = content[:line_start] + HELPER_CODE + content[line_start:]
    print(f"[OK] Helper insere a position {line_start}")

    # --- 2. Inserer le bloc d'injection juste apres softmax_allocate (L948)
    #     et juste avant "# ---- Caps & floors ----"
    anchor_caps = "    # ---- Caps & floors ----"
    if anchor_caps not in new_content:
        print(f"[ERR] Anchor caps introuvable")
        sys.exit(1)
    new_content = new_content.replace(
        anchor_caps,
        INJECTION_BLOCK + anchor_caps,
        1,  # une seule occurrence
    )
    print(f"[OK] Bloc d'injection insere avant '# ---- Caps & floors ----'")

    # --- 3. Remplacer raw_alloc par scaled_alloc dans l'appel apply_caps_floors
    if OLD_CAP_LINE not in new_content:
        print(f"[ERR] Ligne apply_caps_floors introuvable : {OLD_CAP_LINE!r}")
        sys.exit(1)
    new_content = new_content.replace(OLD_CAP_LINE, NEW_CAP_LINE, 1)
    print(f"[OK] apply_caps_floors utilise maintenant scaled_alloc")

    # --- Validation AST + py_compile sur fichier temp
    tmp = TARGET + ".tmp-convergence"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)
    try:
        ast.parse(new_content)
        print("[OK] ast.parse OK")
    except SyntaxError as e:
        print(f"[ERR] SyntaxError : {e}")
        print(f"      Fichier temporaire conserve pour inspection : {tmp}")
        sys.exit(1)
    try:
        py_compile.compile(tmp, doraise=True)
        print("[OK] py_compile OK")
    except py_compile.PyCompileError as e:
        print(f"[ERR] py_compile : {e}")
        sys.exit(1)

    # Ecriture finale
    os.replace(tmp, TARGET)
    print(f"[OK] Fichier patche : {TARGET}")
    print(f"[OK] Marker insere : {MARKER}")
    print()
    print("=" * 60)
    print("PROCHAINE ETAPE :")
    print("  1. Restart API : kill uvicorn + py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print("  2. Run cycle complet -> verifier logs [convergence_sizing]")
    print("  3. Verifier portfolio_targets : les tickers forced_exit (BTC/ETH/AMD/AMZN/GOOGL/META/TSLA) doivent etre a 0")
    print("=" * 60)


if __name__ == "__main__":
    main()
