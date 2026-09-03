# -*- coding: utf-8 -*-
"""
nextones-add-crypto-cg-scheduler-v1.py

Ajoute un job scheduler qui rafraichit les prix crypto via CoinGecko
(pour les tickers absents de Yahoo, ex: HYPE).

Modifications:
  A. data_crypto.py:
     - Ajoute 'HYPE': 'hyperliquid' dans CG_MAP
     - Ajoute une fonction refresh_crypto_prices_to_db() qui upsert les prix
       en table prices (date=today, OHLC=price, marker [CG_REFRESH_TO_DB_V1])
  B. api_server.py:
     - Ajoute un job scheduler interval 2h appelant refresh_crypto_prices_to_db
     - Marker [SCHEDULER_CRYPTO_CG_V1]

Validations:
  - ast.parse + py_compile par fichier modifie
  - smoke import data_crypto + api_server via subprocess
  - rollback automatique sur echec

Backups:
  - data_crypto.py.bak.YYYYMMDDTHHMMSS
  - api_server.py.bak.YYYYMMDDTHHMMSS
"""

import ast
import datetime
import re
import shutil
import subprocess
import sys
import py_compile
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DATA_CRYPTO = ROOT / "data_crypto.py"
API_SERVER = ROOT / "api_server.py"

MARKER_CG_HYPE = "[CG_MAP_HYPE_V1]"
MARKER_CG_REFRESH = "[CG_REFRESH_TO_DB_V1]"
MARKER_SCHED = "[SCHEDULER_CRYPTO_CG_V1]"

# ---- Bloc 1 : ajout HYPE dans CG_MAP (insertion avant le } fermant) ----
HYPE_LINE = "    'HYPE':  'hyperliquid',  # " + MARKER_CG_HYPE + "\n"

# ---- Bloc 2 : nouvelle fonction refresh_crypto_prices_to_db ----
NEW_FUNC = '''

# {marker} BEGIN  ---------------------------------------------------
def refresh_crypto_prices_to_db():
    """Refresh CoinGecko prices and upsert into the 'prices' table.

    Pour chaque ticker du CG_MAP qui existe dans la table 'instruments',
    insere une ligne OHLC synthetique (O=H=L=C=price) datee de today.
    Utilise INSERT OR REPLACE pour etre idempotent sur la cle (instrument_id, date).

    Appele par le scheduler APScheduler ({marker}).
    Retourne un dict {{updated, skipped, errors}}.
    """
    import sqlite3
    from datetime import datetime as _dt
    from models import get_db
    from data_ingestion import upsert_prices

    result = {{"updated": [], "skipped": [], "errors": []}}
    prices = fetch_crypto_prices()
    if not prices:
        print("[crypto_cg] fetch_crypto_prices() vide - skip")
        return result

    today = _dt.utcnow().strftime("%Y-%m-%d")
    conn = get_db()
    try:
        for p in prices:
            ticker = p.get("ticker")
            price = p.get("price")
            if not ticker or price is None:
                result["skipped"].append(ticker)
                continue
            # Find instrument
            row = conn.execute(
                "SELECT id FROM instruments WHERE ticker = ?", (ticker,)
            ).fetchone()
            if not row:
                result["skipped"].append(ticker)
                continue
            instrument_id = row[0] if not hasattr(row, "keys") else row["id"]
            # Build OHLC synthetique
            ohlc_row = {{
                "date": today,
                "open": price, "high": price,
                "low": price,  "close": price,
                "volume": p.get("volume_24h") or 0,
            }}
            try:
                upsert_prices(conn, instrument_id, [ohlc_row])
                result["updated"].append(ticker)
            except Exception as e:
                result["errors"].append({{"ticker": ticker, "err": str(e)}})
        conn.commit()
        print(f"[crypto_cg] updated={{len(result['updated'])}} "
              f"skipped={{len(result['skipped'])}} errors={{len(result['errors'])}}")
    finally:
        conn.close()
    return result
# {marker} END  -----------------------------------------------------
'''.replace("{marker}", MARKER_CG_REFRESH)

# ---- Bloc 3 : nouveau job scheduler dans api_server.py ----
# On va inserer apres la ligne refresh_pplx_geo (L142) et avant scheduler.start()
NEW_JOB_BLOCK = '''
    # {marker} BEGIN  ----------------------------------------------
    def refresh_crypto_cg():
        """Refresh crypto prices via CoinGecko for tickers absents from Yahoo."""
        try:
            print("[scheduler] Refreshing CoinGecko crypto prices...")
            import data_crypto
            res = data_crypto.refresh_crypto_prices_to_db()
            print(f"[scheduler] CG crypto refreshed: updated={{len(res.get('updated', []))}}")
        except Exception as e:
            print(f"[scheduler] CG crypto refresh error: {{e}}")

    scheduler.add_job(refresh_crypto_cg, 'interval', hours=2,
                      id='refresh_crypto_cg',
                      next_run_time=_now + _td(minutes=1))
    # {marker} END  ------------------------------------------------
'''.replace("{marker}", MARKER_SCHED)


def section(t):
    print(f"\n{'='*70}\n  {t}\n{'='*70}")


