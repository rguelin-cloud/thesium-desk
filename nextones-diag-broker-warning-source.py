# -*- coding: utf-8 -*-
# nextones-diag-broker-warning-source.py
# Identifier d'ou vient EXACTEMENT le warning "[WARN] risk_broker_check audit: database is locked"

import os

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

print()
print("=" * 72)
print("[1] Grep complet sur 'risk_broker_check audit' dans tout le projet")
print("-" * 72)
hits = []
for root, dirs, files in os.walk(PROD):
    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "__pycache__", "node_modules", "backups", ".git")]
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                    lines = fh.readlines()
                for i, l in enumerate(lines, 1):
                    if "risk_broker_check audit" in l:
                        hits.append((path, i, l.strip()))
            except Exception:
                pass

for path, i, l in hits:
    rel = os.path.relpath(path, PROD)
    print("  %s:L%d  %s" % (rel, i, l[:160]))

print()
print("=" * 72)
print("[2] Existence et contenu de nextones-risk-broker-check.py")
print("-" * 72)
src = os.path.join(PROD, "nextones-risk-broker-check.py")
if os.path.exists(src):
    print("  PRESENT : %s" % src)
    with open(src, "r", encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.readlines()
    print("  Lignes : %d" % len(lines))
    # Dump complet (c'est court)
    print()
    print("  --- DUMP COMPLET ---")
    for i, l in enumerate(lines, 1):
        print("  L%4d %s" % (i, l.rstrip("\n")))
    print("  --- /DUMP COMPLET ---")
else:
    print("  ABSENT : %s" % src)

print()
print("=" * 72)
print("[3] Test direct du module nextones-risk-broker-check")
print("-" * 72)
try:
    import importlib.util as ilu
    import sys
    p = src
    if os.path.exists(p):
        spec = ilu.spec_from_file_location("_nx_broker_check_test", p)
        mod = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        print("  Module charge OK")
        print("  Attributs : %s" % [a for a in dir(mod) if not a.startswith("_")][:20])
        if hasattr(mod, "check_broker_mapping"):
            print("  check_broker_mapping : OK")
            import inspect
            try:
                sig = inspect.signature(mod.check_broker_mapping)
                print("    signature : check_broker_mapping%s" % sig)
            except Exception:
                pass
    else:
        print("  N/A (fichier absent)")
except Exception as e:
    print("  ERREUR : %s" % e)

print()
print("=" * 72)
print("FIN DIAG")
print("=" * 72)
