# -*- coding: utf-8 -*-
"""
[RISK_CONTROLS_API_V1] Ajoute 2 endpoints dans api_server.py :
  - GET /api/risk/controls/summary   -> liste des 6 controles + parametres
  - GET /api/risk/pretrade/recent    -> N dernieres entrees de risk_pretrade_log

Idempotent : marker [RISK_CONTROLS_API_V1].
Backup auto.
ASCII-only, ecrit en utf-8 sans BOM.
"""
import os, shutil, datetime, re, sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")
MARKER = "[RISK_CONTROLS_API_V1]"

if not os.path.exists(TARGET):
    print(f"ERREUR: {TARGET} introuvable")
    sys.exit(1)

# Backup
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
bkdir = os.path.join(ROOT, f"_backups_risk_controls_api_{ts}")
os.makedirs(bkdir, exist_ok=True)
shutil.copy2(TARGET, os.path.join(bkdir, "api_server.py"))
print(f"Backup -> {bkdir}")

with open(TARGET, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

# Verifier idempotence
n_before_app   = src.count("@app.get")
n_before_post  = src.count("@app.post")
n_marker_before = src.count(MARKER)

if MARKER in src:
    print(f"DEJA INSTALLE ({n_marker_before} marker(s)). Pas de double insertion.")
    print(f"@app.get   = {n_before_app}")
    print(f"@app.post  = {n_before_post}")
    sys.exit(0)

BLOCK = r'''

# ======================================================================
# [RISK_CONTROLS_API_V1] Endpoints risk pre-trade
# ======================================================================
@app.get("/api/risk/controls/summary")
def risk_controls_summary():
    """
    Retourne la liste des 6 controles pre-trade actifs (3 risk_engine.py
    historiques + 3 [RISK_V2]) avec leurs parametres.
    """
    try:
        from risk_pretrade_v2 import DEFAULT_PARAMS as P
    except Exception:
        P = {
            "concentration_max_pct": 0.15,
            "var_confidence": 0.99,
            "var_window_days": 60,
            "var_budget_pct_nav": 0.02,
            "var_marginal_block_pct": 0.005,
            "correl_window_days": 60,
            "correl_block_threshold": 0.85,
            "correl_min_overlap_days": 30,
        }
    controls = [
        {"key": "single_name_limit", "label": "Limite single-name",
         "type": "BLOCK", "param": "99000 USD",
         "source": "risk_engine.py", "marker": "[RISK_V1]"},
        {"key": "sector_limit", "label": "Limite secteur Technology",
         "type": "BLOCK", "param": "249000 USD",
         "source": "risk_engine.py", "marker": "[RISK_V1]"},
        {"key": "var_portfolio_95", "label": "VaR portefeuille 95%",
         "type": "BLOCK", "param": "budget portfolio",
         "source": "risk_engine.py", "marker": "[RISK_V1]"},
        {"key": "concentration", "label": "Concentration par position",
         "type": "BLOCK", "param": f"max {P['concentration_max_pct']*100:.0f}% NAV",
         "source": "risk_pretrade_v2.py", "marker": "[RISK_V2]"},
        {"key": "var_marginal", "label": f"VaR marginal historique {int(P['var_confidence']*100)}%/1j",
         "type": "WARNING", "param": f"window {P['var_window_days']}j, block si delta>{P['var_marginal_block_pct']*100:.1f}%",
         "source": "risk_pretrade_v2.py", "marker": "[RISK_V2]"},
        {"key": "correlation", "label": "Correlation Pearson",
         "type": "WARNING", "param": f"window {P['correl_window_days']}j, seuil {P['correl_block_threshold']:.2f}, min {P['correl_min_overlap_days']}j",
         "source": "risk_pretrade_v2.py", "marker": "[RISK_V2]"},
    ]
    return {"controls": controls, "total": len(controls),
            "mode": "hybrid", "marker": "[RISK_CONTROLS_API_V1]"}


@app.get("/api/risk/pretrade/recent")
def risk_pretrade_recent(limit: int = 20):
    """
    Retourne les N dernieres entrees de risk_pretrade_log (defaut 20).
    """
    import sqlite3, json, os as _os
    DB = _os.environ.get("THESIUM_DB", r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
    limit = max(1, min(int(limit), 200))
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    try:
        rows = c.execute(
            "SELECT id, ts, symbol, side, qty, price, passed, blocked_by, "
            "details_json, marker FROM risk_pretrade_log "
            "ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        c.close()
    items = []
    for r in rows:
        try:
            details = json.loads(r["details_json"]) if r["details_json"] else {}
        except Exception:
            details = {}
        items.append({
            "id": r["id"], "ts": r["ts"], "symbol": r["symbol"],
            "side": r["side"], "qty": r["qty"], "price": r["price"],
            "passed": bool(r["passed"]), "blocked_by": r["blocked_by"],
            "marker": r["marker"], "details": details,
        })
    return {"items": items, "count": len(items),
            "marker": "[RISK_CONTROLS_API_V1]"}
'''

# Insertion en fin de fichier (avant le if __name__ == "__main__" s'il existe)
m = re.search(r'\n(if\s+__name__\s*==\s*[\'"]__main__[\'"])', src)
if m:
    pos = m.start()
    new_src = src[:pos] + BLOCK + src[pos:]
    print(f"Insertion AVANT 'if __name__' (offset {pos})")
else:
    new_src = src.rstrip() + "\n" + BLOCK + "\n"
    print("Insertion EN FIN de fichier")

with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
    f.write(new_src)

# Validation
with open(TARGET, "r", encoding="utf-8-sig") as f:
    chk = f.read()
n_after_get  = chk.count("@app.get")
n_after_post = chk.count("@app.post")
n_marker_after = chk.count(MARKER)
print(f"@app.get   {n_before_app}  -> {n_after_get}   (delta +{n_after_get - n_before_app})")
print(f"@app.post  {n_before_post}  -> {n_after_post} (delta +{n_after_post - n_before_post})")
print(f"marker     {n_marker_before} -> {n_marker_after}")
assert n_after_get - n_before_app == 2, "Devait ajouter +2 @app.get"
assert n_marker_after >= 1, "Marker manquant"
print("OK")
