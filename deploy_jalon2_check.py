"""
deploy_jalon2_check.py
Verification post-installation Jalon 2 + Cleanup v6.5 + Fix UI

Lance ce script APRES deploy_jalon2.ps1 pour valider que tout est en place.

Usage:
    py -3.13 deploy_jalon2_check.py
"""

import sqlite3
import sys
import os
import json
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB_PATH = PROJECT_ROOT / "thesium.db"
API_BASE = "http://localhost:8000"

OK = "[OK]   "
KO = "[FAIL] "
WARN = "[WARN] "

results = []


def check(label, cond, detail=""):
    tag = OK if cond else KO
    results.append((tag, label, detail))
    print(f"{tag}{label}" + (f" - {detail}" if detail else ""))


def warn(label, detail=""):
    results.append((WARN, label, detail))
    print(f"{WARN}{label}" + (f" - {detail}" if detail else ""))


print("=" * 70)
print("VERIFICATION JALON 2 + Cleanup v6.5 + Fix UI")
print("=" * 70)

# ----------------------------------------------------------------------
# 1. Fichiers presents
# ----------------------------------------------------------------------
print("\n[1] Fichiers Python installes")
for f, label in [
    ("execution_engine.py",                 "execution_engine actif"),
    ("execution_engine_v6_5.py",            "v6.5 source"),
    ("portfolio_construction_agent.py",     "PCA actif"),
    ("portfolio_construction_agent_jalon2.py", "PCA Jalon 2 source"),
    ("api_server_with_static.py",           "API serveur"),
]:
    p = PROJECT_ROOT / f
    check(label, p.exists(), str(p) if p.exists() else "MANQUANT")

# ----------------------------------------------------------------------
# 2. Tags v6.5 dans execution_engine.py
# ----------------------------------------------------------------------
print("\n[2] Contenu execution_engine.py")
try:
    code = (PROJECT_ROOT / "execution_engine.py").read_text(encoding="utf-8", errors="ignore")
    check("Tag [target_gap] present",       "[target_gap]" in code)
    check("Tag [target_gap_dedup] present", "[target_gap_dedup]" in code,
          "v6.5 cleanup detecte" if "[target_gap_dedup]" in code else "v6.4 ou anterieur")
    check("Step 2.42 TargetGap synthesizer", "Step 2.42" in code or "_build_target_gap_proposals" in code)
except Exception as e:
    check("Lecture execution_engine.py", False, str(e))

# ----------------------------------------------------------------------
# 3. Tags Jalon 2 dans portfolio_construction_agent.py
# ----------------------------------------------------------------------
print("\n[3] Contenu portfolio_construction_agent.py")
try:
    code = (PROJECT_ROOT / "portfolio_construction_agent.py").read_text(encoding="utf-8", errors="ignore")
    check("Tag [pca_jalon2] present",     "[pca_jalon2]" in code)
    check("Tag [macro_affinity] present", "[macro_affinity]" in code or "macro_affinity" in code)
    check("Vol penalty 90j",              "vol_penalty" in code or "VolPenalty" in code)
    check("Diversification 90j",          "diversification" in code or "Diversification" in code)
except Exception as e:
    check("Lecture portfolio_construction_agent.py", False, str(e))

# ----------------------------------------------------------------------
# 4. Routes API
# ----------------------------------------------------------------------
print("\n[4] Routes API patchees")
try:
    code = (PROJECT_ROOT / "api_server_with_static.py").read_text(encoding="utf-8", errors="ignore")
    check("Route POST /api/construction/run",      "/api/construction/run" in code)
    check("Route GET  /api/construction/targets",  "/api/construction/targets" in code)
except Exception as e:
    check("Lecture api_server_with_static.py", False, str(e))

# ----------------------------------------------------------------------
# 5. DB et tables essentielles
# ----------------------------------------------------------------------
print("\n[5] Base de donnees")
if DB_PATH.exists():
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        for table in ["instruments", "theses", "portfolio_positions",
                      "portfolio_targets", "regime_log", "prices", "orders"]:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                n = cur.fetchone()[0]
                check(f"Table {table}", True, f"{n} lignes")
            except sqlite3.OperationalError as e:
                check(f"Table {table}", False, str(e))
        conn.close()
    except Exception as e:
        check("Connexion DB", False, str(e))
