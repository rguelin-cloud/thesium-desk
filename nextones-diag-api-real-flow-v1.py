# -*- coding: utf-8 -*-
# [DIAG_API_REAL_FLOW_V1]
# 1. Trouver la VRAIE definition de la route /api/dashboard dans api_server_with_static.py
#    (le V4 a echoue car @app.get est peut-etre sur la ligne au-dessus)
# 2. Dump api_server.py L190-330 (helper update + UPDATE portfolio_state L299)
# 3. Verifier si risk_engine.compute_portfolio_metrics (ou nom equivalent) est appele
#    quelque part dans execute_cycle / run_decision_cycle

from pathlib import Path
import re

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")

# ====================================================================
print("=" * 70)
print("1. api_server_with_static.py : recherche /api/dashboard (large)")
print("=" * 70)
API_WS = BASE / "api_server_with_static.py"
ws_lines = read_text(API_WS).splitlines()
for i, l in enumerate(ws_lines):
    if "dashboard" in l.lower():
        print("  L" + str(i+1) + ": " + l[:140])

# ====================================================================
print()
print("=" * 70)
print("2. api_server.py : route /api/dashboard et helper L190-330")
print("=" * 70)
API = BASE / "api_server.py"
api_lines = read_text(API).splitlines()

# Trouver toutes les lignes avec "/api/dashboard"
print("  Lignes contenant '/api/dashboard' :")
for i, l in enumerate(api_lines):
    if "/api/dashboard" in l:
        print("    L" + str(i+1) + ": " + l[:140])

print()
print("  Lignes contenant 'def get_dashboard' ou 'async def dashboard' :")
for i, l in enumerate(api_lines):
    if re.search(r"def\s+\w*dashboard\w*\s*\(", l):
        print("    L" + str(i+1) + ": " + l[:140])

print()
print("  Dump L190-330 (helper + UPDATE portfolio_state L299) :")
for i in range(189, min(330, len(api_lines))):
    print("    L" + str(i+1) + ": " + api_lines[i][:160])

# ====================================================================
print()
print("=" * 70)
print("3. execute_cycle / run_decision_cycle : appelle-t-il risk_engine ?")
print("=" * 70)
for fname in ["api_server.py", "execution_engine.py", "risk_engine.py"]:
    fp = BASE / fname
    if not fp.exists():
        continue
    src = read_text(fp)
    lines = src.splitlines()
    # Cherche les def
    for i, l in enumerate(lines):
        if re.search(r"def\s+(execute_cycle|run_decision_cycle|update_portfolio_metrics)\s*\(", l):
            print()
            print("  " + fname + ":L" + str(i+1) + " : " + l.strip()[:140])
            # Dump 40 lignes du corps
            for j in range(i, min(i + 50, len(lines))):
                ln = lines[j]
                # Stop si on tombe sur une autre def au meme niveau
                if j > i and re.match(r"def\s+\w+\s*\(", ln):
                    break
                print("    L" + str(j+1) + ": " + ln[:160])

# ====================================================================
print()
print("=" * 70)
print("4. risk_engine.py : nom de la fonction patchee (L355)")
print("=" * 70)
re_lines = read_text(BASE / "risk_engine.py").splitlines()
# Cherche la def juste avant L356
for i in range(355, 320, -1):
    if i < len(re_lines) and re.match(r"def\s+\w+\s*\(", re_lines[i]):
        print("  Fonction englobante L355-410 : " + re_lines[i].strip()[:120] + " (L" + str(i+1) + ")")
        break
else:
    print("  Pas trouve avec re.match. Recherche large :")
    for i in range(355, 300, -1):
        if i < len(re_lines) and "def " in re_lines[i]:
            print("    L" + str(i+1) + ": " + re_lines[i].strip()[:140])

# ====================================================================
print()
print("=" * 70)
print("5. Qui APPELLE cette fonction risk_engine ?")
print("=" * 70)
# On suppose qu'on a trouve le nom dans 4. Sinon, on cherche les appels classiques
# update_portfolio_metrics, compute_portfolio_metrics, recalc_metrics, ...
candidates = ["update_portfolio_metrics", "compute_portfolio_metrics", "recalc_metrics",
              "recalculate_portfolio", "refresh_portfolio_state", "update_metrics"]
import os
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__" and "backup" not in d.lower()]
    for fn in files:
        if not fn.endswith(".py") or ".bak." in fn:
            continue
        fp = os.path.join(root, fn)
        try:
            with open(fp, "rb") as f:
                content = f.read()
            if content.startswith(b"\xef\xbb\xbf"):
                content = content[3:]
            text = content.decode("utf-8", errors="ignore")
        except Exception:
            continue
        for cand in candidates:
            for i, line in enumerate(text.splitlines(), 1):
                if cand in line and "def " not in line:
                    rel = os.path.relpath(fp, BASE)
                    print("  " + rel + ":L" + str(i) + " : " + line.strip()[:120])

print()
print("DONE [DIAG_API_REAL_FLOW_V1]")
