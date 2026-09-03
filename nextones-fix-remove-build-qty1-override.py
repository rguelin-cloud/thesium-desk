# -*- coding: utf-8 -*-
"""
Fix: desactiver l'override [BUILD_QTY1_V1] dans execution_engine.py
qui force quantity=1 sur toutes les equities BUY en regime BUILD.

Strategie:
1. Backup execution_engine.py horodate
2. Reperer le bloc try: ... [BUILD_QTY1_V1] ... except a partir de la ligne
   commencant par "# [BUILD_QTY1_V1] override BUILD"
3. Remplacer tout le bloc par une version desactivee (commentaire + pass)
4. Marqueur idempotent: [BUILD_QTY1_REMOVED_V1]

Le calcul correct (ligne 1864-1866) est conserve:
  - crypto: round(target_value / price, 6)
  - equity: math.floor(target_value / price)
Le cap SELL via max_qty (1868-1869) est conserve.
Le filtre min_qty (1897-1899) est conserve.
"""

import shutil
import sys
from pathlib import Path
from datetime import datetime

EE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py")
MARKER_OLD = "[BUILD_QTY1_V1]"
MARKER_NEW = "[BUILD_QTY1_REMOVED_V1]"

def log(m): print(f"[fix-qty1] {m}")

def main():
    if not EE.exists():
        log(f"ERREUR introuvable: {EE}")
        sys.exit(1)

    src = EE.read_text(encoding="utf-8-sig")

    if MARKER_NEW in src:
        log(f"DEJA APPLIQUE ({MARKER_NEW} present). Abort.")
        sys.exit(0)

    if MARKER_OLD not in src:
        log(f"ERREUR: bloc {MARKER_OLD} introuvable. Abort.")
        sys.exit(2)

    # Backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = EE.with_suffix(f".py.bak-buildqty1-{ts}")
    shutil.copy2(EE, bak)
    log(f"Backup: {bak.name}")

    lines = src.splitlines(keepends=True)

    # Trouver la ligne de debut: "# [BUILD_QTY1_V1] override BUILD"
    start_idx = None
    for i, ln in enumerate(lines):
        if "[BUILD_QTY1_V1] override BUILD" in ln:
            start_idx = i
            break
    if start_idx is None:
        log("ERREUR: ligne de debut introuvable")
        sys.exit(3)
    log(f"Bloc commence ligne {start_idx + 1}")

    # Trouver la ligne de fin: la prochaine "except ... [BUILD_QTY1_V1] error"
    end_idx = None
    for j in range(start_idx, min(start_idx + 60, len(lines))):
        if "[BUILD_QTY1_V1] error" in lines[j]:
            # On prend la ligne suivante (apres le print de l'except)
            end_idx = j
            break
    if end_idx is None:
        log("ERREUR: fin du except [BUILD_QTY1_V1] error introuvable")
        sys.exit(4)
    log(f"Bloc se termine ligne {end_idx + 1}")

    # Calcul indentation
    indent = ""
    for ch in lines[start_idx]:
        if ch in (" ", "\t"):
            indent += ch
        else:
            break
    log(f"Indentation detectee: {len(indent)} espaces")

    # Bloc de remplacement (desactivation)
    replacement = (
        f"{indent}# {MARKER_NEW} override desactive le {datetime.now().isoformat(timespec='seconds')}\n"
        f"{indent}# Le bloc [BUILD_QTY1_V1] forcait quantity=1 sur equities BUY en BUILD.\n"
        f"{indent}# Desactive pour laisser quantity = math.floor(target_value / price) (ligne ci-dessus).\n"
        f"{indent}pass\n"
    )

    # Construire le nouveau contenu
    new_lines = lines[:start_idx] + [replacement] + lines[end_idx + 1:]
    new_src = "".join(new_lines)

    # Validation: marqueurs
    if MARKER_NEW not in new_src:
        log("ERREUR: marqueur nouveau absent du resultat")
        sys.exit(5)
    if "[BUILD_QTY1_V1] override BUILD" in new_src:
        log("AVERT: l'ancien header est encore present (devrait avoir disparu)")
        sys.exit(6)

    EE.write_text(new_src, encoding="utf-8")
    log(f"OK - execution_engine.py patche")
    log(f"     Avant: {len(src)} chars, Apres: {len(new_src)} chars")
    log(f"     Bloc supprime: lignes {start_idx + 1} a {end_idx + 1} ({end_idx - start_idx + 1} lignes)")
    log("")
    log("ACTION:")
    log("  1. Redemarrer l'API: py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    log("  2. Lancer un RUN CYCLE et verifier les nouvelles quantites")
    log("     Attendu: pour equity_pct=2% sur portefeuille $100k = $2000")
    log("              NVDA @ $214 -> quantity = floor(2000/214) = 9 (pas 1)")

if __name__ == "__main__":
    main()
