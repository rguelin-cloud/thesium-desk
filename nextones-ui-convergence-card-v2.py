# -*- coding: utf-8 -*-
"""
nextones-ui-convergence-card-v2
Patch chirurgical sur la carte Convergence v1 :
(1) JS : remappe BUCKETS_ORDER de L1_regime/... -> L1/L2/L3/L4/L5 (clés réelles en DB)
(2) CSS : ajoute overrides [data-theme="light"] pour fond/texte/bordures
(3) CSS : ajoute également [data-theme="dark"] explicite (pour ne pas écraser le dark si toggle)

Idempotent via markers :
  JS   : // [CONVERGENCE_JS_V2_FIX]
  HTML : <!-- [CONVERGENCE_CSS_V2_FIX] -->
"""
import os, sys, re, io, shutil
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
INDEX_PATH = os.path.join(BASE, "index.html")
APP_JS_PATH = os.path.join(BASE, "app.js")

JS_V2_MARKER = "// [CONVERGENCE_JS_V2_FIX]"
CSS_V2_MARKER = "<!-- [CONVERGENCE_CSS_V2_FIX] -->"

# --- (1) JS : remplacer BUCKETS_ORDER -----------------------------------------
OLD_BUCKETS = 'const BUCKETS_ORDER = ["L1_regime","L2_positioning","L3_structure","L4_liquidite","L5_risque"];'
NEW_BUCKETS = 'const BUCKETS_ORDER = ["L1","L2","L3","L4","L5"];  ' + JS_V2_MARKER

# --- (1bis) JS : tooltip plus parlant
# Avant : title = key.replace("_"," ") + " : " + dir + ...
# On garde mais on prefix par un label humain via dict.
TOOLTIP_LABEL_MAP = {
    "L1": "L1 Regime (Macro)",
    "L2": "L2 Positioning (Factor)",
    "L3": "L3 Structure (Micro)",
    "L4": "L4 Liquidite (AltData)",
    "L5": "L5 Risque (Exit)",
}

OLD_TOOLTIP = 'const title = key.replace("_"," ") + " : " + dir + (driver && driver !== dir ? " (" + driver + ")" : "");'
NEW_TOOLTIP = (
    'const LABELS = ' + repr(TOOLTIP_LABEL_MAP).replace("'", '"') + ';\n'
    '    const title = (LABELS[key] || key) + " : " + dir + (driver && driver !== dir ? " - " + driver : "");'
)

# --- (2) CSS : block additionnel theme-aware -----------------------------------
CSS_THEME_BLOCK = """
<!-- [CONVERGENCE_CSS_V2_FIX] -->
<style>
  /* Dark mode (defaut, deja couvert mais on rend explicite) */
  html[data-theme="dark"] .conv-section { background:#161b22; border-color:#30363d; }
  html[data-theme="dark"] .conv-section .conv-title h3 { color:#e6edf3; }
  html[data-theme="dark"] .conv-section .conv-cycle-meta,
  html[data-theme="dark"] .conv-section .conv-totals span,
  html[data-theme="dark"] .conv-section .conv-tab { color:#7d8590; }
  html[data-theme="dark"] .conv-section .conv-totals b,
  html[data-theme="dark"] .conv-section .conv-tab.active,
  html[data-theme="dark"] .conv-section .conv-tab:hover,
  html[data-theme="dark"] .conv-section table.conv-table td { color:#e6edf3; }
  html[data-theme="dark"] .conv-section table.conv-table th { color:#7d8590; border-bottom-color:#30363d; }
  html[data-theme="dark"] .conv-section table.conv-table td { border-bottom-color:#21262d; }
  html[data-theme="dark"] .conv-section table.conv-table tr:hover td { background:#1c2128; }
  html[data-theme="dark"] .conv-section .conv-tabs { border-bottom-color:#30363d; }
  html[data-theme="dark"] .conv-section .conv-dot { border-color:#30363d; }
  html[data-theme="dark"] .conv-section .conv-dot.absent { background:#0d1117; }
  html[data-theme="dark"] .conv-section .conv-dot[title]:hover::after {
    background:#0d1117; color:#e6edf3; border-color:#30363d;
  }

  /* Light mode */
  html[data-theme="light"] .conv-section { background:#ffffff; border-color:#d0d7de; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
  html[data-theme="light"] .conv-section .conv-title h3 { color:#1f2328; }
  html[data-theme="light"] .conv-section .conv-cycle-meta,
  html[data-theme="light"] .conv-section .conv-totals span,
  html[data-theme="light"] .conv-section .conv-tab { color:#656d76; }
  html[data-theme="light"] .conv-section .conv-totals b,
  html[data-theme="light"] .conv-section .conv-tab.active,
  html[data-theme="light"] .conv-section .conv-tab:hover,
  html[data-theme="light"] .conv-section table.conv-table td { color:#1f2328; }
  html[data-theme="light"] .conv-section table.conv-table th { color:#656d76; border-bottom-color:#d0d7de; }
  html[data-theme="light"] .conv-section table.conv-table td { border-bottom-color:#eaeef2; }
  html[data-theme="light"] .conv-section table.conv-table tr:hover td { background:#f6f8fa; }
  html[data-theme="light"] .conv-section .conv-tabs { border-bottom-color:#d0d7de; }
  html[data-theme="light"] .conv-section .conv-tab.active { border-bottom-color:#0969da; }
  html[data-theme="light"] .conv-section .conv-dot { border-color:#d0d7de; }
  html[data-theme="light"] .conv-section .conv-dot.absent { background:#f6f8fa; }
  html[data-theme="light"] .conv-section .conv-dot.neutral { background:#8c959f; border-color:#8c959f; }
  html[data-theme="light"] .conv-section .conv-dot[title]:hover::after {
    background:#1f2328; color:#ffffff; border-color:#1f2328;
  }
  /* sizing colors light */
  html[data-theme="light"] .conv-section .conv-sizing.x1 { color:#656d76; }
  html[data-theme="light"] .conv-section .conv-sizing.x0 { color:#cf222e; }
  html[data-theme="light"] .conv-section .conv-sizing.x05 { color:#9a6700; }
  html[data-theme="light"] .conv-section .conv-sizing.x12 { color:#1a7f37; }
  /* regime badges light : on garde les couleurs de fond, on assombrit le texte */
  html[data-theme="light"] .conv-section .conv-regime.forced_exit { background:rgba(207,34,46,0.10); color:#cf222e; }
  html[data-theme="light"] .conv-section .conv-regime.drift { background:rgba(154,103,0,0.10); color:#9a6700; }
  html[data-theme="light"] .conv-section .conv-regime.strong { background:rgba(26,127,55,0.10); color:#1a7f37; }
  html[data-theme="light"] .conv-section .conv-regime.conflict { background:rgba(191,87,16,0.10); color:#bf5710; }
  html[data-theme="light"] .conv-section .conv-regime.neutral,
  html[data-theme="light"] .conv-section .conv-regime.neutral_stable,
  html[data-theme="light"] .conv-section .conv-regime.strong_neutral { background:rgba(101,109,118,0.10); color:#656d76; }
  /* crypto badge */
  html[data-theme="light"] .conv-section .conv-ticker .crypto-badge { background:#efe6fb; color:#6639ba; }
</style>
"""

