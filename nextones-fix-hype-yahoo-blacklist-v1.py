# -*- coding: utf-8 -*-
"""
nextones-fix-hype-yahoo-blacklist-v1.py

Fix: HYPE-USD n'existe pas sur Yahoo Finance -> spam log "Parse error".

Strategie:
  - Ajoute une constante YAHOO_BLACKLIST = {"HYPE"} dans data_ingestion.py
  - Dans la boucle run_ingestion, skip ces tickers AVANT l'appel a fetch_yahoo_prices
  - Log "skip (no Yahoo data)" en INFO au lieu d'un parse error

Marker idempotent: [YAHOO_BLACKLIST_V1]  (en COMMENTAIRE Python, pas en clair)

Backup: data_ingestion.py.bak.YYYYMMDDTHHMMSS
Validation: ast.parse + py_compile + smoke import via subprocess
"""

import ast
import datetime
import re
import shutil
import subprocess
import sys
from pathlib import Path

P = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_ingestion.py")

MARKER = "[YAHOO_BLACKLIST_V1]"
CONST_BLOCK = '''
# {marker} BEGIN  ---------------------------------------------------
# Tickers a NE PAS passer a Yahoo Finance (token absent / delisted).
# Ces tickers sont alimentes par d'autres sources (ex: data_crypto / CoinGecko).
YAHOO_BLACKLIST = {{"HYPE"}}
# {marker} END  -----------------------------------------------------
'''.format(marker=MARKER).strip() + "\n"

OLD_LOOP = (
    "        for inst in instruments:\n"
    "            # Crypto tickers need -USD suffix for Yahoo Finance\n"
    "            yahoo_ticker = inst[\"ticker\"]\n"
    "            if inst[\"asset_class\"] == \"crypto\":\n"
    "                yahoo_ticker = f\"{inst['ticker']}-USD\"\n"
    "            rows = fetch_yahoo_prices(yahoo_ticker, period=period)\n"
)

NEW_LOOP = (
    "        for inst in instruments:\n"
    "            # Crypto tickers need -USD suffix for Yahoo Finance\n"
    "            yahoo_ticker = inst[\"ticker\"]\n"
    "            # " + MARKER + " : skip tickers absents de Yahoo (gestion CoinGecko ailleurs)\n"
    "            if inst[\"ticker\"] in YAHOO_BLACKLIST:\n"
    "                print(f\"[data_ingestion] skip {inst['ticker']} (Yahoo blacklist, source alternative)\")\n"
    "                continue\n"
    "            if inst[\"asset_class\"] == \"crypto\":\n"
    "                yahoo_ticker = f\"{inst['ticker']}-USD\"\n"
    "            rows = fetch_yahoo_prices(yahoo_ticker, period=period)\n"
)


def main():
    if not P.exists():
        print(f"FAIL: {P} introuvable")
        return 1

    src = P.read_text(encoding="utf-8-sig", errors="replace")
    original = src

    # Idempotence
    if MARKER in src:
        print(f"[skip] marker {MARKER} deja present")
        return 0

    # Backup
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = P.with_suffix(P.suffix + f".bak.{ts}")
    shutil.copy2(P, backup)
    print(f"[backup] {backup.name}")

    # Insert constant AFTER YAHOO_BASE definition
    yahoo_base_pat = re.compile(
        r'(YAHOO_BASE\s*=\s*["\'][^"\']+["\']\s*\n)',
        re.MULTILINE,
    )
    m = yahoo_base_pat.search(src)
    if not m:
        print("FAIL: YAHOO_BASE introuvable, je ne sais pas ou inserer la constante")
        return 1
    insert_pos = m.end()
    src = src[:insert_pos] + "\n" + CONST_BLOCK + src[insert_pos:]
    print(f"[insert] YAHOO_BLACKLIST apres YAHOO_BASE")

    # Replace the loop
    if OLD_LOOP not in src:
        print("FAIL: bloc original de la boucle introuvable - patche manuel requis")
        shutil.copy2(backup, P)
        return 1
    src = src.replace(OLD_LOOP, NEW_LOOP, 1)
    print(f"[replace] boucle for inst patchee avec garde blacklist")

    # Validation ast
    try:
        ast.parse(src)
    except SyntaxError as e:
        print(f"FAIL ast.parse L{e.lineno}: {e.msg}")
        shutil.copy2(backup, P)
        return 1

    if src == original:
        print("[noop] aucun changement")
        return 0

    # Write
    P.write_text(src, encoding="utf-8", newline="\n")
    print(f"[write] {P.name} sauvegarde ({len(src)} chars)")

    # Verification post-ecriture
    re_read = P.read_text(encoding="utf-8-sig", errors="replace")
    if MARKER not in re_read:
        print("FAIL: marker absent apres ecriture")
        return 1
    if "YAHOO_BLACKLIST" not in re_read:
        print("FAIL: constante absente apres ecriture")
        return 1

    # py_compile
    import py_compile
    try:
        py_compile.compile(str(P), doraise=True)
        print("[verify] py_compile OK")
    except Exception as e:
        print(f"FAIL py_compile: {e}")
        shutil.copy2(backup, P)
        return 1

    # SMOKE IMPORT via subprocess isole (apprentissage du bug V2)
    print("[smoke] import data_ingestion dans subprocess...")
    proc = subprocess.run(
        [sys.executable, "-c", "import data_ingestion; print('IMPORT_OK')"],
        cwd=str(P.parent),
        capture_output=True,
        text=True,
        timeout=20,
    )
    if proc.returncode == 0 and "IMPORT_OK" in proc.stdout:
        print("[smoke] import OK")
    else:
        print(f"FAIL smoke import: rc={proc.returncode}")
        print(f"  stdout: {proc.stdout}")
        print(f"  stderr: {proc.stderr}")
        shutil.copy2(backup, P)
        print("[rollback] backup restaure")
        return 1

    print("\nOK - relancer uvicorn pour appliquer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
