# -*- coding: utf-8 -*-
"""
[CG_THROTTLE_V2]
Ajoute throttle + retry+backoff sur les appels CoinGecko dans
universe_expansion_agent.py :
  - time.sleep(2.5) avant chaque requests.get vers api.coingecko.com
  - User-Agent identifie (nextones-thesium/1.0)
  - retry automatique sur 429 : 3 tentatives, backoff 10s -> 20s -> 40s

Strategie : on remplace chaque ligne du type
    r = requests.get(<url_coingecko>, ...)
par un appel a une nouvelle fonction _cg_get(url, **kwargs) qui :
    - applique le throttle
    - retry sur 429
    - leve l'exception apres 3 echecs

Idempotent via marker # [CG_THROTTLE_V2].
"""
import re
import shutil
import datetime
import ast
import py_compile
from pathlib import Path

AGENT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\universe_expansion_agent.py")
MARK = "# [CG_THROTTLE_V2]"

HELPER_BLOCK = '''
# [CG_THROTTLE_V2] === BEGIN ============================================
import time as _cg_time_mod
_CG_LAST_CALL_TS = [0.0]  # mutable container (module-level)
_CG_MIN_INTERVAL = 2.5    # seconds between calls
_CG_HEADERS = {"User-Agent": "nextones-thesium/1.0"}

def _cg_get(url, timeout=20, params=None, **kwargs):
    """GET CoinGecko avec throttle + retry 429 (3 tentatives, backoff 10/20/40s)."""
    import requests as _cg_requests
    delays = [10.0, 20.0, 40.0]
    last_exc = None
    for attempt in range(len(delays) + 1):
        # Throttle global
        now = _cg_time_mod.monotonic()
        elapsed = now - _CG_LAST_CALL_TS[0]
        if elapsed < _CG_MIN_INTERVAL:
            _cg_time_mod.sleep(_CG_MIN_INTERVAL - elapsed)
        _CG_LAST_CALL_TS[0] = _cg_time_mod.monotonic()
        try:
            headers = dict(_CG_HEADERS)
            if "headers" in kwargs and kwargs["headers"]:
                headers.update(kwargs.pop("headers"))
            r = _cg_requests.get(url, timeout=timeout, params=params, headers=headers, **kwargs)
            if r.status_code == 429 and attempt < len(delays):
                wait = delays[attempt]
                print(f"[CG_THROTTLE] 429 sur {url} -> wait {wait}s (tentative {attempt+1}/{len(delays)+1})")
                _cg_time_mod.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except Exception as e:
            last_exc = e
            if attempt < len(delays):
                wait = delays[attempt]
                print(f"[CG_THROTTLE] {type(e).__name__} sur {url} -> wait {wait}s")
                _cg_time_mod.sleep(wait)
                continue
            raise
    if last_exc:
        raise last_exc
# [CG_THROTTLE_V2] === END ==============================================
'''


def main():
    if not AGENT.exists():
        print(f"[ERR] introuvable : {AGENT}")
        return

    raw = AGENT.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        txt = raw[3:].decode('utf-8', errors='replace')
    else:
        txt = raw.decode('utf-8', errors='replace')

    if MARK in txt:
        print(f"[SKIP] {MARK} deja present")
        return

    # 1) Inserer le helper apres la derniere ligne d'import en tete de fichier
    #    On insere juste avant la premiere ligne qui n'est ni import ni vide ni commentaire.
    lines = txt.split("\n")
    insert_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("import ") or stripped.startswith("from "):
            insert_idx = i + 1
            continue
        break
    new_lines = lines[:insert_idx] + [HELPER_BLOCK] + lines[insert_idx:]
    txt = "\n".join(new_lines)
    print(f"[OK] helper insere a la ligne {insert_idx}")

    # 2) Remplacer chaque requests.get(...coingecko.com...) par _cg_get(...)
    #    pattern : requests.get(<url_qui_contient_coingecko.com>, ...) ou variable
    #    On vise les lignes du type:  r = requests.get(url, timeout=..., params=...)
    #    ou  resp = requests.get(f"https://api.coingecko.com/...", ...)
    #    Strategie simple : si la ligne contient "requests.get" ET ("coingecko" OR le call utilise
    #    une url construite via base CG), on substitue.
    #
    # Pour rester sur :
    #  - replace exact "requests.get(" -> "_cg_get(" UNIQUEMENT sur des lignes contenant "coingecko"
    #    OU dans une fonction nommee fetch_top_cryptos/fetch_crypto_history.

    # Etape 2a : sur les lignes contenant "coingecko" + "requests.get"
    n_inline = 0
    new_lines = []
    for line in txt.split("\n"):
        if "requests.get(" in line and "coingecko" in line.lower():
            line = line.replace("requests.get(", "_cg_get(")
            n_inline += 1
        new_lines.append(line)
    txt = "\n".join(new_lines)
    print(f"[OK] remplacements inline (coingecko in line) : {n_inline}")

    # Etape 2b : dans le corps de fetch_crypto_history et fetch_top_cryptos,
    # remplacer tout "requests.get(" restant par "_cg_get(".
    def replace_in_func(text, func_name):
        # Trouver la signature
        pat = re.compile(r'^(def\s+' + re.escape(func_name) + r'\b[^\n]*:\s*\n)', re.MULTILINE)
        m = pat.search(text)
        if not m:
            return text, 0
        start = m.end()
        # Trouver la fin de fonction : prochaine ligne 'def ' ou 'class ' a indent 0
        rest = text[start:]
        end_m = re.search(r'^(def\s|class\s)', rest, re.MULTILINE)
        end = start + (end_m.start() if end_m else len(rest))
        body = text[start:end]
        new_body, n = re.subn(r'\brequests\.get\(', '_cg_get(', body)
        return text[:start] + new_body + text[end:], n

    for fname in ("fetch_crypto_history", "fetch_top_cryptos"):
        txt, n = replace_in_func(txt, fname)
        print(f"[OK] remplacements dans {fname} : {n}")

    # 3) Validation
    try:
        ast.parse(txt)
        print("[OK] ast.parse OK")
    except SyntaxError as e:
        print(f"[ERR SYNTAX] {e}")
        # ecrit en .bad pour inspection
        bad = AGENT.with_suffix(".py.bad-throttle-v2")
        bad.write_text(txt, encoding="utf-8")
        print(f"[ERR] dump dans {bad.name}")
        return

    # 4) Backup + ecriture
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bak = AGENT.with_suffix(f".py.bak-{ts}-pre-throttle-v2")
    shutil.copy2(AGENT, bak)
    print(f"[BAK] {bak.name}")

    AGENT.write_bytes(txt.encode('utf-8'))

    try:
        py_compile.compile(str(AGENT), doraise=True)
        print("[OK] py_compile OK")
    except py_compile.PyCompileError as e:
        print(f"[ERR py_compile] {e}")
        return

    n_mark = txt.count(MARK)
    print(f"[OK] {n_mark} occurrence(s) du marker dans le fichier final")
    print()
    print("Patch applique. Pour tester :")
    print("  1) Redemarrer l'API si tu veux le throttle dispo cote serveur :")
    print("     py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print("  2) py -3.13 .\\nextones-trigger-crypto-scan.py")
    print()
    print("Note : avec 2.5s entre calls + retry 10/20/40s, un scan top_n=30 sur cryptos")
    print("peut prendre ~90-180s mais devrait recuperer toutes les histoires.")


if __name__ == "__main__":
    main()
