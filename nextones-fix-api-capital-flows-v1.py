# -*- coding: utf-8 -*-
# [FIX_API_CAPITAL_FLOWS_V1]
# Patche api_server.py pour :
#   1) Exposer GET /api/portfolio/capital-flows (liste)
#   2) Exposer POST /api/portfolio/capital-flow (insert deposit/withdrawal)
#   3) Enrichir la reponse /api/dashboard avec :
#      - portfolio.unrealized_pnl
#      - portfolio.unrealized_pnl_pct
#      - portfolio.total_return (NAV - 1M - net_flows)
#      - portfolio.total_return_pct (en base 1M + net_flows)
#      - portfolio.net_capital_flows
#   4) Patcher le UPDATE portfolio_state L299 pour aussi ecrire
#      unrealized_pnl + unrealized_pnl_pct
#
# Idempotent : skip si marker [FIX_API_CAPITAL_FLOWS_V1] present.

import ast
import os
import py_compile
import re
import shutil
import time
from pathlib import Path

API = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py")
MARKER = "FIX_API_CAPITAL_FLOWS_V1"

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")

def write_text(p, text):
    with open(p, "wb") as f:
        f.write(text.encode("utf-8"))

src = read_text(API)

if MARKER in src:
    print(f"[SKIP] marker {MARKER} deja present")
    raise SystemExit(0)

# Backup
ts = time.strftime("%Y%m%d_%H%M%S")
backup = API.with_suffix(f".py.bak.{ts}")
shutil.copy2(API, backup)
print(f"[OK] backup -> {backup.name}")

# ---- STEP 1 : import capital_flows_helper en haut ----
# On insere apres la derniere ligne d'import (premiere ligne non-import en partant du haut).
lines = src.splitlines(keepends=False)
import_end = 0
for i, l in enumerate(lines):
    s = l.strip()
    if s.startswith("import ") or s.startswith("from "):
        import_end = i + 1
    elif s and not s.startswith("#"):
        # premier vrai code -> on s'arrete
        if import_end > 0:
            break
helper_import = (
    "# [FIX_API_CAPITAL_FLOWS_V1] import helper\n"
    "try:\n"
    "    from capital_flows_helper import compute_total_return, get_net_capital_flows, INITIAL_CAPITAL\n"
    "except Exception:\n"
    "    INITIAL_CAPITAL = 1_000_000.0\n"
    "    def get_net_capital_flows(conn=None): return 0.0\n"
    "    def compute_total_return(nav, conn=None):\n"
    "        tr = nav - INITIAL_CAPITAL\n"
    "        return tr, (tr / INITIAL_CAPITAL * 100.0) if INITIAL_CAPITAL > 0 else 0.0\n"
)
lines.insert(import_end, helper_import)
src = "\n".join(lines) + "\n"

# ---- STEP 2 : patcher le UPDATE portfolio_state (L299 environ) ----
# Cible le bloc "UPDATE portfolio_state SET total_value=?, total_pnl=?, total_pnl_pct=?,
#                  daily_pnl=?, daily_pnl_pct=?, updated_at=? WHERE id=1"
# On l'etend pour SET unrealized_pnl=?, unrealized_pnl_pct=? aussi.
old_update_rgx = re.compile(
    r'(UPDATE\s+portfolio_state\s*\n?\s*SET\s+total_value=\?\s*,\s*total_pnl=\?\s*,\s*total_pnl_pct=\?\s*,\s*\n?\s*daily_pnl=\?\s*,\s*daily_pnl_pct=\?\s*,\s*updated_at=\?\s*\n?\s*WHERE\s+id=1)',
    re.IGNORECASE,
)
m = old_update_rgx.search(src)
if not m:
    print("[ERR] UPDATE portfolio_state pattern not found - aborting")
    raise SystemExit(1)

# On va remplacer le UPDATE + sa tuple de parametres.
# D'abord on cherche le tuple (round(total_value, 2), round(total_pnl, 2), ...) qui suit.
# Le pattern le plus simple : trouver le bloc complet "conn.execute(\"\"\"UPDATE portfolio_state ... WHERE id=1\"\"\", (round(...) ... ))"
# On opere ligne par ligne pour rester robuste.