def patch_data_crypto():
    section("PATCH 1/2 : data_crypto.py")
    src = DATA_CRYPTO.read_text(encoding="utf-8-sig", errors="replace")
    original = src

    if MARKER_CG_HYPE in src and MARKER_CG_REFRESH in src:
        print("[skip] markers deja presents dans data_crypto.py")
        return True, None

    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = DATA_CRYPTO.with_suffix(DATA_CRYPTO.suffix + f".bak.{ts}")
    shutil.copy2(DATA_CRYPTO, backup)
    print(f"[backup] {backup.name}")

    # A. Inserer HYPE dans CG_MAP juste avant le } fermant
    if MARKER_CG_HYPE not in src:
        # Trouve "CG_MAP = {" puis le "}" qui ferme
        m = re.search(r"CG_MAP\s*=\s*\{", src)
        if not m:
            print("FAIL: CG_MAP introuvable")
            shutil.copy2(backup, DATA_CRYPTO)
            return False, backup
        # Cherche le } fermant a partir de m.end()
        close_pos = src.find("}", m.end())
        if close_pos < 0:
            print("FAIL: accolade fermante CG_MAP introuvable")
            shutil.copy2(backup, DATA_CRYPTO)
            return False, backup
        # Insere la ligne HYPE juste avant le }
        src = src[:close_pos] + HYPE_LINE + src[close_pos:]
        print("[insert] HYPE ajoute a CG_MAP")

    # B. Ajouter la fonction refresh_crypto_prices_to_db a la fin du fichier
    if MARKER_CG_REFRESH not in src:
        src = src.rstrip() + "\n" + NEW_FUNC
        print("[append] fonction refresh_crypto_prices_to_db ajoutee")

    # ast.parse
    try:
        ast.parse(src)
    except SyntaxError as e:
        print(f"FAIL ast.parse L{e.lineno}: {e.msg}")
        shutil.copy2(backup, DATA_CRYPTO)
        return False, backup

    if src == original:
        print("[noop]")
        return True, backup

    DATA_CRYPTO.write_text(src, encoding="utf-8", newline="\n")
    print(f"[write] data_crypto.py sauvegarde ({len(src)} chars)")

    # py_compile
    try:
        py_compile.compile(str(DATA_CRYPTO), doraise=True)
        print("[verify] py_compile OK")
    except Exception as e:
        print(f"FAIL py_compile: {e}")
        shutil.copy2(backup, DATA_CRYPTO)
        return False, backup

    # smoke import
    proc = subprocess.run(
        [sys.executable, "-c",
         "import data_crypto; "
         "assert 'HYPE' in data_crypto.CG_MAP, 'HYPE absent CG_MAP'; "
         "assert hasattr(data_crypto, 'refresh_crypto_prices_to_db'), 'fonction absente'; "
         "print('IMPORT_OK')"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=20,
    )
    if proc.returncode == 0 and "IMPORT_OK" in proc.stdout:
        print("[smoke] import OK")
        return True, backup
    print(f"FAIL smoke import: rc={proc.returncode}")
    print(f"  stdout: {proc.stdout}")
    print(f"  stderr: {proc.stderr}")
    shutil.copy2(backup, DATA_CRYPTO)
    print("[rollback] backup restaure")
    return False, backup


def patch_api_server():
    section("PATCH 2/2 : api_server.py")
    src = API_SERVER.read_text(encoding="utf-8-sig", errors="replace")
    original = src

    if MARKER_SCHED in src:
        print("[skip] marker deja present dans api_server.py")
        return True, None

    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = API_SERVER.with_suffix(API_SERVER.suffix + f".bak.{ts}")
    shutil.copy2(API_SERVER, backup)
    print(f"[backup] {backup.name}")

    # On insere NEW_JOB_BLOCK juste apres la ligne refresh_pplx_geo
    pat = re.compile(
        r"(scheduler\.add_job\(refresh_pplx_geo,[^\n]+\n)",
    )
    m = pat.search(src)
    if not m:
        print("FAIL: ligne refresh_pplx_geo introuvable")
        shutil.copy2(backup, API_SERVER)
        return False, backup

    insert_pos = m.end()
    src = src[:insert_pos] + NEW_JOB_BLOCK + src[insert_pos:]
    print("[insert] job refresh_crypto_cg ajoute apres refresh_pplx_geo")

    # ast.parse
    try:
        ast.parse(src)
    except SyntaxError as e:
        print(f"FAIL ast.parse L{e.lineno}: {e.msg}")
        shutil.copy2(backup, API_SERVER)
        return False, backup

    if src == original:
        print("[noop]")
        return True, backup

    API_SERVER.write_text(src, encoding="utf-8", newline="\n")
    print(f"[write] api_server.py sauvegarde ({len(src)} chars)")

    # py_compile
    try:
        py_compile.compile(str(API_SERVER), doraise=True)
        print("[verify] py_compile OK")
    except Exception as e:
        print(f"FAIL py_compile: {e}")
        shutil.copy2(backup, API_SERVER)
        return False, backup

    # smoke import (CRITIQUE - leçon du bug V2)
    proc = subprocess.run(
        [sys.executable, "-c",
         "import api_server; "
         "print('IMPORT_OK')"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=30,
    )
    if proc.returncode == 0 and "IMPORT_OK" in proc.stdout:
        print("[smoke] import OK")
        return True, backup
    print(f"FAIL smoke import: rc={proc.returncode}")
    print(f"  stdout: {proc.stdout}")
    print(f"  stderr: {proc.stderr}")
    shutil.copy2(backup, API_SERVER)
    print("[rollback] backup restaure")
    return False, backup


def main():
    if not DATA_CRYPTO.exists():
        print(f"FAIL: {DATA_CRYPTO} introuvable")
        return 1
    if not API_SERVER.exists():
        print(f"FAIL: {API_SERVER} introuvable")
        return 1

    ok1, _ = patch_data_crypto()
    if not ok1:
        print("\nFAIL patch data_crypto.py - api_server.py non modifie")
        return 1

    ok2, _ = patch_api_server()
    if not ok2:
        print("\nFAIL patch api_server.py - data_crypto.py reste patche (no rollback transverse)")
        print("  Pour rollback complet de data_crypto.py, restaurer le backup .bak manuellement")
        return 1

    print("\n" + "=" * 70)
    print("  OK - 2 patches appliques. Relancer uvicorn pour activer.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
