# -*- coding: utf-8 -*-
"""
Patch 2/2 : ajoute le panneau 'Regime Marche' dans index.html et le
fetch+render dans app.js.

Modifications :
  A) index.html : ajoute <section id="market-regime-card" class="card"> juste
     APRES <section class="tab-content active" id="tab-today"> L972, en tete
     de l'onglet today (avant les autres cards).
  B) app.js : ajoute async function loadMarketRegimeCard() et l'appelle
     depuis loadDashboard() (apres la 1ere instruction du corps).

Markers idempotents :
  - HTML : <!-- [PATCH_UI_MARKET_REGIME_V1] -->
  - JS  :  // [PATCH_UI_MARKET_REGIME_V1]

NOTE : la HTML peut contenir des accents. On l'ecrit en utf-8 sans BOM.
Le code JS injecte est ASCII pur (escape \\u00xx pour les accents).
"""
import os
import re
import shutil
import sys
import time

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
INDEX = os.path.join(ROOT, "index.html")
APPJS = os.path.join(ROOT, "app.js")
HTML_MARKER = "[PATCH_UI_MARKET_REGIME_V1]"
JS_MARKER = "[PATCH_UI_MARKET_REGIME_V1]"

# ---------- A) index.html ----------
print("=" * 70)
print("A) index.html")
print("=" * 70)

with open(INDEX, "r", encoding="utf-8-sig") as f:
    html = f.read()

if HTML_MARKER in html:
    print(f"[SKIP HTML] Marker {HTML_MARKER} deja present.")
else:
    # Recherche de l'ancre : <section class="tab-content active" id="tab-today"
    anchor = '<section class="tab-content active" id="tab-today"'
    idx = html.find(anchor)
    if idx < 0:
        print(f"[ERR] Ancre HTML '{anchor}' introuvable")
        sys.exit(1)
    # Fin de balise ouvrante : trouver le '>' suivant
    close = html.find(">", idx)
    if close < 0:
        print("[ERR] Fermeture de la balise tab-today introuvable")
        sys.exit(2)
    inject_pos = close + 1
    print(f"[OK] Injection HTML apres position {inject_pos} (apres tab-today open)")

    card_html = (
        "\n<!-- " + HTML_MARKER + " -->\n"
        "<section id=\"market-regime-card\" class=\"card\" "
        "style=\"margin:16px 0;padding:14px 16px;border:1px solid #2e3650;"
        "border-radius:10px;background:#1b2030;\">\n"
        "  <div style=\"display:flex;align-items:center;justify-content:space-between;"
        "margin-bottom:10px;\">\n"
        "    <h3 style=\"margin:0;font-size:14px;color:#e6e9f2;\">Regime de Marche</h3>\n"
        "    <span id=\"market-regime-cycle\" style=\"font-size:11px;color:#8a92a6;\">"
        "&mdash;</span>\n"
        "  </div>\n"
        "  <div id=\"market-regime-chips\" style=\"display:flex;gap:10px;flex-wrap:wrap;\">\n"
        "    <div class=\"mr-chip\" data-class=\"equity\" style=\"flex:1;min-width:230px;"
        "padding:10px 12px;border-radius:8px;background:#222a3d;border:1px solid #2e3650;\">\n"
        "      <div style=\"display:flex;justify-content:space-between;align-items:center;\">\n"
        "        <span style=\"font-size:12px;color:#8a92a6;\">EQUITY</span>\n"
        "        <span class=\"mr-regime-badge\" id=\"mr-equity-regime\" "
        "style=\"font-weight:600;font-size:12px;padding:2px 8px;border-radius:4px;\">"
        "&mdash;</span>\n"
        "      </div>\n"
        "      <div id=\"mr-equity-details\" style=\"margin-top:6px;font-size:11px;"
        "color:#cdd3e1;line-height:1.5;\">Chargement...</div>\n"
        "    </div>\n"
        "    <div class=\"mr-chip\" data-class=\"crypto\" style=\"flex:1;min-width:230px;"
        "padding:10px 12px;border-radius:8px;background:#222a3d;border:1px solid #2e3650;\">\n"
        "      <div style=\"display:flex;justify-content:space-between;align-items:center;\">\n"
        "        <span style=\"font-size:12px;color:#8a92a6;\">CRYPTO</span>\n"
        "        <span class=\"mr-regime-badge\" id=\"mr-crypto-regime\" "
        "style=\"font-weight:600;font-size:12px;padding:2px 8px;border-radius:4px;\">"
        "&mdash;</span>\n"
        "      </div>\n"
        "      <div id=\"mr-crypto-details\" style=\"margin-top:6px;font-size:11px;"
        "color:#cdd3e1;line-height:1.5;\">Chargement...</div>\n"
        "    </div>\n"
        "  </div>\n"
        "  <div id=\"mr-impact\" style=\"margin-top:10px;font-size:11px;color:#8a92a6;"
        "font-style:italic;\">&mdash;</div>\n"
        "</section>\n"
    )

    new_html = html[:inject_pos] + card_html + html[inject_pos:]
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = INDEX + f".bak.{ts}"
    shutil.copyfile(INDEX, backup)
    print(f"[OK] Backup -> {backup}")
    with open(INDEX, "w", encoding="utf-8", newline="") as f:
        f.write(new_html)
    print(f"[OK] {INDEX} reecrit ({len(new_html)} chars)")
    print(f"[OK] Marker HTML {HTML_MARKER} present : "
          f"{new_html.count(HTML_MARKER)}")

