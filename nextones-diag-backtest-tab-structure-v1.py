# -*- coding: utf-8 -*-
"""
Dump L2080-L2160 de index.html pour comprendre la structure parent
de <h2>Backtest Portfolio</h2> + reperer ou inserer la card Shadow
hors du grid/flex actuel.
"""
HTML = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html"

with open(HTML, "r", encoding="utf-8-sig", errors="replace") as f:
    lines = f.readlines()

print("Total lines :", len(lines))
print()

# Locate <section id="tab-backtest"> et <h2>Backtest Portfolio</h2>
sec_line = None
h2_line = None
shadow_line = None
for i, line in enumerate(lines, 1):
    if 'id="tab-backtest"' in line and sec_line is None:
        sec_line = i
    if "Backtest Portfolio" in line and h2_line is None:
        h2_line = i
    if "[SHADOW_UI_V1]" in line and shadow_line is None:
        shadow_line = i

print("Section <tab-backtest> at L:", sec_line)
print("<h2>Backtest Portfolio</h2> at L:", h2_line)
print("[SHADOW_UI_V1] marker at L:", shadow_line)
print()

# Dump zone elargie
start = max(0, (sec_line or 2090) - 5)
end = min(len(lines), (h2_line or 2110) + 30)
print("=== Dump L{} a L{} ===".format(start+1, end))
for k in range(start, end):
    marker = ""
    if k+1 == sec_line: marker = " <-- SECTION"
    if k+1 == h2_line: marker = " <-- H2"
    if "[SHADOW_UI_V1]" in lines[k]: marker = " <-- SHADOW"
    print("  L{:5d} | {}{}".format(k+1, lines[k].rstrip(), marker))
print()

print("DONE")