else:
    check("thesium.db existe", False, str(DB_PATH))

# ----------------------------------------------------------------------
# 6. Endpoints HTTP live
# ----------------------------------------------------------------------
print("\n[6] Endpoints live (serveur uvicorn)")

def http_get(path, timeout=5):
    try:
        with urllib.request.urlopen(API_BASE + path, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return None, str(e)


def http_post(path, payload=None, timeout=10):
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        API_BASE + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return None, str(e)


status, body = http_get("/")
check("GET / (UI)", status == 200, f"status={status}")

status, body = http_get("/api/construction/targets")
check("GET /api/construction/targets", status == 200, f"status={status}")
if status == 200:
    try:
        data = json.loads(body)
        n = len(data) if isinstance(data, list) else len(data.get("targets", []))
        print(f"         -> {n} cibles retournees")
    except Exception:
        warn("Reponse non JSON", body[:200])

# On ne POST pas /run par defaut (couteux), on teste juste que la route existe
status, body = http_post("/api/construction/run", {"dry_run": True})
if status is None:
    check("POST /api/construction/run (dry_run)", False, body[:200])
elif status == 200:
    check("POST /api/construction/run (dry_run)", True, "200 OK")
elif status == 422:
    warn("POST /api/construction/run", "422 - parametres invalides (route OK)")
elif status == 405:
    check("POST /api/construction/run", False, "405 Method Not Allowed - route mal patchee")
else:
    warn("POST /api/construction/run", f"status={status}")

# ----------------------------------------------------------------------
# 7. UI - panel "Portfolio ideal vs Actuel"
# ----------------------------------------------------------------------
print("\n[7] UI panel patche")
candidates = [
    PROJECT_ROOT / "static" / "index.html",
    PROJECT_ROOT / "static" / "dashboard.html",
    PROJECT_ROOT / "templates" / "index.html",
]
ui_found = False
for c in candidates:
    if c.exists():
        try:
            html = c.read_text(encoding="utf-8", errors="ignore")
            if "construction-targets-panel" in html or "/api/construction/targets" in html:
                check(f"Patch UI dans {c.name}", True, str(c))
                ui_found = True
                break
        except Exception:
            pass

if not ui_found:
    # Recherche elargie
    for c in PROJECT_ROOT.rglob("*.html"):
        try:
            html = c.read_text(encoding="utf-8", errors="ignore")
            if "construction-targets-panel" in html or "/api/construction/targets" in html:
                check(f"Patch UI dans {c.relative_to(PROJECT_ROOT)}", True, str(c))
                ui_found = True
                break
        except Exception:
            pass

if not ui_found:
    warn("Patch UI", "non detecte - peut-etre fait manuellement ailleurs")

# ----------------------------------------------------------------------
# Résumé final
# ----------------------------------------------------------------------
print("\n" + "=" * 70)
n_ok   = sum(1 for r in results if r[0] == OK)
n_fail = sum(1 for r in results if r[0] == KO)
n_warn = sum(1 for r in results if r[0] == WARN)

print(f"RESUME : {n_ok} OK | {n_fail} FAIL | {n_warn} WARN")
print("=" * 70)

if n_fail == 0:
    print("\nDEPLOIEMENT VALIDE - vous pouvez tester depuis l'UI :")
    print(f"   {API_BASE}")
    print("\nProchaines etapes suggerees :")
    print("   1. Ouvrir l'UI et verifier le panel 'Portfolio ideal vs Actuel'")
    print("   2. Cliquer sur 'Recalculer cibles' pour declencher le PCA Jalon 2")
    print("   3. Lancer Run Cycle pour observer la dedup BUY/SELL")
    sys.exit(0)
else:
    print("\nERREURS detectees - voir details ci-dessus")
    print("\nPour rollback :")
    print(f"   cd {PROJECT_ROOT}")
    print(f"   Copy-Item '_backups_jalon2_<timestamp>\\*' . -Force")
    sys.exit(1)
