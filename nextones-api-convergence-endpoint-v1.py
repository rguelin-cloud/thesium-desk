# -*- coding: utf-8 -*-
"""
[PATCH_API_CONVERGENCE_ENDPOINT_V1]

Ajoute l'endpoint GET /api/convergence/snapshot a api_server_with_static.py.

Reponse :
{
  "cycle_id": "20260609-091332",
  "created_at": "2026-06-09 11:41:04",
  "totals": {
    "n_tickers": 30,
    "forced_exit": 9,
    "drift": 1,
    "strong": 7,
    "conflict": 0,
    "neutral": 13
  },
  "rows": [
    {
      "ticker": "BTC",
      "is_crypto": 1,
      "direction_consensus": "short",
      "sizing_multiplier": 0.0,
      "convergence_pct": 0.33,
      "n_aligned": 1,
      "n_present": 3,
      "forced_exit": 1,
      "drift": 0,
      "regime_label": "forced_exit",
      "buckets": {
        "L1": {"direction": "neutral", "source": "MacroAgent", "driver": "...", "conviction": 5.0},
        "L3": {"direction": "short", "source": "MicrostructureAgent", "driver": "RSI=72", "conviction": 6.5},
        ...
      }
    },
    ...
  ]
}

Tri : forced_exit en tete, puis drift, puis sizing ASC, puis ticker ASC.

Marker : # [API_CONVERGENCE_V1]

Lance :
  py -3.13 nextones-api-convergence-endpoint-v1.py
"""
import sys
import io
import os
import ast
import py_compile
import shutil
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

        # Created_at de ce cycle (le plus recent)
        cur = conn.execute(
            "SELECT MAX(created_at) AS created_at FROM convergence_snapshots "
            "WHERE cycle_id = ?",
            (resolved_cid,)
        )
        created_at = cur.fetchone()["created_at"]

        # Toutes les lignes du cycle
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

            # Classification
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

            # Parse buckets_json
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

        # Tri : fe -> dr -> sizing ASC -> ticker
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

    # Backup
    bk = API + f".bak-conv-api-{TS}"
    shutil.copy2(API, bk)
    print(f"[OK] Backup : {bk}")

    # Strategie d'insertion : juste avant le bloc final `if __name__ == "__main__"`
    # ou si absent, en fin de fichier.
    if 'if __name__ == "__main__"' in c:
        idx = c.index('if __name__ == "__main__"')
        new_c = c[:idx] + ENDPOINT_CODE + "\n\n" + c[idx:]
        print(f"[OK] Endpoint insere avant if __name__ (position {idx})")
    else:
        new_c = c.rstrip() + "\n" + ENDPOINT_CODE + "\n"
        print("[OK] Endpoint ajoute en fin de fichier")

    # Validation
    try:
        ast.parse(new_c)
        print("[OK] ast.parse OK")
    except SyntaxError as e:
        print(f"[ERR] SyntaxError : {e}")
        sys.exit(1)

    tmp = API + ".tmp-conv-api"
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
    print("  Restart uvicorn puis :")
    print("  curl http://localhost:8000/api/convergence/snapshot")


if __name__ == "__main__":
    main()
