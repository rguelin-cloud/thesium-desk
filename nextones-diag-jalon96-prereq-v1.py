# -*- coding: utf-8 -*-
"""
DIAG PHASE 9.6 - API + UI insertion points

1. api_server.py :
   - Localiser app.mount('/', StaticFiles)
   - Localiser un anchor sur pour insertion shadow routes AVANT le mount
   - Pattern auth d'une route existante recente (regime ou backtest)

2. UI HTML/JS :
   - Lister fichiers UI/HTML pertinents
   - Trouver une card existante pour reference (ex: regime, backtest)
   - Identifier le fichier JS qui fait les fetch /api/...

3. shadow_perf_rolling : derniere row par variant (sanity check pour API)
"""
import os
import re
import sqlite3

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API = os.path.join(BASE, "api_server.py")
DB  = os.path.join(BASE, "thesium.db")


def header(t):
    print("=" * 78)
    print(t)
    print("=" * 78)


def search_lines(path, patterns, ctx=0):
    """Retourne [(lineno, line)] pour matches."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.readlines()
    out = []
    for i, ln in enumerate(lines, start=1):
        for p in patterns:
            if re.search(p, ln):
                out.append((i, ln.rstrip("\n")))
                break
    return out


def show_range(path, start, end):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.readlines()
    end = min(end, len(lines))
    for i in range(start, end + 1):
        print("  L{:5d} | {}".format(i, lines[i - 1].rstrip("\n")))


# ============== 1. API ==============
header("api_server.py : localisations critiques")

# 1a. app.mount StaticFiles
mounts = search_lines(API, [r"app\.mount\s*\(", r"StaticFiles"])
print()
print("[1a] app.mount / StaticFiles :")
for ln, txt in mounts:
    print("  L{:5d} | {}".format(ln, txt))

# 1b. Recente route ajoutee (regime endpoint)
print()
print("[1b] Routes recentes (regime, backtest, convergence) :")
regime_routes = search_lines(API, [
    r"@app\.(get|post)\([\"']/api/regime",
    r"@app\.(get|post)\([\"']/api/backtest",
    r"@app\.(get|post)\([\"']/api/convergence",
    r"@app\.(get|post)\([\"']/api/orders/execute-cycle",
])
for ln, txt in regime_routes:
    print("  L{:5d} | {}".format(ln, txt))

# 1c. Marker patches existants (pour eviter collision marker)
print()
print("[1c] Markers patches existants ([XXX_V1]) :")
markers = search_lines(API, [r"\[[A-Z_]+_V\d+\]"])
seen = set()
for ln, txt in markers[:30]:
    m = re.search(r"\[[A-Z_]+_V\d+\]", txt)
    if m:
        key = m.group(0)
        if key not in seen:
            seen.add(key)
            print("  L{:5d} | {}".format(ln, txt.strip()))

# 1d. Sample route protected (depend si JWT requis)
print()
print("[1d] Sample route avec depend(get_current_user) ou similaire (auth pattern) :")
auth_routes = search_lines(API, [
    r"Depends\s*\(\s*get_current_user",
    r"Depends\s*\(\s*verify_token",
    r"current_user\s*:",
])
for ln, txt in auth_routes[:10]:
    print("  L{:5d} | {}".format(ln, txt.strip()))


# ============== 2. UI ==============
print()
header("UI : fichiers candidats")

# Lister les .html et .js dans le projet (limite)
candidates_html = []
candidates_js = []
for root, dirs, files in os.walk(BASE):
    # Skip backups, __pycache__, logs, .git
    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "logs", "node_modules")]
    if "bak" in root.lower():
        continue
    for f in files:
        if f.endswith(".html"):
            full = os.path.join(root, f)
            try:
                sz = os.path.getsize(full)
            except OSError:
                sz = 0
            candidates_html.append((full, sz))
        elif f.endswith(".js"):
            full = os.path.join(root, f)
            try:
                sz = os.path.getsize(full)
            except OSError:
                sz = 0
            candidates_js.append((full, sz))

candidates_html.sort(key=lambda x: -x[1])
candidates_js.sort(key=lambda x: -x[1])

print()
print("[2a] Top 8 HTML files (par taille) :")
for p, sz in candidates_html[:8]:
    print("  {:>9} bytes  {}".format(sz, p))

print()
print("[2b] Top 8 JS files (par taille) :")
for p, sz in candidates_js[:8]:
    print("  {:>9} bytes  {}".format(sz, p))

# Chercher card existante (regime, backtest) dans le plus gros HTML
if candidates_html:
    main_html = candidates_html[0][0]
    print()
    print("[2c] Cards existantes dans {} :".format(os.path.basename(main_html)))
    cards = search_lines(main_html, [
        r"id=[\"']regime[-_]",
        r"id=[\"']backtest[-_]",
        r"id=[\"']convergence[-_]",
        r"id=[\"']pplx[-_]",
    ])
    for ln, txt in cards[:15]:
        print("  L{:5d} | {}".format(ln, txt.strip()[:120]))

# Chercher fetch() / apiFetch() pattern dans top JS
if candidates_js:
    main_js = candidates_js[0][0]
    print()
    print("[2d] Pattern fetch dans {} :".format(os.path.basename(main_js)))
    fetches = search_lines(main_js, [
        r"apiFetch\s*\(",
        r"fetch\s*\(\s*[\"']/api/",
    ])
    for ln, txt in fetches[:8]:
        print("  L{:5d} | {}".format(ln, txt.strip()[:120]))


# ============== 3. DB sanity ==============
print()
header("shadow_perf_rolling : latest state (sanity)")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print()
print("All rows currently :")
for r in cur.execute(
    "SELECT variant_id, window_days, as_of_day, "
    "return_variant_pct, return_prod_pct, delta_pct, "
    "sharpe_variant, max_dd_variant_pct, n_orders_variant, recommendation "
    "FROM shadow_perf_rolling ORDER BY variant_id, window_days, as_of_day"
).fetchall():
    print("  v{} win={} day={} ret={:.3f}% delta={} sharpe={} dd={:.3f}% n_ord={} reco={}".format(
        r["variant_id"], r["window_days"], r["as_of_day"],
        r["return_variant_pct"] or 0.0,
        "{:.3f}%".format(r["delta_pct"]) if r["delta_pct"] is not None else "N/A",
        "{:.3f}".format(r["sharpe_variant"]) if r["sharpe_variant"] is not None else "N/A",
        r["max_dd_variant_pct"] or 0.0,
        r["n_orders_variant"], r["recommendation"]
    ))

conn.close()

print()
print("=" * 78)
print("DIAG DONE")
print("=" * 78)
