# -*- coding: utf-8 -*-
"""
[API_UNIVERSE_V2]
Insere les 5 endpoints /api/universe/* dans le bon fichier API
en garantissant les imports Depends/HTTPException/APIRouter.

Cible auto-detectee: fichier API qui contient '@app.post("/api/orders/execute-cycle")'
- typiquement api_server.py chez ce projet.

Idempotent (marker [API_UNIVERSE_V2_BEGIN]/[API_UNIVERSE_V2_END]).
Backup auto.

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-api-universe-endpoints-v2.py
"""
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

MARK_BEGIN = "# [API_UNIVERSE_V2_BEGIN]"
MARK_END   = "# [API_UNIVERSE_V2_END]"


def find_api_file() -> Path | None:
    """Trouve le fichier qui contient les routes existantes."""
    candidates = [
        ROOT / "api_server.py",
        ROOT / "api_server_with_static.py",
    ]
    for p in candidates:
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        if "/api/orders/execute-cycle" in txt or "/api/orders/pending" in txt:
            return p
    return None


def ensure_imports(txt: str) -> tuple[str, list[str]]:
    """Verifie/ajoute les imports FastAPI necessaires."""
    needed = ["Depends", "HTTPException", "Body", "Query"]
    changes = []

    # Cherche un 'from fastapi import ...'
    m = re.search(r"^from\s+fastapi\s+import\s+([^\n]+)$", txt, re.MULTILINE)
    if m:
        current = m.group(1)
        missing = [n for n in needed if not re.search(rf"\b{n}\b", current)]
        if missing:
            new_line = current.rstrip().rstrip(",") + ", " + ", ".join(missing)
            txt = txt[:m.start(1)] + new_line + txt[m.end(1):]
            changes.append(f"ajout import fastapi: {missing}")
    else:
        # Pas de 'from fastapi import' ; on en ajoute un en haut apres les autres imports
        new_import = f"from fastapi import {', '.join(needed)}\n"
        # Trouver une bonne place: apres le dernier import en haut
        last_import_end = 0
        for m in re.finditer(r"^(import\s+\S+|from\s+\S+\s+import[^\n]+)\s*$", txt, re.MULTILINE):
            last_import_end = m.end()
        if last_import_end > 0:
            txt = txt[:last_import_end] + "\n" + new_import + txt[last_import_end:]
        else:
            txt = new_import + txt
        changes.append(f"insertion 'from fastapi import {needed}'")

    # get_current_user / require_manager : on attend qu'ils existent deja
    if "def get_current_user" not in txt and "get_current_user" not in txt:
        changes.append("[WARN] get_current_user introuvable - dependra de l'auth existante")

    return txt, changes