# Nouveau SQL (avec unrealized_pnl/unrealized_pnl_pct)
new_update_sql = (
    "UPDATE portfolio_state \n"
    "                    SET total_value=?, total_pnl=?, total_pnl_pct=?, \n"
    "                        unrealized_pnl=?, unrealized_pnl_pct=?, \n"
    "                        daily_pnl=?, daily_pnl_pct=?, updated_at=? \n"
    "                    WHERE id=1"
)
src_new = old_update_rgx.sub(new_update_sql, src, count=1)

# Maintenant trouver la tuple de parametres juste apres (round(total_value, 2), round(total_pnl, 2), round(total_pnl_pct, 4), round(daily_pnl, 2), ...)
# On insere round(unrealized_pnl, 2), round(unrealized_pnl_pct, 4) APRES total_pnl_pct.
# Pattern de la tuple :
tuple_rgx = re.compile(
    r"(WHERE id=1\"\"\",\s*\n\s*\()"        # debut tuple apres SQL
    r"(round\(total_value,\s*\d+\)\s*,\s*round\(total_pnl,\s*\d+\)\s*,\s*round\(total_pnl_pct,\s*\d+\))"  # 3 premiers
    r"(\s*,\s*round\(daily_pnl)",            # avant daily_pnl
)
m2 = tuple_rgx.search(src_new)
if not m2:
    print("[ERR] tuple parametres UPDATE introuvable - aborting")
    raise SystemExit(2)

# Avant de patcher la tuple, il faut calculer unrealized_pnl/pct dans le scope.
# On insere ces calculs juste AVANT le conn.execute. Pour ca on trouve l'indent et la ligne
# qui commence le conn.execute("""UPDATE portfolio_state...
exec_rgx = re.compile(
    r"^(\s*)conn\.execute\(\"\"\"UPDATE\s+portfolio_state",
    re.MULTILINE,
)
m3 = exec_rgx.search(src_new)
if not m3:
    print("[ERR] ligne conn.execute(\"\"\"UPDATE portfolio_state introuvable - aborting")
    raise SystemExit(3)

indent = m3.group(1)
insertion_block = (
    f"{indent}# [FIX_API_CAPITAL_FLOWS_V1] calcul unrealized + total_return\n"
    f"{indent}try:\n"
    f"{indent}    _sum_cost = sum((p.get('quantity') or 0) * (p.get('avg_cost') or 0) for p in (positions or []))\n"
    f"{indent}    _sum_mv   = sum((p.get('quantity') or 0) * (p.get('current_price') or p.get('avg_cost') or 0) for p in (positions or []))\n"
    f"{indent}    unrealized_pnl = _sum_mv - _sum_cost\n"
    f"{indent}    unrealized_pnl_pct = (unrealized_pnl / _sum_cost * 100.0) if _sum_cost > 0 else 0.0\n"
    f"{indent}except Exception:\n"
    f"{indent}    unrealized_pnl = 0.0\n"
    f"{indent}    unrealized_pnl_pct = 0.0\n"
)
# Insere avant la ligne conn.execute
src_new = src_new[:m3.start()] + insertion_block + src_new[m3.start():]

# Re-cherche la tuple apres insertion (positions ont change)
m2 = tuple_rgx.search(src_new)
if not m2:
    print("[ERR] re-recherche tuple parametres a echoue - aborting")
    raise SystemExit(4)

# Patch la tuple : ajoute round(unrealized_pnl, 2), round(unrealized_pnl_pct, 4) apres total_pnl_pct
replacement = m2.group(1) + m2.group(2) + ", round(unrealized_pnl, 2), round(unrealized_pnl_pct, 4)" + m2.group(3)
src_new = src_new[:m2.start()] + replacement + src_new[m2.end():]

# ---- STEP 3 : enrichir la reponse JSON de /api/dashboard ----
# La fonction get_dashboard() retourne un dict avec une cle "portfolio". On va ajouter
# unrealized_pnl/_pct + total_return/_pct + net_capital_flows juste apres construction du dict.
# Heuristique : on cherche la premiere occurrence "portfolio" : {...} ou return {... "portfolio": ...}
# Plus simple : on patche la fonction get_dashboard pour faire un post-process.
# On cherche "def get_dashboard" puis le premier "return" suivant.
gd_rgx = re.compile(r"def\s+get_dashboard\s*\(")
m4 = gd_rgx.search(src_new)
if not m4:
    print("[ERR] def get_dashboard introuvable")
    raise SystemExit(5)

