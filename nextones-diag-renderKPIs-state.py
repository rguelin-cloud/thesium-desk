# -*- coding: utf-8 -*-
# [DIAG_RENDERKPIS_STATE]
# Verifie l'etat exact de renderKPIs apres v2 :
# - marker present ?
# - labels des cards generes ?
# - presence de Unrealized P&L et Total Return ?

from pathlib import Path
import re

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
JS = BASE / "app.js"

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")

js = read_text(JS)

print("=" * 60)
print("ETAT renderKPIs APRES V2")
print("=" * 60)
print()
print("Marker V2 dans JS : " + ("OUI" if "FIX_UI_PNL_2FIELDS_AND_FLOWS_V2" in js else "NON"))
print("Marker V1 dans JS : " + ("OUI" if "FIX_UI_PNL_2FIELDS_AND_FLOWS_V1" in js else "NON"))
print()
print("Unrealized P&L dans JS : " + ("OUI" if "Unrealized P&amp;L" in js or "Unrealized P&L" in js else "NON"))
print("Total Return  dans JS : " + ("OUI" if "Total Return" in js else "NON"))
print()
print("const unrealizedPnl dans JS : " + ("OUI" if "const unrealizedPnl" in js else "NON"))
print("const totalReturn   dans JS : " + ("OUI" if "const totalReturn" in js else "NON"))
print()

# Localise kpiGrid.innerHTML = `
idx = js.find("kpiGrid.innerHTML = `")
print("Occurrences kpiGrid.innerHTML = ` : " + str(js.count("kpiGrid.innerHTML = `")))
print()

if idx >= 0:
    # Lit jusqu'au backtick suivi de ;
    scan = idx + len("kpiGrid.innerHTML = `")
    i = scan
    end = -1
    while i < len(js):
        if js[i] == "`":
            j = i + 1
            while j < len(js) and js[j] in (" ", "\t"):
                j += 1
            if j < len(js) and js[j] == ";":
                end = i
                break
        i += 1
    if end > 0:
        block = js[scan:end]
        labels = re.findall(r'<div class="kpi-label">([^<]+)</div>', block)
        print("Labels generes par renderKPIs (" + str(len(labels)) + " cards) :")
        for k, lab in enumerate(labels, 1):
            print("  " + str(k) + ". " + lab)
        print()
        print("Taille du innerHTML : " + str(len(block)) + " chars")
        # Dump premieres 600 chars
        print()
        print("--- DUMP debut innerHTML (600 chars) ---")
        print(block[:600])
        print("--- DUMP fin innerHTML (600 chars) ---")
        print(block[-600:])

print()
print("DONE [DIAG_RENDERKPIS_STATE]")
