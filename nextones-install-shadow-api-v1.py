# -*- coding: utf-8 -*-
"""
PATCH PHASE 9.6 - Shadow API endpoints
[SHADOW_API_V1]

Injecte 2 endpoints GET dans api_server.py APRES @app.get("/api/backtest/presets")
(L2905), bien AVANT le mount commente L3395.

Routes ajoutees :
  GET /api/shadow/variants       -> liste 4 variants actifs
  GET /api/shadow/perf-rolling   -> derniere row par variant pour window=30

Anchor : '@app.get("/api/backtest/presets")' -> on remonte jusqu a la prochaine
ligne vide apres la fin du handler, puis on insere le bloc.

Strategie idempotente : skip si marker '[SHADOW_API_V1] BEGIN' present.

Backup : .py.bak.<timestamp>
"""
import os
import re
import sys
import time
import ast
import py_compile
import shutil

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API  = os.path.join(BASE, "api_server.py")

MARKER_BEGIN = "[SHADOW_API_V1] BEGIN"
MARKER_END   = "[SHADOW_API_V1] END"


def log(msg):
    print(msg, flush=True)


def main():
    if not os.path.exists(API):
        log("[ERR] api_server.py introuvable : " + API)
        sys.exit(1)

    # 1. Read
    with open(API, "rb") as f:
        raw = f.read()
    src = raw.decode("utf-8-sig")  # strip BOM si present

    # 2. Idempotence
    if MARKER_BEGIN in src:
        log("[SKIP] marker '{}' deja present : patch deja applique.".format(MARKER_BEGIN))
        sys.exit(0)

    # 3. Localiser anchor : ligne contenant @app.get("/api/backtest/presets")
    lines = src.split("\n")
    anchor_idx = None
    for i, ln in enumerate(lines):
        if '@app.get("/api/backtest/presets")' in ln:
            anchor_idx = i
            break

    if anchor_idx is None:
        log("[ERR] anchor '@app.get(\"/api/backtest/presets\")' introuvable.")
        sys.exit(2)

    log("[OK] anchor presets trouve a la ligne {} (1-based : {})".format(
        anchor_idx, anchor_idx + 1
    ))

    # 4. Trouver la fin du handler presets : on cherche la prochaine def/decorator
    #    de top-level (non indente) apres l'anchor. La ligne PRECEDENTE = insertion point.
    insert_after_idx = None
    for j in range(anchor_idx + 1, len(lines)):
        ln = lines[j]
        # Top-level statement : commence par '@app.' ou 'def ' ou '# ===' ou '# ---'
        # On veut la prochaine route ou la prochaine section
        if (ln.startswith("@app.") or
            ln.startswith("def ") or
            ln.startswith("async def ") or
            ln.startswith("class ") or
            (ln.startswith("# ") and ("=====" in ln or "-----" in ln))):
            insert_after_idx = j - 1
            break

    if insert_after_idx is None:
        log("[ERR] impossible de trouver la fin du handler presets.")
        sys.exit(3)

    # Reculer jusqu a la derniere ligne non vide
    while insert_after_idx > anchor_idx and lines[insert_after_idx].strip() == "":
        insert_after_idx -= 1

    log("[OK] insertion point apres ligne {} (1-based)".format(insert_after_idx + 1))
    log("     preview last 3 lines avant insertion :")
    for k in range(max(0, insert_after_idx - 2), insert_after_idx + 1):
        log("       L{:5d} | {}".format(k + 1, lines[k]))

    # 5. Construire le bloc a inserer (ASCII pur, no emoji)
    block = '''

# ===== [SHADOW_API_V1] BEGIN =====
# Phase 9.6 - Endpoints lecture shadow_variants + shadow_perf_rolling
# Affichage card "Shadow Variants J-30" dans onglet Backtest

@app.get("/api/shadow/variants")
def shadow_list_variants(user: dict = Depends(get_current_user)):
    """Liste tous les variants actifs (id, name, description, settings)."""
    import json
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT variant_id, name, description, settings_json, active "
            "FROM shadow_variants WHERE active=1 ORDER BY variant_id"
        ).fetchall()
        out = []
        for r in rows:
            try:
                settings = json.loads(r["settings_json"] or "{}")
            except Exception:
                settings = {}
            out.append({
                "variant_id": r["variant_id"],
                "name": r["name"],
                "description": r["description"],
                "settings": settings,
            })
        return {"success": True, "variants": out}
    finally:
        conn.close()


@app.get("/api/shadow/perf-rolling")
def shadow_perf_rolling(window: int = 30, user: dict = Depends(get_current_user)):
    """Latest as_of_day pour chaque variant sur la window donnee (default 30j)."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        # Latest as_of_day disponible
        row = conn.execute(
            "SELECT MAX(as_of_day) AS d FROM shadow_perf_rolling WHERE window_days=?",
            (window,),
        ).fetchone()
        latest = row["d"] if row else None
        if not latest:
            return {
                "success": True,
                "window_days": window,
                "as_of_day": None,
                "rows": [],
                "message": "Aucune donnee perf rolling - lancer shadow_perf_rolling_j30.py",
            }
        # Rows + join shadow_variants pour nom
        rows = conn.execute(
            "SELECT p.variant_id, v.name AS variant_name, v.description, "
            "p.window_days, p.as_of_day, "
            "p.nav_variant, p.nav_prod, "
            "p.return_variant_pct, p.return_prod_pct, p.delta_pct, "
            "p.sharpe_variant, p.sharpe_prod, "
            "p.max_dd_variant_pct, p.max_dd_prod_pct, "
            "p.n_cycles, p.n_orders_variant, p.n_orders_prod, "
            "p.recommendation, p.recommendation_memo, "
            "p.created_at "
            "FROM shadow_perf_rolling p "
            "LEFT JOIN shadow_variants v ON v.variant_id = p.variant_id "
            "WHERE p.window_days=? AND p.as_of_day=? "
            "ORDER BY p.variant_id",
            (window, latest),
        ).fetchall()
        out = [dict(r) for r in rows]
        return {
            "success": True,
            "window_days": window,
            "as_of_day": latest,
            "rows": out,
        }
    finally:
        conn.close()

# ===== [SHADOW_API_V1] END =====

'''

    # 6. Reconstruire le contenu
    new_lines = lines[:insert_after_idx + 1] + block.split("\n") + lines[insert_after_idx + 1:]
    new_src = "\n".join(new_lines)

    # 7. Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = API + ".bak." + ts
    shutil.copy2(API, bak)
    log("[OK] backup : " + bak)

    # 8. Ecriture temp + validation
    tmp = API + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_src)

    try:
        with open(tmp, "rb") as f:
            d = f.read()
        non_ascii = sum(1 for b in d if b > 127)
        log("[CHECK] non-ASCII bytes : {}".format(non_ascii))
        ast.parse(d.decode("utf-8"))
        log("[CHECK] ast.parse : OK")
        py_compile.compile(tmp, doraise=True)
        log("[CHECK] py_compile : OK")
    except Exception as e:
        log("[ERR] validation echouee : " + repr(e))
        log("[ERR] rollback : suppression tmp, fichier original intact.")
        os.remove(tmp)
        sys.exit(4)

    # 9. Swap
    os.replace(tmp, API)
    log("[OK] api_server.py patche.")

    # 10. Verifications post
    with open(API, "rb") as f:
        d2 = f.read()
    if MARKER_BEGIN.encode() in d2 and MARKER_END.encode() in d2:
        log("[OK] markers BEGIN + END verifies dans le fichier.")
    else:
        log("[WARN] markers non trouves apres swap !")

    log("")
    log("=" * 78)
    log("PATCH [SHADOW_API_V1] DONE")
    log("=" * 78)
    log("Backup     : " + bak)
    log("Routes ajoutees :")
    log("  GET /api/shadow/variants")
    log("  GET /api/shadow/perf-rolling?window=30")
    log("")
    log("Prochaine etape : redemarrer uvicorn pour charger les nouvelles routes.")


if __name__ == "__main__":
    main()