# On cherche la 1ere ligne "return " apres get_dashboard et on insere AVANT.
# Pour rester sur cette fonction, on lit ligne par ligne avec indent tracking.
after = src_new[m4.start():]
lines_after = after.splitlines(keepends=True)
def_indent = None
ret_offset = None
acc_idx = 0
for i, l in enumerate(lines_after):
    if i == 0:
        # ligne "def get_dashboard(...):"
        acc_idx += len(l)
        continue
    stripped = l.lstrip()
    if def_indent is None and stripped:
        def_indent = len(l) - len(stripped)
    if stripped.startswith("return "):
        # Verifier qu'on est toujours dans la fonction (indent >= def_indent)
        cur_indent = len(l) - len(stripped)
        if cur_indent >= def_indent and cur_indent <= def_indent + 4:
            ret_offset = acc_idx
            break
    acc_idx += len(l)

if ret_offset is None:
    print("[ERR] return de get_dashboard introuvable")
    raise SystemExit(6)

abs_pos = m4.start() + ret_offset
# Le bloc inject avant return : on cherche l'indent du return
# Cette ligne commence par def_indent spaces -> on prend def_indent
indent_ret = " " * (def_indent or 4)
enrich_block = (
    f"{indent_ret}# [FIX_API_CAPITAL_FLOWS_V1] enrichir portfolio avec unrealized + total_return\n"
    f"{indent_ret}try:\n"
    f"{indent_ret}    _pf = locals().get('portfolio') or locals().get('result', {{}}).get('portfolio') or {{}}\n"
    f"{indent_ret}    if isinstance(_pf, dict):\n"
    f"{indent_ret}        _nav = float(_pf.get('total_value') or 0)\n"
    f"{indent_ret}        _net = get_net_capital_flows()\n"
    f"{indent_ret}        _tr, _trp = compute_total_return(_nav)\n"
    f"{indent_ret}        _pf['net_capital_flows'] = round(_net, 2)\n"
    f"{indent_ret}        _pf['total_return'] = round(_tr, 2)\n"
    f"{indent_ret}        _pf['total_return_pct'] = round(_trp, 4)\n"
    f"{indent_ret}        # unrealized depuis DB (deja ecrit par UPDATE)\n"
    f"{indent_ret}        try:\n"
    f"{indent_ret}            _c = conn.cursor() if 'conn' in locals() else None\n"
    f"{indent_ret}            if _c is not None:\n"
    f"{indent_ret}                _c.execute('SELECT unrealized_pnl, unrealized_pnl_pct FROM portfolio_state WHERE id=1')\n"
    f"{indent_ret}                _r = _c.fetchone()\n"
    f"{indent_ret}                if _r:\n"
    f"{indent_ret}                    _pf['unrealized_pnl'] = float(_r[0] or 0)\n"
    f"{indent_ret}                    _pf['unrealized_pnl_pct'] = float(_r[1] or 0)\n"
    f"{indent_ret}        except Exception:\n"
    f"{indent_ret}            pass\n"
    f"{indent_ret}except Exception as _e:\n"
    f"{indent_ret}    pass\n"
)
src_new = src_new[:abs_pos] + enrich_block + src_new[abs_pos:]