# ---------- B) app.js ----------
print()
print("=" * 70)
print("B) app.js")
print("=" * 70)

with open(APPJS, "r", encoding="utf-8-sig") as f:
    js = f.read()

if JS_MARKER in js:
    print(f"[SKIP JS] Marker {JS_MARKER} deja present.")
    sys.exit(0)

# Trouver 'async function loadDashboard()'
m = re.search(r"async\s+function\s+loadDashboard\s*\(\s*\)\s*\{", js)
if not m:
    print("[ERR] async function loadDashboard() introuvable")
    sys.exit(3)
inject_after = m.end()
print(f"[OK] Injection JS apres loadDashboard() open (pos {inject_after})")

# Code JS injecte : ASCII pur, accents en \\u
js_block = (
    "\n  // " + JS_MARKER + " - charge le panneau Regime Marche\n"
    "  try { await loadMarketRegimeCard(); } catch(e) { console.warn('marketRegime:', e); }\n"
)

# Helper function : ajoutee en fin de fichier
helper_js = (
    "\n\n// " + JS_MARKER + " --- helpers Regime Marche ---\n"
    "function _mrRegimeColor(r) {\n"
    "  if (r === 'STRESS') return {bg:'#5a1f1f',fg:'#ffb3b3',border:'#9c2b2b'};\n"
    "  if (r === 'CALM')   return {bg:'#1f4f3a',fg:'#9be3bf',border:'#2c7d59'};\n"
    "  if (r === 'NORMAL') return {bg:'#2a3a55',fg:'#a9b8d9',border:'#3d4f73'};\n"
    "  return {bg:'#333',fg:'#999',border:'#444'};\n"
    "}\n"
    "function _mrFmtNum(v, dp, suffix) {\n"
    "  if (v === null || v === undefined || isNaN(v)) return '\\u2014';\n"
    "  return Number(v).toFixed(dp) + (suffix || '');\n"
    "}\n"
    "async function loadMarketRegimeCard() {\n"
    "  const card = document.getElementById('market-regime-card');\n"
    "  if (!card) return;\n"
    "  let data;\n"
    "  try {\n"
    "    data = await apiFetch('/api/regime/current');\n"
    "  } catch(err) {\n"
    "    document.getElementById('mr-impact').textContent = "
    "'Erreur chargement r\\u00e9gime : ' + (err.message || err);\n"
    "    return;\n"
    "  }\n"
    "  if (!data || data.error) {\n"
    "    document.getElementById('mr-impact').textContent = "
    "'Donn\\u00e9es indisponibles' + (data && data.error ? ' : ' + data.error : '');\n"
    "    return;\n"
    "  }\n"
    "  const cycleEl = document.getElementById('market-regime-cycle');\n"
    "  cycleEl.textContent = 'Cycle ' + (data.cycle_id || '\\u2014') + "
    "'  -  Portfolio: ' + (data.portfolio_regime || '\\u2014');\n"
    "  function _render(prefix, bucket) {\n"
    "    const badge = document.getElementById('mr-' + prefix + '-regime');\n"
    "    const det = document.getElementById('mr-' + prefix + '-details');\n"
    "    if (!bucket) {\n"
    "      badge.textContent = 'N/A';\n"
    "      det.textContent = 'Aucune donn\\u00e9e';\n"
    "      return;\n"
    "    }\n"
    "    const c = _mrRegimeColor(bucket.regime);\n"
    "    badge.textContent = bucket.regime || '\\u2014';\n"
    "    badge.style.background = c.bg;\n"
    "    badge.style.color = c.fg;\n"
    "    badge.style.border = '1px solid ' + c.border;\n"
    "    const parts = [];\n"
    "    if (bucket.vix !== null && bucket.vix !== undefined) {\n"
    "      parts.push('VIX ' + _mrFmtNum(bucket.vix, 2));\n"
    "    }\n"
    "    parts.push('Vol ' + _mrFmtNum(bucket.vol_pct, 1, '%'));\n"
    "    parts.push('DD 5j ' + _mrFmtNum(bucket.dd_pct, 2, '%'));\n"
    "    parts.push('BUY x' + _mrFmtNum(bucket.buy_mult, 2));\n"
    "    parts.push('SELL x' + _mrFmtNum(bucket.sell_mult, 2));\n"
    "    let html = parts.join(' \\u2022 ');\n"
    "    if (bucket.signals) {\n"
    "      const sig = bucket.signals;\n"
    "      const sub = [];\n"
    "      if (sig.vix) sub.push('vix=' + sig.vix);\n"
    "      if (sig.vol) sub.push('vol=' + sig.vol);\n"
    "      if (sig.dd)  sub.push('dd=' + sig.dd);\n"
    "      if (sub.length) {\n"
    "        html += '<br><span style=\"color:#8a92a6;font-size:10px;\">'\n"
    "             + sub.join(' / ')\n"
    "             + ' \\u2192 ' + (sig.n_calm || 0) + ' CALM / '\n"
    "             + (sig.n_stress || 0) + ' STRESS</span>';\n"
    "      }\n"
    "    }\n"
    "    det.innerHTML = html;\n"
    "  }\n"
    "  _render('equity', data.equity);\n"
    "  _render('crypto', data.crypto);\n"
    "  const impactBits = [];\n"
    "  function _impactFor(label, b) {\n"
    "    if (!b) return null;\n"
    "    if (b.regime === 'STRESS') return label + ' STRESS : BUY x' + b.buy_mult + "
    "', SELL x' + b.sell_mult + ' (acheter la baisse)';\n"
    "    if (b.regime === 'CALM')   return label + ' CALM : BUY x' + b.buy_mult + "
    "', SELL x' + b.sell_mult + ' (take profit facilit\\u00e9)';\n"
    "    return label + ' NORMAL : multiplicateurs neutres';\n"
    "  }\n"
    "  const ie = _impactFor('Equity', data.equity);\n"
    "  const ic = _impactFor('Crypto', data.crypto);\n"
    "  if (ie) impactBits.push(ie);\n"
    "  if (ic) impactBits.push(ic);\n"
    "  document.getElementById('mr-impact').textContent = impactBits.join('  |  ');\n"
    "}\n"
)

