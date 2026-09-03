# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-SHADOW-CONTEXT-V1]
#
# Diag pre-wiring du routeur Phase 3C etape 4.
#
# But : extraire le contexte exact autour du marker [NEXTONES-SHADOW-EXEC-V1]
# dans execution_engine.py pour preparer l'installeur du routeur.
#
# Sorties :
#   - 60 lignes de contexte autour du marker (le bloc shadow_executor wiring)
#   - signature de la fonction englobante
#   - variables disponibles dans le scope (ticker, side, qty, cycle_id, etc.)
#   - presence colonne is_live dans broker_shadow_orders

import os
import re
import sqlite3
import sys

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
ENGINE = os.path.join(PROD, "execution_engine.py")
DB = os.path.join(PROD, "thesium.db")

print("=" * 70)
print("DIAG SHADOW CONTEXT - prep wiring routeur Phase 3C etape 4")
print("=" * 70)

# 1. Lire engine et chercher le marker
if not os.path.exists(ENGINE):
    print(f"[FATAL] {ENGINE} introuvable")
    sys.exit(2)

with open(ENGINE, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()

marker_lines = []
for i, ln in enumerate(lines):
    if "NEXTONES-SHADOW-EXEC-V1" in ln:
        marker_lines.append(i)

print()
print(f"Marker [NEXTONES-SHADOW-EXEC-V1] trouve sur {len(marker_lines)} ligne(s)")
for ml in marker_lines:
    print(f"  L{ml+1}: {lines[ml].rstrip()}")

# 2. Pour chaque marker, dump 30 lignes avant + 30 apres
print()
for ml in marker_lines:
    print("-" * 70)
    print(f"CONTEXTE AUTOUR L{ml+1}")
    print("-" * 70)
    start = max(0, ml - 30)
    end = min(len(lines), ml + 31)
    for i in range(start, end):
        prefix = ">>>" if i == ml else "   "
        print(f"{prefix} L{i+1:5d} : {lines[i].rstrip()}")

# 3. Detecter la fonction englobante (def ... avant le marker)
print()
print("-" * 70)
print("FONCTION ENGLOBANTE")
print("-" * 70)
if marker_lines:
    ml = marker_lines[0]
    fn_pat = re.compile(r"^\s*def\s+(\w+)\s*\(([^)]*)\)")
    for i in range(ml, -1, -1):
        m = fn_pat.match(lines[i])
        if m:
            print(f"  L{i+1}: def {m.group(1)}({m.group(2)})")
            # Dump entete + 5 lignes
            for j in range(i, min(i + 6, len(lines))):
                print(f"    {lines[j].rstrip()}")
            break
    else:
        print("  Aucune def trouvee en remontant (peut etre module-level)")

# 4. Variables candidates (ticker, side, qty, cycle_id, asset_class)
print()
print("-" * 70)
print("VARIABLES SCOPE (recherche dans 80 lignes avant marker)")
print("-" * 70)
candidates = ["ticker", "side", "qty", "quantity", "cycle_id",
              "asset_class", "entry_price", "price", "thesium_ticker",
              "order_id", "proposal_id"]
if marker_lines:
    ml = marker_lines[0]
    block = "".join(lines[max(0, ml - 80):ml + 5])
    for var in candidates:
        # cherche affectation ou usage
        if re.search(rf"\b{var}\b\s*=", block):
            print(f"  [ASSIGNED] {var}")
        elif re.search(rf"\b{var}\b", block):
            print(f"  [USED]     {var}")

# 5. Schema broker_shadow_orders
print()
print("-" * 70)
print("SCHEMA broker_shadow_orders (focus is_live)")
print("-" * 70)
if os.path.exists(DB):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info(broker_shadow_orders)")
        cols = cur.fetchall()
        has_is_live = False
        for c in cols:
            cid, name, typ, notnull, dflt, pk = c
            mark = " <-- IS_LIVE" if name == "is_live" else ""
            print(f"  {cid:>3} {name:<22} {typ:<12} notnull={notnull} default={dflt}{mark}")
            if name == "is_live":
                has_is_live = True
        print()
        if has_is_live:
            print("  [OK] colonne is_live deja presente")
            cur.execute("""
                SELECT is_live, COUNT(*) FROM broker_shadow_orders
                GROUP BY is_live
            """)
            for row in cur.fetchall():
                print(f"     is_live={row[0]} count={row[1]}")
        else:
            print("  [TODO] colonne is_live ABSENTE - sera ajoutee par installeur")
    finally:
        conn.close()
else:
    print(f"  [WARN] DB {DB} introuvable")

# 6. Vue rapide insert shadow_executor (pour comprendre le pattern d'ecriture)
print()
print("-" * 70)
print("INSERT broker_shadow_orders (callsites)")
print("-" * 70)
insert_pat = re.compile(r"INSERT\s+INTO\s+broker_shadow_orders", re.IGNORECASE)
for i, ln in enumerate(lines):
    if insert_pat.search(ln):
        print(f"  L{i+1}: {ln.rstrip()[:120]}")

# Cherche aussi dans broker_shadow_executor.py si existe
SHADOW_EXEC = os.path.join(PROD, "nextones-broker-shadow-executor.py")
if os.path.exists(SHADOW_EXEC):
    print()
    print(f"  Dans {os.path.basename(SHADOW_EXEC)} :")
    with open(SHADOW_EXEC, "r", encoding="utf-8-sig") as f:
        slines = f.readlines()
    for i, ln in enumerate(slines):
        if insert_pat.search(ln):
            print(f"    L{i+1}: {ln.rstrip()[:120]}")

print()
print("=" * 70)
print("FIN DIAG - colle la sortie complete")
print("=" * 70)