ENDPOINTS_BLOCK = '''
{MARK_BEGIN}
# Universe Expansion v1 - Endpoints (Jalon 4)
# Ces endpoints sont inseres automatiquement par nextones-api-universe-endpoints-v2.py
try:
    from universe_expansion_agent import (
        run_scan as _universe_run_scan,
        approve_candidate as _universe_approve,
        reject_candidate as _universe_reject,
    )
except Exception as _e:
    _universe_run_scan = None
    _universe_approve = None
    _universe_reject = None
    print(f"[API_UNIVERSE] import warning: {{_e}}")


def _universe_db():
    """Connexion DB en sqlite3.Row, comme le reste du projet."""
    import sqlite3 as _sqlite3
    _conn = _sqlite3.connect(r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\thesium.db",
                             timeout=30.0)
    _conn.row_factory = _sqlite3.Row
    try:
        _conn.execute("PRAGMA busy_timeout = 30000;")
    except Exception:
        pass
    return _conn


@app.get("/api/universe/candidates")
def universe_list_candidates(
    status: str = Query("pending"),
    limit: int = Query(50),
    user: dict = Depends(get_current_user),
):
    """Liste les candidats universe (pending|approved|rejected|all)."""
    conn = _universe_db()
    try:
        if status == "all":
            rows = conn.execute(
                "SELECT * FROM universe_candidates ORDER BY proposed_at DESC LIMIT ?;",
                (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM universe_candidates WHERE status=? "
                "ORDER BY proposed_at DESC LIMIT ?;",
                (status, limit)
            ).fetchall()
        return {{"candidates": [dict(r) for r in rows], "total": len(rows)}}
    finally:
        conn.close()


@app.get("/api/universe/candidates/{{cand_id}}")
def universe_get_candidate(cand_id: int, user: dict = Depends(get_current_user)):
    conn = _universe_db()
    try:
        row = conn.execute(
            "SELECT * FROM universe_candidates WHERE id=?;",
            (cand_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return dict(row)
    finally:
        conn.close()


@app.post("/api/universe/candidates/{{cand_id}}/approve")
def universe_approve(
    cand_id: int,
    body: dict = Body(default={{}}),
    user: dict = Depends(get_current_user),
):
    if _universe_approve is None:
        raise HTTPException(status_code=503, detail="universe_expansion_agent not available")
    max_w = body.get("max_weight_pct")
    try:
        res = _universe_approve(
            cand_id,
            reviewed_by=user.get("username", "system"),
            max_weight_pct=max_w,
        )
        return {{"success": True, "result": res}}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/universe/candidates/{{cand_id}}/reject")
def universe_reject(
    cand_id: int,
    body: dict = Body(default={{}}),
    user: dict = Depends(get_current_user),
):
    if _universe_reject is None:
        raise HTTPException(status_code=503, detail="universe_expansion_agent not available")
    notes = body.get("notes", "")
    try:
        res = _universe_reject(
            cand_id,
            reviewed_by=user.get("username", "system"),
            notes=notes,
        )
        return {{"success": True, "result": res}}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/universe/scan")
def universe_scan(
    body: dict = Body(default={{}}),
    user: dict = Depends(get_current_user),
):
    if _universe_run_scan is None:
        raise HTTPException(status_code=503, detail="universe_expansion_agent not available")
    role = user.get("role", "")
    if role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="admin/manager only")
    top = int(body.get("top", 5))
    dry_run = bool(body.get("dry_run", False))
    try:
        res = _universe_run_scan(top_n=top, dry_run=dry_run)
        return {{"success": True, "result": res}}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
{MARK_END}
'''.format(MARK_BEGIN=MARK_BEGIN, MARK_END=MARK_END)


def main() -> int:
    api = find_api_file()
    if not api:
        print("[FAIL] Fichier API introuvable (cherche '/api/orders/execute-cycle').")
        return 1
    print(f"[INFO] Cible: {api.name}")

    txt = api.read_text(encoding="utf-8-sig", errors="replace")

    if MARK_BEGIN in txt:
        # remplacer le bloc existant
        start = txt.index(MARK_BEGIN)
        end_pat = MARK_END
        if end_pat in txt[start:]:
            end_idx = txt.index(end_pat, start) + len(end_pat)
            old_block = txt[start:end_idx]
            print(f"[INFO] bloc existant detecte ({len(old_block)} chars), remplacement.")
            txt = txt[:start] + ENDPOINTS_BLOCK.strip() + txt[end_idx:]
        else:
            print("[WARN] MARK_BEGIN sans MARK_END, append plutot.")
            txt = txt.rstrip() + "\n\n" + ENDPOINTS_BLOCK
    else:
        # Verifier les imports avant ajout
        txt, ch = ensure_imports(txt)
        for c in ch:
            print(f"[IMPORT] {c}")
        # append a la fin
        txt = txt.rstrip() + "\n\n" + ENDPOINTS_BLOCK

    # Backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = api.with_suffix(f".py.bak-{ts}-jalon4-v2")
    shutil.copy2(api, bak)
    print(f"[BACKUP] {bak.name}")

    api.write_text(txt, encoding="utf-8")
    print(f"[OK] {api.name} patche.")

    # Verification syntaxe
    import py_compile
    try:
        py_compile.compile(str(api), doraise=True)
        print(f"[OK] {api.name} compile sans erreur de syntaxe.")
    except py_compile.PyCompileError as e:
        print(f"[FAIL] erreur de syntaxe : {e}")
        print(f"[ACTION] restaure manuellement depuis {bak.name}")
        return 2

    print("\nProchaine etape : redemarre uvicorn et teste:")
    print('  curl -X POST http://localhost:8000/api/universe/scan -H "Authorization: Bearer $TOK" -d "{\\"dry_run\\":true,\\"top\\":5}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