# ---- STEP 4 : ajouter les endpoints GET/POST capital-flow ----
# On ajoute a la fin du fichier (ou juste avant le if __name__ == "__main__":)
endpoints_block = '''

# [FIX_API_CAPITAL_FLOWS_V1] endpoints capital flows
from pydantic import BaseModel as _BMCF
from fastapi import HTTPException as _HE_CF

class _CapitalFlowIn(_BMCF):
    amount: float
    side: str  # "deposit" or "withdrawal"
    date: str = None
    note: str = None

@app.get("/api/portfolio/capital-flows")
def list_capital_flows():
    conn = db()
    try:
        cur = conn.execute(
            "SELECT id, date, amount, side, note, created_at "
            "FROM capital_flows ORDER BY date DESC, id DESC"
        )
        rows = [
            {
                "id": r[0],
                "date": r[1],
                "amount": float(r[2] or 0),
                "side": r[3],
                "note": r[4] or "",
                "created_at": r[5],
            }
            for r in cur.fetchall()
        ]
        cur = conn.execute(
            "SELECT "
            "COALESCE(SUM(CASE WHEN side='deposit' THEN amount END), 0) - "
            "COALESCE(SUM(CASE WHEN side='withdrawal' THEN amount END), 0) "
            "FROM capital_flows"
        )
        net = float(cur.fetchone()[0] or 0)
        return {"flows": rows, "net_capital_flows": round(net, 2), "count": len(rows)}
    finally:
        conn.close()

@app.post("/api/portfolio/capital-flow")
def create_capital_flow(payload: _CapitalFlowIn):
    if payload.side not in ("deposit", "withdrawal"):
        raise _HE_CF(status_code=400, detail="side must be 'deposit' or 'withdrawal'")
    if payload.amount is None or payload.amount <= 0:
        raise _HE_CF(status_code=400, detail="amount must be > 0")
    from datetime import datetime as _dt
    date = payload.date or _dt.utcnow().strftime("%Y-%m-%d")
    conn = db()
    try:
        cur = conn.execute(
            "INSERT INTO capital_flows (date, amount, side, note) VALUES (?, ?, ?, ?)",
            (date, float(payload.amount), payload.side, payload.note or ""),
        )
        new_id = cur.lastrowid
        # Repercute aussi sur portfolio_state.cash :
        # deposit => cash += amount ; withdrawal => cash -= amount
        delta = float(payload.amount) if payload.side == "deposit" else -float(payload.amount)
        conn.execute(
            "UPDATE portfolio_state SET cash = COALESCE(cash, 0) + ?, "
            "total_value = COALESCE(total_value, 0) + ?, "
            "updated_at = datetime('now') WHERE id=1",
            (delta, delta),
        )
        conn.commit()
        return {"ok": True, "id": new_id, "date": date, "amount": float(payload.amount), "side": payload.side}
    finally:
        conn.close()

@app.delete("/api/portfolio/capital-flow/{flow_id}")
def delete_capital_flow(flow_id: int):
    conn = db()
    try:
        cur = conn.execute("SELECT amount, side FROM capital_flows WHERE id=?", (flow_id,))
        r = cur.fetchone()
        if not r:
            raise _HE_CF(status_code=404, detail="flow not found")
        amount = float(r[0] or 0)
        side = r[1]
        # Inverse l'effet sur cash/total_value
        delta = -amount if side == "deposit" else amount
        conn.execute(
            "UPDATE portfolio_state SET cash = COALESCE(cash, 0) + ?, "
            "total_value = COALESCE(total_value, 0) + ?, "
            "updated_at = datetime('now') WHERE id=1",
            (delta, delta),
        )
        conn.execute("DELETE FROM capital_flows WHERE id=?", (flow_id,))
        conn.commit()
        return {"ok": True, "deleted_id": flow_id}
    finally:
        conn.close()
# [/FIX_API_CAPITAL_FLOWS_V1]
'''

# Insere avant `if __name__ == "__main__":` si present, sinon a la fin
main_rgx = re.compile(r'\nif\s+__name__\s*==\s*["\']__main__["\']\s*:', re.MULTILINE)
m5 = main_rgx.search(src_new)
if m5:
    src_new = src_new[:m5.start()] + endpoints_block + src_new[m5.start():]
else:
    src_new = src_new + endpoints_block

# ---- Validation ----
try:
    ast.parse(src_new)
except SyntaxError as e:
    # Sauve un .broken pour debug
    broken = API.with_suffix(".py.broken")
    write_text(broken, src_new)
    print(f"[ERR] AST parse failed : {e}")
    print(f"      Broken output -> {broken.name}")
    raise SystemExit(7)

write_text(API, src_new)

try:
    py_compile.compile(str(API), doraise=True)
    print("[OK] py_compile passed")
except py_compile.PyCompileError as e:
    print(f"[ERR] py_compile failed : {e}")
    raise SystemExit(8)

print(f"[OK] api_server.py patche avec marker [{MARKER}]")
print(f"[OK] backup    : {backup.name}")
print()
print("Endpoints ajoutes :")
print("  GET    /api/portfolio/capital-flows")
print("  POST   /api/portfolio/capital-flow   {amount, side, date?, note?}")
print("  DELETE /api/portfolio/capital-flow/{id}")
print()
print("Champs ajoutes a /api/dashboard.portfolio :")
print("  unrealized_pnl, unrealized_pnl_pct")
print("  total_return, total_return_pct")
print("  net_capital_flows")
print()
print("DONE [FIX_API_CAPITAL_FLOWS_V1]")
