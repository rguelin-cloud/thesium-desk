# -*- coding: utf-8 -*-
# [DIAG_UI_PATCH_APPLIED_V2]
# Verifie ce qui a ete reellement applique dans index.html et app.js.

from pathlib import Path
import re

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
HTML = BASE / "index.html"
JS = BASE / "app.js"

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")

html = read_text(HTML)
js = read_text(JS)

def section(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)

section("1. Markers")
print("  HTML marker : " + ("OUI" if "FIX_UI_PNL_2FIELDS_AND_FLOWS_V1" in html else "NON"))
print("  JS   marker : " + ("OUI" if "FIX_UI_PNL_2FIELDS_AND_FLOWS_V1" in js else "NON"))

section("2. PIVA encore present ?")
print("  portfolioIdealSection : " + ("OUI" if "portfolioIdealSection" in html else "NON"))

PAT_CALL = r"^\s*renderPortfolioIdeal\s*\("
PAT_FUNC = r"^function\s+renderPortfolioIdeal"
print("  renderPortfolioIdeal call  : " + ("OUI" if re.search(PAT_CALL, js, re.MULTILINE) else "NON"))
print("  function renderPortfolioIdeal : " + ("OUI" if re.search(PAT_FUNC, js, re.MULTILINE) else "NON"))

PAT_H2 = r"<h2[^>]*>[^<]*Portfolio[^<]*[Ii]d[^<]*al[^<]*vs[^<]*actuel[^<]*</h2>"
print("  h2 'Portfolio ideal vs actuel' : " + ("OUI" if re.search(PAT_H2, html) else "NON"))

section("3. Capital Flow UI")
print("  HTML capitalFlowModal : " + ("OUI" if "capitalFlowModal" in html else "NON"))
print("  HTML capitalFlowBtn   : " + ("OUI" if "capitalFlowBtn" in html else "NON"))
print("  JS openCapitalFlowModal : " + ("OUI" if "openCapitalFlowModal" in js else "NON"))

section("4. Skeleton kpi-grid")
m = re.search(r'<div class="kpi-grid" id="kpiGrid">(.*?)</div>', html, re.DOTALL)
if m:
    inner = m.group(1)
    n_cards = inner.count('<div class="kpi-card">')
    print("  Cards dans skeleton : " + str(n_cards))
    for line in inner.splitlines():
        if line.strip():
            print("    " + line.strip()[:120])
else:
    print("  [!] skeleton introuvable")

section("5. renderKPIs : combien de cards genere ?")
m = re.search(r"kpiGrid\.innerHTML\s*=\s*`([\s\S]*?)`;", js)
if m:
    block = m.group(1)
    n_html_cards = block.count('<div class="kpi-card">')
    print("  Cards dans renderKPIs : " + str(n_html_cards))
    labels = re.findall(r'<div class="kpi-label">([^<]+)</div>', block)
    print("  Labels : " + str(labels))
else:
    print("  [!] kpiGrid.innerHTML introuvable")

section("6. VAR (95%) source ?")
for kw in ["VAR (95%)", "var_95", "var95"]:
    hits_js = [(i, l.strip()[:120]) for i, l in enumerate(js.splitlines(), 1) if kw in l][:5]
    if hits_js:
        print("  JS [" + kw + "] -> " + str(len(hits_js)) + " hits")
        for ln, t in hits_js:
            print("    L" + str(ln) + ": " + t)
    hits_html = [(i, l.strip()[:120]) for i, l in enumerate(html.splitlines(), 1) if kw in l][:5]
    if hits_html:
        print("  HTML [" + kw + "] -> " + str(len(hits_html)) + " hits")
        for ln, t in hits_html:
            print("    L" + str(ln) + ": " + t)

section("7. Backups recents (verifier que les patches ont tente)")
for p in BASE.iterdir():
    name = p.name
    if (".html.bak.2026061" in name) or (".js.bak.2026061" in name):
        size = p.stat().st_size
        mtime = p.stat().st_mtime
        import datetime
        ts = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        print("  " + name + "  size=" + str(size) + "  " + ts)

print()
print("DONE [DIAG_UI_PATCH_APPLIED_V2]")
