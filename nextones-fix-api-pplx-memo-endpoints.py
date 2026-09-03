# -*- coding: utf-8 -*-
"""
Patch api_server.py : ajoute les endpoints /api/pplx/memo et /api/pplx/memo/list.
Idempotent via marker [PPLX_MEMO_API_V1].

Usage:
    py -3.13 nextones-fix-api-pplx-memo-endpoints.py
"""
import sys
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
TARGET = ROOT / "api_server.py"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
MARKER = "[PPLX_MEMO_API_V1]"

# Bloc a inserter : 2 endpoints + helper DB
PATCH_BLOCK = f'''
# === {MARKER} : MemoAgent Perplexity - on-demand memo par symbole ===
from pathlib import Path as _P_memo
_db_memo = _P_memo(__file__).resolve().parent / "thesium.db"

def _memo_db_conn():
    import sqlite3 as _sql
    return _sql.connect(str(_db_memo))


@app.get("/api/pplx/memo")
def get_pplx_memo(symbol: str, force: bool = False):
    """
    Renvoie le memo IA pour un symbole.
    - symbol : ticker (ex: NVDA, BTC, ETH)
    - force : si True, bypass le cache et appelle Perplexity
    Cache : 1h (geree par MemoAgent + pplx_client)
    """
    import json as _json
    import time as _time
    sym = (symbol or "").upper().strip()
    if not sym or len(sym) > 12:
        return {{"available": False, "error": "symbol invalide"}}

    # Sans force : tente le cache DB d'abord (rapide)
    if not force:
        try:
            cx = _memo_db_conn()
            row = cx.execute(
                "SELECT payload_json, citations_json, generated_at, generated_ts, model, elapsed_s "
                "FROM pplx_memo_context WHERE symbol=?",
                (sym,)
            ).fetchone()
            cx.close()
            if row:
                payload_json, citations_json, generated_at, generated_ts, model, elapsed_s = row
                age = int(_time.time()) - int(generated_ts)
                return {{
                    "available": True,
                    "symbol": sym,
                    "payload": _json.loads(payload_json),
                    "citations": _json.loads(citations_json) if citations_json else [],
                    "generated_at": generated_at,
                    "model": model,
                    "elapsed_s": elapsed_s,
                    "age_seconds": age,
                    "cached": True
                }}
        except Exception as _e:
            print(f"[PPLX-MEMO-API] cache lookup failed: {{_e}}")

    # Force ou cache miss : appel agent (peut prendre 8-15s)
    try:
        from pplx_memo_agent import run_memo_agent
        result = run_memo_agent(sym, force=force)
        if not result.get("payload"):
            return {{
                "available": False,
                "symbol": sym,
                "error": result.get("error", "payload vide")
            }}
        result["available"] = True
        return result
    except Exception as _e:
        import traceback
        print(f"[PPLX-MEMO-API] agent error: {{_e}}")
        print(traceback.format_exc())
        return {{"available": False, "symbol": sym, "error": str(_e)}}


@app.get("/api/pplx/memo/list")
def list_pplx_memos():
    """Liste tous les symbols avec un memo en cache, tries par recence."""
    import json as _json
    import time as _time
    try:
        cx = _memo_db_conn()
        rows = cx.execute(
            "SELECT symbol, generated_at, generated_ts, model, elapsed_s "
            "FROM pplx_memo_context ORDER BY generated_ts DESC LIMIT 100"
        ).fetchall()
        cx.close()
        now = int(_time.time())
        items = []
        for sym, gen_at, gen_ts, model, elapsed_s in rows:
            age_min = (now - int(gen_ts)) // 60
            items.append({{
                "symbol": sym,
                "generated_at": gen_at,
                "model": model,
                "elapsed_s": elapsed_s,
                "age_minutes": age_min,
                "fresh": age_min < 60
            }})
        return {{"available": True, "count": len(items), "items": items}}
    except Exception as _e:
        return {{"available": False, "error": str(_e), "items": []}}
# === END {MARKER} ===
'''


def main():
    if not TARGET.exists():
        print(f"[KO] Fichier introuvable : {TARGET}")
        sys.exit(1)

    text = TARGET.read_text(encoding="utf-8-sig")
    # Detection marker (idempotent)
    if MARKER in text:
        print(f"[SKIP] Marker {MARKER} deja present, rien a faire.")
        return

    # Backup
    bak = TARGET.with_name(TARGET.name + f".bak_memo_{TS}")
    bak.write_text(text, encoding="utf-8")
    print(f"[BAK] {bak.name}")

    # Compte avant
    before_routes = len(re.findall(r"@app\.(get|post|put|delete|patch)\(", text))
    before_defs = len(re.findall(r"^def\s+\w+", text, flags=re.MULTILINE))
    print(f"[BEFORE] {before_routes} routes, {before_defs} top-level def")

    # Append en fin de fichier (les endpoints sont juste des routes supplementaires)
    if not text.endswith("\n"):
        text += "\n"
    new_text = text + PATCH_BLOCK + "\n"

    TARGET.write_text(new_text, encoding="utf-8", newline="\n")

    # Compte apres
    after = TARGET.read_text(encoding="utf-8")
    after_routes = len(re.findall(r"@app\.(get|post|put|delete|patch)\(", after))
    after_defs = len(re.findall(r"^def\s+\w+", after, flags=re.MULTILINE))
    print(f"[AFTER]  {after_routes} routes, {after_defs} top-level def")
    print(f"[DELTA]  +{after_routes - before_routes} routes, +{after_defs - before_defs} def")
    print(f"[MARKER] {MARKER} present : {MARKER in after}")

    # Validation syntaxe
    import ast
    try:
        ast.parse(after)
        print("[SYNTAX] OK")
    except SyntaxError as e:
        print(f"[SYNTAX] KO : {e}")
        # Restore
        TARGET.write_text(text, encoding="utf-8", newline="\n")
        print("[RESTORED] Patch annule.")
        sys.exit(2)

    print("\n=== Patch applique avec succes ===")
    print("Redemarre l'API : py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")


if __name__ == "__main__":
    main()
