# -*- coding: utf-8 -*-
"""
Installe le Patch 2 UI Shadow Variants (Jalon 9.6) :
  - index.html : <section id="shadow-variants-card"> avant <h2>Backtest Portfolio</h2>
  - app.js     : fonction renderShadowVariants() + hook tab change + bouton Rafraichir
Markers : [SHADOW_UI_V1] BEGIN / END
Idempotent : skip si marker present.
Backup .bak.<timestamp> avant ecriture.
ASCII pur, validation stricte avant write.
"""
import os
import shutil
from datetime import datetime

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
HTML = os.path.join(ROOT, "index.html")
JS = os.path.join(ROOT, "app.js")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

MARK_HTML_BEGIN = "<!-- [SHADOW_UI_V1] BEGIN -->"
MARK_HTML_END = "<!-- [SHADOW_UI_V1] END -->"
MARK_JS_BEGIN = "/* [SHADOW_UI_V1] BEGIN */"
MARK_JS_END = "/* [SHADOW_UI_V1] END */"

# -----------------------------------------------------------------------------
# HTML bloc a inserer juste AVANT <h2>Backtest Portfolio</h2>
# -----------------------------------------------------------------------------
HTML_BLOCK = """{begin}
      <div id="shadow-variants-card" class="card" style="margin-bottom:16px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <h2 style="margin:0;">Shadow Variants - Perf J-30</h2>
          <button id="shadow-refresh-btn" class="pplx-refresh-btn" type="button">Rafraichir</button>
        </div>
        <div id="shadow-variants-meta" style="font-size:12px;opacity:0.75;margin-bottom:8px;">Chargement...</div>
        <div style="overflow-x:auto;">
          <table id="shadow-variants-table" style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead>
              <tr style="text-align:left;border-bottom:1px solid var(--border-color,#444);">
                <th style="padding:6px 8px;">Variant</th>
                <th style="padding:6px 8px;text-align:right;">Return</th>
                <th style="padding:6px 8px;text-align:right;">Delta</th>
                <th style="padding:6px 8px;text-align:right;">Sharpe</th>
                <th style="padding:6px 8px;text-align:right;">Max DD</th>
                <th style="padding:6px 8px;text-align:right;">N Orders</th>
                <th style="padding:6px 8px;text-align:center;">Reco</th>
              </tr>
            </thead>
            <tbody id="shadow-variants-tbody">
              <tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Chargement...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      {end}
""".format(begin=MARK_HTML_BEGIN, end=MARK_HTML_END)

