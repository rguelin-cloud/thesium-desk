# -*- coding: utf-8 -*-
"""
nextones-fix-crypto-cg-hype-only-v2.py

Restreint refresh_crypto_prices_to_db() aux SEULS tickers de YAHOO_BLACKLIST
(actuellement HYPE) pour ne pas ecraser le vrai OHLC Yahoo des autres crypto
(BTC/ETH/LINK/SOL/ZEC).

Strategie:
  - Modifie refresh_crypto_prices_to_db dans data_crypto.py pour filtrer
    sur YAHOO_BLACKLIST importe depuis data_ingestion.
  - Si ticker n'est pas dans la blacklist -> skip (vrai OHLC YF preserve).
  - Marker idempotent: [CG_REFRESH_HYPE_ONLY_V2]

Backup data_crypto.py.bak.YYYYMMDDTHHMMSS
Validation: ast.parse + py_compile + smoke import (verifie comportement)
"""

import ast
import datetime
import re
import shutil
import subprocess
import sys
import py_compile
from pathlib import Path

P = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_crypto.py")

MARKER = "[CG_REFRESH_HYPE_ONLY_V2]"

# Le bloc cible : la boucle a l'interieur de refresh_crypto_prices_to_db
# On va inserer un filtre apres le "for p in prices:" et avant le "ticker = p.get('ticker')"
# Approche plus robuste : remplacer le bloc complet en s'appuyant sur le marker V1
# qui delimite la fonction.

OLD_FUNC_BODY_FRAGMENT = '''        for p in prices:
            ticker = p.get("ticker")
            price = p.get("price")
            if not ticker or price is None:
                result["skipped"].append(ticker)
                continue'''

NEW_FUNC_BODY_FRAGMENT = '''        # ''' + MARKER + ''' : filtre = uniquement tickers YAHOO_BLACKLIST
        try:
            from data_ingestion import YAHOO_BLACKLIST
        except Exception:
            YAHOO_BLACKLIST = {"HYPE"}
        for p in prices:
            ticker = p.get("ticker")
            price = p.get("price")
            if not ticker or price is None:
                result["skipped"].append(ticker)
                continue
            # ''' + MARKER + ''' : ne pas ecraser le vrai OHLC Yahoo des autres crypto
            if ticker not in YAHOO_BLACKLIST:
                result["skipped"].append(ticker)
                continue'''


def main():
    if not P.exists():
        print(f"FAIL: {P} introuvable")
        return 1

    src = P.read_text(encoding="utf-8-sig", errors="replace")
    original = src

    if MARKER in src:
        print(f"[skip] marker {MARKER} deja present")
        return 0

    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = P.with_suffix(P.suffix + f".bak.{ts}")
    shutil.copy2(P, backup)
    print(f"[backup] {backup.name}")

    if OLD_FUNC_BODY_FRAGMENT not in src:
        print("FAIL: fragment original introuvable - le patch V1 a-t-il ete applique ?")
        return 1

    src = src.replace(OLD_FUNC_BODY_FRAGMENT, NEW_FUNC_BODY_FRAGMENT, 1)
    print(f"[replace] filtre YAHOO_BLACKLIST insere dans refresh_crypto_prices_to_db")

    # ast.parse
    try:
        ast.parse(src)
    except SyntaxError as e:
        print(f"FAIL ast.parse L{e.lineno}: {e.msg}")
        shutil.copy2(backup, P)
        return 1

    if src == original:
        print("[noop]")
        return 0

    P.write_text(src, encoding="utf-8", newline="\n")
    print(f"[write] data_crypto.py sauvegarde ({len(src)} chars)")

    # py_compile
    try:
        py_compile.compile(str(P), doraise=True)
        print("[verify] py_compile OK")
    except Exception as e:
        print(f"FAIL py_compile: {e}")
        shutil.copy2(backup, P)
        return 1

    # Smoke import + verification semantique
    proc = subprocess.run(
        [sys.executable, "-c",
         "import data_crypto; "
         "from data_ingestion import YAHOO_BLACKLIST; "
         "assert 'HYPE' in YAHOO_BLACKLIST, 'HYPE pas dans blacklist'; "
         "src = open('data_crypto.py', encoding='utf-8-sig').read(); "
         "assert 'YAHOO_BLACKLIST' in src, 'YAHOO_BLACKLIST pas reference'; "
         "print('IMPORT_OK')"],
        cwd=str(P.parent), capture_output=True, text=True, timeout=20,
    )
    if proc.returncode == 0 and "IMPORT_OK" in proc.stdout:
        print("[smoke] import OK")
        print("\nOK - relancer uvicorn pour activer")
        return 0
    print(f"FAIL smoke import: rc={proc.returncode}")
    print(f"  stdout: {proc.stdout}")
    print(f"  stderr: {proc.stderr}")
    shutil.copy2(backup, P)
    print("[rollback] backup restaure")
    return 1


if __name__ == "__main__":
    sys.exit(main())
