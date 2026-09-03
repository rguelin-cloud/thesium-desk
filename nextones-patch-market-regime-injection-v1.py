# -*- coding: utf-8 -*-
"""
[PATCH_MARKET_REGIME_INJECTION_V1]
Injecte detect_market_regime() dans execution_engine.py juste apres
detect_portfolio_regime() (L2064).

Effet :
  - Calcule equity_regime + crypto_regime a chaque cycle
  - Persiste dans market_regime_log
  - Enrichit regime_info avec market_regime pour usage downstream
  - Logge dans regime_log les colonnes equity_regime/crypto_regime + caps

Idempotent : skip si marker present.
Backup auto avec timestamp.
ASCII-pur sur l'injection.
"""
import os
import re
import ast
import py_compile
import shutil
import datetime
import sys
import tempfile

EE_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"
MARKER = "PATCH_MARKET_REGIME_INJECTION_V1"

# Bloc a injecter (ASCII pur)
INJECTION_BLOCK = """
    # ============================================================
    # [PATCH_MARKET_REGIME_INJECTION_V1]
    # Step 2.35 : DETECTION DU REGIME MARCHE (equity + crypto)
    # ============================================================
    market_info = None
    try:
        from market_regime_v1 import detect_market_regime, log_market_regime
        market_info = detect_market_regime(conn)
        eq = market_info.get('equity', {})
        cr = market_info.get('crypto', {})
        print(
            f"[market_regime] equity={eq.get('regime')} "
            f"(vix={eq.get('vix_value')}, vol={eq.get('realized_vol_pct')}, "
            f"dd={eq.get('drawdown_5d_pct')}, buy_x{eq.get('buy_mult')}, "
            f"sell_x{eq.get('sell_mult')}) | "
            f"crypto={cr.get('regime')} "
            f"(vol={cr.get('realized_vol_pct')}, dd={cr.get('drawdown_5d_pct')}, "
            f"buy_x{cr.get('buy_mult')}, sell_x{cr.get('sell_mult')})"
        )
        log_market_regime(conn, cycle_id, market_info)
        # Attache au regime_info pour usage downstream
        regime_info['market'] = market_info
    except Exception as e:
        import traceback
        print(f"[market_regime] ERREUR (non bloquant) : {e}")
        traceback.print_exc()
        market_info = None
    # ============================================================
    # FIN [PATCH_MARKET_REGIME_INJECTION_V1]
    # ============================================================

"""


def main():
    if not os.path.exists(EE_PATH):
        print(f"[ERREUR] Fichier introuvable : {EE_PATH}")
        sys.exit(1)

    with open(EE_PATH, "r", encoding="utf-8-sig") as f:
        content = f.read()

    # Idempotent
    if MARKER in content:
        print(f"[SKIP] Marker {MARKER} deja present, aucune action")
        sys.exit(0)

    # Verifier ASCII du bloc inject
    for i, b in enumerate(INJECTION_BLOCK.encode("utf-8")):
        if b > 127:
            print(f"[ERREUR] Bloc injection contient byte non-ASCII a position {i} : 0x{b:02x}")
            sys.exit(1)
    print("[OK] Injection block est ASCII pur")

    # Trouver le point d'injection : juste apres le bloc try/except detect_portfolio_regime
    # On cherche le pattern "regime_info = {\"regime\": \"MAINTAIN\"" (fallback)
    # puis on injecte apres la ligne suivante (ferm de l'except)
    lines = content.splitlines(keepends=True)

    # Recherche : ligne contenant 'detect_portfolio_regime(conn)' (appel, pas def)
    target_line_idx = None
    for i, line in enumerate(lines):
        if "detect_portfolio_regime(conn)" in line and "def " not in line:
            target_line_idx = i
            break
    if target_line_idx is None:
        print("[ERREUR] Impossible de trouver 'detect_portfolio_regime(conn)'")
        sys.exit(1)

    print(f"[INFO] Appel detect_portfolio_regime trouve a L{target_line_idx+1}")

    # On cherche la fin du bloc try/except qui entoure cet appel
    # = la ligne 'regime_info = {"regime": "MAINTAIN"...}' + la ligne ')' qui ferme le dict
    end_block_idx = None
    for j in range(target_line_idx, min(target_line_idx + 30, len(lines))):
        if 'regime_info = {"regime": "MAINTAIN"' in lines[j]:
            # Cherche la ligne fermante (contient '"n_positions": 0}' ou similaire)
            for k in range(j, min(j + 5, len(lines))):
                if '"n_positions"' in lines[k]:
                    end_block_idx = k + 1
                    break
            break
    if end_block_idx is None:
        print("[ERREUR] Impossible de trouver fin du bloc try/except detect_portfolio_regime")
        sys.exit(1)

    print(f"[INFO] Fin du bloc try/except trouvee a L{end_block_idx}")
    print(f"[INFO] Injection apres L{end_block_idx}")

    # Construction du nouveau contenu
    new_lines = lines[:end_block_idx] + [INJECTION_BLOCK] + lines[end_block_idx:]
    new_content = "".join(new_lines)

    # Validation AST sur le nouveau contenu
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        print(f"[ERREUR] ast.parse a echoue : {e}")
        sys.exit(1)
    print("[OK] ast.parse passe")

    # Validation py_compile via tmp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(new_content)
        tmp_path = tmp.name
    try:
        py_compile.compile(tmp_path, doraise=True)
        print("[OK] py_compile passe")
    except py_compile.PyCompileError as e:
        print(f"[ERREUR] py_compile a echoue : {e}")
        os.unlink(tmp_path)
        sys.exit(1)
    os.unlink(tmp_path)

    # Backup
    ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    backup = f"{EE_PATH}.bak.{ts}"
    shutil.copy2(EE_PATH, backup)
    print(f"[OK] Backup cree : {backup}")

    # Write atomique
    with open(EE_PATH, "w", encoding="utf-8", newline="") as f:
        f.write(new_content)
    print(f"[OK] Patch ecrit dans {EE_PATH}")

    # Verification finale
    with open(EE_PATH, "r", encoding="utf-8-sig") as f:
        final = f.read()
    if MARKER in final:
        print(f"[OK] Marker {MARKER} present apres ecriture")
    else:
        print(f"[ERREUR] Marker absent apres ecriture")
        sys.exit(1)
    print(f"[OK] Nouveau fichier : {len(final.splitlines())} lignes (avant : {len(lines)})")
    print(f"\n[PATCH_MARKET_REGIME_INJECTION_V1] TERMINE")


if __name__ == "__main__":
    main()