# -----------------------------------------------------------------------------
# JS bloc a inserer en fin de app.js (auto-init via DOMContentLoaded + tab hook)
# -----------------------------------------------------------------------------
JS_BLOCK = r"""
""" + MARK_JS_BEGIN + r"""
(function(){
  function fmtPct(v){
    if (v === null || v === undefined || isNaN(v)) return "-";
    var sign = v > 0 ? "+" : "";
    return sign + Number(v).toFixed(3).replace(".",",") + "%";
  }
  function fmtNum(v, dec){
    if (v === null || v === undefined || isNaN(v)) return "-";
    return Number(v).toFixed(dec === undefined ? 2 : dec).replace(".",",");
  }
  function recoBadge(reco){
    var color = "#888";
    var bg = "rgba(136,136,136,0.15)";
    var label = reco || "neutral";
    if (reco === "champion"){ color = "#22c55e"; bg = "rgba(34,197,94,0.15)"; }
    else if (reco === "reject"){ color = "#ef4444"; bg = "rgba(239,68,68,0.15)"; }
    return '<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;color:'+color+';background:'+bg+';">'+label+'</span>';
  }
  async function renderShadowVariants(){
    var meta = document.getElementById("shadow-variants-meta");
    var tbody = document.getElementById("shadow-variants-tbody");
    if (!meta || !tbody) return;
    meta.textContent = "Chargement...";
    tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Chargement...</td></tr>';
    try {
      var perfResp = await apiFetch("/api/shadow/perf-rolling?window=30");
      var perf = await perfResp.json();
      if (!perf || !perf.success){
        meta.textContent = "Erreur API perf-rolling";
        tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;color:#ef4444;">Erreur : '+(perf && perf.error ? perf.error : "inconnu")+'</td></tr>';
        return;
      }
      var rows = perf.rows || [];
      meta.textContent = "Fenetre " + perf.window_days + "j | as_of_day=" + perf.as_of_day + " | " + rows.length + " variants";
      if (rows.length === 0){
        tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Aucune donnee</td></tr>';
        return;
      }
      var html = "";
      rows.forEach(function(r){
        html += '<tr style="border-bottom:1px solid var(--border-color,#333);">';
        html += '<td style="padding:6px 8px;font-weight:600;">'+(r.variant_name || r.variant_id || "?")+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtPct(r.ret_pct)+'</td>';
        var deltaColor = r.delta_pct > 0 ? "#22c55e" : (r.delta_pct < 0 ? "#ef4444" : "inherit");
        html += '<td style="padding:6px 8px;text-align:right;color:'+deltaColor+';">'+fmtPct(r.delta_pct)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtNum(r.sharpe,2)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtPct(r.max_dd_pct)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+(r.n_orders !== undefined ? r.n_orders : "-")+'</td>';
        html += '<td style="padding:6px 8px;text-align:center;">'+recoBadge(r.reco)+'</td>';
        html += '</tr>';
      });
      tbody.innerHTML = html;
    } catch(e){
      meta.textContent = "Erreur reseau";
      tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;color:#ef4444;">Exception : '+e.message+'</td></tr>';
    }
  }
  window.renderShadowVariants = renderShadowVariants;

  function bindShadowUI(){
    var btn = document.getElementById("shadow-refresh-btn");
    if (btn && !btn.dataset.shadowBound){
      btn.dataset.shadowBound = "1";
      btn.addEventListener("click", renderShadowVariants);
    }
    var tabLink = document.querySelector('a[data-tab="backtest"]');
    if (tabLink && !tabLink.dataset.shadowBound){
      tabLink.dataset.shadowBound = "1";
      tabLink.addEventListener("click", function(){
        setTimeout(renderShadowVariants, 120);
      });
    }
    if (document.querySelector('#tab-backtest.active') || (location.hash === "#backtest")){
      renderShadowVariants();
    }
  }
  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", bindShadowUI);
  } else {
    bindShadowUI();
  }
})();
""" + MARK_JS_END + r"""
"""

# -----------------------------------------------------------------------------
# Patch HTML
# -----------------------------------------------------------------------------
def patch_html():
    with open(HTML, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()
    if MARK_HTML_BEGIN in src:
        print("[SKIP] HTML marker deja present")
        return False
    anchor = "<h2>Backtest Portfolio</h2>"
    if anchor not in src:
        print("[ERR] anchor HTML introuvable :", anchor)
        return False
    bak = HTML + ".bak." + TS
    shutil.copy2(HTML, bak)
    print("[BAK] HTML ->", bak)
    new = src.replace(anchor, HTML_BLOCK + "      " + anchor, 1)
    with open(HTML, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("[OK] HTML patche, +{} chars".format(len(new) - len(src)))
    return True

# -----------------------------------------------------------------------------
# Patch JS
# -----------------------------------------------------------------------------
def patch_js():
    with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()
    if MARK_JS_BEGIN in src:
        print("[SKIP] JS marker deja present")
        return False
    bak = JS + ".bak." + TS
    shutil.copy2(JS, bak)
    print("[BAK] JS ->", bak)
    new = src.rstrip() + "\n\n" + JS_BLOCK + "\n"
    with open(JS, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("[OK] JS patche, +{} chars".format(len(new) - len(src)))
    return True

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("INSTALL SHADOW UI V1 (Jalon 9.6 Patch 2)")
    print("=" * 70)
    h = patch_html()
    j = patch_js()
    print()
    print("HTML patched :", h)
    print("JS   patched :", j)
    print()
    print("Next steps :")
    print("  1. Hard reload navigateur (Ctrl+Shift+R) sur l'onglet Backtest")
    print("  2. Verifier card 'Shadow Variants - Perf J-30' visible")
    print("  3. Cliquer 'Rafraichir' -> 4 lignes (v1 v2 v3 v4)")
    print("  4. v2 tight_conv doit etre en badge vert 'champion' +3,931%")
    print("DONE")
