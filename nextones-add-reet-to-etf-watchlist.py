# -*- coding: utf-8 -*-
"""
NEXTONES - Patch idempotent : ajoute REET a ETF_SPDR_SECTORIELS dans
universe_expansion_agent.py pour qu'il soit scoree au prochain scan.

Marker idempotent : [ADD_REET_V1]

Strategie :
  - Lit le fichier avec utf-8-sig, ecrit utf-8 sans BOM
  - Backup *.bak.addreet.YYYYMMDD-HHMMSS avant ecriture
  - Verifie idempotence via marker [ADD_REET_V1]
  - Verifie absence prealable de la ligne REET (double securite)
  - Insertion ciblee apres la ligne XLRE (sector RealEstate)
  - Validation ast.parse + py_compile avant ecriture finale
  - Rollback automatique si validation echoue

Usage : py -3.13 nextones-add-reet-to-etf-watchlist.py
"""
from __future__ import annotations

import ast
import py_compile
import shutil
import sys
from datetime import datetime
from pathlib import Path

AGENT_PATH = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\universe_expansion_agent.py")
MARKER = "[ADD_REET_V1]"

# Ligne a inserer (alignee sur le style existant : ticker, name, sector)
# Marker en commentaire Python pour idempotence
REET_LINE = ('    {"ticker": "REET", "name": "iShares Global REIT ETF",  '
             '"sector": "RealEstate"},  # ' + MARKER)

# Pivot : on cherche cette ligne pour inserer apres
PIVOT_LINE_SIGNATURE = '"ticker": "XLRE"'


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def main():
    log("=== nextones-add-reet-to-etf-watchlist START ===")

    if not AGENT_PATH.exists():
        log(f"FATAL : fichier introuvable {AGENT_PATH}")
        sys.exit(1)

    # Lecture utf-8-sig
    original = AGENT_PATH.read_text(encoding="utf-8-sig")
    log(f"Fichier lu : {len(original)} caracteres, "
        f"{original.count(chr(10))} lignes")

    # Idempotence : marker deja present ?
    if MARKER in original:
        log(f"Marker {MARKER} deja present -> rien a faire (idempotent)")
        log("Verification : REET present dans ETF_SPDR_SECTORIELS ?")
        if '"ticker": "REET"' in original:
            log("  OK : REET deja dans le fichier")
        else:
            log("  WARN : marker present mais ligne REET manquante (incoherent)")
        return

    # Double securite : REET deja present autre part ?
    if '"ticker": "REET"' in original:
        log("ATTENTION : REET present mais sans notre marker. Abort pour eviter doublon.")
        sys.exit(2)

    # Recherche du pivot
    lines = original.split("\n")
    pivot_idx = -1
    for i, line in enumerate(lines):
        if PIVOT_LINE_SIGNATURE in line:
            pivot_idx = i
            break

    if pivot_idx < 0:
        log(f"FATAL : ligne pivot '{PIVOT_LINE_SIGNATURE}' introuvable")
        sys.exit(3)

    log(f"Pivot trouve a la ligne {pivot_idx + 1} : {lines[pivot_idx].strip()[:80]}")

    # Construction du nouveau contenu : insere REET_LINE apres pivot
    new_lines = lines[:pivot_idx + 1] + [REET_LINE] + lines[pivot_idx + 1:]
    new_content = "\n".join(new_lines)

    log(f"Nouveau contenu : {len(new_content)} caracteres, "
        f"+1 ligne ajoutee")

    # Validation syntaxe avant ecriture
    log("Validation ast.parse...")
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        log(f"FATAL ast.parse : {e}")
        sys.exit(4)
    log("  ast.parse OK")

    # Backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = AGENT_PATH.with_suffix(f".py.bak.addreet.{ts}")
    shutil.copy2(AGENT_PATH, backup_path)
    log(f"Backup : {backup_path.name}")

    # Ecriture utf-8 sans BOM
    AGENT_PATH.write_text(new_content, encoding="utf-8")
    log(f"Fichier ecrit : {AGENT_PATH}")

    # Validation py_compile post-ecriture
    log("Validation py_compile...")
    try:
        py_compile.compile(str(AGENT_PATH), doraise=True)
    except py_compile.PyCompileError as e:
        log(f"FATAL py_compile : {e}")
        log("ROLLBACK en cours...")
        shutil.copy2(backup_path, AGENT_PATH)
        log("Rollback effectue. Fichier restaure.")
        sys.exit(5)
    log("  py_compile OK")

    # Double-check : marker et REET presents
    final = AGENT_PATH.read_text(encoding="utf-8-sig")
    assert MARKER in final, "Marker absent post-ecriture"
    assert '"ticker": "REET"' in final, "REET absent post-ecriture"
    log(f"Verification finale OK : marker {MARKER} et REET presents")

    log("=== nextones-add-reet-to-etf-watchlist END ===")
    log("")
    log("Prochaines etapes :")
    log("  1. Redemarrer l'API si necessaire pour recharger le module :")
    log("     (en general l'agent est instancie a chaque scan,")
    log("     un POST /api/universe/scan devrait suffire)")
    log("  2. Declencher un scan :")
    log("     POST /api/universe/scan")
    log("  3. Verifier : py -3.13 .\\nextones-check-reet-status.py")
    log("     REET devrait apparaitre avec un score, mom12-1, sharpe, etc.")


if __name__ == "__main__":
    main()