# ---------------------------------------------------------------------------
def patch_app_js():
    print(f"\n[APPJS] {APP_JS_PATH}")
    with open(APP_JS_PATH, "r", encoding="utf-8-sig") as f:
        js = f.read()
    print(f"[APPJS] {len(js)} chars")

    if JS_V2_MARKER in js:
        print("[APPJS] SKIP : marker V2 present")
        return False

    changed = False

    # remap buckets
    if OLD_BUCKETS in js:
        js = js.replace(OLD_BUCKETS, NEW_BUCKETS)
        print("[APPJS] OK : BUCKETS_ORDER remappe -> L1..L5")
        changed = True
    else:
        # fallback : pattern plus laxe
        pat = re.compile(r'const\s+BUCKETS_ORDER\s*=\s*\[[^\]]+\]\s*;')
        m = pat.search(js)
        if m:
            js = js[:m.start()] + NEW_BUCKETS + js[m.end():]
            print("[APPJS] OK : BUCKETS_ORDER remappe (fallback regex)")
            changed = True
        else:
            print("[APPJS] ECHEC : BUCKETS_ORDER introuvable")
            return False

    # remap tooltip
    if OLD_TOOLTIP in js:
        js = js.replace(OLD_TOOLTIP, NEW_TOOLTIP)
        print("[APPJS] OK : tooltip remappe avec libelles humains")
        changed = True
    else:
        print("[APPJS] WARN : tooltip pattern introuvable (non bloquant)")

    if not changed:
        print("[APPJS] aucun changement applique")
        return False

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = APP_JS_PATH + f".bak-conv-v2-{ts}"
    shutil.copy2(APP_JS_PATH, bak)
    print(f"[APPJS] backup : {bak}")

    with open(APP_JS_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(js)
    print(f"[APPJS] OK : ecrit")
    return True

def patch_index_html():
    print(f"[INDEX] {INDEX_PATH}")
    with open(INDEX_PATH, "r", encoding="utf-8-sig") as f:
        html = f.read()
    print(f"[INDEX] {len(html)} chars")

    if CSS_V2_MARKER in html:
        print("[INDEX] SKIP : marker CSS V2 present")
        return False

    # Insertion juste avant </head>
    pat = re.compile(r'</head>', re.IGNORECASE)
    m = pat.search(html)
    if not m:
        print("[INDEX] ECHEC : </head> introuvable")
        return False

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = INDEX_PATH + f".bak-conv-css-v2-{ts}"
    shutil.copy2(INDEX_PATH, bak)
    print(f"[INDEX] backup : {bak}")

    new_html = html[:m.start()] + CSS_THEME_BLOCK + "\n" + html[m.start():]
    with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_html)
    print(f"[INDEX] OK : +{len(new_html)-len(html)} chars")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("CONVERGENCE CARD V2 FIX (buckets + theme)")
    print("=" * 60)
    r1 = patch_app_js()
    r2 = patch_index_html()
    print()
    print(f"[RESULT] app.js: {'PATCHED' if r1 else 'SKIPPED'}   index.html: {'PATCHED' if r2 else 'SKIPPED'}")
    print("[NEXT] Hard-reload navigateur (Ctrl+F5)")
