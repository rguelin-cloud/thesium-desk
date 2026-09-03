# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-SHADOW-VS-RISK-V1]
# Diagnostic apres validator V3 :
#  - Pourquoi risk a refuse AAPL ?
#  - Le bloc shadow est-il avant ou apres le return success=False du risk ?
#  - Faut-il deplacer shadow ou bypass le risk pour le test ?

import os
import sys
import json
import sqlite3

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
sys.path.insert(0, PROD_DIR)
DB = os.path.join(PROD_DIR, "thesium.db")


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


# ------------------------- 1 -------------------------
banner("[1] Derniere ligne risk_pretrade_log")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cols = [r[1] for r in con.execute("PRAGMA table_info(risk_pretrade_log)").fetchall()]
print(f"  colonnes : {cols}")
for r in con.execute("SELECT * FROM risk_pretrade_log ORDER BY id DESC LIMIT 3"):
    d = dict(r)
    for k, v in list(d.items()):
        if v is not None and len(str(v)) > 500:
            d[k] = str(v)[:500] + "..."
    print()
    print("  --- row ---")
    for k, v in d.items():
        print(f"    {k} = {v}")


# ------------------------- 2 -------------------------
banner("[2] Ordre 177 cote orders (status, side, qty)")
o = con.execute("SELECT * FROM orders WHERE id=177").fetchone()
if o:
    d = dict(o)
    for k, v in d.items():
        sv = str(v)
        if len(sv) > 300:
            sv = sv[:300] + "..."
        print(f"  {k} = {sv}")
else:
    print("  pas d'ordre 177")


# ------------------------- 3 -------------------------
banner("[3] Localise le bloc [NEXTONES-SHADOW-EXEC-V1] dans execution_engine.py")
ee_path = os.path.join(PROD_DIR, "execution_engine.py")
with open(ee_path, "r", encoding="utf-8-sig") as f:
    src = f.read()

marker = "[NEXTONES-SHADOW-EXEC-V1]"
mpos = src.find(marker)
print(f"  marker char index : {mpos}")

# Quelle est la fonction qui contient le marker ?
# On cherche le 'def ' qui le precede le plus proche
def_idx = src.rfind("\ndef ", 0, mpos)
if def_idx >= 0:
    func_line = src[def_idx+1:src.find("\n", def_idx+1)]
    print(f"  fonction englobante : {func_line}")

# Y a-t-il un 'return' AVANT le marker dans la meme fonction ?
# (qui indiquerait que risk refuse en court-circuit avant le shadow)
slice_before = src[def_idx:mpos]
n_returns_before = slice_before.count("\n        return ") + slice_before.count("\n    return ")
print(f"  nombre de 'return' AVANT le marker dans la fonction : {n_returns_before}")

# Contexte autour du marker (-1000 / +500 chars)
banner("[4] Contexte autour du marker (-800 / +400 chars)")
start = max(0, mpos - 800)
end = min(len(src), mpos + 400)
ctx = src[start:end]
# Numerote chaque ligne
lines = ctx.split("\n")
# Trouver le numero de ligne du marker dans le fichier source
line_no_marker = src[:mpos].count("\n") + 1
print(f"  ligne marker dans le fichier : {line_no_marker}")
print()
print("--- DEBUT CONTEXTE ---")
print(ctx)
print("--- FIN CONTEXTE ---")


# ------------------------- 5 -------------------------
banner("[5] Snippet autour des returns success=False du risk dans create_and_execute_order")
# Trouver la fonction create_and_execute_order
fn_idx = src.find("def create_and_execute_order")
if fn_idx >= 0:
    # fin de la fonction = prochain def au meme niveau d'indentation
    fn_end = src.find("\ndef ", fn_idx + 5)
    if fn_end < 0:
        fn_end = len(src)
    fn_body = src[fn_idx:fn_end]
    print(f"  fonction longueur : {len(fn_body)} chars, def@char {fn_idx}, end@char {fn_end}")

    # Cherche occurrences de 'Risk check' et de 'reason' / return success
    for kw in ["Risk check", "risk_result", "approved", "return {", "success\": False", "approved_qty"]:
        idx = 0
        while True:
            j = fn_body.find(kw, idx)
            if j < 0:
                break
            ln = fn_body[:j].count("\n") + 1
            line_no_in_file = src[:fn_idx].count("\n") + ln
            print(f"  hit '{kw}' fnline={ln} fileline={line_no_in_file}")
            idx = j + 1


con.close()
print()
print("[DONE]")
