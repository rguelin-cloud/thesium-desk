# -*- coding: utf-8 -*-
"""
Diag : repérer le point d'injection UI pour la carte Convergence Engine.
- Cherche la carte PPLX dans index.html (onglet Today)
- Repere apifetch dans app.js + signature
- Identifie classes CSS utilisees (pplx-cycle-snapshot, etc.)
"""
import sys, os, re, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def read(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()

# -------- index.html --------
candidates_html = []
for root, dirs, files in os.walk(BASE):
    for fn in files:
        if fn.lower() == "index.html":
            candidates_html.append(os.path.join(root, fn))

print(f"[INDEX.HTML] {len(candidates_html)} fichier(s) trouve(s)")
for p in candidates_html:
    print(f"  {p}  ({os.path.getsize(p)} bytes)")
print()

main_html = None
for p in candidates_html:
    if "static" in p.lower() or "ui" in p.lower():
        main_html = p
        break
if not main_html and candidates_html:
    main_html = max(candidates_html, key=os.path.getsize)

print(f"[INDEX.HTML PRINCIPAL] {main_html}")
print()

if main_html:
    html = read(main_html)
    lines = html.split("\n")
    print(f"[STATS] {len(lines)} lignes, {len(html)} chars")
    print()

    # Onglet Today
    print("[ONGLET TODAY] occurences id=today / data-tab=today / Today")
    for i, line in enumerate(lines, 1):
        if re.search(r'(id\s*=\s*["\']tab-today|data-tab\s*=\s*["\']today|>\s*Today\s*<)', line, re.IGNORECASE):
            print(f"  L{i}: {line.strip()[:140]}")
    print()

    # Carte PPLX dans Today
    print("[CARTE PPLX] classes pplx-* trouvees")
    pplx_classes = set()
    for m in re.finditer(r'class\s*=\s*["\']([^"\']*pplx[^"\']*)["\']', html, re.IGNORECASE):
        for c in m.group(1).split():
            if "pplx" in c.lower():
                pplx_classes.add(c)
    for c in sorted(pplx_classes):
        print(f"  {c}")
    print()

    # Position carte pplx-cycle-snapshot ou pplx-memo
    print("[POSITION PPLX-CYCLE-SNAPSHOT / PPLX-MEMO]")
    for i, line in enumerate(lines, 1):
        if re.search(r'pplx-(cycle-snapshot|memo|crypto|geo|factor|thesis)', line, re.IGNORECASE):
            print(f"  L{i}: {line.strip()[:160]}")
    print()

    # Tab Today balise wrap
    print("[STRUCTURE TAB TODAY] cherche <div class=\"tab-content\" data-tab=\"today\">")
    in_today = False
    today_start = None
    for i, line in enumerate(lines, 1):
        if not in_today and re.search(r'data-tab\s*=\s*["\']today["\']', line) and "tab-content" in line:
            in_today = True
            today_start = i
            print(f"  TAB TODAY START L{i}: {line.strip()[:160]}")
        elif in_today and re.match(r'\s*</div>\s*<!--', line):
            print(f"  TAB TODAY END? L{i}: {line.strip()[:160]}")

# -------- app.js --------
candidates_js = []
for root, dirs, files in os.walk(BASE):
    for fn in files:
        if fn.lower() in ("app.js",):
            candidates_js.append(os.path.join(root, fn))

print()
print(f"[APP.JS] {len(candidates_js)} fichier(s)")
for p in candidates_js:
    print(f"  {p}  ({os.path.getsize(p)} bytes)")
print()

main_js = None
if candidates_js:
    main_js = max(candidates_js, key=os.path.getsize)
print(f"[APP.JS PRINCIPAL] {main_js}")
print()

if main_js:
    js = read(main_js)
    lines_js = js.split("\n")
    print(f"[STATS APP.JS] {len(lines_js)} lignes")
    print()

    # apifetch signature
    print("[APIFETCH SIGNATURE]")
    for i, line in enumerate(lines_js, 1):
        if "apifetch" in line.lower() and ("function" in line.lower() or "=>" in line or "async" in line.lower()):
            print(f"  L{i}: {line.strip()[:200]}")
    print()

    # window.apifetch
    print("[WINDOW.APIFETCH]")
    for i, line in enumerate(lines_js, 1):
        if re.search(r'window\.apifetch', line, re.IGNORECASE):
            print(f"  L{i}: {line.strip()[:200]}")
    print()

    # Pattern existant : loadPplxXxx ou renderPplxXxx
    print("[LOAD/RENDER PPLX FUNCTIONS]")
    for i, line in enumerate(lines_js, 1):
        if re.search(r'(async\s+function|function)\s+(load|render|update)(Pplx|Memo|Cycle|Geo)', line):
            print(f"  L{i}: {line.strip()[:200]}")
    print()

    # Auto-refresh / setInterval
    print("[AUTO-REFRESH / SETINTERVAL]")
    for i, line in enumerate(lines_js, 1):
        if "setInterval" in line and ("pplx" in line.lower() or "today" in line.lower() or "cycle" in line.lower()):
            print(f"  L{i}: {line.strip()[:200]}")
    print()

    # DOMContentLoaded / init
    print("[INIT / DOMContentLoaded]")
    for i, line in enumerate(lines_js, 1):
        if re.search(r'(DOMContentLoaded|window\.onload|document\.addEventListener)', line):
            print(f"  L{i}: {line.strip()[:200]}")

print()
print("[DONE]")