# Verif ASCII strict pour le JS injecte
def _check_ascii(snippet, label):
    for i, ch in enumerate(snippet):
        if ord(ch) > 127:
            print(f"[ERR] Non-ASCII char dans {label} at pos {i}: U+{ord(ch):04X} ({ch!r})")
            sys.exit(20)
_check_ascii(js_block, "js_block")
_check_ascii(helper_js, "helper_js")

# Injection : appel apres loadDashboard() open + helper en fin de fichier
new_js = js[:inject_after] + js_block + js[inject_after:] + helper_js

ts = time.strftime("%Y%m%d-%H%M%S")
backup_js = APPJS + f".bak.{ts}"
shutil.copyfile(APPJS, backup_js)
print(f"[OK] Backup -> {backup_js}")
with open(APPJS, "w", encoding="utf-8", newline="") as f:
    f.write(new_js)
print(f"[OK] {APPJS} reecrit ({len(new_js)} chars)")
print(f"[OK] Marker JS {JS_MARKER} present x{new_js.count(JS_MARKER)}")
print(f"[OK] function loadMarketRegimeCard x{new_js.count('function loadMarketRegimeCard')}")

print()
print("=" * 70)
print("PATCH UI APPLIQUE (HTML + JS)")
print("=" * 70)
print("Apres restart API + reload du dashboard, le panneau apparait en tete")
print("de l'onglet 'Today' avec 2 chips Equity / Crypto et un resume d'impact.")
