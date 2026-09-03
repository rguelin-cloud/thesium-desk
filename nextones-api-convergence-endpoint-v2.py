# -*- coding: utf-8 -*-
"""
[PATCH_API_CONVERGENCE_ENDPOINT_V2]

Fix du bug d'insertion v1 : c.index("if __name__") matchait L22 (commentaire)
au lieu de L215 (vrai code). On utilise regex multiline + ancrage debut de ligne.

Cible : api_server_with_static.py
Marker : # [API_CONVERGENCE_V1]

Lance :
  py -3.13 nextones-api-convergence-endpoint-v2.py
"""
import sys
import io
import os
import ast
import py_compile
import shutil
import re
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API = os.path.join(ROOT, "api_server_with_static.py")
MARKER = "# [API_CONVERGENCE_V1]"
TS = datetime.now().strftime("%Y%m%d-%H%M%S")

ENDPOINT_CODE = '''

# =============================================================================
# [API_CONVERGENCE_V1] Convergence Engine snapshot endpoint
# =============================================================================
@app.get("/api/convergence/snapshot")
async def get_convergence_snapshot(cycle_id: str = None):
    """[API_CONVERGENCE_V1]
    Retourne le snapshot Convergence Engine pour un cycle donne.
    Si cycle_id non fourni, prend le plus recent.
    """
    import json as _json
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Resolution cycle_id
        resolved_cid = cycle_id
        if not resolved_cid:
            cur = conn.execute(
                "SELECT cycle_id FROM convergence_snapshots "
                "ORDER BY rowid DESC LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                resolved_cid = row["cycle_id"]
        if not resolved_cid:
            return {"status": "empty", "cycle_id": None, "rows": [], "totals": {}}

        cur = conn.execute(
            "SELECT MAX(created_at) AS created_at FROM convergence_snapshots "
            "WHERE cycle_id = ?",
            (resolved_cid,)
        )
        created_at = cur.fetchone()["created_at"]

        cur = conn.execute("""
            SELECT ticker, is_crypto, direction_consensus, sizing_multiplier,
                   convergence_pct, n_aligned, n_present, forced_exit, drift,
                   buckets_json
            FROM convergence_snapshots
            WHERE cycle_id = ?
        """, (resolved_cid,))

        rows = []
        n_fe = 0
        n_dr = 0
        n_strong = 0
        n_conflict = 0
        n_neutral = 0

        for r in cur.fetchall():
            _mult = r["sizing_multiplier"]
            mult = float(_mult) if _mult is not None else 1.0
            cons = r["direction_consensus"] or ""
            _fe = r["forced_exit"]
            fe = int(_fe) if _fe is not None else 0
            _dr = r["drift"]
            dr = int(_dr) if _dr is not None else 0
            n_al = int(r["n_aligned"] or 0)

            if fe:
                regime_label = "forced_exit"
                n_fe += 1
            elif dr:
                regime_label = "drift"
                n_dr += 1
            elif mult >= 1.0 and n_al >= 3:
                regime_label = "strong_" + cons
                n_strong += 1
            elif mult < 1.0:
                regime_label = "conflict_" + cons
                n_conflict += 1
            else:
                regime_label = "neutral_stable"
                n_neutral += 1

            buckets = {}
            try:
                if r["buckets_json"]:
                    buckets = _json.loads(r["buckets_json"])
            except Exception:
                buckets = {}

            rows.append({
                "ticker": r["ticker"],
                "is_crypto": int(r["is_crypto"] or 0),
                "direction_consensus": cons,
                "sizing_multiplier": round(mult, 3),
                "convergence_pct": round(float(r["convergence_pct"] or 0), 3),
                "n_aligned": n_al,
                "n_present": int(r["n_present"] or 0),
                "forced_exit": fe,
                "drift": dr,
                "regime_label": regime_label,
                "buckets": buckets,
            })

        def _sort_key(x):
            return (
                -x["forced_exit"],
                -x["drift"],
                x["sizing_multiplier"],
                x["ticker"],
            )
        rows.sort(key=_sort_key)

        return {
            "status": "ok",
            "cycle_id": resolved_cid,
            "created_at": created_at,
            "totals": {
                "n_tickers": len(rows),
                "forced_exit": n_fe,
                "drift": n_dr,
                "strong": n_strong,
                "conflict": n_conflict,
                "neutral": n_neutral,
            },
            "rows": rows,
        }
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "detail": str(e),
            "traceback": traceback.format_exc(),
        }
    finally:
        conn.close()

'''


def main():
    if not os.path.exists(API):
        print(f"[ERR] {API} introuvable")
        sys.exit(1)

    with open(API, "r", encoding="utf-8-sig") as f:
        c = f.read()

    if MARKER in c:
        print(f"[SKIP] {MARKER} deja present")
        sys.exit(0)

    bk = API + f".bak-conv-api-v2-{TS}"
    shutil.copy2(API, bk)
    print(f"[OK] Backup : {bk}")

    # Cherche la VRAIE ligne 'if __name__' (en debut de ligne, pas dans un commentaire)
    pattern = re.compile(r"^if __name__\s*==\s*[\"']__main__[\"']\s*:\s*$", re.MULTILINE)
    m = pattern.search(c)
    if not m:
        print("[ERR] if __name__ introuvable via regex stricte")
        # Fallback : on l'ajoute en fin de fichier juste avant le bloc UTF-8 patch
        if "# ---------- UTF-8 StaticFiles patch ----------" in c:
            idx = c.index("# ---------- UTF-8 StaticFiles patch ----------")
            new_c = c[:idx] + ENDPOINT_CODE + "\n\n" + c[idx:]
            print(f"[OK] Endpoint insere avant UTF-8 patch (offset {idx})")
        else:
            # Vraiment dernier recours : fin de fichier
            new_c = c.rstrip() + "\n" + ENDPOINT_CODE + "\n"
            print("[OK] Endpoint ajoute en fin de fichier")
    else:
        idx = m.start()
        new_c = c[:idx] + ENDPOINT_CODE + "\n\n" + c[idx:]
        print(f"[OK] Endpoint insere avant 'if __name__' (offset {idx})")

    # Validation
    try:
        ast.parse(new_c)
        print("[OK] ast.parse OK")
    except SyntaxError as e:
        print(f"[ERR] SyntaxError : {e}")
        print(f"      Ligne : {e.lineno}")
        sys.exit(1)

    tmp = API + ".tmp-conv-api-v2"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_c)
    try:
        py_compile.compile(tmp, doraise=True)
        print("[OK] py_compile OK")
    except py_compile.PyCompileError as e:
        print(f"[ERR] py_compile : {e}")
        sys.exit(1)

    os.replace(tmp, API)
    print(f"[OK] Ecrit : {os.path.basename(API)}")
    print()
    print("Test :")
    print("  Restart uvicorn puis dans une autre fenetre :")
    print('  curl http://localhost:8000/api/convergence/snapshot')


if __name__ == "__main__":
    main()
