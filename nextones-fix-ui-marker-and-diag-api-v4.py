# -*- coding: utf-8 -*-
# [FIX_UI_MARKER_AND_DIAG_API_V4]
# 1. app.js : supprime ligne marker dans template literal (L1086)
# 2. Diag api_server.py : trouve le bloc qui construit data.portfolio (SELECT portfolio_state)
#    pour preparer le patch d'enrichissement (unrealized + total_return)
# 3. Diag risk_engine.py : verifie le code patche actuel (L355-410)
# 4. Diag autres writers de portfolio_state : qui ecrit unrealized_pnl=0 ?

import re
import sys
import time
from pathlib import Path

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")

def write_text(p, s):
    with open(p, "wb") as f:
        f.write(s.encode("utf-8"))

# ====================================================================
# 1. FIX app.js : retire le marker du template
# ====================================================================
print("=" * 70)
print("1. FIX app.js : retire marker du template")
print("=" * 70)
APP = BASE / "app.js"
js = read_text(APP)

# Cherche : `\n    /* [FIX_UI_PNL_6_CARDS_V3] */\n
old_line = "\n    /* [FIX_UI_PNL_6_CARDS_V3] */\n"
new_line = "\n"

if old_line in js:
    js2 = js.replace(old_line, new_line, 1)
    # Backup + ecrire
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = APP.with_suffix(".js.bak." + ts)
    write_text(bak, js)
    write_text(APP, js2)
    print("  OK : marker retire du template (backup " + bak.name + ")")
    # Ajout marker en commentaire HORS template, juste au-dessus
    js3 = read_text(APP)
    new_target = "  const kpiGrid = document.getElementById('kpiGrid');\n  kpiGrid.innerHTML = `\n"
    marker_above = "  const kpiGrid = document.getElementById('kpiGrid');\n  // [FIX_UI_PNL_6_CARDS_V4]\n  kpiGrid.innerHTML = `\n"
    if new_target in js3 and "[FIX_UI_PNL_6_CARDS_V4]" not in js3:
        js4 = js3.replace(new_target, marker_above, 1)
        write_text(APP, js4)
        print("  OK : marker V4 ajoute en commentaire au-dessus du template")
else:
    print("  SKIP : marker line introuvable (deja retire ?)")

# ====================================================================
# 2. DIAG api_server.py : bloc /api/dashboard portfolio
# ====================================================================
print()
print("=" * 70)
print("2. DIAG api_server.py : route /api/dashboard")
print("=" * 70)
API = BASE / "api_server_with_static.py"
if not API.exists():
    API = BASE / "api_server.py"
if not API.exists():
    print("  ERR : api_server file introuvable")
    sys.exit(1)
print("  Fichier : " + API.name)

api_src = read_text(API)
api_lines = api_src.splitlines()

# Trouve la route @app.get("/api/dashboard")
route_matches = [i for i, l in enumerate(api_lines)
                 if "/api/dashboard" in l and ("@app." in l or "@router." in l)]
print("  Routes /api/dashboard trouvees : L=" + str([i+1 for i in route_matches]))

for ridx in route_matches:
    # Dump 60 lignes
    print()
    print("  --- Route a L" + str(ridx + 1) + " ---")
    for i in range(ridx, min(ridx + 80, len(api_lines))):
        line = api_lines[i]
        print("    L" + str(i+1) + ": " + line[:140])
        # Stop si on tombe sur le prochain @app.
        if i > ridx and line.strip().startswith("@app."):
            break

# ====================================================================
# 3. DIAG risk_engine.py : code actuel L355-410 (verifier que patch est en place)
# ====================================================================
print()
print("=" * 70)
print("3. DIAG risk_engine.py : code actuel L355-410")
print("=" * 70)
re_lines = read_text(BASE / "risk_engine.py").splitlines()
for i in range(354, min(415, len(re_lines))):
    print("  L" + str(i+1) + ": " + re_lines[i][:160])

# ====================================================================
# 4. DIAG autres writers de portfolio_state qui pourraient ecraser
# ====================================================================
print()
print("=" * 70)
print("4. DIAG : qui ecrit portfolio_state.unrealized_pnl ?")
print("=" * 70)
import os
for root, dirs, files in os.walk(BASE):
    # Skip backups dirs et __pycache__
    dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__" and "backup" not in d.lower()]
    for fn in files:
        if not fn.endswith(".py"):
            continue
        if ".bak." in fn:
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
        # Lignes contenant "portfolio_state" ET "UPDATE" ou "INSERT"
        for i, line in enumerate(text.splitlines(), 1):
            if "portfolio_state" in line and ("UPDATE" in line.upper() or "INSERT" in line.upper() or "REPLACE" in line.upper()):
                rel = os.path.relpath(fp, BASE)
                print("  " + rel + ":L" + str(i) + " : " + line.strip()[:120])

print()
print("DONE [FIX_UI_MARKER_AND_DIAG_API_V4]")
