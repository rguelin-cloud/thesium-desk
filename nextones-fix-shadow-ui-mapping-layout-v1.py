# -*- coding: utf-8 -*-
"""
Fix unifie Jalon 9.6 Patch 2 :
  1. HTML : deplace la card Shadow HORS du grid - retire l'ancienne insertion
     avant <h2>Backtest Portfolio</h2>, et re-insere tout en haut de
     <section id="tab-backtest"> (juste apres balise d'ouverture).
  2. JS : corrige le mapping des champs API :
       ret_pct       -> return_variant_pct
       sharpe        -> sharpe_variant
       max_dd_pct    -> max_dd_variant_pct
       n_orders      -> n_orders_variant
       reco          -> recommendation

Idempotent : markers
  [SHADOW_UI_V1_FIX_LAYOUT]  pour HTML
  [SHADOW_UI_V1_FIX_MAPPING] pour JS

Pas de heredoc, ASCII pur, validation stricte avant ecriture.
"""
import os
import re
import shutil
from datetime import datetime

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
HTML = os.path.join(ROOT, "index.html")
JS = os.path.join(ROOT, "app.js")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

MARK_OLD_BEGIN = "<!-- [SHADOW_UI_V1] BEGIN -->"
MARK_OLD_END = "<!-- [SHADOW_UI_V1] END -->"
MARK_LAYOUT_BEGIN = "<!-- [SHADOW_UI_V1_FIX_LAYOUT] BEGIN -->"
MARK_LAYOUT_END = "<!-- [SHADOW_UI_V1_FIX_LAYOUT] END -->"
MARK_MAP_FIX = "/* [SHADOW_UI_V1_FIX_MAPPING] */"

# -----------------------------------------------------------------------------
# Nouveau bloc HTML : en tete de <section id="tab-backtest"> + width:100%
# -----------------------------------------------------------------------------
HTML_BLOCK = (
    "        " + MARK_LAYOUT_BEGIN + "\n"
    '        <div id="shadow-variants-card" class="card" '
    'style="display:block;width:100%;clear:both;margin:0 0 16px 0;box-sizing:border-box;grid-column:1 / -1;">\n'
    '          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">\n'
    '            <h2 style="margin:0;">Shadow Variants - Perf J-30</h2>\n'
    '            <button id="shadow-refresh-btn" class="pplx-refresh-btn" type="button">Rafraichir</button>\n'
    '          </div>\n'
    '          <div id="shadow-variants-meta" style="font-size:12px;opacity:0.75;margin-bottom:8px;">Chargement...</div>\n'
    '          <div style="overflow-x:auto;">\n'
    '            <table id="shadow-variants-table" style="width:100%;border-collapse:collapse;font-size:13px;">\n'
    '              <thead>\n'
    '                <tr style="text-align:left;border-bottom:1px solid var(--border-color,#444);">\n'
    '                  <th style="padding:6px 8px;">Variant</th>\n'
    '                  <th style="padding:6px 8px;text-align:right;">Return</th>\n'
    '                  <th style="padding:6px 8px;text-align:right;">Delta</th>\n'
    '                  <th style="padding:6px 8px;text-align:right;">Sharpe</th>\n'
    '                  <th style="padding:6px 8px;text-align:right;">Max DD</th>\n'
    '                  <th style="padding:6px 8px;text-align:right;">N Orders</th>\n'
    '                  <th style="padding:6px 8px;text-align:center;">Reco</th>\n'
    '                </tr>\n'
    '              </thead>\n'
    '              <tbody id="shadow-variants-tbody">\n'
    '                <tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Chargement...</td></tr>\n'
    '              </tbody>\n'
    '            </table>\n'
    '          </div>\n'
    '        </div>\n'
    "        " + MARK_LAYOUT_END + "\n"
)

