# -*- coding: utf-8 -*-
# nextones-diag-broker-check-detail.py
# Dump COMPLET du code broker_check pour patcher proprement le param conn=

import os

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def dump_range(path, start, end, label):
    print()
    print("=" * 72)
    print("%s : %s (L%d-%d)" % (label, os.path.basename(path), start, end))
    print("-" * 72)
    if not os.path.exists(path):
        print("  ABSENT : %s" % path)
        return
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.readlines()
    total = len(lines)
    s = max(1, start)
    e = min(total, end)
    for i in range(s, e + 1):
        print("  L%4d %s" % (i, lines[i - 1].rstrip("\n")))

# 1. risk_broker_check.py : signature + corps de check_broker_mapping
rbc = os.path.join(PROD, "risk_broker_check.py")
print()
print("=" * 72)
print("[1] risk_broker_check.py - structure complete")
print("-" * 72)
if os.path.exists(rbc):
    with open(rbc, "r", encoding="utf-8-sig", errors="replace") as fh:
        txt = fh.read()
    print("  Taille : %d bytes, %d lignes" % (len(txt.encode("utf-8")), txt.count("\n") + 1))
    # Trouver def check_broker_mapping
    lines = txt.splitlines()
    for i, l in enumerate(lines, 1):
        if l.lstrip().startswith("def ") or l.lstrip().startswith("class "):
            print("    [DEF L%4d] %s" % (i, l.rstrip()[:160]))
    # Recherche sqlite3.connect / cursor / commit
    print()
    print("  Patterns DB :")
    for i, l in enumerate(lines, 1):
        s = l.strip()
        if any(k in s for k in ("sqlite3.connect", ".execute(", ".commit(", ".cursor(", ".close()")):
            print("    L%4d %s" % (i, s[:160]))
else:
    print("  ABSENT")

# 2. Dump COMPLET du fichier risk_broker_check.py (il est court)
if os.path.exists(rbc):
    print()
    print("=" * 72)
    print("[2] risk_broker_check.py - DUMP COMPLET")
    print("-" * 72)
    with open(rbc, "r", encoding="utf-8-sig", errors="replace") as fh:
        for i, l in enumerate(fh.readlines(), 1):
            print("  L%4d %s" % (i, l.rstrip("\n")))

# 3. risk_pretrade.py : appel et log autour L380-505
rpt = os.path.join(PROD, "risk_pretrade.py")
dump_range(rpt, 378, 510, "[3] risk_pretrade.py - bloc [NEXTONES-BROKER-CHECK-V1]")

# 4. risk_pretrade.py : voir comment _conn() est utilise dans run_pretrade_checks (et si conn passe au broker_check)
print()
print("=" * 72)
print("[4] risk_pretrade.py - run_pretrade_checks + appel broker_check")
print("-" * 72)
if os.path.exists(rpt):
    with open(rpt, "r", encoding="utf-8-sig", errors="replace") as fh:
        rpt_lines = fh.readlines()
    # Trouver def run_pretrade_checks
    start_idx = None
    for i, l in enumerate(rpt_lines):
        if l.lstrip().startswith("def run_pretrade_checks"):
            start_idx = i
            break
    if start_idx is not None:
        # Dump 60 lignes
        for j in range(start_idx, min(start_idx + 80, len(rpt_lines))):
            print("  L%4d %s" % (j + 1, rpt_lines[j].rstrip("\n")))

print()
print("=" * 72)
print("FIN DIAG")
print("=" * 72)
