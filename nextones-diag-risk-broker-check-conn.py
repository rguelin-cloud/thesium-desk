# -*- coding: utf-8 -*-
# nextones-diag-risk-broker-check-conn.py
# Diagnostic : localiser le code de risk_broker_check et son ouverture de connexion
# Pour pouvoir patcher proprement [NEXTONES-BROKER-CHECK-V1] avec conn partagee

import os
import re
import sys

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

print()
print("=" * 72)
print("[1] Localiser risk_broker_check (fichier source)")
print("-" * 72)

candidates = []
for root, dirs, files in os.walk(PROD):
    # Eviter venv/cache
    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "__pycache__", "node_modules", "backups", ".git")]
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                    txt = fh.read()
                if "risk_broker_check" in txt or "risk_broker_check audit" in txt:
                    candidates.append((path, txt))
            except Exception as e:
                print("  [SKIP] %s : %s" % (path, e))

print("  Fichiers contenant 'risk_broker_check' : %d" % len(candidates))
for path, _ in candidates:
    rel = os.path.relpath(path, PROD)
    print("    - %s" % rel)

print()
print("=" * 72)
print("[2] Inspection des appels et definitions")
print("-" * 72)
for path, txt in candidates:
    rel = os.path.relpath(path, PROD)
    print()
    print("  === %s ===" % rel)
    lines = txt.splitlines()
    # def risk_broker_check
    for i, l in enumerate(lines, 1):
        if re.search(r"def\s+risk_broker_check|def\s+_?broker_check|def\s+check_broker", l):
            print("    [DEF L%d] %s" % (i, l.strip()))
    # appels
    for i, l in enumerate(lines, 1):
        if "risk_broker_check" in l and "def " not in l:
            print("    [CALL L%d] %s" % (i, l.strip()[:160]))
    # audit log
    for i, l in enumerate(lines, 1):
        if "risk_broker_check audit" in l:
            print("    [LOG L%d] %s" % (i, l.strip()[:160]))
    # ouvertures de conn dans ce fichier
    for i, l in enumerate(lines, 1):
        if "sqlite3.connect" in l:
            print("    [DB-OPEN L%d] %s" % (i, l.strip()[:160]))
    # marker BROKER-CHECK
    for i, l in enumerate(lines, 1):
        if "[NEXTONES-BROKER-CHECK" in l or "BROKER_CHECK" in l:
            print("    [MARKER L%d] %s" % (i, l.strip()[:160]))

print()
print("=" * 72)
print("[3] Trouver le module qui DEFINIT risk_broker_check")
print("-" * 72)
defined_in = None
for path, txt in candidates:
    if re.search(r"def\s+risk_broker_check\s*\(", txt):
        defined_in = path
        print("  [DEFINED] %s" % os.path.relpath(path, PROD))
        # Dump des 40 premieres lignes apres la def
        m = re.search(r"def\s+risk_broker_check\s*\(([^)]*)\)", txt)
        if m:
            print("  Signature actuelle : risk_broker_check(%s)" % m.group(1).strip())
        # Extraire le corps autour
        idx = txt.find("def risk_broker_check")
        if idx >= 0:
            sn = txt[idx:idx+1500]
            print("  --- DEF SNIPPET ---")
            for ln in sn.splitlines()[:35]:
                print("    " + ln)
            print("  --- /DEF SNIPPET ---")
        break

if not defined_in:
    print("  [WARN] risk_broker_check non trouve comme def, peut-etre importe ?")

print()
print("=" * 72)
print("[4] Verifier comment risk_pretrade.py appelle le broker_check")
print("-" * 72)
rp_path = os.path.join(PROD, "risk_pretrade.py")
if os.path.exists(rp_path):
    with open(rp_path, "r", encoding="utf-8-sig", errors="replace") as fh:
        rp_txt = fh.read()
    rp_lines = rp_txt.splitlines()
    for i, l in enumerate(rp_lines, 1):
        if "broker_check" in l.lower() or "broker_mapping" in l.lower() or "NEXTONES-BROKER" in l:
            print("    L%4d %s" % (i, l.rstrip()[:160]))

print()
print("=" * 72)
print("FIN DIAG")
print("=" * 72)