# -----------------------------------------------------------------------------
# Patch HTML
# -----------------------------------------------------------------------------
def patch_html():
    with open(HTML, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()

    if MARK_LAYOUT_BEGIN in src:
        print("[SKIP] HTML layout marker deja present")
        return False

    # 1. Retirer ancien bloc [SHADOW_UI_V1] BEGIN ... END
    pat = re.compile(
        r"\s*" + re.escape(MARK_OLD_BEGIN) + r".*?" + re.escape(MARK_OLD_END) + r"\s*",
        re.DOTALL
    )
    m = pat.search(src)
    if m:
        bak = HTML + ".bak." + TS
        shutil.copy2(HTML, bak)
        print("[BAK] HTML ->", bak)
        cleaned = pat.sub("\n      ", src, count=1)
        print("[OK] Ancien bloc retire ({} chars)".format(len(src) - len(cleaned)))
    else:
        cleaned = src
        bak = HTML + ".bak." + TS
        shutil.copy2(HTML, bak)
        print("[BAK] HTML ->", bak)
        print("[WARN] Ancien bloc [SHADOW_UI_V1] BEGIN/END introuvable - on insere quand meme")

    # 2. Inserer la nouvelle card juste APRES <section ... id="tab-backtest" ...>
    anchor_re = re.compile(r'(<section\b[^>]*\bid="tab-backtest"[^>]*>\s*\n)', re.IGNORECASE)
    m2 = anchor_re.search(cleaned)
    if not m2:
        print("[ERR] balise <section id=\"tab-backtest\"> introuvable - abort")
        return False
    new = cleaned[:m2.end()] + HTML_BLOCK + cleaned[m2.end():]

    with open(HTML, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("[OK] HTML patche, +{} chars".format(len(new) - len(src)))
    return True

# -----------------------------------------------------------------------------
# Patch JS : remplacer le forEach de mapping
# -----------------------------------------------------------------------------
def patch_js():
    with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()

    if MARK_MAP_FIX in src:
        print("[SKIP] JS mapping marker deja present")
        return False

    # Bloc OLD a remplacer : le forEach complet qui construit les cellules
    OLD = (
        "      rows.forEach(function(r){\n"
        "        html += '<tr style=\"border-bottom:1px solid var(--border-color,#333);\">';\n"
        "        html += '<td style=\"padding:6px 8px;font-weight:600;\">'+(r.variant_name || r.variant_id || \"?\")+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+fmtPct(r.ret_pct)+'</td>';\n"
        "        var deltaColor = r.delta_pct > 0 ? \"#22c55e\" : (r.delta_pct < 0 ? \"#ef4444\" : \"inherit\");\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;color:'+deltaColor+';\">'+fmtPct(r.delta_pct)+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+fmtNum(r.sharpe,2)+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+fmtPct(r.max_dd_pct)+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+(r.n_orders !== undefined ? r.n_orders : \"-\")+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:center;\">'+recoBadge(r.reco)+'</td>';\n"
        "        html += '</tr>';\n"
        "      });\n"
    )

    NEW = (
        "      " + MARK_MAP_FIX + "\n"
        "      rows.forEach(function(r){\n"
        "        html += '<tr style=\"border-bottom:1px solid var(--border-color,#333);\">';\n"
        "        html += '<td style=\"padding:6px 8px;font-weight:600;\">'+(r.variant_name || r.variant_id || \"?\")+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+fmtPct(r.return_variant_pct)+'</td>';\n"
        "        var deltaColor = r.delta_pct > 0 ? \"#22c55e\" : (r.delta_pct < 0 ? \"#ef4444\" : \"inherit\");\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;color:'+deltaColor+';\">'+fmtPct(r.delta_pct)+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+fmtNum(r.sharpe_variant,2)+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+fmtPct(r.max_dd_variant_pct)+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:right;\">'+(r.n_orders_variant !== undefined && r.n_orders_variant !== null ? r.n_orders_variant : \"-\")+'</td>';\n"
        "        html += '<td style=\"padding:6px 8px;text-align:center;\">'+recoBadge(r.recommendation)+'</td>';\n"
        "        html += '</tr>';\n"
        "      });\n"
    )

    if OLD not in src:
        print("[ERR] bloc OLD JS introuvable - dump zone autour de 'rows.forEach' :")
        idx = src.find("rows.forEach")
        if idx > 0:
            print(src[max(0, idx-100):idx+1200])
        return False

    bak = JS + ".bak." + TS
    shutil.copy2(JS, bak)
    print("[BAK] JS ->", bak)
    new = src.replace(OLD, NEW, 1)
    with open(JS, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("[OK] JS patche, delta={} chars".format(len(new) - len(src)))
    return True

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("FIX UNIFIE SHADOW UI V1 : layout + mapping API")
    print("=" * 70)
    h = patch_html()
    print()
    j = patch_js()
    print()
    print("HTML patched :", h)
    print("JS   patched :", j)
    print()
    print("Next :")
    print("  Ctrl+Shift+R sur navigateur puis tab Backtest")
    print("  Attendu : card en haut pleine largeur, 4 lignes remplies,")
    print("           v2 tight_conv badge VERT 'champion' delta +3,931%")
    print("DONE")
